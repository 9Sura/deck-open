import difflib
import json
import os
import random
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import requests

# PATHS
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PI_DIR = DATA_DIR / "pi"
ADJACENT_PI_DIR = PI_DIR / "adjacent"
EVENTS_CONFIG_PATH = DATA_DIR / "events.json"
PROMPTS_DIR = BASE_DIR / "src" / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.txt"
ICDC_PROMPT_PATH = PROMPTS_DIR / "icdc.txt"
OUTPUT_DIR = BASE_DIR / "output"
REPO_ROOT = BASE_DIR.parents[1]

# icdc_gate is a stdlib-only sibling, so importing it at module level is not the
# cycle the in-function imports further down were guarding against. It is imported
# here because two module-level facts now live in it: the core-quota table (one
# definition shared by the selector and the gate) and `list_items`, which decides
# where a bullet begins for both the file that STORES the skills block and the
# check that COMPARES it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import icdc_gate as gate  # noqa: E402  (path shim above)

# The library's own dedup key, imported rather than restated for the same reason
# `harvest_pis` imports the quota table from the gate: the writer of `data/pi/`
# owns what counts as ONE indicator, and a selector carrying a second copy of that
# judgement is how the two come to disagree about it. `harvest_pis` imports only
# `icdc_gate` and the stdlib, so this adds no cycle.
from harvest_pis import normalize_pi  # noqa: E402  (path shim above)


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a local .env into os.environ (no dependency).

    Ported verbatim in behaviour from generate_test.py:24 -- this module had no
    .env loader, so keys sitting in the repo-root .env were invisible to it and
    the `anthropic` backend could never authenticate from a normal checkout.

    Looks in the repo root and this package dir. Never overrides a variable that
    is already set in the real environment, so an explicit `export` still wins.
    The .env file is git-ignored; real keys are never committed.
    """
    for env_path in (REPO_ROOT / ".env", BASE_DIR / ".env"):
        if not env_path.is_file():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value


_load_dotenv()


# OLLAMA REQUIREMENTS (same env contract as test-gen-model)
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY")
REQUEST_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600"))

# DECIDED: the default STAYS 0.5. Plan 03 §3g proposed raising it to 0.8 to fight
# cross-day mode collapse, on the reasoning that 0.5 "was tuned to pin down a 3B
# model." Two measurements taken after that was written argue against it:
#   1. Summary 03 found run-to-run variance already significant at 0.5 -- ACT
#      failed K3 on one run and passed on the next from the same seed. Raising
#      temperature trades gate pass-rate stability for novelty we can get
#      elsewhere, and §6b's publish threshold is derived from that pass rate.
#   2. §5d's seed axes attack mode collapse STRUCTURALLY and deterministically
#      (a distinct coprime stride per axis, stepped past anything used in 14
#      days), which is a stronger guarantee than sampling noise: consecutive
#      days differ by construction rather than by chance.
# The knob stays env-overridable, so raising it is one variable away if the
# first two batches' similarity distribution says novelty is actually short.
TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.5"))

# Context sized to the real workload, not padded: the largest prompt (a team
# event at ICDC with a capped example) measures ~3.5k tokens + ~1.2k output, so
# 8192 leaves comfortable headroom while roughly halving the KV-cache memory vs.
# 16384 -- a meaningful saving on a 16 GB machine. Env-overridable if you raise
# MAX_EXAMPLE_CHARS or feed multiple examples.
NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))

# Stream tokens from Ollama by default so the user sees live progress instead of
# a blank terminal. Set OLLAMA_STREAM=0 for the blocking path (programmatic use).
STREAM = os.environ.get("OLLAMA_STREAM", "1").lower() not in ("0", "false", "no", "")

# Roleplays are big, so 1 example is usually enough context; env-overridable.
MAX_EXAMPLE_ROLEPLAYS = int(os.environ.get("ROLEPLAY_MAX_EXAMPLES", "1"))
# Cap total example characters so a couple of long roleplays can't blow num_ctx.
MAX_EXAMPLE_CHARS = int(os.environ.get("ROLEPLAY_MAX_EXAMPLE_CHARS", "9000"))
MAX_RETRIES = int(os.environ.get("ROLEPLAY_MAX_RETRIES", "2"))

# Originality guard: a smaller model tends to lean on the example roleplay's
# scenario instead of inventing its own -- from a wholesale copy down to a
# find-and-replace clone (same plot, swapped names). We reject a generated scenario
# too similar to any example we showed it (measured on the situation section) and
# retry WITHOUT the example. Observed scores: original ~0.05-0.22, reworked premise
# ~0.38, substitution-clone ~0.49, verbatim copy ~0.96. 0.4 catches clones/copies
# while tolerating originals whose shared DECA boilerplate inflates the baseline; a
# flagged attempt is regenerated without the example, which reliably scores ~0.05.
ORIGINALITY_THRESHOLD = float(os.environ.get("ROLEPLAY_ORIGINALITY_THRESHOLD", "0.4"))

EXAMPLE_DELIM = "\n\n=== NEXT EXAMPLE ROLEPLAY ===\n\n"

# Token counts from the most recent blocking call_ollama (see the note there).
LAST_STATS: Dict[str, int] = {}

DIFFICULTY_LEVELS = ["District", "State", "ICDC"]

# DECA writes a few instructional-area names with specific punctuation; everything
# else is just the slug title-cased. (Mirrors clusters.json area_names.)
AREA_NAME_OVERRIDES: Dict[str, str] = {
    "marketing_information_management": "Marketing-Information Management",
    "financial_information_management": "Financial-Information Management",
    "product_service_management": "Product/Service Management",
}


# ----------------------------
# Load per-event config
# ----------------------------
# Event metadata (format, timing, pi_count, eligible instructional areas) lives in
# data/events.json so content changes don't require touching this module -- exactly
# like test-gen-model's clusters.json.
def _load_events_config() -> Tuple[Dict[str, Dict], Dict]:
    raw = json.loads(EVENTS_CONFIG_PATH.read_text(encoding="utf-8"))
    return raw["events"], raw.get("_meta", {})


EVENTS, EVENTS_META = _load_events_config()


# ----------------------------
# Small helpers
# ----------------------------
def humanize_area(slug: str) -> str:
    """Turn a pi/ file stem into its DECA instructional-area name."""
    return AREA_NAME_OVERRIDES.get(slug, slug.replace("_", " ").title())


def prompt_choice(label: str, choices: List[str]) -> str:
    options = ", ".join(choices)
    lookup = {c.lower(): c for c in choices}
    while True:
        answer = input(f"{label} ({options}): ").strip()
        if answer.lower() in lookup:
            return lookup[answer.lower()]
        print(f"  '{answer}' is not valid. Choose one of: {options}\n")


def prompt_optional(label: str) -> Optional[str]:
    answer = input(f"{label} (press Enter to skip): ").strip()
    return answer or None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def situation_header(event_cfg: Dict) -> str:
    """Team Decision Making events use CASE STUDY SITUATION; everything else
    (series/principles) uses EVENT SITUATION. Drives both the prompt and the
    format-aware validation."""
    return "CASE STUDY SITUATION" if event_cfg["format"] == "team" else "EVENT SITUATION"


def skills_for(event_cfg: Dict) -> List[str]:
    """The official 21st Century Skills block for this event, verbatim (plan 04 §2).

    Keyed by FORMAT out of `events.json` `_meta.format_defaults`, with a per-event
    override key winning if one is ever added. THREE sets exist, not one plus a
    variant: team replaces Communication with Communication and Collaboration, and
    principles drops Problem Solving. The canonical-variant rule and the corpus
    counts behind each block are in `_meta.twenty_first_century_skills`.

    Raises rather than defaulting. `skills_count()` used to answer 3-or-4 from the
    format alone, and an author told only "list exactly 4 skills" has no way to know
    WHICH four -- 605 of 720 banked roleplays got them wrong, 170 of them omitting
    Creativity and Innovation entirely. A silent fallback here would put that back.
    """
    if not event_cfg.get("includes_21st_century_skills"):
        return []
    override = event_cfg.get("twenty_first_century_skills")
    if override:
        return list(override)
    fmt = event_cfg.get("format", "series")
    defaults = (EVENTS_META.get("format_defaults") or {}).get(fmt) or {}
    skills = defaults.get("twenty_first_century_skills")
    if not skills:
        raise ValueError(
            f"events.json _meta.format_defaults['{fmt}'] carries no "
            "twenty_first_century_skills block, so the official skills for "
            f"{event_cfg.get('event_code', '?')} cannot be rendered or checked "
            "(plan 04 §2.3). Add it there, keyed by format."
        )
    return list(skills)


def skills_count(event_cfg: Dict) -> int:
    """How many 21st-Century skills this event lists -- derived from the block itself.

    Series/team list 4 and principles 3, but that is now a CONSEQUENCE of the
    canonical blocks rather than a second, independently-maintained rule.
    """
    return len(skills_for(event_cfg))


# ----------------------------
# Phase 2 -- Performance indicators
# ----------------------------
def load_pi_by_area(event_cfg: Dict) -> Dict[str, List[str]]:
    """Map each of the event's eligible instructional areas -> its IN-AREA PIs.

    This reads ONE OF TWO TIERS. `harvest_pis.py` splits every area into the PIs
    the corpus files under it with corroboration (`data/pi/<area>.txt`, this
    function) and the PIs that merely shared a case with them
    (`data/pi/adjacent/<area>.txt`, `load_adjacent_pi_by_area` below). The core
    quota draws from this tier only -- see `select_event_pis`.

    Raises on an eligible area that resolves to zero PIs (plan 05 D7). This used
    to warn and carry on, and the silence is why PFL spent months listing an
    empty ``risk_management`` and drawing from three areas while its config
    claimed four -- an area contributing nothing looks identical to an area that
    was never listed. An area with no PIs is a config or data error: either give
    the file content, or take the area off the event.
    """
    pi_by_area: Dict[str, List[str]] = {}
    for slug in event_cfg["instructional_areas"]:
        pi_file = PI_DIR / f"{slug}.txt"
        if not pi_file.exists():
            raise FileNotFoundError(
                f"{event_cfg.get('event_code', '?')} lists instructional area "
                f"'{slug}' but {pi_file} does not exist. Add the file or remove "
                f"the area from events.json."
            )

        lines = [ln.strip() for ln in read_text(pi_file).splitlines() if ln.strip()]
        if not lines:
            raise ValueError(
                f"{event_cfg.get('event_code', '?')} lists instructional area "
                f"'{slug}' but {pi_file.name} is empty, so the area silently "
                f"contributes no PIs. Populate it or remove the area from "
                f"events.json (plan 05 D7)."
            )

        pi_by_area[humanize_area(slug)] = lines

    return pi_by_area


def load_adjacent_pi_by_area(event_cfg: Dict) -> Dict[str, List[str]]:
    """The CO-OCCURRENCE tier per eligible area -- adjacent support only.

    Deliberately forgiving where `load_pi_by_area` raises. An empty or missing
    file here is a real state rather than a config error: an area the corpus
    supplies nothing for (business_law, financial_information_management,
    strategic_management) has no co-occurrence tier at all, and D7's argument
    does not apply -- the area still contributes its in-area lines, so it is not
    silently contributing nothing. A checkout that predates the tier split gets
    {} and behaves as it did before, which is why this returns rather than
    raising: the missing file cannot make an event unrunnable.
    """
    adjacent_by_area: Dict[str, List[str]] = {}
    for slug in event_cfg["instructional_areas"]:
        pi_file = ADJACENT_PI_DIR / f"{slug}.txt"
        if not pi_file.exists():
            continue
        lines = [ln.strip() for ln in read_text(pi_file).splitlines() if ln.strip()]
        if lines:
            adjacent_by_area[humanize_area(slug)] = lines

    return adjacent_by_area


def check_core_pi_tier(
    pi_items: Sequence[Dict[str, str]], declared_area: str, event_cfg: Dict
) -> List[str]:
    """Is every CORE PI actually in the declared area's in-area tier?

    `gate.check_pi_quota` already proves each core PI is FILED under the declared
    area; this proves the area filed it with corroboration rather than because one
    case happened to carry it. Both read the banked artifact's own
    `performanceIndicators` record, so both audit a shelf after the fact.

    It lives here rather than in `icdc_gate` because it needs `data/pi/`, and the
    gate reads no data files -- every other knob it owns is computable from the
    roleplay text alone. It is wired in beside the quota in `fill_bank`.

    A TIER LOOKUP IS UNAMBIGUOUS WHERE AN AREA LOOKUP IS NOT. §3.2b's warning is
    that a PI STRING cannot be mapped back to an area, because 25.8% of corpus PIs
    have several. Tier is a property of the (area, PI) PAIR, and the artifact
    records both -- so this recovers something real rather than guessing the way a
    string-to-area remap would.

    Silent when the tier data is absent: a checkout that has not re-harvested
    since the split has no `adjacent/`, and reporting every core PI as untiered
    there would be noise about the checkout rather than about the roleplay.
    """
    if not ADJACENT_PI_DIR.exists() or not declared_area:
        return []

    try:
        in_area = set(load_pi_by_area(event_cfg).get(declared_area, []))
    except (FileNotFoundError, ValueError):
        return []
    if not in_area:
        return []

    stray = [
        it["pi"] for it in pi_items
        if (it.get("role") or "") == "core"
        and (it.get("area") or "") == declared_area
        and it["pi"] not in in_area
    ]
    if not stray:
        return []
    return [
        f"quota: {len(stray)} core performance indicator(s) are in the "
        f"co-occurrence tier of '{declared_area}', not its in-area tier: "
        + "; ".join(stray)
    ]


# Plan 05 §3.1's core quota. It MOVED to icdc_gate with plan 05 §7 step 3 and is
# re-exported here under its old name: the gate now proves the quota off a banked
# file's own provenance (`gate.check_pi_quota`), and a selector and a gate reading
# two copies of the same number is how they come to disagree.
CORE_MINIMUM_BY_PI_COUNT: Dict[int, int] = gate.CORE_MINIMUM_BY_PI_COUNT


def _dedupe_by_key(pis: Sequence[str]) -> List[str]:
    """One entry per INDICATOR, first spelling in the given order wins.

    Order-preserving, because the caller's order is the file's order and every draw
    downstream is seeded: a set here would make the pool depend on hash iteration and
    break "re-resolving a work order reproduces it."
    """
    seen: set = set()
    out: List[str] = []
    for pi in pis:
        key = normalize_pi(pi)
        if key in seen:
            continue
        seen.add(key)
        out.append(pi)
    return out


def select_event_pis(
    pi_by_area: Dict[str, List[str]],
    event_cfg: Dict,
    adjacent_by_area: Optional[Dict[str, List[str]]] = None,
) -> Tuple[List[Dict[str, str]], str]:
    """Declare an instructional area, then draw a quota'd PI bundle for it (plan 05 §3).

    This replaces a pooled `random.sample` over every eligible PI, under which the
    displayed area was a PLURALITY LABEL computed after the fact: 81.0% of the 720
    banked roleplays span three or more source areas and the displayed area held
    47.8% of the slots. The procedure is now:

      1. DECLARE the area first, drawn from the event's own `instructional_areas`
         under `area_weights` (uniform unless events.json says otherwise -- OQ1).
      2. Draw the CORE from that area's IN-AREA TIER:
         `CORE_MINIMUM_BY_PI_COUNT[pi_count]` PIs.
      3. Draw the REMAINDER from the other eligible areas AND from every area's
         co-occurrence tier, as adjacent support.
      4. Return them CORE FIRST. There is no `random.shuffle` any more: official
         cases do not shuffle, and shuffling is what made the recorded order carry
         no information. `format_pi_list` renders this order and the prompt asks the
         author to reproduce it, so nothing downstream may re-sort it.

    STEP 2 IS TIERED, and that is the 2026-08-23 change. `harvest_pis.py` files a
    corpus PI under the area its CASE declared, which put the PIs DECA lists under
    an area and the PIs that merely shared a case with them in one flat file. The
    core drew uniformly over both, so "Detail the functions of room service." was
    a drawable core ECONOMICS PI on the strength of one hospitality case that
    declared Economics -- and 15 of the 19 BLTDM roleplays the 2026-08-23 recheck
    failed, failed on a core PI the situation could not demonstrate. The core now
    draws from the in-area tier alone.

    EVERY DRAW IS DEDUPED BY INDICATOR, not by PI string, and both steps are. Two
    spellings of one indicator are two distinct strings, which is how BLTDM-0032
    banked "Communicate core values of product/service." and the typo variant
    "Communicate core vale of product/service." in one bundle. `normalize_pi` is the
    key and it comes from `harvest_pis`, so the selector and the library agree on
    what one indicator is; only the KEY normalizes, never the spelling written into
    the record.

    STEP 3 IS NOT TIERED, deliberately. A co-occurrence PI is uncorroborated for
    that area, not wrong, and adjacent support is exactly the job it was doing
    usefully. Narrowing the adjacent pool too would cost variety and fix nothing:
    an adjacent PI makes no claim about the declared area.

    `adjacent_by_area` is loaded from `load_adjacent_pi_by_area` when not passed.
    It is a parameter rather than an unconditional load so a caller that already
    has both tiers does not re-read the tree per candidate, and so a test can hand
    in a pool without touching disk.

    Draws come from the MODULE-LEVEL `random`, which every caller seeds immediately
    beforehand (`<CODE>:<date>` or `<CODE>:<bank id>`). A local `random.Random()`
    here would break "re-resolving a work order reproduces it" and the OQ7 probe's
    A/B, both of which rely on two runs resolving the same roleplay.

    Returns (pi_items, declared_area), each item `{area, pi, role}` with `role` in
    {"core", "adjacent"} -- D5's schema, and the only record of which area a PI came
    from: 25.8% of corpus PIs are filed by DECA under more than one area, so the
    mapping cannot be recovered from the strings afterwards (§3.2b).
    """
    pi_count = event_cfg["pi_count"]
    if pi_count not in CORE_MINIMUM_BY_PI_COUNT:
        raise ValueError(
            f"{event_cfg.get('event_code', '?')} has pi_count {pi_count}, which plan "
            f"05 §3.1's quota table does not cover ({sorted(CORE_MINIMUM_BY_PI_COUNT)}). "
            "Add the row deliberately -- guessing a core minimum silently sets the bar "
            "the whole shelf is authored against."
        )
    core_min = CORE_MINIMUM_BY_PI_COUNT[pi_count]

    if adjacent_by_area is None:
        adjacent_by_area = load_adjacent_pi_by_area(event_cfg)

    # Slug order from events.json, so the weighting is keyed on the same slugs the
    # config names. pi_by_area is humanized, and load_pi_by_area has already raised
    # on any eligible area that resolves to zero PIs (D7).
    slugs = [s for s in event_cfg["instructional_areas"] if humanize_area(s) in pi_by_area]
    if not slugs:
        raise RuntimeError(
            f"no eligible instructional areas resolved for "
            f"{event_cfg.get('event_code', '?')}"
        )

    # An area too thin to fill the core cannot be declared, and that is a data/config
    # error rather than something to route around: silently skipping it would change
    # the weighting without saying so, which is D7's own argument one level up. This
    # reads the IN-AREA tier, which is what the core draws from, so the tier split
    # moved the margin. Nothing trips it today, but the slack is now ONE PI at the
    # tightest: marketing_information_management holds 4 against a core minimum of
    # 3 (AAM/ENT/FMS/RMS), entrepreneurship and human_resources_management hold 5
    # against 4 (ETDM). `harvest_pis.py` runs this same check per event before it
    # writes, so raising MIN_IN_AREA_SUPPORT surfaces there rather than here.
    thin = [s for s in slugs if len(pi_by_area[humanize_area(s)]) < core_min]
    if thin:
        raise ValueError(
            f"{event_cfg.get('event_code', '?')} lists instructional area(s) "
            f"{thin} holding fewer than the {core_min} PIs plan 05 §3.1's quota "
            "requires of a DECLARED area. Populate the file(s) or take the area off "
            "the event in events.json."
        )

    weights = event_cfg.get("area_weights") or {}
    declared = random.choices(slugs, weights=[weights.get(s, 1) for s in slugs], k=1)[0]
    declared_area = humanize_area(declared)

    # THE CORE POOL IS DEDUPED BEFORE IT IS SAMPLED, on the same normalized key the
    # adjacent pool uses below. `random.sample` cannot draw one list entry twice, but
    # it happily draws two entries that are two SPELLINGS of one indicator -- which is
    # exactly what banked BLTDM-0032 with "Communicate core values of product/service."
    # and the typo variant "Communicate core vale of product/service." in one core
    # bundle (audits/BLTDM_30_Roleplay_Recheck_Report.pdf, 2026-08-23).
    core_pool = _dedupe_by_key(pi_by_area[declared_area])
    if len(core_pool) < core_min:
        # `thin` above measured the RAW file, which is what `harvest_pis` reports and
        # what the operator would go and look at. Only a library carrying duplicate
        # spellings can reach here, and re-harvesting is the fix.
        raise ValueError(
            f"{event_cfg.get('event_code', '?')}'s declared area '{declared_area}' "
            f"holds {len(pi_by_area[declared_area])} PI line(s) but only "
            f"{len(core_pool)} distinct indicator(s), fewer than the {core_min} plan "
            "05 §3.1's quota requires. Re-run harvest_pis.py --write."
        )
    core = [
        {"area": declared_area, "pi": pi, "role": "core"}
        for pi in random.sample(core_pool, core_min)
    ]

    # Adjacent support, from every OTHER eligible area's in-area tier PLUS every
    # eligible area's co-occurrence tier -- the declared area's included, since a PI
    # that merely shared a case with the declared area is adjacent support by
    # definition and excluding it would throw away the pool the tier split created.
    #
    # Deduped by INDICATOR, not by (area, pi): 25.8% of corpus PIs are filed under
    # more than one area (§3.2b), so the same indicator really does appear in several
    # of an event's pools, and without this the pool holds it twice -- which both
    # over-weights it and can put a duplicate bullet in the prompt, breaking
    # parse_roleplay's join back onto this record. The dedup now spans both tiers for
    # the same reason it spanned areas.
    #
    # THE KEY IS `normalize_pi`, NOT THE RAW STRING. Two spellings of one indicator
    # are two distinct strings, so a string key let a typo variant and its correct
    # spelling both into one bundle. `harvest_pis` collapses the pair at the library
    # level now, but the library is a data file and this is the selector: keying on
    # the same function means a spelling that gets past the harvest -- a new corpus
    # file, an area whose lines are kept rather than harvested -- still cannot split
    # one indicator into two slots. Only the KEY normalizes; the SPELLING written into
    # the record stays verbatim, because the prompt asks the author to reproduce it
    # word for word and `validate_roleplay` compares it literally.
    #
    # IN-AREA IS ENUMERATED FIRST, then co-occurrence, both in events.json slug
    # order, so the dedup is deterministic under the seed rather than dependent on
    # dict iteration -- and a PI in both tiers keeps its in-area attribution, which
    # is the better-evidenced one. (`harvest_pis.py` already makes the two tiers
    # disjoint per area; this holds the ordering across DIFFERENT areas, where they
    # legitimately overlap.)
    taken = {normalize_pi(it["pi"]) for it in core}
    adjacent_pool: List[Dict[str, str]] = []
    for tier, skip_declared in ((pi_by_area, True), (adjacent_by_area, False)):
        for s in slugs:
            if skip_declared and s == declared:
                continue
            area = humanize_area(s)
            for pi in tier.get(area, []):
                key = normalize_pi(pi)
                if key in taken:
                    continue
                taken.add(key)
                adjacent_pool.append({"area": area, "pi": pi, "role": "adjacent"})
    remainder = pi_count - core_min

    if len(adjacent_pool) < remainder:
        # Unreachable on today's data (every event has >=4 eligible areas); kept as a
        # warn-not-crash exactly as the pooled version handled an underfilled draw.
        print(
            f"  [warn] only {len(adjacent_pool)} adjacent PI(s) available for "
            f"{event_cfg.get('event_code', '?')}; {remainder} wanted. Using all available."
        )
        adjacent = adjacent_pool
    else:
        adjacent = random.sample(adjacent_pool, remainder)

    return core + adjacent, declared_area


# ----------------------------
# Phase 3 -- Example roleplays
# ----------------------------
def load_examples(event_cfg: Dict) -> List[str]:
    """Sample 1-2 whole seeded roleplays as style references.

    The seeded .txt files are already clean (no page furniture / OCR artifacts),
    so they load as-is. Total length is capped at MAX_EXAMPLE_CHARS so a couple of
    long roleplays can't overflow num_ctx. Returns the individual example texts so
    the originality guard can compare the generated scenario against each one.
    """
    folder = DATA_DIR / event_cfg["data_folder"]
    files = sorted(folder.glob("*.txt"))
    if not files:
        print(f"  [warn] No example files found in {folder}")
        return []

    k = min(MAX_EXAMPLE_ROLEPLAYS, len(files))
    sample_files = random.sample(files, k)

    examples: List[str] = []
    used = 0
    for f in sample_files:
        text = read_text(f)
        if used + len(text) > MAX_EXAMPLE_CHARS and examples:
            break  # keep at least one example, but don't blow the budget
        examples.append(text)
        used += len(text)

    print(
        f"  Sampled {len(examples)} example roleplay(s) "
        f"(~{used} chars) from {len(files)} file(s) in {folder.name}/"
    )
    return examples


# ----------------------------
# Phase 4 -- Prompt assembly + Ollama call
# ----------------------------
def format_pi_list(pi_items: List[Dict[str, str]]) -> str:
    return "\n".join(f"- {it['pi']}" for it in pi_items)


STRICT_REMINDER = (
    "FORMATTING REMINDER: Output ONLY the finished roleplay, no preamble or commentary. "
    "Include every required section header in order: 'CAREER CLUSTER' (only if this event "
    "has one), 'INSTRUCTIONAL AREA', "
    "the event name, '21st CENTURY SKILLS' (if this event "
    "includes it), 'PERFORMANCE INDICATORS', the situation section, and "
    "'JUDGE ROLE-PLAY CHARACTERIZATION'. Under PERFORMANCE INDICATORS, reproduce EVERY "
    "performance indicator EXACTLY as given, word for word -- do not reword, add, or drop any."
)

ORIGINALITY_REMINDER = (
    "ORIGINALITY REMINDER: Your previous attempt reused the example roleplay's scenario. "
    "You must INVENT A COMPLETELY NEW scenario: a different company name, industry, "
    "characters, products, business problem, and judge questions. Do NOT reuse the "
    "example's company, situation, or questions in any form. The example is a FORMAT "
    "reference only."
)


def build_user_message(
    event_cfg: Dict,
    level: str,
    declared_area: str,
    pi_items: List[Dict[str, str]],
    examples: List[str],
    extra_context: Optional[str] = None,
    reminder: str = "",
) -> str:
    include_skills = bool(event_cfg.get("includes_21st_century_skills"))
    canonical_skills = skills_for(event_cfg)
    # PFL is the sole event with career_cluster: null -- DECA publishes it without a
    # CAREER CLUSTER line, and all 10 PFL corpus files confirm it. Emitting a made-up
    # "General" cluster asked for a header DECA doesn't use AND made validate_roleplay's
    # unconditional CAREER CLUSTER requirement fail 1 of 28 events on every run.
    career_cluster = event_cfg.get("career_cluster")
    parts = [
        f"EVENT NAME: {event_cfg['event_name']}",
        f"EVENT CODE: {event_cfg['event_code']}",
        (
            f"CAREER CLUSTER: {career_cluster}"
            if career_cluster
            else "CAREER CLUSTER: none -- this event has no career cluster; "
            "OMIT the CAREER CLUSTER line entirely"
        ),
        f"INSTRUCTIONAL AREA: {declared_area}",
        f"COMPETITION LEVEL: {level}",
        f"PARTICIPANT ROLES: {event_cfg['participant_roles']}",
        f"PREPARATION MINUTES: {event_cfg['prep_minutes']}",
        f"PRESENTATION MINUTES: {event_cfg['presentation_minutes']}",
        f"JUDGE QUESTION MINUTES: {event_cfg.get('judge_question_minutes', 0)}",
        # The COUNT, beside the minutes, and in the user message rather than in a
        # brief because it is a per-event measurement that both briefs have to reach:
        # the ICDC brief is assembled per event but `system.txt` is read raw on the
        # day path, so a number substituted into a prompt file would only reach one
        # of them. `gate.judge_question_count` raises on an unmeasured event, so this
        # cannot quietly become a default.
        f"JUDGE QUESTIONS: {gate.judge_question_count(event_cfg)}",
        f"SITUATION SECTION HEADER: {situation_header(event_cfg)}",
        # SCENARIO SHAPE, plan 05 §5.2 step 3. The system brief is shared by all
        # 28 events and tells the author to "assign the participant(s) a specific
        # role (job title) at a named, original company" -- correct for 27 of
        # them and the reason PFL's whole shelf is corporate accounting cases
        # with a CFO judge. Fixing PFL's PI areas and seed axes does not reach
        # it: the instruction is upstream of both. This is an OVERRIDE line in
        # the per-event user message rather than a fork of the shared brief, on
        # the CAREER CLUSTER precedent a few lines up -- an event that names no
        # `scenario_shape` emits nothing here, so the other 27 user messages are
        # byte-identical.
        *(
            [f"SCENARIO SHAPE: {event_cfg['scenario_shape']}"]
            if event_cfg.get("scenario_shape")
            else []
        ),
        # 21st CENTURY SKILLS, plan 04 §2.3 step 2. This used to read "list exactly
        # {n} skills", which is an instruction scored by nothing -- the question
        # bank's `key_length_rank` shape (project CLAUDE.md §10-10). Only 5 of 720
        # banked files got the COUNT wrong and 605 got the composition wrong,
        # because an author told a number has no way to know WHICH skills. DECA
        # prints a fixed block per format, so the author TRANSCRIBES it; the
        # comparison in validate_roleplay is verbatim, which is why this renders the
        # exact strings rather than describing them.
        (
            "INCLUDE 21st CENTURY SKILLS: yes -- reproduce these "
            f"{len(canonical_skills)} skills VERBATIM, in this order, title and "
            "description, changing nothing:\n"
            + "\n".join(f"- {sk}" for sk in canonical_skills)
            if include_skills
            else "INCLUDE 21st CENTURY SKILLS: no -- omit that section entirely"
        ),
        "",
        "PERFORMANCE INDICATORS TO ASSESS (reproduce each one VERBATIM, in this order):",
        format_pi_list(pi_items),
    ]

    if extra_context:
        parts += ["", f"ADDITIONAL CONTEXT / CONSTRAINTS: {extra_context}"]

    if examples:
        parts += [
            "",
            "EXAMPLE ROLEPLAY(S) (style/tone/format reference ONLY -- never copy the "
            "company, product, characters, or scenario):",
            EXAMPLE_DELIM.join(examples),
        ]

    if reminder:
        parts += ["", reminder]

    return "\n".join(parts)


def call_ollama(
    system_prompt: str, user_message: str, stream: Optional[bool] = None
) -> str:
    if stream is None:
        stream = STREAM

    url = f"{OLLAMA_API_URL.rstrip('/')}/api/chat"
    headers = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": stream,
        "options": {
            "temperature": TEMPERATURE,
            "num_ctx": NUM_CTX,
        },
    }

    if not stream:
        resp = requests.post(
            url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        # Keep Ollama's own token counts from the last blocking call. prompt_eval_count
        # is the only way to tell a prompt that FIT from one Ollama silently truncated
        # to num_ctx -- and a truncated prompt drops the START of the system message,
        # i.e. exactly the difficulty spec, with no error anywhere.
        LAST_STATS.clear()
        LAST_STATS.update(
            {k: data[k] for k in
             ("prompt_eval_count", "eval_count", "total_duration", "load_duration")
             if k in data}
        )
        return data.get("message", {}).get("content", "").strip()

    # Streaming path: accumulate NDJSON chunks and print a '.' to stderr as each
    # section header lands, so a long generation shows live progress.
    pieces: List[str] = []
    printed = 0
    with requests.post(
        url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT, stream=True
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if chunk.get("error"):
                raise requests.RequestException(chunk["error"])
            piece = chunk.get("message", {}).get("content", "")
            if piece:
                pieces.append(piece)
                done_count = "".join(pieces).count("\n\n")
                if done_count > printed:
                    sys.stderr.write("." * (done_count - printed))
                    sys.stderr.flush()
                    printed = done_count
            if chunk.get("done"):
                break
    if printed:
        sys.stderr.write("\n")
        sys.stderr.flush()
    return "".join(pieces).strip()


# ----------------------------
# Phase 4b -- the backend seam (§3g)
# ----------------------------
# `ollama` is the author and the only backend a normal run touches (§3e: local,
# $0, permanent). The rest are kept REACHABLE but unused -- §3d's rule is "keep
# the seam able to reach them; don't design around them," after this repo's own
# history recorded Groq 429 / Cerebras 402 / Gemini 429 in a single sitting.
LLM_BACKEND = os.environ.get("ROLEPLAY_LLM_BACKEND", "ollama")

# Manual spot-check only (§5c: ~12 cents for 10 roleplays, no standing commitment).
# Plan 03 §3c priced the referee on claude-sonnet-5; set ANTHROPIC_MODEL to pick it.
# NOT claude-haiku-4-5 -- a cheap rater systematically undercalls the hard tier,
# measured directly during the question-bank work.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
ANTHROPIC_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "16000"))

# OpenAI-compatible chat-completions hosts: one implementation, three providers.
_OPENAI_COMPATIBLE: Dict[str, Tuple[str, str, str]] = {
    # backend: (base url, env var holding the key, default model)
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai",
               "GEMINI_API_KEY", "gemini-2.0-flash"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "llama-3.3-70b"),
}


def call_llm(system_prompt: str, user_message: str, *, backend: Optional[str] = None) -> str:
    """Same (system, user) -> str contract the retry loop already expects.

    `backend` forces one provider -- used by the manual spot-check (§5c) to run
    on something other than the author's model. Defaults to ROLEPLAY_LLM_BACKEND
    (itself defaulting to "ollama"), so a normal run is byte-identical to the
    direct call_ollama it replaced.
    """
    backend = (backend or LLM_BACKEND).lower()

    if backend == "ollama":
        return call_ollama(system_prompt, user_message)
    if backend == "anthropic":
        return _call_anthropic(system_prompt, user_message)
    if backend in _OPENAI_COMPATIBLE:
        return _call_openai_compatible(backend, system_prompt, user_message)
    raise ValueError(
        f"unknown backend {backend!r}; expected one of: ollama, anthropic, "
        + ", ".join(_OPENAI_COMPATIBLE)
    )


def _call_anthropic(system_prompt: str, user_message: str) -> str:
    """Official SDK, lazily imported so `anthropic` stays an optional dependency.

    Three things this deliberately does NOT send:
      - temperature / top_p / top_k. Opus 5 and Sonnet 5 removed them and reject
        a non-default value with a 400.
      - a thinking config. Opus 5 thinks by default; max_tokens caps thinking
        PLUS response text together, hence the generous default above.
      - an assistant prefill. Removed on this model family (400).
    `cache_control` goes on the frozen system prompt (~1,540 tokens, comfortably
    over the cacheable minimum) so repeated spot-check calls read the cache.
    """
    try:
        import anthropic  # noqa: PLC0415  (optional dependency, imported on use)
    except ImportError as e:  # pragma: no cover -- depends on the local env
        raise RuntimeError(
            "the 'anthropic' backend needs the official SDK: pip install anthropic"
        ) from e

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=ANTHROPIC_MAX_TOKENS,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_message}],
    )

    # Safety classifiers can decline with a normal HTTP 200 and an empty (or
    # partial) content list. Reading content[0] unconditionally would raise an
    # IndexError that looks nothing like the refusal it actually is.
    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None)
        raise RuntimeError(f"anthropic refused the request (category: {category})")

    return "".join(b.text for b in response.content if b.type == "text").strip()


def _call_openai_compatible(backend: str, system_prompt: str, user_message: str) -> str:
    """Gemini / Groq / Cerebras -- one implementation, kept reachable but unused."""
    base_url, key_var, default_model = _OPENAI_COMPATIBLE[backend]
    api_key = os.environ.get(key_var)
    if not api_key:
        raise RuntimeError(f"backend {backend!r} needs {key_var} in the environment or .env")

    model = os.environ.get(f"{backend.upper()}_MODEL", default_model)
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": TEMPERATURE,
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ----------------------------
# Phase 5 -- Validation + retry
# ----------------------------
def _has_header(text: str, header: str) -> Optional[int]:
    """Return the match position of a section header (line-anchored, allowing an
    optional trailing colon), or None. Case-insensitive on the label."""
    m = re.search(rf"^{re.escape(header)}\s*:?\s*$", text, flags=re.M | re.I)
    if m:
        return m.start()
    # Some corpus headers are inline, e.g. "CAREER CLUSTER: Marketing".
    m = re.search(rf"^{re.escape(header)}\s*:", text, flags=re.M | re.I)
    return m.start() if m else None


def _scenario_slice(text: str, sit_header: str) -> str:
    """Return the scenario prose (from the situation header to the judge section, or
    to the end). This is the part a copy-prone model lifts from the example, so it's
    what the originality guard compares."""
    start = _has_header(text, sit_header)
    if start is None:
        start = _has_header(text, "EVENT SITUATION")
    if start is None:
        start = _has_header(text, "CASE STUDY SITUATION")
    if start is None:
        return text
    end = _has_header(text, "JUDGE ROLE-PLAY CHARACTERIZATION")
    return text[start : end if end is not None else len(text)]


def scenario_similarity(text: str, event_cfg: Dict, examples: List[str]) -> float:
    """Max similarity (0-1) between the generated scenario and any example scenario.
    ~0.2 for an original scenario, ~0.95 for a near-copy."""
    if not examples:
        return 0.0
    gen = _scenario_slice(text, situation_header(event_cfg))
    return max(
        difflib.SequenceMatcher(None, gen, _scenario_slice(ex, situation_header(event_cfg))).ratio()
        for ex in examples
    )


def validate_roleplay(
    text: str,
    event_cfg: Dict,
    pi_items: List[Dict[str, str]],
    examples: Optional[List[str]] = None,
    declared_area: Optional[str] = None,
) -> List[str]:
    """Return a list of structural/fidelity problems ([] means the roleplay passes).

    Checks (mirrors the plan's Phase 5, plus an originality guard):
      - required section headers present and in order (situation header is
        format-aware: EVENT SITUATION vs CASE STUDY SITUATION),
      - 21st CENTURY SKILLS present iff the event includes it, and -- when it is --
        VERBATIM against the official block for the event's format (plan 04 §2.3
        step 3),
      - the model's INSTRUCTIONAL AREA line echoes the area the draw DECLARED,
      - every selected PI reproduced verbatim, and the count matches,
      - the scenario is not a near-copy of any example we showed the model.

    `declared_area` is optional only so that callers with no selection record in
    hand (the corpus-validation paths) keep working; every generating path passes
    it, and when it is absent the echo check is skipped rather than guessed at.
    """
    issues: List[str] = []
    include_skills = bool(event_cfg.get("includes_21st_century_skills"))
    include_cluster = bool(event_cfg.get("career_cluster"))
    sit_header = situation_header(event_cfg)
    other_header = "EVENT SITUATION" if sit_header == "CASE STUDY SITUATION" else "CASE STUDY SITUATION"

    # PARTICIPANT INSTRUCTIONS IS NOT IN THIS LIST (2026-08-23). The block is no
    # longer authored -- `parse_roleplay.participant_instructions_for` renders DECA's
    # own wording from the event config -- so requiring it here would fail a
    # candidate for omitting a section the brief no longer asks for. A candidate that
    # writes one anyway is recorded as an `unexpected-section` defect by the parser
    # and is not discarded for it.
    ordered = [
        *(["CAREER CLUSTER"] if include_cluster else []),
        "INSTRUCTIONAL AREA",
        "PERFORMANCE INDICATORS",
        sit_header,
        "JUDGE ROLE-PLAY CHARACTERIZATION",
    ]

    positions: List[int] = []
    for header in ordered:
        pos = _has_header(text, header)
        if pos is None:
            issues.append(f"missing section: {header}")
        else:
            positions.append(pos)

    # Order check only over the headers that were found.
    if positions != sorted(positions):
        issues.append("section headers are out of order")

    # 21st Century Skills: present iff the event includes it.
    has_skills = _has_header(text, "21st CENTURY SKILLS") is not None
    if include_skills and not has_skills:
        issues.append("missing section: 21st CENTURY SKILLS")
    if not include_skills and has_skills:
        issues.append("unexpected 21st CENTURY SKILLS section")

    # 21st Century Skills, VERBATIM (plan 04 §2.3 step 3). One issue per mismatched
    # position, each naming the expected string, so a repair has something to act on
    # rather than a count.
    #
    # BLOCKING, and in `validate_roleplay` rather than beside it, for §2.3's stated
    # reason: this is the same kind of check as the verbatim-PI comparison two
    # blocks down, and it moves no rate `fill_buffer.py` was measured against
    # because no day-path output could have passed it either. NO NORMALISATION --
    # §2.3 step 5 puts that on the corpus EXTRACTION alone; a file that disagrees
    # must fail rather than be quietly corrected, or the bank stops being diffable
    # against the corpus. Only the list marker is stripped, by the same
    # `gate.list_items` that decides where a bullet begins when parse_roleplay
    # STORES the block.
    if include_skills and has_skills:
        expected = skills_for(event_cfg)
        found = gate.list_items(gate.section_lines(text, "21st CENTURY SKILLS"))
        if len(found) != len(expected):
            issues.append(
                f"21st Century Skills: {len(found)} skill(s) listed, this event's "
                f"format lists {len(expected)}"
            )
        for i, want in enumerate(expected):
            got = found[i] if i < len(found) else ""
            if got != want:
                issues.append(
                    f"21st Century Skills #{i + 1} is not verbatim: expected "
                    f"{want!r}, got {got!r}"
                )

    # The model's INSTRUCTIONAL AREA line must echo the area the draw DECLARED.
    # BLOCKING (plan 05 §7 step 3c): it is a one-line-of-prose fidelity failure of
    # the same family as a non-verbatim PI, the line is handed to the author in the
    # prompt, and a bank has no clock -- a failure is discarded and re-authored
    # (03-plan §6e), never repaired in. `parse_roleplay` records the same
    # disagreement as an `area-echo-mismatch` defect; that record is what makes an
    # already-banked file auditable, and this is what stops a new one being banked.
    if declared_area:
        m = re.search(r"^\s*INSTRUCTIONAL AREA\s*:\s*(.+?)\s*$", text, flags=re.M | re.I)
        echoed = m.group(1).strip() if m else ""
        if echoed and echoed.lower() != declared_area.lower():
            issues.append(
                f"INSTRUCTIONAL AREA echoes {echoed!r}, but the draw declared "
                f"{declared_area!r}"
            )

    # CAREER CLUSTER: present iff the event has one (PFL has none -- see build_user_message).
    # Symmetric with the skills check above, so a model that ignores the omit instruction
    # and invents a cluster for PFL is caught rather than silently accepted.
    if not include_cluster and _has_header(text, "CAREER CLUSTER") is not None:
        issues.append("unexpected CAREER CLUSTER section (this event has none)")

    # The wrong situation header must not leak in for this format.
    if _has_header(text, other_header) is not None:
        issues.append(f"wrong situation header for format: {other_header}")

    # PI fidelity -- the highest-value check. Every selected PI must appear verbatim.
    missing_pis = [it["pi"] for it in pi_items if it["pi"] not in text]
    if missing_pis:
        issues.append(f"{len(missing_pis)}/{len(pi_items)} performance indicator(s) not verbatim")

    # Originality -- the scenario must not be lifted from an example we showed it.
    if examples:
        sim = scenario_similarity(text, event_cfg, examples)
        if sim >= ORIGINALITY_THRESHOLD:
            issues.append(f"scenario too similar to example ({sim:.0%}) -- not original")

    return issues


def generate_roleplay(
    event_key: str, level: str, extra_context: Optional[str] = None
) -> Optional[str]:
    event_cfg = EVENTS[event_key]
    system_prompt = read_text(SYSTEM_PROMPT_PATH)

    print(f"\nResolving PIs and examples for '{event_key}'...")
    pi_by_area = load_pi_by_area(event_cfg)
    if not pi_by_area:
        raise RuntimeError(
            f"No performance indicators available for event '{event_key}'. "
            "Seed the relevant data/pi/*.txt files first."
        )

    pi_items, declared_area = select_event_pis(pi_by_area, event_cfg)
    examples = load_examples(event_cfg)

    print(
        f"\n  {len(pi_items)} performance indicator(s), "
        f"declared instructional area: {declared_area}"
    )
    for it in pi_items:
        print(f"       - ({it['role']:8}) [{it['area']}] {it['pi']}")

    # Generate, validating each attempt and keeping the best one across retries.
    best_text: Optional[str] = None
    best_issues: Optional[List[str]] = None
    reminder = ""
    # When the model copies the example scenario, the fix is to retry WITHOUT the
    # example -- a smaller model can't copy what it can't see. This flag drops the
    # example from the next prompt once we detect plagiarism.
    drop_examples = False

    for attempt in range(1, MAX_RETRIES + 2):
        print(f"\n  Generating roleplay (attempt {attempt}/{MAX_RETRIES + 1})...")
        prompt_examples = [] if drop_examples else examples
        user_message = build_user_message(
            event_cfg, level, declared_area, pi_items, prompt_examples, extra_context, reminder
        )
        try:
            output = call_llm(system_prompt, user_message)
        except requests.RequestException as e:
            print(f"    [error] model request failed: {e}")
            break

        # Always validate originality against the real examples, even on a retry
        # where we withheld them from the prompt.
        issues = validate_roleplay(output, event_cfg, pi_items, examples, declared_area)
        if best_issues is None or len(issues) < len(best_issues):
            best_text, best_issues = output, issues

        if not issues:
            print("    valid roleplay generated.")
            break

        print(f"    attempt {attempt}: {len(issues)} issue(s): {'; '.join(issues)}")
        if attempt <= MAX_RETRIES:
            # Tailor the retry: plagiarism -> drop the example + originality nudge;
            # structural/verbatim slips -> the formatting reminder.
            not_original = any("not original" in i for i in issues)
            structural = any("not original" not in i for i in issues)
            reminders = []
            if not_original:
                drop_examples = True
                reminders.append(ORIGINALITY_REMINDER)
            if structural:
                reminders.append(STRICT_REMINDER)
            reminder = "\n\n".join(reminders)

    if best_issues:
        print(
            f"\n  [warn] best attempt still has {len(best_issues)} issue(s): "
            f"{'; '.join(best_issues)}"
        )

    return best_text


# ----------------------------
# Phase 6a -- the importable surface (§6a)
# ----------------------------
# Follows the generate_test.py:800 precedent: an importable entry point, while
# main() stays interactive and byte-untouched.
#
# BOTH of summary 03's required architecture deviations live HERE, not in the
# bake-off harness, because a deviation that only exists in a slice tool is a
# deviation production does not have:
#
#   (a) TWO-PASS GENERATION. Single-pass output is immovable at ~290 words --
#       which is the District series median (289), i.e. the model reproducing
#       the length of the only corpus that exists. Three escalating prompt
#       variants were tried and the HEAVIEST length language produced the
#       FEWEST words. A focused second call that expands an EXISTING situation
#       reaches 705-882 words with no telegraphing introduced. Prompting does
#       not move this; do not retry that path.
#
#   (b) THE DISTRICT EXEMPLAR IS WITHHELD FROM THE PROMPT BUT KEPT FOR SCORING.
#       Withholding raises difficulty (§3f's A/B) and removes the plagiarism
#       failure mode outright (BLTDM went 0.62 -> 0.05 on the same seed purely
#       from withholding). Keeping it for SCORING is what stops the originality
#       number becoming a meaningless 0.00: scenario_similarity() short-circuits
#       to 0.0 on an empty example list and validate_roleplay() then skips the
#       originality check entirely. That bug silently voided one headline number
#       once already -- keep the two example lists separate.

# The knob spec is appended to the brief for the ICDC tier; the brief is unchanged
# for District/State.
#
# The situation's paragraph count is the one structural number the knob spec fixes
# itself, and it is now MEASURED rather than derived from a knob. The retired
# icdc_plus.txt fixed it at 7 because its own paragraph plan was role / background /
# ONE PER STAKEHOLDER (K1 required >= 3) / constraints / the task. With K1 gone the
# number comes from the corpus instead -- medians over the 396 real situations:
#
#     principles  4      series  5      team  6
#
# The per-paragraph word target stays the band divided by this rather than a
# constant, for the reason that outlived the old tier: a fixed per-paragraph floor
# times a paragraph count is a second length rule, and two length rules disagree.
SITUATION_PARAGRAPHS_BY_FORMAT: Dict[str, int] = {
    "principles": 4,
    "series": 5,
    "team": 6,
}
SITUATION_PARAGRAPHS_DEFAULT = 5


def situation_paragraphs(event_cfg: Dict) -> int:
    """Corpus-median paragraph count for this event's format."""
    return SITUATION_PARAGRAPHS_BY_FORMAT.get(
        event_cfg.get("format", ""), SITUATION_PARAGRAPHS_DEFAULT
    )


