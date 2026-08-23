"""Build payloads for, and apply, the distractor-length repair (plan 07 §2.2 / §3).

Sibling to tag_difficulty.py: the *judgment* (what should this distractor say?)
is made by Sonnet subagents reading `src/prompts/repair_distractors.txt`; this
script is the deterministic payload builder and applier. No model is called here.

The defect is measured by audit_tells.py: the key is the longest option 66% of
the time bank-wide, so a student who reads no stems scores 64%. The repair
lengthens the three distractors toward the key's length. It never touches the
key -- plan 07 §2.2 ("lengthen distractors, never trim the key"), because
trimming damages the one option that must stay correct and precise.

WHAT THIS ENFORCES (plan 07 §3's invariant, and §9's acceptance of it):
    may change:  the three distractors, `explanation`
    frozen:      `id`, `question`, `answer`, `performanceIndicator`,
                 `instructionalArea`, `cluster`, `level`, `difficulty`, and
                 `options[answer]` -- the correct option, byte-identical.

`difficulty` is frozen here even though §3's invariant permits it to differ:
that movement is §4's job, with an independent tagger on tag-stripped payloads.
An author guessing at it during the repair is exactly the leaked-tag failure
plan 04 §3 calls the single most important methodological rule.

The applier VALIDATES EVERY PART BEFORE WRITING ANYTHING (plan 07 §13). A
partial apply cannot corrupt a file: either all parts pass and the file is
written once, or nothing is written and the run exits non-zero.

THE THREE HARD GATES (plan 07 §3.1). All were warnings during §2's pilot, when
they were the method under test and failing the run would have hidden the very
number the pilot existed to read. §2 is spent; they are the production controls
now, and a control that only warns is not a control (§1.1):

    1. RULE 4. Any distractor the repair CHANGED must be free of absolute
       qualifiers. A distractor left byte-identical is a pre-existing defect
       and not this pass's to answer for.
    2. EXPLANATION FRESHNESS, in its trivial form: if a distractor moved, the
       explanation may not be byte-identical. The pilot left 10 of 77 stale,
       which is ~300 at §3's scale.
    3. THE ASSIGNED RANK. The key must sit at `key_length_rank`, with no
       distractor tied at exactly key_length. Pilot compliance was 77/77, so
       this costs approximately nothing and closes the path where it does not.

WHAT GATE 2 DOES NOT DO, AND WHY IT IS NOT ENOUGH ON ITS OWN. It binds
"the explanation CHANGED", not "the explanation is TRUE" -- no script here can
reach the second, and an agent can satisfy this one with a cosmetic edit. That
would trade ~300 visibly stale explanations for some smaller number of
invisibly false ones, which is the whack-a-mole §11 says to expect from every
control this plan adds. The gate is therefore paired with a sampled read of the
slice gate's explanations at the base rate (§13) to measure what it produced.
Do not read a green run here as evidence the explanations are true.

A failing part does not end the run: `--reject` writes the failed items back out
as a fresh payload carrying their violations, so a second agent redoes only
those and the parts merge back through the same --check/--apply path. That is
rejection sampling (plan 07 §2.1's option B) at the part level, and it is what
makes the gate hard rather than merely loud.

Unlike tag_difficulty.py this never touches manifest.json, and so does not race:
a repair changes no field the manifest records (count, areaCounts,
letterDistribution, difficultyCounts are all invariant under it).

Payload out (one item per flagged question):
    { "id", "performanceIndicator", "question", "answer",
      "key", "key_length", "key_length_rank", "distractors_longer_than_key",
      "distractors_shorter_than_key", "margin", "max_top_gap",
      "distractor_targets": [L1, L2, L3],
      "distractors": { "A": {"text", "length"}, ... }, "explanation" }
  `max_top_gap` + `distractor_targets` carry GATE 4; `distractor_targets` is the
  midpoint of the rank+cap window, so an agent writing to it satisfies both
  without deriving either. The six banned words are NOT emitted per item -- they
  are identical everywhere and live in repair_distractors.txt.
  A reject payload adds "violations": [...] and is otherwise the same shape, so
  the repair prompt reads it without knowing which round it is in.

Part in (what the subagent emits; either form accepted):
    [ { "id": ..., "options": {"A","B","C","D"}, "explanation": ... } ]
    { "repairs": [ ... ] }

TWO SELECTORS (plan 07 §3b). --build-payload defaults to selecting on the MARGIN
(key_len - longest_distractor), which is the right work list for an UNREPAIRED
file. It cannot see an already-repaired one: once the key is no longer the
longest option the margin goes negative while the top gap -- the quantity the
"pick the conspicuously longest option" strategy actually reads -- stays large.
--min-top-gap selects on that instead, and --freeze-rank pins the rank the item
already holds so a length edit cannot quietly break it. See build_payload().

Usage:
    python repair_options.py <file.json> --build-payload payload.json
    # already-repaired file: select on the gap, keep the rank it already passed
    python repair_options.py <file.json> --build-payload payload.json \
                             --min-top-gap 20 --freeze-rank
    python repair_options.py <file.json> --parts dir/ --payload payload.json --check
    python repair_options.py <file.json> --parts dir/ --payload payload.json --check \
                             --reject round2.json
    python repair_options.py <file.json> --parts dir/ --payload payload.json --apply
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bank_paths import BANK_DIR  # noqa: E402  the ONE bank path (#203)

OPTION_KEYS = ("A", "B", "C", "D")

# Plan 05 §5a's decisive band -- the work list audit_tells.py --flag emits.
DEFAULT_MIN_MARGIN = 20
# Assigning the rank is reproducible or it is not a method (plan 05 §4's seed).
DEFAULT_SEED = 505

# Ranks are ASSIGNED, balanced 25/25/25/25, exactly as the answer letter is.
#
# Plan 07 §2.2 specified the target as a distance -- "bring every distractor
# within 10ch of it". The pilot honored that 100% (231/231 distractors in band)
# and the tell barely moved: 78% of distractors landed SHORTER than the key,
# piling up at the allowed edge, mean +3.8ch, and the repaired items still
# measured 66.2% key-is-longest against a 29.2% null.
#
# The reason is structural, not an authoring failure. `key is longest` measures
# ORDER; a distance band constrains MAGNITUDE and leaves the SIGN free, and the
# model spends its slack the same way every time -- key longest by a hair. A
# constraint has to bind the quantity the metric reads.
#
# Rank binds it directly: with the key's length-rank assigned uniformly,
# key-is-longest is 25% BY CONSTRUCTION, and so is the mirror (key shortest),
# which is why this does not just trade one tell for the other (§11).
# It is also more lenient than the band it replaces -- no distance floor, so a
# distractor may be much shorter than a long key rather than padded up to it.
RANKS = (1, 2, 3, 4)

# authoring.txt rule 4's list, verbatim -- and it stays verbatim. Elaborating it
# is how you change it (plan 07 §13), and holding the list fixed is what keeps
# this pass's before/after gap comparable to the number the pilot measured.
#
# A distractor that is wrong ONLY because of an absolute is eliminable without
# domain knowledge -- the same class of defect as the length tell, in a
# dimension audit_tells.py cannot see.
#
# This is here because the rank pilot injected it. Making a distractor LONGER
# than a frozen key while keeping it WRONG has an easy path -- append a
# justification clause and make the clause absolute -- and the pilot took it:
# the key/distractor gap widened from +16.9pp to +21.2pp over 231 distractors.
# The keys are frozen, so every point of that came from the new distractors.
# Optimising one metric invites the next defect (plan 07 §11's whack-a-mole);
# a repair pass that fixes length and quietly installs rule 4 has not helped.
#
# THE GATE BINDS EVERY DISTRACTOR THE REPAIR CHANGED, not only the ones that
# "gained" an absolute (owner, 2026-07-14). 955 of the 6,864 distractors in §3's
# scope already carry one, and this pass rewrites distractors wholesale -- so
# "inherited" is a fiction: an agent can replace a distractor's content entirely,
# keep the word, and a clean-before/absolute-after test reads it as pre-existing
# and passes it. Changed-must-be-clean has no such hole, is simpler to state, and
# costs the author nothing it was not already doing.
ABSOLUTE_QUALIFIERS = re.compile(
    r"\b(only|never|always|regardless|strictly|immediately)\b", re.IGNORECASE
)
# Emitted per item, as an assignment rather than a rule. Rule 12's lesson: the
# constraint is the thing in the payload, not the prose wrapped around it.
BANNED_QUALIFIERS = ("only", "never", "always", "regardless", "strictly", "immediately")

# GATE 4 -- the top-gap cap. The rank binds ORDER and leaves MAGNITUDE free, and
# the hospitality/ICDC slice measured what that costs: of 48 rank-1 items, 17
# kept a key >30ch clear of every distractor (up to 72ch), and "pick the
# conspicuously longest option, else abstain" scored 17/26 = 65% against a 25%
# null. Every one of those hits was a rank-1 item -- ranks 2-4 contribute zero by
# construction, since a longer distractor sits above the key.
#
# The variance was BETWEEN AGENTS, not in the method: three of five agents closed
# the margin unasked (median 8-21ch) and two did not (median 33-47ch). Both were
# obeying the prompt, which says "there is NO distance target". So the fix is the
# design, not more n (§13) -- and it is the pairing authoring.txt rule 12 already
# has: a BAND *and* a RANK, the combination that measured 25.0% in §2's Arm A.
# repair_distractors.txt assigned rank alone.
#
# The cap binds the exact quantity the strategy reads: with lengths sorted
# L1 >= L2 >= L3 >= L4, require L1 - L2 <= cap. Capping the TOP gap kills the
# strategy at every threshold in BOTH directions -- a conspicuous distractor
# (the anti-tell) is blocked by the same rule as a conspicuous key, so this
# cannot trade the tell for its mirror.
#
# It is NOT the "within 10ch" distance target §1.1 disproved. That failed because
# distance ALONE leaves the sign free: 231/231 complied and 78% landed just short
# of the key, so the key stayed longest. Rank fixes the sign; the cap fixes the
# size. Neither works alone.
DEFAULT_MAX_TOP_GAP = 20

# Frozen by plan 07 §3's invariant. `options` is checked separately (only the
# key is frozen inside it); `explanation` is the other thing the pass may edit.
FROZEN_FIELDS = (
    "id", "question", "answer", "performanceIndicator",
    "instructionalArea", "cluster", "level", "difficulty",
)


def _load(path: Path) -> List[Dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        sys.exit(f"{path.name} is not a JSON array of questions")
    return data


def _margin(q: Dict) -> Optional[Tuple[int, int, str]]:
    """(margin, key_len, answer) for a well-formed question, else None.

    Mirrors audit_tells._measure's definition so the two agree on the work list.
    """
    opts = q.get("options") or {}
    ans = str(q.get("answer", "")).strip().upper()
    if ans not in OPTION_KEYS or not all(str(opts.get(k, "")).strip() for k in OPTION_KEYS):
        return None
    lengths = {k: len(str(opts[k]).strip()) for k in OPTION_KEYS}
    key_len = lengths[ans]
    runner_up = max(v for k, v in lengths.items() if k != ans)
    return key_len - runner_up, key_len, ans


def _assign_ranks(n: int, seed: int) -> List[int]:
    """n ranks, balanced 25/25/25/25, shuffled so rank does not track margin."""
    ranks = [RANKS[i % 4] for i in range(n)]
    random.Random(seed).shuffle(ranks)
    return ranks


def observed_rank(opts: Dict, ans: str) -> Tuple[int, int]:
    """(rank of the key by length, count of distractors tied with it).

    Rank 1 = the key is the longest. A distractor of EQUAL length is not longer,
    so it does not push the key's rank down -- but it does make the key "among
    the longest", which is what audit_tells.py counts. Ties are reported so the
    caller can flag them rather than have them silently pass as rank 1.
    """
    key_len = len(str(opts[ans]).strip())
    longer = sum(1 for k in OPTION_KEYS
                 if k != ans and len(str(opts[k]).strip()) > key_len)
    tied = sum(1 for k in OPTION_KEYS
               if k != ans and len(str(opts[k]).strip()) == key_len)
    return longer + 1, tied


def top_gap(opts: Dict) -> Tuple[int, str]:
    """(L1 - L2, the letter holding L1) -- what the magnitude strategy reads.

    "Pick the conspicuously longest option, else abstain" fires exactly when
    L1 - L2 > threshold, and it is right when L1 is the key. So this is the
    quantity to bind, and binding it is direction-agnostic: it blocks a
    conspicuous distractor for the same reason it blocks a conspicuous key.
    """
    lengths = sorted(((len(str(opts[k]).strip()), k) for k in OPTION_KEYS),
                     reverse=True)
    return lengths[0][0] - lengths[1][0], lengths[0][1]


def distractor_targets(key_len: int, rank: int, max_gap: int) -> List[int]:
    """Three concrete target lengths, longest first, that satisfy rank AND cap.

    Both constraints are pure arithmetic on key_length -- yet the payload used to
    emit only the rank and the cap and leave the agent to solve for the windows.
    Measured cost of that: agents' first drafts failed 25-60% of items on 1-6
    character misses, and every failure is a re-author + re-measure cycle. The one
    agent that derived these windows explicitly before drafting missed 5%.

    The targets sit mid-window, away from both edges, because the two rules bound
    each other: at rank 1 the longest distractor must be >= key-cap (or the key is
    conspicuous) AND < key (or the rank breaks), so overshooting trades one
    violation for the other. They are a starting point, not a constraint -- the
    gate reads the rank and the gap, never these numbers.
    """
    k, g = key_len, max_gap
    if rank == 1:      # key longest; top distractor must come up within g of it
        out = [k - g // 2, k - g - 20, k - g - 50]
    elif rank == 2:    # exactly one above the key, and it is L1 -> within g of key
        out = [k + g // 2, k - 20, k - 50]
    elif rank == 3:    # two above the key; the cap binds those two to each other
        out = [k + g + 5, k + g // 2, k - 30]
    else:              # rank 4 -- all three above; cap binds the top two
        out = [k + g + 10, k + g, k + 5]
    return [max(20, v) for v in out]


def build_payload(path: Path, min_margin: Optional[int], seed: int,
                  max_gap: int = DEFAULT_MAX_TOP_GAP,
                  min_top_gap: Optional[int] = None,
                  freeze_rank: bool = False) -> List[Dict]:
    """The flagged items, selected by MARGIN (default) or by TOP GAP.

    TWO SELECTORS, because margin cannot see the scope plan 07 §3b targets.
    `finance/ICDC` was repaired before GATE 4 existed, so its 88 cap-breaching
    items are ALREADY repaired: their margin is small, and for the 63 whose
    conspicuous option is a DISTRACTOR it is negative -- the key is not the
    longest option at all. That is not a tuning problem. It is arithmetic:

        the key holds L1  =>  top_gap == margin
        a distractor holds L1  =>  margin < 0, while top_gap may be anything

    So `margin >= N` and `top_gap > N` select disjoint halves of the defect
    whenever a distractor is the conspicuous one, and NO value of --min-margin
    reaches them. --min-top-gap selects on the quantity the magnitude strategy
    actually reads (top_gap), ignoring margin entirely, and sorts worst-gap-first.
    `margin` is still EMITTED either way -- repair_distractors.txt documents and
    reads the field, and dropping it would be a prompt change by the back door.

    freeze_rank pins `key_length_rank` to the rank the item ALREADY HOLDS
    (observed_rank) instead of a freshly shuffled assignment. For a re-repair of
    already-ranked items an assignment would be a silent scope explosion: these
    items came through §3's rank gate and passed, so a fresh 25/25/25/25 roll
    hands ~75% of them a rank they do not hold, turning a minimal length edit
    into a full re-repair -- and it would perturb a bank metric that already
    passes at 28.5% for no defect (§1.2, and §12: do not chase chance).

    Pinning is not the same as omitting: validate() SKIPS GATE 3 for any id
    absent from the payload, so an unpinned rank means a trim could sail past
    the key with nothing to say so. Pin it and the rank becomes a constraint the
    item already satisfies -- free, and it holds the length edit in place.
    """
    if (min_margin is None) == (min_top_gap is None):
        raise ValueError("build_payload needs exactly one of min_margin / min_top_gap")

    items = []
    gaps: List[int] = []
    for q in _load(path):
        m = _margin(q)
        if m is None:
            continue
        margin, key_len, ans = m
        opts = q["options"]
        # The well-formedness guard above (_margin -> None) is shared on purpose:
        # both selectors must agree on what a ratable item is.
        gap = top_gap(opts)[0]
        if min_top_gap is not None:
            # `>`, not `>=`: an item sitting exactly AT the cap already satisfies
            # GATE 4, so selecting it would be an edit with no defect behind it.
            if gap <= min_top_gap:
                continue
        elif margin < min_margin:
            continue
        gaps.append(gap)
        # `instructionalArea` and a per-item copy of `banned_qualifiers` used to
        # ride along here. The six words are byte-identical on every item and are
        # already stated in repair_distractors.txt, and the area is not used for
        # authoring -- together ~6.5% of the batch, paid once per item for nothing.
        items.append({
            "id": q.get("id"),
            "performanceIndicator": q.get("performanceIndicator"),
            "question": q.get("question"),
            "answer": ans,
            "key": opts[ans],
            "key_length": key_len,
            "margin": margin,
            "distractors": {
                k: {"text": opts[k], "length": len(str(opts[k]).strip())}
                for k in OPTION_KEYS if k != ans
            },
            "explanation": q.get("explanation"),
            "_answer_opts": opts,  # popped below; observed_rank needs the options
        })

    # Worst-first, by whichever quantity did the selecting.
    order = sorted(range(len(items)),
                   key=(lambda n: -gaps[n]) if min_top_gap is not None
                   else (lambda n: -items[n]["margin"]))
    items = [items[n] for n in order]

    if freeze_rank:
        ranks = [observed_rank(i["_answer_opts"], i["answer"])[0] for i in items]
    else:
        ranks = _assign_ranks(len(items), seed)

    for item, rank in zip(items, ranks):
        item.pop("_answer_opts")
        item["key_length_rank"] = rank
        item["distractors_longer_than_key"] = rank - 1
        item["distractors_shorter_than_key"] = 4 - rank
        item["max_top_gap"] = max_gap
        item["distractor_targets"] = distractor_targets(item["key_length"], rank, max_gap)
    return items


def _load_parts(paths: List[Path]) -> Dict[str, Dict]:
    """Merge repair parts into one {id -> repair} map. Duplicate ids are fatal."""
    repairs: Dict[str, Dict] = {}
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            sys.exit(f"  [error] cannot read {p.name}: {e}")
        if isinstance(data, dict) and "repairs" in data:
            data = data["repairs"]
        if not isinstance(data, list):
            sys.exit(f"  [error] {p.name} is not a repair list")
        n = 0
        for entry in data:
            if not isinstance(entry, dict):
                continue
            qid = entry.get("id")
            if not qid:
                sys.exit(f"  [error] {p.name}: entry with no id")
            if qid in repairs:
                sys.exit(f"  [error] {p.name}: duplicate repair for {qid}")
            repairs[qid] = entry
            n += 1
        print(f"  loaded {n:>3} repair(s) from {p.name}")
    return repairs


def validate(
    questions: List[Dict],
    repairs: Dict[str, Dict],
    payload: Optional[List[Dict]] = None,
) -> Tuple[List[Tuple[Optional[str], str]], List[Tuple[Optional[str], str]]]:
    """((id, error)..., (id, warning)...). Errors block the write.

    `payload` is the item list these parts answer. It carries the assigned rank,
    so without it the rank gate cannot run at all -- which is why --apply
    requires it rather than quietly skipping the control.

    Errors are the two hard gates (rank, rule 4) plus §3's invariant. Warnings
    are the things no script can adjudicate: a stale explanation is caught only
    in its trivial form, and whether a rewritten one is TRUE is beyond this
    check entirely (plan 07 §9).
    """
    errors: List[Tuple[Optional[str], str]] = []
    warnings: List[Tuple[Optional[str], str]] = []
    by_id = {q.get("id"): q for q in questions}
    assigned = {i["id"]: i["key_length_rank"]
                for i in (payload or []) if "key_length_rank" in i}
    # Absent from a pre-cap payload, in which case GATE 4 stays silent for that
    # item rather than inventing a constraint the agent was never given.
    gap_cap = {i["id"]: i["max_top_gap"]
               for i in (payload or []) if "max_top_gap" in i}

    for qid in repairs:
        if qid not in by_id:
            errors.append((qid, "not in this file (foreign id)"))

    for qid, r in repairs.items():
        q = by_id.get(qid)
        if q is None:
            continue

        # The frozen scalars. An agent that rewrote the stem invalidates the run.
        for f in FROZEN_FIELDS:
            if f in r and r[f] != q.get(f):
                errors.append((qid, f"`{f}` was modified (frozen by §3's invariant)"))

        opts = r.get("options")
        if not isinstance(opts, dict):
            errors.append((qid, "no `options` object"))
            continue
        if set(opts) != set(OPTION_KEYS):
            errors.append((qid, f"options keys are {sorted(opts)}, want A-D"))
            continue
        if any(not str(opts[k]).strip() for k in OPTION_KEYS):
            errors.append((qid, "an option is empty"))
            continue

        ans = str(q.get("answer", "")).strip().upper()
        committed_key = str(q["options"][ans])
        # The one that matters most: an agent "fixing" the tell by mangling the key.
        if str(opts[ans]) != committed_key:
            errors.append((qid, f"options[{ans}] -- THE KEY -- was modified. "
                                f"Frozen byte-for-byte (§3). Trimming the key is "
                                f"not a repair."))

        moved = [k for k in OPTION_KEYS
                 if k != ans and str(opts[k]) != str(q["options"].get(k, ""))]

        # GATE 1 -- rule 4, over every distractor this repair CHANGED.
        for k in moved:
            hit = ABSOLUTE_QUALIFIERS.search(str(opts[k]))
            if hit:
                errors.append((qid, f"option {k} was rewritten and uses the absolute "
                                    f"\"{hit.group(0)}\" -- authoring.txt rule 4"))

        # GATE 2 -- the explanation moved with its distractors.
        expl = r.get("explanation")
        if not isinstance(expl, str) or not expl.strip():
            errors.append((qid, "no `explanation` (it is rewritten with the options)"))
        elif moved and expl.strip() == str(q.get("explanation", "")).strip():
            errors.append((qid, f"option(s) {', '.join(moved)} were rewritten but the "
                                f"explanation is byte-identical -- it now argues against "
                                f"option text that no longer exists (§9)"))

        # GATE 3 -- the assigned rank, the control the whole pass rests on.
        if qid in assigned:
            want = assigned[qid]
            got, tied = observed_rank(opts, ans)
            if got != want:
                errors.append((qid, f"key ranks {got} by length, assigned {want}"))
            elif tied:
                # Rank honored on strict comparison, but a tie still makes the key
                # "among the longest" for audit_tells.py. Only bites at rank 1.
                errors.append((qid, f"key ranks {got} as assigned, but {tied} "
                                    f"distractor(s) tie it at exactly {len(committed_key.strip())}ch"))

        # GATE 4 -- the top-gap cap. The rank leaves magnitude free; this binds it.
        if qid in gap_cap:
            cap = gap_cap[qid]
            gap, holder = top_gap(opts)
            if gap > cap:
                whose = "THE KEY" if holder == ans else f"distractor {holder}"
                errors.append((qid, f"option {holder} ({whose}) stands {gap}ch clear "
                                    f"of the next longest -- cap is {cap}ch. A "
                                    f"conspicuously longest option is pickable "
                                    f"without reading the stem, whichever option "
                                    f"holds it (§3 magnitude)"))

    # Not an error: a part legitimately covers a slice of the payload. They are
    # still work outstanding, so --reject collects them for the next round.
    for qid in (i["id"] for i in (payload or [])):
        if qid not in repairs:
            warnings.append((qid, "in the payload, but no repair was returned"))

    return errors, warnings


def build_reject(
    payload: List[Dict],
    errors: List[Tuple[Optional[str], str]],
    missing: List[str],
) -> List[Dict]:
    """Round 2's payload: every item that still needs an agent, and why.

    Same shape as --build-payload's output plus `violations`, so the repair
    prompt reads it unchanged and does not need to know which round it is in.
    """
    by_id = {i["id"]: i for i in payload}
    viol: Dict[str, List[str]] = {}
    for qid, msg in errors:
        if qid in by_id:
            viol.setdefault(qid, []).append(msg)
    for qid in missing:
        viol.setdefault(qid, []).append("no repair was returned for this item")
    # Payload order is worst-margin-first; keep it.
    return [{**by_id[qid], "violations": viol[qid]} for qid in by_id if qid in viol]


def apply_repairs(path: Path, repairs: Dict[str, Dict]) -> Dict:
    """Write options+explanation through, preserving field order. Caller validates first."""
    questions = _load(path)
    out = []
    n = 0
    for q in questions:
        r = repairs.get(q.get("id"))
        if r is None:
            out.append(q)
            continue
        merged = dict(q)  # preserves key order; only the two fields are replaced
        merged["options"] = {k: r["options"][k] for k in OPTION_KEYS}
        merged["explanation"] = r["explanation"]
        out.append(merged)
        n += 1
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"applied": n, "total": len(questions)}


def _resolve(target: str) -> Path:
    p = Path(target)
    if not p.exists():
        matches = sorted(BANK_DIR.glob(f"*/{target}"))
        if len(matches) == 1:
            return matches[0]
        if not matches:
            sys.exit(f"no such question file: {target}")
        sys.exit(f"ambiguous: {target} matches {[str(m) for m in matches]}")
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description="Build/apply the distractor-length repair.")
    ap.add_argument("file", help="question-bank file (path, or bare name e.g. pbm-association-1.json)")
    ap.add_argument("--build-payload", metavar="OUT", help="write the flagged items to OUT as JSON")
    ap.add_argument("--parts", metavar="DIR_OR_FILE", nargs="*", default=[],
                    help="repair part file(s) or a directory of them")
    ap.add_argument("--apply", action="store_true", help="write the repairs (validates first)")
    ap.add_argument("--check", action="store_true", help="validate parts and stop")
    ap.add_argument("--payload", metavar="PATH",
                    help="the payload these parts answer; carries the assigned rank, "
                         "so --apply requires it")
    ap.add_argument("--reject", metavar="OUT",
                    help="write the items that failed the gate (and any the parts "
                         "missed) to OUT as a fresh payload for the next round")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"rank assignment seed (default {DEFAULT_SEED})")
    # Mutually exclusive, and argparse refuses rather than silently picking one.
    # Neither carries an argparse default: the two selectors must be
    # distinguishable from "not given", or --min-margin's default would look like
    # an explicit request on every --min-top-gap run. DEFAULT_MIN_MARGIN is
    # applied below, only when no selector was named at all.
    sel = ap.add_mutually_exclusive_group()
    sel.add_argument("--min-margin", type=int, default=None,
                     help=f"--build-payload includes margins >= this (default {DEFAULT_MIN_MARGIN})")
    sel.add_argument("--min-top-gap", type=int, default=None, metavar="N",
                     help="select on the TOP GAP (L1-L2 > N) instead of the margin, "
                          "ignoring margin entirely. The selector for already-repaired "
                          "items, whose conspicuous option may be a DISTRACTOR -- "
                          "margin is negative there and no --min-margin reaches them "
                          "(plan 07 §3b).")
    ap.add_argument("--freeze-rank", action="store_true",
                    help="emit key_length_rank = the rank the key ALREADY holds, "
                         "not a freshly shuffled assignment. Use when repairing "
                         "items that already passed the rank gate: it pins the rank "
                         "a length edit must not break, instead of re-rolling it.")
    ap.add_argument("--max-top-gap", type=int, default=DEFAULT_MAX_TOP_GAP,
                    help=f"the longest option may not exceed the second-longest by "
                         f"more than this (default {DEFAULT_MAX_TOP_GAP}). Binds "
                         f"MAGNITUDE; the rank binds ORDER. Emitted per item.")
    args = ap.parse_args()

    path = _resolve(args.file)

    if args.build_payload:
        out = Path(args.build_payload)
        try:
            out.resolve().relative_to(BANK_DIR)
        except ValueError:
            pass
        else:
            sys.exit(f"  refusing to write the payload inside the bank: {out}")
        # Only default when NEITHER selector was named -- see the group above.
        min_margin = args.min_margin
        if min_margin is None and args.min_top_gap is None:
            min_margin = DEFAULT_MIN_MARGIN
        items = build_payload(path, min_margin, args.seed, args.max_top_gap,
                              min_top_gap=args.min_top_gap, freeze_rank=args.freeze_rank)
        out.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        total = len(_load(path))
        crit = (f"top gap > {args.min_top_gap}" if args.min_top_gap is not None
                else f"margin >= {min_margin}")
        print(f"\n  {len(items)} of {total} question(s) flagged ({crit}) in {path.name}")
        if items:
            dist = {r: sum(1 for i in items if i["key_length_rank"] == r) for r in RANKS}
            worst = items[0]
            lens = sorted([worst["key_length"]]
                          + [d["length"] for d in worst["distractors"].values()], reverse=True)
            if args.min_top_gap is not None:
                print(f"    worst gap {lens[0] - lens[1]}ch  ({worst['id']}, "
                      f"margin {worst['margin']}ch)")
            else:
                print(f"    worst margin {worst['margin']}ch  ({worst['id']})")
            if args.freeze_rank:
                # NOT "by construction" -- these ranks were MEASURED off the bank,
                # not assigned. Claiming construction here would report a control
                # that never ran (§1.2), and the whole point of --freeze-rank is
                # that it changes no rank at all.
                print(f"    key-length ranks, FROZEN as observed: {dist}")
                print(f"    => key-is-longest is {100 * dist[1] / len(items):.0f}% "
                      f"as measured; this pass does not move it")
            else:
                print(f"    assigned key-length ranks (seed {args.seed}): {dist}")
                print(f"    => key-is-longest is {100 * dist[1] / len(items):.0f}% by construction")
        print(f"  wrote {out}\n")
        return

    if not args.parts:
        sys.exit("nothing to do: pass --build-payload OUT, or --parts DIR --apply/--check")

    paths: List[Path] = []
    for p in (Path(x) for x in args.parts):
        paths.extend(sorted(p.glob("*.json")) if p.is_dir() else [p])
    if not paths:
        sys.exit("no part files found")

    repairs = _load_parts(paths)
    questions = _load(path)

    # Without the payload there is no assigned rank, so the rank gate cannot run.
    # Applying anyway would skip the control silently, which is the failure mode
    # this whole section exists to close (§1.1).
    if args.apply and not args.payload:
        sys.exit("  --apply requires --payload: the assigned rank lives there, and "
                 "it is a gate, not a report.")
    payload = json.loads(Path(args.payload).read_text(encoding="utf-8")) if args.payload else None

    errors, warnings = validate(questions, repairs, payload)
    missing = [i["id"] for i in (payload or []) if i["id"] not in repairs]

    def _show(rows: List[Tuple[Optional[str], str]], limit: int = 25) -> None:
        for qid, msg in rows[:limit]:
            print(f"    {qid}: {msg}" if qid else f"    {msg}")
        if len(rows) > limit:
            print(f"    ... and {len(rows) - limit} more")

    if warnings:
        print(f"\n  \033[33m{len(warnings)} warning(s)\033[0m (measurements, not blockers)")
        _show(warnings)

    if args.reject:
        if payload is None:
            sys.exit("  --reject requires --payload: the round-2 items are built from it.")
        out = Path(args.reject)
        rejects = build_reject(payload, errors, missing)
        out.write_text(json.dumps(rejects, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"\n  wrote {len(rejects)} item(s) needing another round -> {out}")

    if errors:
        failed = len({qid for qid, _ in errors if qid})
        print(f"\n  \033[31mFAIL\033[0m {len(errors)} violation(s) across {failed} item(s); "
              f"refusing to write {path.name}")
        _show(errors)
        if not args.reject:
            print("  re-run with --reject OUT.json to emit them for another round")
        print()
        sys.exit(1)

    # "four gates" only if the payload actually carried a cap -- GATE 4 is silent
    # on a pre-cap payload, and reporting it as run would be a lie of the exact
    # kind §1.2 is about.
    n_gates = "four" if any("max_top_gap" in i for i in (payload or [])) else "three"
    print(f"\n  \033[32mOK\033[0m {len(repairs)} repair(s) pass all {n_gates} gates and §3's invariant")

    if args.check or not args.apply:
        print("  --check: nothing written\n")
        return

    report = apply_repairs(path, repairs)
    print(f"  applied {report['applied']} of {report['total']} question(s) -> {path.name}")
    print(f"  now re-measure: audit_tells.py --path \"{path}\"\n")


if __name__ == "__main__":
    main()
