"""Assemble + validate a question-bank set from authored JSON parts.

This is the *bank assembler*, not a generator. The DECA questions are authored
upstream (see plans/02-question-bank-generation-plan.md) and dropped as JSON
arrays; this script merges the parts for one cluster x level, runs the
structural-accuracy gate, assigns stable ids, and writes the committed
`question-bank/<cluster>/<level>.json` plus refreshes `manifest.json`.

No model is called here. The "accuracy gate" is a set of cheap structural checks
over authored content (one answer, four distinct options, no length giveaway,
explanation addresses the distractors) plus two-key dedup -- content hash (stem +
options) and stem hash (options-blind, issue #34), both keyed on the
punctuation-folded `dedup_norm` so a curly-quote twin is still a twin (issue
#64) -- and a per-area coverage
ledger; everything the plan's section 4.3/4.4 asks for that can be enforced
mechanically. A question that fails a hard check is dropped and logged; soft
checks (e.g. explanation coverage) are warnings only.

Writes `question-bank/<cluster>/<cluster>-<level>-<set>.json` (e.g.
`marketing/marketing-district-1.json`); pass `--set N` to author additional
independent sets for the same cluster x level.

Pool mode (`--pool`, plan 03 section 3.2) assembles an *original* pool file
`<cluster>-<level>-pool.json` instead of a numbered set. Pools carry a
`difficulty` label per question (required, tagged at authoring time), are deduped
against the *entire committed bank* (not just their own parts) so they can't
re-serve an existing set question -- on stem alone as well as on stem + options --
and land in the manifest's `pools` section with per-file `difficultyCounts`.

Usage:
    python build_question_bank.py <cluster> <level> part1.json [part2.json ...]

    # or point it at a directory of parts:
    python build_question_bank.py <cluster> <level> --parts-dir path/to/dir

    # author a second (or later) set for the same cluster x level:
    python build_question_bank.py <cluster> <level> --set 2 --parts-dir path/to/dir

    # author the original pool for a cluster x level (difficulty-tagged parts):
    python build_question_bank.py <cluster> <level> --pool --parts-dir path/to/dir
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# PATHS
from bank_paths import BANK_DIR, MANIFEST_PATH, REPO_ROOT  # noqa: E402  the ONE bank path (#203)

VALID_LEVELS = {"District", "Association", "ICDC"}
OPTION_KEYS = ("A", "B", "C", "D")
DIFFICULTY_TIERS = ("easy", "medium", "hard")

# Bank schema version; bump when the question object shape changes.
BANK_VERSION = 1
# Manifest version that introduced difficultyCounts + the pools section (plan 03).
MANIFEST_VERSION_V2 = 2


# ----------------------------
# Cluster id prefixes (for stable question ids)
# ----------------------------
CLUSTER_PREFIX = {
    "pbm": "pbm",
    "marketing": "mkt",
    "finance": "fin",
    "hospitality": "hos",
    "entrepreneurship": "ent",
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ----------------------------
# Structural-accuracy gate (section 4.3) + dedup (section 4.4)
# ----------------------------
REQUIRED_FIELDS = (
    "question",
    "options",
    "answer",
    "explanation",
    "instructionalArea",
    "performanceIndicator",
)

# ----------------------------
# Banned combination-style options (section prompt rule 5)
# ----------------------------
# Rule 5 bans an option that points at the OTHER options instead of saying something.
# Two instruments, because the two shapes need different matching:
#
#   BANNED_PHRASES     -- matched as a bare substring anywhere in the option. Safe
#                         only because these phrases are long; an accidental
#                         substring match is not a real hazard.
#   COMBINATION_OPTION -- the letter-pair shape ("A and B"), matched ANCHORED at the
#                         start of the option.
#
# The letter phrase MUST live only in the regex (issue #88). It was originally in the
# substring list, where `a and b` matched "protecting dat(a and b)eing honest in
# interactions" and HARD-FAILED a clean distractor -- the third time a slice read a
# tool's own bug as author non-compliance (§10-11 finding 3). The first anchoring pass
# fixed that one phrase but left `both a and b` in the substring list, still unanchored
# and still false-positiving ("...a rule that holds for both a and b parts of the
# form"), while anchoring the rest so tightly that any leading noun defeated it:
# `Options A and B` and `Choices A and B are correct` are exactly the shape rule 5
# bans and both walked straight through. So the leading words a real combination
# option carries are part of the pattern now, and the pair is `[abcd] and [abcd]`
# rather than literally `a and b` -- which also closes `Both A and C`, the same defect,
# never caught by any version.
#
# The anchor is the whole design, not a shortcut: a combination option LEADS with the
# letters, and requiring the match at the start is exactly what keeps ordinary prose
# ("data and being", "for both a and b parts") out. Prose that names other options
# mid-sentence is NOT caught, deliberately -- a hard drop is too expensive to spend on
# a guess. Measured against the committed bank: 0 of 12,778 rows match, before or
# after; this is a guard-correctness fix, not a data repair.
#
# Pinned by `slice-tools/fixtures_combination_option.py` -- assert a gate's behaviour
# in a test, not only in a comment (#72/#75/#76, and now the second time this
# predicate has been wrong).
BANNED_PHRASES = ("all of the above", "none of the above")
_COMBO_LEAD = r"(?:both|either|the|options?|choices?|answers?|statements?|responses?)"
COMBINATION_OPTION = re.compile(rf"^(?:{_COMBO_LEAD}\s+){{0,3}}[abcd]\s+and\s+[abcd]\b")

# THE TWO RATIO SOFTS `build_area.py`'s LENGTH LADDER CAN ITSELF CAUSE (#139).
#
# Both thresholds and both message markers are named HERE, beside the code that emits
# them, because `check_authored.py` filters on them: it suppresses a ratio soft whose
# own payload assignment produced it, and it needs the same numbers this gate used
# plus a stable substring to recognise the message by. Two copies of `0.45` in two
# files is #88 exactly -- the combination-option predicate was wrong in both
# directions because its behaviour lived in a comment on one side and in a regex on
# the other. Pinned by `slice-tools/fixtures_ladder_assigned_softs.py`, which asserts
# that a message check_question actually emits still contains its marker, so
# rewording the string breaks the fixture instead of silently disarming the filter.
#
# The 2.2x HARD drop is deliberately NOT named here and is never suppressed: no rung
# of any shipped ladder comes within 0.5x of it (easy rank 1 is the closest at 1.71x),
# so a 2.2x row is author drift by construction. Same for the >=20ch absolute margin.
LENGTH_GIVEAWAY_RATIO = 1.5   # key over this multiple of the distractor mean -> soft
REVERSE_TELL_RATIO = 0.45     # key under this multiple -> the mirror soft
SOFT_LENGTH_GIVEAWAY_RATIO = f"(>{LENGTH_GIVEAWAY_RATIO}x)"  # derived, so it can't go stale
SOFT_REVERSE_TELL = "possible reverse length tell"


def _norm(text: str) -> str:
    """Lowercase, collapse whitespace -- for comparison (NOT for dedup keys).

    Kept exactly as it was for the non-dedup comparisons below (duplicate option
    texts, thin explanation, stem-restates-the-PI). Those want a literal reading;
    only the dedup hashes fold punctuation, via `dedup_norm`.
    """
    return re.sub(r"\s+", " ", str(text).strip().lower())


# Typographic folding for the dedup keys (issue #64). `_norm` above only lowercases
# and collapses whitespace, so two stems differing by one curly apostrophe --
# `What is a company's 'brand promise'?` (pbm-icdc-pool-0714) vs `What is a
# company's brand promise?` (fin-icdc-pool-0110) -- hash apart, and every gate that
# keys on those hashes reports "0 dupes" on a pair a student reads as one question.
#
# The fold is deliberately TYPOGRAPHIC ONLY. Quotes, brackets, sentence punctuation
# and hyphen-vs-space cannot change which question is being asked. `%`, `$`, `#`,
# `&`, `+`, `=`, `<`, `>` and digits can, and are kept: dropping `%` would merge
# "margin rises 5%" with "margin rises 5", a FALSE dupe -- and a false positive here
# is not free, because `collapse_stem_dupes.py --apply` DELETES what this key calls
# a twin. Anything looser than exact-after-folding (stemming, fuzzy/Jaccard) is a
# different instrument with a different failure mode and stays in its own tool: see
# detect_stem_restatement.py.
#
# The map is written as ESCAPES, never as the characters themselves: this file is
# read in terminals and by tools that silently normalize lookalike/invisible
# characters, and a pasted nbsp is undebuggable (docs/issue-finding-and-debugging.md §1c).
_SMART_CHARS = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",   # curly single quotes
    "\u201c": '"', "\u201d": '"', "\u201e": '"',                   # curly double quotes
    "\u2013": "-", "\u2014": "-", "\u2212": "-",                   # en dash, em dash, minus
    "\u00a0": " ", "\u2009": " ", "\u202f": " ",                   # nbsp, thin, narrow nbsp
}
_DROP_CHARS_RE = re.compile(r"[\"'`…,.;:!?()\[\]{}]")
_SPACE_CHARS_RE = re.compile(r"[-/\\|]")


def dedup_norm(text: str) -> str:
    """Normalize a stem/option for a DEDUP KEY: lowercase, fold typography, strip
    sentence punctuation, collapse whitespace.

    Meaning-bearing symbols survive on purpose -- see the note above `_SMART_CHARS`.
    """
    s = str(text)
    for smart, plain in _SMART_CHARS.items():
        s = s.replace(smart, plain)
    s = s.lower()
    s = _DROP_CHARS_RE.sub("", s)
    s = _SPACE_CHARS_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def content_hash(q: Dict) -> str:
    """Stable hash of the normalized stem + the four option texts."""
    parts = [dedup_norm(q.get("question", ""))]
    opts = q.get("options", {}) or {}
    parts += [dedup_norm(opts.get(k, "")) for k in OPTION_KEYS]
    return hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()[:12]


def stem_hash(q: Dict) -> str:
    """Stable hash of the normalized stem ALONE -- deliberately options-blind.

    `content_hash` keys on stem + options, so re-authoring the same stem with a
    reworded option set walks straight through it: issue #34 found 12 word-for-word
    identical stems shipped twice that way, 10 of them inside one pool, most with
    conflicting difficulty tags. A student drawing a 50-question test out of that
    780-item pool can be served the same question twice in one sitting, badged Easy
    once and Medium once. The stem is the unit a student recognizes, so the stem is
    what dedup has to key on.

    Keyed on `dedup_norm`, not `_norm` (issue #64): the stem is the unit a student
    recognizes, and a student does not recognize a pair of quotes.
    """
    return hashlib.sha1(dedup_norm(q.get("question", "")).encode("utf-8")).hexdigest()[:12]


def load_bank_hashes(exclude: Optional[Path] = None) -> set:
    """Content hashes of every question already committed to the bank.

    Enforces cross-file originality (plan 03 section 3.2): a pool question must
    not collide with any existing set. ``exclude`` skips one file so a pool can
    be re-assembled idempotently without matching against its own prior output.
    """
    hashes: set = set()
    if not BANK_DIR.exists():
        return hashes
    excl = exclude.resolve() if exclude else None
    for path in sorted(BANK_DIR.glob("*/*.json")):
        if excl is not None and path.resolve() == excl:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, list):
            for q in data:
                if isinstance(q, dict):
                    hashes.add(content_hash(q))
    return hashes


def load_bank_stems(exclude: Optional[Path] = None) -> Dict[str, List[Dict]]:
    """stem_hash -> the committed questions carrying that stem (issue #34).

    Each entry keeps the id, cluster, level and difficulty, because the two
    collision kinds are not the same defect and must not carry the same penalty:

      * SAME cluster x level -- both copies live in one candidate pool, so one
        sitting can serve both. A hard drop.
      * DIFFERENT cluster x level -- `loadCandidates` is scoped to one
        cluster x level, so the two can never co-occur in a test, a focus quiz, or
        a PI drill. Generic PIs are genuinely shared across clusters (`Explain
        ethical dilemmas` is authored for both finance/ICDC and pbm/Association),
        and hard-dropping there would starve whichever cluster is authored second
        of its only coverage for that PI. A soft flag.

    ``exclude`` skips one file, mirroring `load_bank_hashes`, so re-assembling a
    pool doesn't collide with its own prior output.
    """
    stems: Dict[str, List[Dict]] = {}
    if not BANK_DIR.exists():
        return stems
    excl = exclude.resolve() if exclude else None
    for path in sorted(BANK_DIR.glob("*/*.json")):
        if excl is not None and path.resolve() == excl:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, list):
            continue
        for q in data:
            if not isinstance(q, dict):
                continue
            stems.setdefault(stem_hash(q), []).append({
                "id": q.get("id"),
                "cluster": q.get("cluster"),
                "level": q.get("level"),
                "difficulty": q.get("difficulty"),
            })
    return stems


def check_question(q: Dict, require_difficulty: bool = False) -> Tuple[List[str], List[str]]:
    """Return (hard_errors, soft_warnings) for a single question object.

    Hard errors drop the question; soft warnings are reported but kept.
    ``require_difficulty`` (pool mode) makes a valid `difficulty` tier mandatory.
    """
    hard: List[str] = []
    soft: List[str] = []

    # Shape / required fields.
    for f in REQUIRED_FIELDS:
        if f not in q or q[f] in (None, "", {}):
            hard.append(f"missing field '{f}'")
    if hard:
        return hard, soft  # nothing else is trustworthy without the fields

    # Exactly four labeled options, all non-empty and distinct.
    opts = q["options"]
    if not isinstance(opts, dict) or set(opts.keys()) != set(OPTION_KEYS):
        hard.append("options must be an object with exactly keys A,B,C,D")
        return hard, soft
    texts = [str(opts[k]).strip() for k in OPTION_KEYS]
    if any(not t for t in texts):
        hard.append("an option is empty")
    normed = [_norm(t) for t in texts]
    if len(set(normed)) != 4:
        hard.append("duplicate option texts")

    # Exactly one answer, a single valid letter.
    ans = str(q["answer"]).strip().upper()
    if ans not in OPTION_KEYS:
        hard.append(f"answer '{q['answer']}' is not one of A-D")

    # Banned combination-style options (section prompt rule 5). Both instruments are
    # defined at module level, with the reasoning for the split -- read it before
    # touching either one; each has been wrong once.
    if any(any(b in n for b in BANNED_PHRASES) or COMBINATION_OPTION.match(n) for n in normed):
        hard.append("contains an all/none/both-style option")

    # Length-giveaway guard (plan 05 §3). Calibrated, not invented: this check
    # already existed as a lone soft warning at 2.2x, which fires on 1.2% of pools
    # and 1.6% of sets while 60%/70% of the bank carries the tell. A smoke detector
    # with the battery out. Flag rates below are measured against the committed
    # bank; each threshold's cost is known before it is adopted.
    #
    #   rule                     pools   sets
    #   key > 2.2x avg  (was the only rule, soft)    1%     2%   -> now a HARD drop
    #   key > 1.8x avg                               4%     7%
    #   key > 1.5x avg                              13%    23%   -> the new soft flag
    #   key > 1.3x avg                              29%    42%
    #   longest AND >=20ch over runner-up           13%    30%   -> soft; ratio misses these
    #
    # 1.5x soft catches the decisive band without flagging a quarter of every batch,
    # which would train whoever reads the report to ignore it -- the exact failure
    # that produced this defect. 2.2x becomes a drop because that outlier is
    # indefensible, but the drop stays in the tail ONLY: a hard rule at 1.5x
    # collapses yield and teaches the generator to contort options to hit a ratio.
    if ans in OPTION_KEYS and all(texts):
        lengths = {k: len(str(opts[k]).strip()) for k in OPTION_KEYS}
        correct_len = lengths[ans]
        others = [lengths[k] for k in OPTION_KEYS if k != ans]
        avg_other = sum(others) / len(others)
        longest_other = max(others)
        if correct_len > 2.2 * avg_other:
            hard.append(
                f"length giveaway: correct option is {correct_len / avg_other:.1f}x the "
                f"average distractor (>2.2x)"
            )
        elif correct_len > LENGTH_GIVEAWAY_RATIO * avg_other:
            soft.append(
                f"possible length giveaway: correct option is "
                f"{correct_len / avg_other:.1f}x the average distractor "
                f"{SOFT_LENGTH_GIVEAWAY_RATIO}"
            )
        elif correct_len - longest_other >= 20:
            # The ratio rule misses this when options are short but the key still
            # towers over every one of them (e.g. 55ch vs 35/34/33: only 1.6x).
            # NOT assignment-caused and so never suppressed by #139: the ladder's
            # designed top gap is 10ch (easy) / 13ch (medium), nowhere near 20.
            soft.append(
                f"possible length giveaway: correct option is "
                f"{correct_len - longest_other}ch longer than every distractor (>=20ch)"
            )
        # The mirror defect: a conspicuously SHORT key is just as gameable.
        if avg_other > 0 and correct_len < REVERSE_TELL_RATIO * avg_other:
            soft.append(f"{SOFT_REVERSE_TELL}: correct option is much shorter")

    # Explanation should address the distractors (soft -- can't be exact).
    expl = _norm(q["explanation"])
    if len(expl) < 60:
        soft.append("explanation looks thin (<60 chars)")

    # Stem shouldn't just restate the PI verbatim (soft).
    if _norm(q["question"]) == _norm(q["performanceIndicator"]):
        soft.append("stem restates the performance indicator verbatim")

    # Pool questions are difficulty-tagged at authoring time (plan 03 section 3.2).
    if require_difficulty:
        diff = _norm(q.get("difficulty", ""))
        if diff not in DIFFICULTY_TIERS:
            hard.append(f"difficulty '{q.get('difficulty')}' is not one of easy/medium/hard")

    return hard, soft


# ----------------------------
# Assemble one set
# ----------------------------
def load_parts(paths: List[Path]) -> List[Dict]:
    items: List[Dict] = []
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [error] cannot read {p.name}: {e}")
            continue
        if not isinstance(data, list):
            print(f"  [error] {p.name} is not a JSON array; skipping")
            continue
        print(f"  loaded {len(data):>3} question(s) from {p.name}")
        items.extend(data)
    return items


def build_set(
    cluster: str, level: str, raw: List[Dict], set_num: int = 1,
    *, pool: bool = False, seed_hashes: Optional[set] = None,
    seed_stems: Optional[Dict[str, List[Dict]]] = None,
) -> Tuple[List[Dict], Dict]:
    """Validate, dedup, id, and return (questions, report) for one set.

    ``set_num`` distinguishes multiple independent sets for the same
    cluster x level (e.g. two 100-question marketing/District exams); it is
    woven into every question id so ids stay unique across the whole bank.

    ``pool`` mode (plan 03 section 3.2) labels ids `<cluster>-<level>-pool-NNNN`,
    requires an authored `difficulty` per question, and tallies difficultyCounts.
    ``seed_hashes`` pre-loads content hashes to dedup against (e.g. the whole
    committed bank) so pool questions can't duplicate an existing set;
    ``seed_stems`` does the same options-blind (issue #34), and is what catches a
    re-authored stem wearing a fresh set of distractors.
    """
    prefix = CLUSTER_PREFIX.get(cluster, _slug(cluster)[:3])
    label = "pool" if pool else str(set_num)
    id_prefix = f"{prefix}-{level.lower()}-{label}-"

    # ID ASSIGNMENT IS BY IDENTITY, NOT BY POSITION (plan 10-4).
    #
    # This used to be `seq = len(kept) + 1`, which silently re-labels every
    # pre-existing item that sits after a GAP in the incoming id sequence. The
    # additive contract assemble_slice.py states -- "existing pool first so its
    # items keep ids 0001..N" -- holds only for a gap-free pool, and
    # finance-district is not one: the issue-34 stem-dedup collapse removed 10
    # items in place (780 -> 770), leaving holes at 0372, 0376, 0378-0383. On the
    # first additive assemble after that, 399 committed items shifted id and
    # `verify_bank --additive` failed with a wall of "changed beyond difficulty".
    #
    # That is not a cosmetic renumber. Question ids are the join key for the
    # frontend progress log: every Attempt stores one, and /review re-hydrates
    # missed questions by id (lib/progress/resolver.ts). Re-pointing an id at a
    # different question silently rewrites what a student got wrong.
    #
    # So: an item arriving WITH an id for this file keeps it, and newly authored
    # items take the lowest unused numbers above the current maximum. Gaps stay
    # gaps -- they are cheaper than a renumber, and nothing depends on density.
    used_nums: set = set()
    for q in raw:
        qid = str(q.get("id") or "")
        if qid.startswith(id_prefix) and qid[len(id_prefix):].isdigit():
            used_nums.add(int(qid[len(id_prefix):]))
    next_num = max(used_nums) + 1 if used_nums else 1

    def assign_id(q: Dict) -> str:
        """This item's id: preserved if it already has one for this file, else fresh."""
        nonlocal next_num
        qid = str(q.get("id") or "")
        if qid.startswith(id_prefix) and qid[len(id_prefix):].isdigit():
            return qid
        while next_num in used_nums:
            next_num += 1
        used_nums.add(next_num)
        return f"{id_prefix}{next_num:04d}"

    seen_hashes: set = set(seed_hashes or ())
    seen_stems: Dict[str, List[Dict]] = {h: list(v) for h, v in (seed_stems or {}).items()}
    kept: List[Dict] = []
    dropped: List[Dict] = []
    soft_flags: List[Dict] = []
    letter_counts = {k: 0 for k in OPTION_KEYS}
    area_counts: Dict[str, int] = {}
    difficulty_counts = {t: 0 for t in DIFFICULTY_TIERS}

    for i, q in enumerate(raw):
        hard, soft = check_question(q, require_difficulty=pool)
        if hard:
            dropped.append({"index": i, "reasons": hard, "question": q.get("question", "")[:80]})
            continue

        h = content_hash(q)
        if h in seen_hashes:
            reason = "duplicate of an existing bank question" if pool else "duplicate content hash"
            dropped.append({"index": i, "reasons": [reason], "question": q.get("question", "")[:80]})
            continue

        # Stem-only dedup (issue #34). Runs after the content hash so an exact
        # duplicate still reports as one; what lands here is the subtler case --
        # same stem, reworded options -- which the content hash cannot see.
        sh = stem_hash(q)
        twins = seen_stems.get(sh, [])
        same_slice = [t for t in twins if t["cluster"] == cluster and t["level"] == level]
        if same_slice:
            # Both copies would sit in one candidate pool, so one sitting can draw
            # both. Dropping the newcomer IS the difficulty reconciliation: the tag
            # that survives is the one graded against the options that survive.
            t = same_slice[0]
            reason = f"duplicate stem of {t['id']} (options differ; stem-only dedup)"
            mine = _norm(q.get("difficulty", "")) or "untagged"
            if t.get("difficulty") and mine != t["difficulty"]:
                reason += f" -- conflicting difficulty '{mine}' vs kept '{t['difficulty']}'"
            dropped.append({"index": i, "reasons": [reason], "question": q.get("question", "")[:80]})
            continue
        if twins:
            # Another cluster x level already uses this stem. Never co-servable, so
            # it is reported, not dropped (see load_bank_stems).
            others = ", ".join(f"{t['id']} ({t['cluster']}/{t['level']})" for t in twins[:3])
            soft.append(f"stem already used in another cluster x level: {others}")
        seen_hashes.add(h)
        qid = assign_id(q)  # exactly once per kept item -- it consumes a number
        seen_stems.setdefault(sh, []).append({
            "id": qid,
            "cluster": cluster,
            "level": level,
            "difficulty": _norm(q.get("difficulty", "")) or None,
        })

        if soft:
            soft_flags.append({"index": i, "warnings": soft, "question": q.get("question", "")[:80]})

        ans = str(q["answer"]).strip().upper()
        letter_counts[ans] += 1
        area = q["instructionalArea"]
        area_counts[area] = area_counts.get(area, 0) + 1

        obj = {
            "id": qid,
            "cluster": cluster,
            "level": level,
            "instructionalArea": area,
            "performanceIndicator": q["performanceIndicator"],
            "question": q["question"],
            "options": {k: str(q["options"][k]).strip() for k in OPTION_KEYS},
            "answer": ans,
            "explanation": q["explanation"],
        }
        diff = _norm(q.get("difficulty", ""))
        if diff in DIFFICULTY_TIERS:
            difficulty_counts[diff] += 1
            obj["difficulty"] = diff  # placed just before `verified`, matching tag_difficulty
        obj["verified"] = True
        kept.append(obj)

    report = {
        "kept": len(kept),
        "dropped": dropped,
        "soft_flags": soft_flags,
        "letterDistribution": letter_counts,
        "areaCounts": dict(sorted(area_counts.items(), key=lambda kv: -kv[1])),
        "difficultyCounts": difficulty_counts,
    }
    return kept, report


# ----------------------------
# Manifest
# ----------------------------
def update_manifest(
    cluster: str, level: str, questions: List[Dict], report: Dict,
    set_num: int, file_name: str, *, pool: bool = False,
) -> None:
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    else:
        manifest = {"version": BANK_VERSION, "sets": {}}

    manifest.setdefault("version", BANK_VERSION)
    section = "pools" if pool else "sets"
    manifest.setdefault(section, {})
    if pool:
        # Pools are a v2 manifest feature; don't let the version regress.
        manifest["version"] = max(manifest.get("version", BANK_VERSION), MANIFEST_VERSION_V2)
        key = f"{cluster}-{level.lower()}-pool"
        entry = {
            "cluster": cluster,
            "level": level,
            "file": file_name,
            "count": len(questions),
            "areaCounts": report["areaCounts"],
            "letterDistribution": report["letterDistribution"],
            "difficultyCounts": report["difficultyCounts"],
        }
    else:
        key = f"{cluster}-{level.lower()}-{set_num}"
        entry = {
            "cluster": cluster,
            "level": level,
            "set": set_num,
            "file": file_name,
            "count": len(questions),
            "areaCounts": report["areaCounts"],
            "letterDistribution": report["letterDistribution"],
        }
    manifest[section][key] = entry
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def write_set(
    cluster: str, level: str, questions: List[Dict], set_num: int, *, pool: bool = False,
) -> Path:
    out_dir = BANK_DIR / cluster
    out_dir.mkdir(parents=True, exist_ok=True)
    name = (
        f"{cluster}-{level.lower()}-pool.json" if pool
        else f"{cluster}-{level.lower()}-{set_num}.json"
    )
    out_path = out_dir / name
    out_path.write_text(
        json.dumps(questions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return out_path


# ----------------------------
# CLI
# ----------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Assemble + validate a question-bank set.")
    ap.add_argument("cluster")
    ap.add_argument("level")
    ap.add_argument("parts", nargs="*", help="JSON part files")
    ap.add_argument("--parts-dir", help="directory of JSON part files")
    ap.add_argument(
        "--set", type=int, default=1, dest="set_num",
        help="set number for multiple sets of the same cluster x level (default 1)",
    )
    ap.add_argument(
        "--pool", action="store_true",
        help="assemble the original pool file (difficulty required, deduped against "
             "the whole bank, written to manifest 'pools'); ignores --set",
    )
    args = ap.parse_args()

    level = args.level.capitalize() if args.level.lower() != "icdc" else "ICDC"
    if level not in VALID_LEVELS:
        sys.exit(f"level must be one of {sorted(VALID_LEVELS)}; got '{args.level}'")

    paths: List[Path] = [Path(p) for p in args.parts]
    if args.parts_dir:
        paths += sorted(Path(args.parts_dir).glob("*.json"))
    if not paths:
        sys.exit("no part files given (positional paths or --parts-dir)")

    target = "pool" if args.pool else f"set {args.set_num}"
    print(
        f"\nAssembling {args.cluster} / {level} ({target}) "
        f"from {len(paths)} part file(s)..."
    )
    raw = load_parts(paths)
    print(f"  {len(raw)} raw question(s) collected")

    # Pool originality: dedup against every committed question except this pool's
    # own prior output (so re-runs are idempotent). Both keys are seeded -- the
    # content hash for exact re-serves, the stem hash for re-authored stems.
    seed_hashes: Optional[set] = None
    seed_stems: Optional[Dict[str, List[Dict]]] = None
    if args.pool:
        own = BANK_DIR / args.cluster / f"{args.cluster}-{level.lower()}-pool.json"
        seed_hashes = load_bank_hashes(exclude=own)
        seed_stems = load_bank_stems(exclude=own)
        print(f"  deduping against {len(seed_hashes)} existing bank question(s) "
              f"({len(seed_stems)} distinct stem(s))")
    print()

    questions, report = build_set(
        args.cluster, level, raw, args.set_num, pool=args.pool,
        seed_hashes=seed_hashes, seed_stems=seed_stems,
    )

    out_path = write_set(args.cluster, level, questions, args.set_num, pool=args.pool)
    update_manifest(
        args.cluster, level, questions, report, args.set_num, out_path.name, pool=args.pool
    )

    print(f"  kept:    {report['kept']}")
    print(f"  dropped: {len(report['dropped'])}")
    if report["dropped"]:
        for d in report["dropped"]:
            print(f"    - #{d['index']}: {', '.join(d['reasons'])} :: {d['question']}")
    print(f"  soft flags: {len(report['soft_flags'])}")
    for s in report["soft_flags"]:
        print(f"    ~ #{s['index']}: {', '.join(s['warnings'])} :: {s['question']}")
    if args.pool:
        dc = report["difficultyCounts"]
        print(f"\n  difficultyCounts: easy {dc['easy']} · medium {dc['medium']} · hard {dc['hard']}")
    print(f"\n  letter distribution: {report['letterDistribution']}")
    print(f"  areas covered ({len(report['areaCounts'])}):")
    for area, n in report["areaCounts"].items():
        print(f"       {n:>3}  {area}")
    print(f"\n  wrote {out_path.relative_to(REPO_ROOT)}")
    print(f"  updated {MANIFEST_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