def build_icdc_system_prompt(event_cfg: Dict, brief_path: Optional[Path] = None) -> str:
    """<brief> + the §5a knob spec, with this event's length band and target substituted.

    THE BAND, NOT THE FLOOR (plan 05 D9/D10, §7 steps 2 and 3). The author is told
    `situation_word_band(event_cfg)`, whose multipliers and window live on
    `icdc_gate.BAND_LO_MULT` and are not restated here -- a second copy of them is
    what left `events.json`'s `_meta` describing a pair plan 05 had already replaced.
    Step 2 moved every author-facing string onto the band; step 3 moved the GATE, so
    the per-format floor is gone from the repo entirely and the stated number and the
    enforced number are the same one again. They disagreed outright on two of three
    formats while the seam was open (principles' 450 floor against a 336-411 ceiling),
    which is why nothing may reintroduce a floor beside a band.

    THE TARGET IS THE MEAN, AND IT IS NOT THE OLD TARGET (plan 06 OQ1). The target
    this function substitutes is `authentic_situation_mean` itself -- the centre of
    the band, not a number outside it. The one plan 05 deleted was ~40% OVER the
    then-floor, an inflation meant to counter a model that undershoots any stated
    length, and it went with the floor because a band already has a top and asking
    past it requests exactly the over-long case the band exists to stop. A target
    inside the band is the opposite instruction and is what OQ1 chose INSTEAD of
    moving the multipliers: the shelf's authors park at whatever ceiling they are
    given, so the fix is to state where to aim, not to lower where it fails. The
    band stays a rail that fails in both directions.

    `brief_path` defaults to `system.txt`, which is what the Ollama day path uses
    and must keep using -- its measured pass rates were taken against that brief.
    `fill_bank.py` passes `authoring-bank-bare.txt` instead (§4d): the question
    bank measured a bare brief beating a full one 7-of-8 against 0-of-43, twice,
    and the equivalent here is dropping the corpus apparatus and every instruction
    the knob spec already supersedes. THE KNOB SPEC ITSELF IS SHARED either way --
    one source, so a K3 fix reaches both authors.
    """
    import icdc_gate as gate  # noqa: PLC0415  (sibling module; avoids an import cycle)

    lo, hi = gate.situation_word_band(event_cfg)
    # Read from the mean the band was fitted to, never derived back out of `lo`/`hi`:
    # `situation_word_band` owns the edges, and a target recomputed from an edge would
    # drift off the mean the moment either multiplier moved. The subscript cannot raise
    # here -- the call above already raised on an event with no measured mean.
    target = round(event_cfg["authentic_situation_mean"])
    paras = situation_paragraphs(event_cfg)
    para_lo, para_hi = round(lo / paras), round(hi / paras)

    knobs = (
        read_text(ICDC_PROMPT_PATH)
        .replace("SITUATION_WORD_MIN", str(lo))
        .replace("SITUATION_WORD_MAX", str(hi))
        .replace("SITUATION_WORD_TARGET", str(target))
        .replace("SITUATION_PARA_HINT", str(paras))
        .replace("SITUATION_PARA_WORDS", f"{para_lo} to {para_hi} words")
    )
    return f"{read_text(brief_path or SYSTEM_PROMPT_PATH)}\n\n{knobs}"


