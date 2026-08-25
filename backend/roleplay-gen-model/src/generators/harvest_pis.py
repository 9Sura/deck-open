#!/usr/bin/env python3
"""Rebuild data/pi/ from the 396-file corpus in data/<CODE>/.

Plan 05 §3.2a step 1. Costs no model tokens: every (instructional area,
performance indicator) pair is already in the repo, carried by the
``INSTRUCTIONAL AREA:`` header and ``PERFORMANCE INDICATORS`` block that all
396 corpus files have.

Output is TWO TIERS per area, not one list (2026-08-23):

  * ``data/pi/<area>.txt``           in-area  -- what a CORE quota may draw from
  * ``data/pi/adjacent/<area>.txt``  co-occurrence -- adjacent support only

An (area, PI) pair is in-area at ``MIN_IN_AREA_SUPPORT`` supporting corpus cases
or more. See that constant for the measurement and for why the floor is 2.

Merge policy is HYBRID (plan 05 OQ1a, decided 2026-08-19):

  * the corpus is authoritative for any area it supplies PIs for -- the
    existing lines for that area are discarded;
  * the existing lines are kept only for an area the corpus supplies ZERO
    for, so no event loses an eligible area to a gap in the corpus;
  * where a PI appears in both and the two disagree about its area, the
    corpus area wins and the library copy is dropped, so a PI string has
    exactly one home. Two homes would make the plan 05 §3 core-quota
    attribution ambiguous, which is the drift D5 exists to eliminate.

Nothing is written without ``--write``. The report is the same either way, and a
second ``--write`` is a no-op: the merge converges, so re-running produces a
byte-identical tree. Note the ``before`` column then reads the previous run's
output rather than the original library.

``backend/test-gen-model/data/pi/`` IS A SEPARATE LIBRARY AND MUST NOT BE
RE-SYNCED TO THIS ONE. The two were byte-for-byte identical on 23 of 24 files
until this harvest -- one was copied from the other and a single later update
(test-gen's 18 ``risk_management`` PIs) was never copied back
(audits/DECA_PI_recheck_report.md, 2026-08-19). This harvest deliberately breaks
that relationship: the roleplay library is now derived from the roleplay corpus
and disagrees with test-gen's on 21 of 24 files by design. Copying either way
would destroy one of them. In particular the 18 ``risk_management`` PIs are
business-risk PIs and do NOT fix PFL, which needs DECA's personal "Managing
Risk" (plan 05 5.2).
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import icdc_gate  # noqa: E402

# The core quota this harvest has to leave satisfiable, imported rather than
# restated: the gate owns the number (plan 05 §7 step 3) and a second copy here
# is how a floor gets raised past a quota nobody re-checked.
CORE_MINIMUM_BY_PI_COUNT = icdc_gate.CORE_MINIMUM_BY_PI_COUNT

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PI_DIR = DATA_DIR / "pi"
ADJACENT_DIR = PI_DIR / "adjacent"
EVENTS_JSON = DATA_DIR / "events.json"
PROVENANCE = PI_DIR / "_provenance.json"

# THE TIER SPLIT. A harvested PI is filed under a case's DECLARED area heading,
# which files two different things in one place: the PIs DECA actually lists
# under that area, and every other PI that happened to share a case with them.
# Both landed in one flat file, and `select_event_pis` drew the CORE quota
# uniformly over it -- so "Detail the functions of room service." was drawable as
# a core Economics PI, because one hospitality case declaring Economics carried
# it. That is the mechanism behind the audit's off-topic core PIs
# (audits/BLTDM_30_Roleplay_Recheck_Report.pdf, 2026-08-23).
#
# Support count separates the two populations cleanly and for free. Across the
# 396-file corpus, 696 of 1,005 distinct (area, PI) pairs are carried by exactly
# ONE case. Under Economics -- 32 declaring cases -- the supported end reads
# "Identify factors affecting a business's profit." (21 cases), "Explain the
# concept of competition." (19), "Determine factors affecting business risk."
# (19); the single-case tail is where room service, food loss and the nation's
# unemployment rate sit. Every PI the audit named as off-topic is a 1x pair, and
# no supported pair was named.
#
# 2 is the floor rather than 3 because 3 starves real areas: human resources
# management holds 30 pairs, 5 at >=2 and ONE at >=3, and operations 53/13/4
# against a core minimum of 4. The threshold is data, not a law -- raising it
# tightens the in-area tier and shrinks every core pool, so re-read the per-area
# counts this prints before moving it.
MIN_IN_AREA_SUPPORT = 2

# A SINGLE-CASE PAIR IS NOT A WRONG PAIR. It is a pair a second case has not
# corroborated, and demoting it costs variety rather than correctness: the
# co-occurrence tier stays fully eligible as ADJACENT support, which is what
# these PIs were doing usefully in the first place. Nothing is deleted here.

AREA_RE = re.compile(r"^INSTRUCTIONAL AREA[S]?:\s*(.+?)\s*$", re.M)
PI_BLOCK_RE = re.compile(
    r"^PERFORMANCE INDICATORS[^\n]*\n(.*?)(?:\n\s*\n)", re.M | re.S
)

# Corpus area headings that need consolidating before use. Recorded here
# rather than applied silently, because a mapping is an editorial decision.
CONSOLIDATE: Dict[str, str] = {
    # ENT/district_2018_1.txt's header is truncated by the scan
    # ("INSTRUCTIONAL AREA: Information Management and" with nothing after).
    # The source PDF prints it over TWO lines -- "Information Management and
    # Marketing-Information Management" -- and the extractor dropped the second
    # (audits/DECA_PI_recheck_report.md, 2026-08-19). So the heading names two
    # areas, not one, and this mapping is a judgement rather than a lookup: its
    # five PIs are marketing-research PIs ("Explain the nature of marketing
    # research", "Interpret statistical findings"), so the block is filed under
    # marketing-information management. There is no area named
    # "information_management_and" and one must never be created.
    "information_management_and": "marketing_information_management",

    # PFL, plan 05 §5.2 step 1. Its ten corpus files declare NINE area headings
    # spanning three DECA renamings; DECA's current PFL list has SIX, and the
    # nine are historical predecessors or combinations of them, not nine extra
    # sections (audits/DECA_PI_recheck_report.md, 2026-08-19). Consolidating is
    # free and it is a prerequisite rather than a tidy-up: the corpus supplies
    # only 30 PIs across the nine, which is 3 per area except Credit and Debt's
    # 6, so four of them yield C(3,3) = ONE distinct core set against a 30-deep
    # shelf and plan 05 §3's quota is unsatisfiable as filed.
    #
    # "spending_and_saving" folds into SPENDING and is not split. One of its
    # three PIs ("Compare the advantages and disadvantages of saving for
    # financial goals.") reads as a Saving PI and an earlier draft of this step
    # proposed splitting the heading across both areas. It is not split, for
    # two reasons: this harvest's unit is the FILE's declared heading and a
    # per-PI override is not expressible in it, and 149 of 578 distinct corpus
    # PIs (25.8%) are filed by DECA under more than one area anyway, so "the
    # area this PI belongs to" is not a question with an answer. The heading is
    # the evidence; the verb is not.
    "credit_and_debt": "managing_credit",
    "employment_and_income": "earning_income",
    "risk_management_and_insurance": "managing_risk",
    "spending_and_saving": "spending",
}

# DECA's six current Personal Financial Literacy instructional areas, in DECA's
# own order. CONSOLIDATE above maps the corpus's nine historical headings onto
# these; `events.json` lists exactly these six for PFL.
PFL_AREAS = [
    "earning_income",
    "spending",
    "saving",
    "investing",
    "managing_credit",
    "managing_risk",
]

# DECA's PUBLISHED PFL performance indicators, extracted by
# `import_pfl_pis.py` from the National Standards for Personal Financial
# Education (2021) -- the document deca.org/compete/personal-financial-literacy
# links as PFL's "Performance Indicators" and the PFL guidelines name as the
# source of its role-play situations. Unioned onto the corpus lines for the six
# PFL areas only.
#
# This file is a SECOND SOURCE, not a second writer: `harvest_pis.py` remains
# the only thing that writes `data/pi/*.txt`, so a re-harvest cannot silently
# drop the imported lines the way two writers over one tree would.
PFL_PUBLISHED = PI_DIR / "_pfl_national_standards_g12.json"


def load_pfl_published() -> Dict[str, List[str]]:
    """The published grade-12 outcomes per PFL area, or {} if not imported yet.

    Absent is not an error: the corpus half of the harvest stands on its own and
    a checkout that has not run `import_pfl_pis.py --write` should still be able
    to rebuild `data/pi/` from the corpus. The report says which half it got.
    """
    if not PFL_PUBLISHED.exists():
        return {}
    payload = json.loads(PFL_PUBLISHED.read_text(encoding="utf-8"))
    topics = payload.get("topics", {})
    unknown = sorted(set(topics) - set(PFL_AREAS))
    if unknown:
        raise ValueError(
            f"{PFL_PUBLISHED.name} carries area(s) that are not PFL areas: "
            f"{', '.join(unknown)}. PFL's six areas are {', '.join(PFL_AREAS)}."
        )
    return {slug: [strip_bullets(ln) for ln in lines if strip_bullets(ln)]
            for slug, lines in topics.items()}


def slugify_area(area: str) -> str:
    """DECA's printed area heading -> a data/pi/ file slug."""
    a = unicodedata.normalize("NFKD", area).strip()
    a = re.sub(r"[^\w\s/&-]", "", a)
    a = a.lower().replace("&", "and").replace("/", " ")
    return re.sub(r"[\s-]+", "_", a).strip("_")


# Leading bullet glyphs to strip off a harvested line. The private-use range
# is not decoration: 30 corpus files from 2020 carry a second, INVISIBLE bullet
# after the ordinary "- " -- U+F0A7, the Wingdings square, left behind by the
# PDF extraction on 161 lines. It survives a plain lstrip of "-*\u2022 \t",
# normalize_pi() strips it from the dedup KEY but not from the spelling that
# gets written, so 40 of them shipped into data/pi/ before this existed.
_BULLET_RE = re.compile(r"^[\s\-*\u00b7\u2010-\u2015\u2022\u25aa\u25cf\u25e6\uf000-\uf8ff]+")


def strip_bullets(line: str) -> str:
    """Drop every leading bullet layer. Idempotent by construction."""
    return _BULLET_RE.sub("", line).strip()


# Words the key drops outright. Articles carry no part of an indicator's identity
# and DECA prints them inconsistently across years -- "Explain concept of
# competition." (1 case) against "Explain the concept of competition." (29).
_ARTICLE_RE = re.compile(r"\b(?:a|an|the)\b")

# EDITORIAL SPELLING EQUIVALENCES, written as the two PIs themselves and normalized
# at import so the table can never drift out of step with the key it feeds.
# One entry, and the bar for a second one is high: a pair belongs here only when
# the two spellings differ by a WORD rather than by punctuation, an article or a
# plural -- everything mechanical is already collapsed above, and anything softer
# than an exact hand-recorded pair would be the PI-usability classifier plan 05
# §11 refuses.
#
# THE CORPUS IS NOT EDITED FOR THIS ONE, and that is the whole reason it is here.
# "Communicate core vale of product/service." was a single file's non-word typo
# and was fixed at source (FMS/district_2019_2.txt). "overhead/operating expenses"
# is printed by TWO independent DECA documents in two different events and years
# (ENT/district_2025_1, QSRM/district_2024_1) against 14 printings of
# "overhead/operating costs" -- two documents agreeing is DECA's own variance, not
# our extraction, and rewriting DECA's text to tidy our dedup would make the
# corpus undiffable against the source PDFs. `canonical()` picks "costs" on count.
_ALIAS_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("Explain the nature of overhead/operating expenses.",
     "Explain the nature of overhead/operating costs."),
)