EXPAND_SYSTEM = (
    "You expand DECA roleplay situation sections. Output ONLY the rewritten situation "
    "section, starting with its header line. No preamble, no commentary."
)


def expand_situation(
    body: str, event_cfg: Dict, band: Tuple[int, int]
) -> Optional[str]:
    """Second pass: rewrite the situation section longer, then splice it back in.

    THE PASS IS ONE-SIDED AND THE TARGET IS NOT (plan 05 §7 step 2). This exists for
    the Ollama day path's ~290-word plateau, which Sonnet does not have (OQ7), so it
    only ever pushes output UP -- but D9's target is a BAND, and an "at least N words"
    prompt aimed at a band overshoots its top. It is therefore given both ends and told
    both, rather than being deleted: the plateau it was built for is still real on that
    model. The trigger is a K7 gate failure IN THE SHORT DIRECTION ONLY
    (`gate.f7_too_short`): the gate IS the band and fails both ways, and handing an
    over-long situation to a pass whose whole job is to lengthen it would rewrite it
    in exactly the wrong direction.

    THE INSTRUCTIONS IN THIS PROMPT ARE PART OF THE TIER, not neutral padding
    advice. The ICDC+ version told the model to give each named stakeholder a
    paragraph and to add a paragraph of specific numeric limits -- i.e. it re-injected
    K1 and K2 on every expansion. A retry pass that reintroduces the shape the tier
    removed is worse than no retry pass, so this one lengthens by DEEPENING the single
    scenario and must keep doing so.

    The `exhibit` parameter is GONE with K3. F3 bans the block outright, so there is
    no above-the-situation figure set for the expansion to stay consistent with; a
    case that has one is rejected by the gate rather than expanded around.

    Returns the spliced body, or None if the section boundaries can't be located.
    """
    import icdc_gate as gate  # noqa: PLC0415

    sit_header = situation_header(event_cfg)
    start = _has_header(body, sit_header)
    end = _has_header(body, "JUDGE ROLE-PLAY CHARACTERIZATION")
    if start is None or end is None:
        return None

    current = body[start:end]
    have = gate.situation_word_count(current)
    lo, hi = band
    para_lo = round(lo / situation_paragraphs(event_cfg))

    user = f"""Rewrite the {sit_header} below so it runs between {lo} and {hi} WORDS.

Keep the same company, the same people, and the SAME single decision. Do NOT resolve the
dilemma, do NOT say which option is best, and do NOT add a concluding recommendation.

Lengthen it by DEEPENING what is already there, in paragraphs of about {para_lo} words:
- fill in the company, its industry, its size and the history the decision turns on
- make the problem more concrete: what actually happened, in what order, and who noticed
- make the real cost of EACH course of action visible, without ranking them
- state more precisely what the judge wants analysed, decided, or recommended

Do NOT lengthen it by any of the following. Each one is the shape this event is not:
- adding another person with a stake in the decision, or giving anyone a personal name
- adding a table, an exhibit, or a labelled block of figures
- adding budgets, per-day capacity limits, or deadlines that collide with each other
- adding a second storyline alongside the one already there

The current version is about {have} words. Lengthen it past {lo} words, and stop before
{hi}: a situation over {hi} words is as much a failure as one under {lo}.

{current}"""

    expanded = call_llm(EXPAND_SYSTEM, user)
    if not expanded.strip():
        return None

    # Re-anchor: the model may or may not echo the header line back.
    if _has_header(expanded, sit_header) is None:
        expanded = f"{sit_header}\n\n{expanded.strip()}"
    return f"{body[:start]}{expanded.strip()}\n\n{body[end:]}"