def normalize_pi(pi: str) -> str:
    """Dedup key. Never written to disk -- only ever compared.

    Collapses the four ways the corpus spells one indicator differently, measured
    over the 584 distinct spellings the 396-file corpus carries:

      punctuation      "customer-service" == "customer service"      (2 pairs)
      articles         "Explain concept of" == "Explain the concept of"  (+6)
      trailing plural  "the function of prices" == "the functions of"     (+11)
      alias table      the one hand-recorded word pair, `_KEY_ALIASES`     (+1)

    Every one of those 19 merges was read individually before this widened, and all
    19 join two spellings of the SAME indicator -- there is no pair among them that
    a human would call two different PIs. The dedup key was punctuation-DELETING
    before ("customer-service" -> "customerservice", which does not equal "customer
    service"), and the split pairs it left behind are what put a typo variant and
    its correct spelling in one BLTDM bundle
    (audits/BLTDM_30_Roleplay_Recheck_Report.pdf, 2026-08-23).

    Widening the key does not choose the SPELLING: `canonical()` still writes the
    most-frequent one, so a merge adopts what DECA prints most often and drops the
    outlier. Re-read the report's per-area deltas before widening this further --
    every area's line count moves.

    THE PLURAL FOLD IS CRUDE ON PURPOSE. It strips one trailing "s" from words of
    four letters or more that do not already end in "ss"; it is a dedup key, not a
    stemmer, and it never has to produce a real word. Nothing reads it back.
    """
    key = _mechanical_key(pi)
    return _KEY_ALIASES.get(key, key)


def _mechanical_key(pi: str) -> str:
    """`normalize_pi` without the alias table -- everything a rule can do alone."""
    p = unicodedata.normalize("NFKD", pi).lower().strip().rstrip(".")
    # Punctuation becomes a SPACE, not nothing -- a hyphen and a space are the same
    # word boundary to a reader and must be the same one here.
    p = re.sub(r"[^a-z0-9]+", " ", p)
    p = re.sub(r"\s+", " ", _ARTICLE_RE.sub(" ", p)).strip()
    return " ".join(
        w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
        for w in p.split()
    )


_KEY_ALIASES: Dict[str, str] = {
    _mechanical_key(variant): _mechanical_key(canon) for variant, canon in _ALIAS_PAIRS
}


def read_lines(path: Path) -> List[str]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = strip_bullets(line)
        if line:
            out.append(line)
    return out


def harvest_corpus(event_codes: Set[str]) -> Tuple[
    Dict[str, Dict[str, collections.Counter]],
    Dict[str, Dict[str, Set[str]]],
    List[str],
]:
    """area slug -> {dedup key -> Counter of the spellings seen}, plus support.

    Support is the set of SOURCE FILES an (area, key) pair appears in, not a
    line count: a case that lists the same indicator twice is one case's worth
    of evidence, and the tier split below turns this number into a floor.
    """
    found: Dict[str, Dict[str, collections.Counter]] = collections.defaultdict(
        lambda: collections.defaultdict(collections.Counter)
    )
    support: Dict[str, Dict[str, Set[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(set)
    )
    skipped: List[str] = []
    for path in sorted(DATA_DIR.glob("*/*.txt")):
        code = path.parent.name
        if code not in event_codes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        areas = AREA_RE.findall(text)
        block = PI_BLOCK_RE.search(text)
        if not areas:
            skipped.append(f"{code}/{path.name}: no INSTRUCTIONAL AREA header")
            continue
        if not block:
            skipped.append(f"{code}/{path.name}: no PERFORMANCE INDICATORS block")
            continue
        if len(areas) > 1:
            skipped.append(
                f"{code}/{path.name}: {len(areas)} INSTRUCTIONAL AREA headers"
            )
            continue
        slug = slugify_area(areas[0])
        slug = CONSOLIDATE.get(slug, slug)
        for line in block.group(1).splitlines():
            pi = strip_bullets(line)
            if pi:
                key = normalize_pi(pi)
                found[slug][key][pi] += 1
                support[slug][key].add(f"{code}/{path.name}")
    return found, support, skipped


def canonical(spellings: collections.Counter) -> str:
    """Most-frequent spelling; ties broken alphabetically so the output is
    byte-stable across runs."""
    top = max(c for c in spellings.values())
    return sorted(s for s, c in spellings.items() if c == top)[0]


def global_spellings(
    corpus: Dict[str, Dict[str, collections.Counter]]
) -> Dict[str, collections.Counter]:
    """key -> every spelling of it seen ANYWHERE, summed across areas.

    ONE INDICATOR GETS ONE SPELLING, and the count that picks it is corpus-wide
    rather than per-area. Counting per area writes the same PI two different ways
    in two different files -- "Demonstrate a customer service mindset." under
    economics and "Demonstrate a customer-service mindset." under customer
    relations, which is what the per-area count produced the moment `normalize_pi`
    started collapsing the two. The area is a filing property of the pair; the
    SPELLING is DECA's, and DECA's most-printed wording does not change with which
    area a case declared.
    """
    merged: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for keys in corpus.values():
        for key, spellings in keys.items():
            merged[key].update(spellings)
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="write data/pi/*.txt and _provenance.json (default: report only)")
    args = ap.parse_args()

    events = json.loads(EVENTS_JSON.read_text(encoding="utf-8"))["events"]
    codes = {cfg["data_folder"] for cfg in events.values()}

    corpus, support, skipped = harvest_corpus(codes)
    for line in skipped:
        print(f"  [warn] {line}", file=sys.stderr)

    # The in-area tier only. `PI_DIR.glob` does not recurse, so `adjacent/` is
    # not read back as an area named "adjacent" -- and it must not be, because a
    # re-harvest recomputes the co-occurrence tier from the corpus every time.
    existing: Dict[str, List[str]] = {}
    for path in sorted(PI_DIR.glob("*.txt")):
        existing[path.stem] = read_lines(path)

    spelling_of = global_spellings(corpus)

    # --- cross-area conflicts: the corpus area wins -----------------------
    corpus_home: Dict[str, Set[str]] = collections.defaultdict(set)
    for slug, pis in corpus.items():
        for key in pis:
            corpus_home[key].add(slug)

    conflicts: List[Tuple[str, str, str]] = []   # (library area, corpus areas, PI)
    for slug, lines in existing.items():
        for line in lines:
            key = normalize_pi(line)
            homes = corpus_home.get(key)
            if homes and slug not in homes:
                conflicts.append((slug, "/".join(sorted(homes)), line))

    # --- hybrid merge, split into the two tiers ---------------------------
    # `result` is the IN-AREA tier and keeps the `<area>.txt` path it always had,
    # so every reader that wants "the PIs of this area" keeps working and gets a
    # cleaner answer. `adjacent` is the co-occurrence tier, written beside it.
    result: Dict[str, List[str]] = {}
    adjacent: Dict[str, List[str]] = {}
    kept_areas: List[str] = []
    for slug in sorted(set(corpus) | set(existing)):
        if slug in corpus and corpus[slug]:
            in_area, co_occur = [], []
            for key in corpus[slug]:
                cases = len(support[slug][key])
                (in_area if cases >= MIN_IN_AREA_SUPPORT else co_occur).append(
                    canonical(spelling_of[key])
                )
            result[slug] = sorted(in_area)
            adjacent[slug] = sorted(co_occur)
        else:
            # corpus supplies nothing for this area: keep what is there so no
            # event loses an eligible area to a gap in the corpus.
            #
            # KEPT LIBRARY LINES ARE IN-AREA, and that is a read of what they are
            # rather than a default. They come from a per-area list, so filing
            # them under this area IS the claim they carry -- the co-occurrence
            # problem is a property of harvesting by a case's declared heading,
            # and these were never harvested that way. There is no support count
            # to threshold them against and inventing one would be fiction; the
            # three areas this covers are named in the provenance.
            keep = [ln for ln in existing.get(slug, [])
                    if slug in corpus_home.get(normalize_pi(ln), {slug})]
            result[slug] = sorted(set(keep))
            adjacent[slug] = []
            if keep:
                kept_areas.append(slug)

    # --- PFL: union DECA's published list onto the corpus lines -----------
    # Corpus spelling wins a collision: it is the wording DECA actually printed
    # on a role-play, and 10 of the 30 corpus PFL PIs are verbatim National
    # Standards outcomes already, so the overlap is real rather than theoretical.
    #
    # These land IN-AREA and skip the support floor, which is the whole point of
    # having them: the National Standards document publishes its outcomes UNDER
    # an area heading, so a published line is DECA filing the PI under the area
    # directly. That is a stronger claim than two corpus cases agreeing, not a
    # weaker one, and thresholding it would throw away the better evidence.
    published = load_pfl_published()
    added: Dict[str, int] = {}
    for slug in PFL_AREAS:
        lines = published.get(slug, [])
        if not lines:
            continue
        have = {normalize_pi(ln) for ln in result.get(slug, [])}
        fresh = []
        for ln in lines:
            key = normalize_pi(ln)
            if key in have:
                continue
            have.add(key)
            fresh.append(ln)
        if fresh:
            result[slug] = sorted(result.get(slug, []) + fresh)
            added[slug] = len(fresh)

    # --- the two tiers are disjoint, per area -----------------------------
    # A published PFL outcome can be worded like a single-case corpus line, which
    # would put one indicator in both of an area's files. The selector unions the
    # tiers to build its adjacent pool, so a line in both is drawable twice and
    # `select_event_pis`'s dedup-by-PI-string would have to catch it downstream.
    # Cheaper to keep the promotion authoritative here: in-area wins.
    promoted: Dict[str, int] = {}
    for slug, lines in adjacent.items():
        in_area_keys = {normalize_pi(ln) for ln in result.get(slug, [])}
        trimmed = [ln for ln in lines if normalize_pi(ln) not in in_area_keys]
        if len(trimmed) != len(lines):
            promoted[slug] = len(lines) - len(trimmed)
        adjacent[slug] = trimmed

    # --- report -----------------------------------------------------------
    print(f"corpus files scanned: "
          f"{sum(1 for p in DATA_DIR.glob('*/*.txt') if p.parent.name in codes)}"
          f"  |  skipped: {len(skipped)}")
    print(f"distinct corpus areas: {len(corpus)}  |  cross-area conflicts resolved "
          f"to the corpus: {len(conflicts)}")
    print(f"tier floor: an (area, PI) pair is IN-AREA at "
          f">= {MIN_IN_AREA_SUPPORT} supporting corpus case(s)")
    print()
    print(f"{'area':<36} {'before':>6} {'in-area':>8} {'adj':>5} {'delta':>6}  source")
    for slug in sorted(result):
        before, after = len(existing.get(slug, [])), len(result[slug])
        if slug in corpus and corpus[slug]:
            src = "corpus"
        elif after:
            src = "existing (corpus supplies none)"
        else:
            src = "EMPTY"
        if slug in added:
            src = f"{src} + published ({added[slug]})"
        tag = "  [PFL]" if slug in PFL_AREAS else ""
        print(f"{slug:<36} {before:>6} {after:>8} {len(adjacent.get(slug, [])):>5} "
              f"{after - before:>+6}  {src}{tag}")
    tot_b, tot_a = sum(len(v) for v in existing.values()), sum(len(v) for v in result.values())
    tot_adj = sum(len(v) for v in adjacent.values())
    print(f"{'TOTAL':<36} {tot_b:>6} {tot_a:>8} {tot_adj:>5} {tot_a - tot_b:>+6}")

    # WHICH AREAS CAN STILL BE DECLARED. The in-area tier is what a core quota
    # draws from, so a floor that leaves an area under its core minimum has taken
    # the area off every event that lists it -- and `load_pi_by_area` raises at
    # generation time rather than here, one step too late to be read as a
    # threshold problem. Say it now, per event, against that event's own quota.
    starved: List[str] = []
    for code, cfg in sorted(events.items()):
        core_min = CORE_MINIMUM_BY_PI_COUNT.get(cfg["pi_count"])
        if core_min is None:
            continue
        for slug in cfg["instructional_areas"]:
            have = len(result.get(slug, []))
            if have < core_min:
                starved.append(
                    f"  {code:<7} {slug:<34} {have} in-area PI(s), core minimum {core_min}"
                )
    if starved:
        print(f"\nAREAS THAT CAN NO LONGER FILL A CORE QUOTA at this floor:")
        for line in starved:
            print(line)
        print("  Lower MIN_IN_AREA_SUPPORT, populate the area, or take it off the "
              "event in events.json.")
    if promoted:
        print(f"\npromoted out of the co-occurrence tier (also in-area): "
              + ", ".join(f"{s} ({n})" for s, n in sorted(promoted.items())))

    if published:
        print(f"\nPFL published list: {sum(len(v) for v in published.values())} "
              f"grade-12 outcomes read from {PFL_PUBLISHED.name}, "
              f"{sum(added.values())} new after dedup against the corpus.")
    else:
        print(f"\nPFL published list: {PFL_PUBLISHED.name} is ABSENT -- the six PFL "
              f"areas carry corpus lines only. Run import_pfl_pis.py --write "
              f"(plan 05 §5.2).")

    if conflicts:
        print(f"\ncross-area conflicts (library copy dropped, corpus area kept):")
        for lib, corp, pi in sorted(conflicts):
            print(f"  {lib:<32} -> {corp:<32} | {pi}")

    # A CONSOLIDATE source can never be produced again by construction, so its
    # file is an orphan rather than an empty area -- leaving a zero-line
    # `credit_and_debt.txt` on disk would keep it eligible for `events.json` and
    # would trip plan 05 D7's raise the moment someone listed it. Other empty
    # files are left alone: they are areas the corpus simply has nothing for.
    retired = sorted(slug for slug in CONSOLIDATE if (PI_DIR / f"{slug}.txt").exists())
    for slug in retired:
        result.pop(slug, None)
        adjacent.pop(slug, None)

    empty = [s for s, v in result.items() if not v]
    if empty:
        print(f"\nareas resolving to ZERO PIs: {', '.join(empty)}")
        print("  plan 05 D7: an eligible area with no PIs comes off the event "
              "rather than silently contributing nothing.")

    if retired:
        print(f"\nretired (consolidated away, file deleted): {', '.join(retired)}")

    if not args.write:
        print("\n(report only -- pass --write to update data/pi/)")
        return 0

    for slug in retired:
        (PI_DIR / f"{slug}.txt").unlink()
        stale = ADJACENT_DIR / f"{slug}.txt"
        if stale.exists():
            stale.unlink()

    ADJACENT_DIR.mkdir(exist_ok=True)
    for slug, lines in result.items():
        (PI_DIR / f"{slug}.txt").write_text(
            "".join(f"{ln}\n" for ln in lines), encoding="utf-8"
        )
    # An area with an empty co-occurrence tier still gets its file, so "this area
    # has no adjacent lines" and "this area has not been harvested since the split"
    # are distinguishable on disk rather than both reading as a missing file.
    for slug in result:
        (ADJACENT_DIR / f"{slug}.txt").write_text(
            "".join(f"{ln}\n" for ln in adjacent.get(slug, [])), encoding="utf-8"
        )
    PROVENANCE.write_text(json.dumps({
        "generated_by": "src/generators/harvest_pis.py",
        "plan": "05-pi-selection-and-regeneration-plan.md §3.2a step 1",
        "merge_policy": "hybrid (OQ1a, decided 2026-08-19)",
        "tier_split": {
            "why": (
                "harvesting by a case's declared INSTRUCTIONAL AREA header files two "
                "populations in one place: the PIs DECA lists under the area, and every "
                "PI that shared a case with them. The core quota drew uniformly over "
                "both, so a co-occurrence PI was drawable as a CORE PI of an area it "
                "does not belong to -- the mechanism behind the off-topic core PIs in "
                "audits/BLTDM_30_Roleplay_Recheck_Report.pdf (2026-08-23)."
            ),
            "rule": (
                f"an (area, PI) pair is IN-AREA at >= {MIN_IN_AREA_SUPPORT} supporting "
                "corpus case(s), co-occurrence below that"
            ),
            "min_in_area_support": MIN_IN_AREA_SUPPORT,
            "in_area_path": "data/pi/<area>.txt",
            "co_occurrence_path": "data/pi/adjacent/<area>.txt",
            "core_draws_from": "in-area only",
            "adjacent_draws_from": "both tiers, every eligible area",
            "not_a_deletion": (
                "a single-case pair is uncorroborated, not wrong; the co-occurrence tier "
                "stays fully eligible as adjacent support and nothing is dropped"
            ),
            "kept_library_lines_are_in_area": (
                "an area the corpus supplies nothing for keeps its existing library "
                "lines in the in-area tier: they come from a per-area list rather than "
                "from harvesting a case heading, so they never had this defect and "
                "there is no support count to threshold them against"
            ),
            "pfl_published_lines_are_in_area": (
                "the National Standards outcomes are published UNDER an area heading, "
                "which is DECA filing the PI directly -- stronger evidence than two "
                "corpus cases agreeing, so they skip the floor"
            ),
        },
        "co_occurrence_promoted_to_in_area": {s_: n for s_, n in sorted(promoted.items())},
        "corpus_files": sum(1 for p in DATA_DIR.glob("*/*.txt") if p.parent.name in codes),
        "consolidated_area_slugs": CONSOLIDATE,
        "pfl_areas": PFL_AREAS,
        "pfl_published_source": (
            json.loads(PFL_PUBLISHED.read_text(encoding="utf-8")).get("_source")
            if PFL_PUBLISHED.exists() else None
        ),
        "pfl_published_lines_added": {s_: n for s_, n in sorted(added.items())},
        "areas_kept_from_the_existing_library": sorted(kept_areas),
        "cross_area_conflicts_resolved_to_the_corpus": [
            {"library_area": a, "corpus_area": b, "pi": c}
            for a, b, c in sorted(conflicts)
        ],
        "areas_with_zero_pis": sorted(empty),
        "retired_area_files": retired,
        "do_not_resync_with": {
            "path": "backend/test-gen-model/data/pi/",
            "why": (
                "a separate library that was byte-identical on 23 of 24 files before this "
                "harvest; the roleplay library is now corpus-derived and diverges by design. "
                "Copying either way destroys one of them. test-gen's 18 risk_management PIs "
                "are business-risk PIs and do not fix PFL."
            ),
        },
        "pi_counts": {s: len(v) for s, v in sorted(result.items())},
        "adjacent_pi_counts": {s: len(adjacent.get(s, [])) for s in sorted(result)},
    }, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {len(result)} in-area file(s) to {PI_DIR}, "
          f"{len(result)} co-occurrence file(s) to {ADJACENT_DIR.name}/, "
          f"and {PROVENANCE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