def _exhibit_text(body: str) -> str:
    """The exhibit heading plus its rows, as authored, or "" when there is none."""
    import icdc_gate as gate  # noqa: PLC0415

    heading, _ = gate.find_exhibit(body)
    if heading is None:
        return ""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line.strip().rstrip(":").strip() == heading:
            rows, _ = gate.exhibit_block(lines, i)
            return "\n".join([line.strip(), *(r.rstrip() for r in rows)])
    return ""


def generate_one(
    event_key: str,
    day: date,
    *,
    tier: str = "icdc",
    require_icdc: bool = True,
    recent: Sequence[Dict] = (),
    quiet: bool = False,
    bank_id: Optional[str] = None,
    axes: Optional[Dict[str, str]] = None,
) -> Dict:
    """Generate ONE roleplay for one event on one day. Importable, seeded, scored.

    Seeded per event-day (`random.seed(f"{event_key}:{day.isoformat()}")`) so PI
    selection, example sampling and seed-axis choice are reproducible -- which is
    what lets `fill_buffer.py --dry-run` print exactly the PIs the real run uses.

    TWO IDENTITIES, one code path (plan 03 §6e). `bank_id` switches the seed from
    `<CODE>:<date>` to `<CODE>:<BANK_ID>` -- same construction, date removed -- so
    `fill_bank.py --author ollama` gets a reproducible draw for a roleplay that has
    no date. `axes` lets that caller supply the shelf-spread axes it resolved with
    `seed_axes.pick_for_bank`, since the shelf-wide rule cannot be derived from
    `recent`, which is time-windowed. Both default to the day behaviour, so
    `fill_buffer.py` is untouched.

    `recent` is the cross-day comparison set for this event (§5d), each entry
    carrying at least `date` and `excerpt`. Cross-day similarity is COMPUTED and
    RECORDED here; whether it rejects is the caller's decision, because the
    threshold is explicitly uncalibrated until two batches have run.

    Returns a dict; the raw text goes to parse_roleplay.py, which owns the
    frontend JSON contract. This function never writes to the archive.
    """
    import icdc_gate as gate  # noqa: PLC0415
    import seed_axes  # noqa: PLC0415

    event_cfg = EVENTS[event_key]
    fmt = event_cfg.get("format", "series")
    band = gate.situation_word_band(event_cfg)
    day_key = day.isoformat()

    random.seed(f"{event_key}:{bank_id}" if bank_id else f"{event_key}:{day_key}")

    pi_by_area = load_pi_by_area(event_cfg)
    if not pi_by_area:
        raise RuntimeError(
            f"No performance indicators available for event '{event_key}'. "
            "Seed the relevant data/pi/*.txt files first."
        )
    pi_items, declared_area = select_event_pis(pi_by_area, event_cfg)

    if axes is None:
        axes = seed_axes.pick(event_key, day, recent=recent)

    # Deviation (b): loaded for SCORING always; withheld from the PROMPT at this tier.
    examples = load_examples(event_cfg) if not quiet else _load_examples_quiet(event_cfg)
    icdc = tier == "icdc"
    prompt_examples: List[str] = [] if icdc else examples

    system_prompt = build_icdc_system_prompt(event_cfg) if icdc else read_text(SYSTEM_PROMPT_PATH)
    extra_context = seed_axes.as_context(axes, event_key)

    reminder = ""
    best: Optional[Dict] = None
    started = time.monotonic()

    for attempt in range(1, MAX_RETRIES + 2):
        if not quiet:
            print(f"  [{event_key} {day_key}] attempt {attempt}/{MAX_RETRIES + 1}...")

        user_message = build_user_message(
            event_cfg, "ICDC", declared_area, pi_items, prompt_examples, extra_context, reminder
        )
        raw = call_llm(system_prompt, user_message)
        body, report = gate.split_self_report(raw)
        passes = 1

        # Deviation (a): the second pass fires only when DENSITY is what failed.
        # Everything else (F3/F6/F8, structure, PI verbatim) the first pass
        # already handles, and re-writing on any other failure risks trading a
        # knob it got right for the one it missed.
        icdc_issues = gate.check_icdc_shape(body, event_cfg) if icdc else []
        # `f7_too_short`, NOT `startswith("F7")`. The band fails in BOTH directions
        # and this pass only ever LENGTHENS a situation, so an over-long one matched
        # on the knob id would be rewritten the wrong way. Under this tier's band
        # (ceiling = the retired tier's floor) the LONG direction is the common one.
        if icdc and gate.f7_too_short(icdc_issues):
            spliced = expand_situation(body, event_cfg, band)
            if spliced:
                body, passes = spliced, 2
                icdc_issues = gate.check_icdc_shape(body, event_cfg)
                # Re-attach the self-report tail. The expansion pass returns only
                # the roleplay, and parse_roleplay re-splits the tail itself to
                # build meta.claimed -- hand it a tail-less body and every
                # generation records "self-report:missing" and an empty claim set,
                # silently discarding the one thing Python can contradict.
                tail_at = raw.find(gate.SELF_REPORT_START)
                raw = body + ("\n\n" + raw[tail_at:] if tail_at != -1 else "")
            # If the expansion could not locate the section boundaries it returns
            # None and `raw` stays exactly as generated -- tail included.

        structural = validate_roleplay(body, event_cfg, pi_items, examples, declared_area)
        report_issues = gate.check_self_report(body, report) if icdc else []
        cross_day = _cross_day_similarity(body, event_cfg, recent)

        scored = {
            "event": event_key,
            "date": day_key,
            "format": fmt,
            "tier": tier,
            # `raw` keeps the self-report tail (parse_roleplay re-splits it to
            # build meta.claimed); `body` is the scored, tail-free roleplay.
            "raw": raw,
            "body": body,
            "attempt": attempt,
            "passes": passes,
            "axes": axes,
            # The FULL selection record, not the bare strings it used to carry:
            # parse_roleplay joins each authored PI back onto this to recover its
            # source area (D5), and a flattened list makes that impossible one step
            # earlier than anything downstream could notice.
            "pi_items": pi_items,
            "declared_area": declared_area,
            "structural_issues": structural,
            "icdc_issues": icdc_issues if require_icdc else [],
            "self_report_issues": report_issues,
            "exemplar_similarity": round(scenario_similarity(body, event_cfg, examples), 4),
            "cross_day_similarity": round(cross_day["score"], 4),
            "cross_day_nearest": cross_day["nearest"],
            "situation_words": gate.situation_word_count(
                _scenario_slice(body, situation_header(event_cfg))
            ),
            "situation_band": list(band),
            "model": OLLAMA_MODEL if LLM_BACKEND == "ollama" else ANTHROPIC_MODEL,
        }
        scored["passed"] = not scored["structural_issues"] and not scored["icdc_issues"]

        if best is None or (scored["passed"] and not best["passed"]):
            best = scored
        if scored["passed"]:
            break

        if attempt <= MAX_RETRIES:
            reminder = _repair_reminder(scored)

    assert best is not None
    best["seconds"] = round(time.monotonic() - started, 1)
    return best


def _load_examples_quiet(event_cfg: Dict) -> List[str]:
    """load_examples without its per-call print -- a 196-roleplay batch is noisy enough."""
    folder = DATA_DIR / event_cfg["data_folder"]
    files = sorted(folder.glob("*.txt"))
    if not files:
        return []
    out, used = [], 0
    for f in random.sample(files, min(MAX_EXAMPLE_ROLEPLAYS, len(files))):
        text = read_text(f)
        if used + len(text) > MAX_EXAMPLE_CHARS and out:
            break
        out.append(text)
        used += len(text)
    return out


def _cross_day_similarity(
    text: str, event_cfg: Dict, recent: Sequence[Dict]
) -> Dict[str, object]:
    """Max situation-slice similarity against this event's recent days (§5d).

    Compared against the STORED EXCERPT, which is capped at 800 chars, so this
    is a bounded-length comparison rather than the full-text one the exemplar
    guard runs. That is deliberate -- the index is a derived cache, and a
    truncated comparison is the honest read of what it holds.
    """
    if not recent:
        return {"score": 0.0, "nearest": None}
    gen = _scenario_slice(text, situation_header(event_cfg))
    best_score, nearest = 0.0, None
    for entry in recent:
        excerpt = entry.get("excerpt") or ""
        if not excerpt:
            continue
        score = difflib.SequenceMatcher(None, gen[: len(excerpt)], excerpt).ratio()
        if score > best_score:
            best_score, nearest = score, entry.get("date")
    return {"score": best_score, "nearest": nearest}


def _repair_reminder(scored: Dict) -> str:
    """The targeted retry nudge, assembled from what actually failed."""
    bits: List[str] = []
    if any("not original" in i for i in scored["structural_issues"]):
        bits.append(ORIGINALITY_REMINDER)
    if any("not original" not in i for i in scored["structural_issues"]):
        bits.append(STRICT_REMINDER)
    if scored["icdc_issues"]:
        bits.append(
            "DIFFICULTY REMINDER: your previous attempt missed these ICDC-tier rules: "
            + "; ".join(scored["icdc_issues"])
            + ". Fix every one of them."
        )
    return "\n\n".join(bits)


# ----------------------------
# Phase 6 -- Output + CLI
# ----------------------------
def save_output(event_key: str, level: str, text: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"{event_key.lower()}_{level.lower()}_{stamp}.txt"
    out_path.write_text(text, encoding="utf-8")
    return out_path


def main() -> None:
    print("Generate a DECA roleplay for a given event.\n")

    event_key = prompt_choice("DECA event", list(EVENTS.keys()))
    level = prompt_choice("Competition level", DIFFICULTY_LEVELS)
    extra_context = prompt_optional("Additional context")

    text = generate_roleplay(event_key, level, extra_context)

    if not text:
        print("\nNo roleplay was generated.")
        return

    out_path = save_output(event_key, level, text)
    print(f"\nRoleplay generated and saved to: {out_path}")


if __name__ == "__main__":
    main()
