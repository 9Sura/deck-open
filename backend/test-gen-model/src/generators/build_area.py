"""Build one plan-10 authoring chunk's payload, straight from the PI deficit.

Third member of the payload-builder family. `author_pool.py` (easy/medium) and
`author_hard.py` (hard) both draw their PIs from `generate_test.allocate_questions`
-- an AREA allocator: it decides how many questions an instructional area gets and
then samples PIs inside it. Plan 10 is the inverse job. The PI is the primary key
of every row and the counts come from a measured per-(PI, tier) deficit, so there
is no draw anywhere: `pi_deficit.py` says this PI owes 2 medium, and this emits
exactly 2 medium rows for it. Using the area allocator here would re-scatter the
work across PIs and undo the entire point of the plan (§10-2 method note 1).

No model is called here.

    python pi_deficit.py finance ICDC --out DIR/wo.json
    python build_area.py DIR/wo.json --areas "Operations" --out DIR/ops.json
    python build_area.py DIR/wo.json --areas "Financial Analysis" --tiers hard \
        --out DIR/fa-hard.json          # the strong/blind-verify path, on its own

WHAT EACH ROW CARRIES, and why it is not just a PI + a tier:

  answer_letter          rule 10 -- ASSIGNED, never chosen by the author, balanced
                         A/B/C/D across the chunk.
  key_length_rank        rule 12(b) -- where the key sits when the four options are
                         sorted by length (1 = longest). Balanced 25/25/25/25.
                         RANKED PAYLOADS ONLY; --free-rank sends the bit below.
  key_may_be_longest     --free-rank's replacement for the rank: one bit, true on
                         --key-longest-rate of rows (default 25%%). False means at
                         least one distractor must be >= the key. Assigned, like the
                         letter, because a batch statistic the author is told not to
                         measure is a statistic nothing enforces -- §10-3 chunk 2 came
                         back at 71.3%% key-is-longest and paid 100.7k to repair it;
                         chunk 3, authored against this bit, came back at 27.7%% with
                         no repair agent at all.
  option_length_band     the length register all four options share.
  key_target_len   \\     §10-1 method note 3. Concrete per-option character counts,
  distractor_target_lens/ derived from band+rank so rule 12 holds BY CONSTRUCTION.
                         Emitting only the rank and leaving agents to solve for the
                         windows cost 25-60% first-draft failures on 1-6 character
                         misses (repair_options.distractor_targets' docstring
                         measured it); handing over the numbers made a 22-item batch
                         pass in 21 tool-calls instead of ~70-85.
  avoid                  compact signatures of what this PI ALREADY has at this
                         level -- a ~10-word stem gist + the key, never the full
                         question+options+explanation. Deep PIs accumulate many
                         stems and the full-text payload is the hidden token cost
                         ([[pool-expansion-tag-payload-scoping]]).
  route                  hard only: C1 chained computation / C2 two near-correct,
                         derived per row by author_hard.hard_route from the curated
                         PI pool. NOT rendered into the prompt and not gated (#175);
                         it is for the payload record and build_hard_verify's
                         stage-2 scoping, which need it TRUE rather than obeyed.

THE TARGET LENGTHS ARE COMPUTED HERE, NOT BORROWED. `repair_options.distractor_targets`
solves the mirror problem -- the key's length is already frozen and the distractors
move to meet it -- so its windows reach 70 characters below the key. That is wider
than every authoring band we use (medium is 50 wide, hard 30), so borrowing it would
emit targets outside the band it is supposed to satisfy. Authoring sets all four
lengths at once, so it can lay all four across the band at once: four evenly spaced
targets INSET FROM BOTH EDGES (see `_ladder`), the key taking the slot its rank
names. Band, rank, and the <=20ch top-gap cap then all hold by construction for
every band in DEFAULT_BANDS.
"""
import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

# Same-dir imports: this module lives beside the tools it composes.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from author_hard import (  # noqa: E402
    _balanced,
    hard_route,
    load_computational_pis,
    OPTION_KEYS,
    RANKS,
)
from author_pool import DEFAULT_BANDS  # noqa: E402
from build_question_bank import CLUSTER_PREFIX  # noqa: E402
from pi_deficit import TIERS, load_cluster_questions, slug  # noqa: E402

# author_pool covers easy/medium; author_hard's constant band covers hard.
BANDS = dict(DEFAULT_BANDS)
BANDS["hard"] = (60, 90)

DEFAULT_SEED = 505       # plan 05 §4's seed -- reproducible or it is not a method
MAX_TOP_GAP = 20         # repair_options.DEFAULT_MAX_TOP_GAP -- the cap rule 12 enforces
DEFAULT_AVOID_N = 8      # per PI; deep PIs would otherwise dominate the payload

# The no-information baseline: four options, one is longest by chance. Rule 12's
# real target, and audit_tells' bar (0.35) is this plus tolerance.
DEFAULT_KEY_LONGEST_RATE = 0.25
GIST_WORDS = 10

# THE C1/C2 ROUTE DERIVATION LIVES IN author_hard.hard_route AND IS IMPORTED, not
# copied. It used to be duplicated here with its own cluster allow-list in front of
# it, and the allow-list was #175's bug; one definition is what stops the two tools
# disagreeing about a row's route again.


# HOW FAR THE LADDER SITS INSIDE THE BAND, as a share of band width (#74).
#
# The ladder used to span the band edge to edge, which handed the top rung the
# number `hi` itself and the bottom rung `lo` itself: easy 15-55 -> [55, 42, 28, 15].
# The two interior rungs then carried ~13ch of margin in both directions while the
# two rungs that actually sit against a wall carried none, and the function exists
# to keep options inside the band.
#
# MEASURED over the plan-10 tails of the six closed hospitality/pbm pools (the pool
# rows past each level's pre-plan-10 size), authoring error is one-directional --
# options run LONG, effectively never short:
#
#     easy    9,980 options   6.9% over `hi`   0.2% under `lo`   median excess 8ch
#     medium  4,692 options   5.6% over `hi`   0.3% under `lo`   median excess 8ch
#
# So the margin is split 2:1 toward the ceiling, where the errors go, rather than
# evenly. The top rung drops 7ch on easy and 8ch on medium, and on the same
# measurement that recovers 47% / 53% of the over-`hi` options -- ASSUMING the miss
# is an offset from whatever number the author was handed, and that an over-`hi`
# option came from the top rung, which is close to true (rung 2 would have to run
# 13ch over to break the ceiling at all). It does not touch the tail: the p90 excess
# is 29ch and no rung placement helps a runaway option. This narrows the miss; it
# does not close it, and `check_authored`'s strict-band line is still the instrument
# that says how much is left.
#
# THE INSETS ARE ALSO WHY THE STEP IS band_width/4 AND NOT /3. That is the cost
# side: adjacent rungs sit 10ch apart on easy where they used to sit 13ch, so the
# targets are a slightly weaker signal for the rank/LONGEST= assignment. They were
# already inside each other's TARGET_TOLERANCE (8ch) before this change, and rank
# compliance is scored on the authored lengths rather than on the targets, so the
# assignment is unchanged in kind. Rung 3 does not move at these insets and the
# ladder's mean moves only band_width/24 (1.7ch on easy), so the length register
# the band names is preserved -- what changes is that no rung sits on an edge.
#
# NOT A FIX FOR SHORT HARD OPTIONS. #74 also reports plan-10 hard options under the
# 60ch floor, but those rows are term-identification items whose options are single
# noun phrases ("Embezzlement", 12ch) -- 7 rows carrying 27 of the 92 hard options
# measured, at a median 38ch below the floor. That is the hard band being wrong for
# that item shape, not a rung aimed at the wrong number, and no inset addresses it.
LADDER_INSET_TOP = 1 / 6.0      # of band width, taken off `hi`
LADDER_INSET_BOTTOM = 1 / 12.0  # of band width, added to `lo`


def _ladder(band) -> List[int]:
    """Four evenly spaced option-length targets inside `band`, longest first.

    Inset from both edges, asymmetrically -- see LADDER_INSET_TOP. easy 15-55 ->
    [48, 38, 28, 18]; medium 35-85 -> [77, 64, 52, 39]; hard 60-90 -> [85, 78, 70, 62].
    """
    lo, hi = band
    width = hi - lo
    top = hi - width * LADDER_INSET_TOP
    bottom = lo + width * LADDER_INSET_BOTTOM
    step = (top - bottom) / 3.0
    return [round(top - step * i) for i in range(4)]


def target_lengths(band, rank: int) -> Dict:
    """Four option lengths across `band`, the key taking slot `rank` (1 = longest).

    Returns {"key": int, "distractors": [int, int, int]} (distractors longest first).
    Evenly spaced, so the top gap is band_width/4 -- <=13 for every band we ship,
    comfortably under the cap rule 12 enforces.
    """
    ladder = _ladder(band)
    key = ladder[rank - 1]
    return {"key": key, "distractors": [v for i, v in enumerate(ladder) if i != rank - 1]}


def option_targets(band, longest_letter: str, seed: int) -> Dict[str, int]:
    """Per-LETTER character targets for a --free-rank row: {"A": 50, "B": 37, ...}.

    ADVISORY, NOT A NEW ASSIGNMENT. Nothing gates these. The row's only ordering
    assignment is still `longest_letter`, and this function is built to agree with
    it: the assigned letter gets the top rung, the other three are dealt the rest.

    WHY THIS EXISTS -- §10-10, and it is the largest single repair driver measured
    in plan-10. `option_length_band` alone gives the author a RANGE, and staying
    inside a range across four options is a measurement, which is exactly the kind
    of instruction this module already proved does not survive contact (see
    `longest_letters`: an assigned letter got ~100% compliance while the prose
    length rule got ~20%). §10-10's concept chunks came back with band violations
    on 25 of 50, 50 of 75 and 83 of 93 rows, every one reading `option C is 66ch,
    outside band 15-55` -- while letter compliance held at ~100% in the same
    batches. 821k of that slice's 2,438k concept phase was repair, and this class
    was most of it.

    Hard rows never had the problem, because they have carried explicit
    `key_target_len` + `distractor_target_lens` since §10-1. This closes the gap:
    writing to a number is not a measurement, it is a target.

    NOT the rank. `--free-rank` exists to drop the per-item key_length_rank, which
    cost an author 15-of-21 misses in chunk 7, and that stays dropped -- these are
    four suggested lengths consistent with the letter the author was already given,
    with no test attached and no failure mode for missing one.

    The rungs are INSET from the band edges rather than laid across it (#74): the
    top rung is the one every measured over-run comes from, and aiming it at `hi`
    exactly gave it nothing to be wrong with. See LADDER_INSET_TOP for the numbers.
    """
    ladder = _ladder(band)
    rest = [k for k in OPTION_KEYS if k != longest_letter]
    random.Random(seed).shuffle(rest)
    return dict([(longest_letter, ladder[0])] + list(zip(rest, ladder[1:])))


def _gist(text: str, words: int = GIST_WORDS) -> str:
    toks = re.sub(r"\s+", " ", str(text).strip()).split(" ")
    return " ".join(toks[:words]) + ("..." if len(toks) > words else "")


def build_avoid(cluster: str, level: str, scope: str, cap: int) -> Dict[str, List[Dict]]:
    """performanceIndicator -> compact signatures of its existing questions.

    Scoped to the same cluster x level by default: that is where a stem collision is
    a HARD drop at assembly (issue #34), so it is where avoiding one actually saves
    an authored question. `--avoid-scope cluster` widens it at a token cost.
    """
    by_pi: Dict[str, List[Dict]] = defaultdict(list)
    for q in load_cluster_questions(cluster):
        if scope == "level" and q.get("level") != level:
            continue
        pi = q.get("performanceIndicator")
        if not pi:
            continue
        opts = q.get("options") or {}
        by_pi[pi].append({
            "id": q.get("id", ""),
            "gist": _gist(q.get("question", "")),
            "key": _gist(str(opts.get(str(q.get("answer", "")).strip().upper(), "")), 8),
        })
    # Most recent first (ids are sequential within a file), then capped.
    for pi, items in by_pi.items():
        items.sort(key=lambda d: str(d["id"]), reverse=True)
        by_pi[pi] = [{k: v for k, v in d.items() if k != "id"} for d in items[:cap]]
    return by_pi


def key_longest_flags(n: int, rate: float, seed: int) -> List[bool]:
    """Which items MAY carry the longest key -- rule 12's BATCH statistic turned
    into a per-item assignment, for --free-rank payloads.

    MEASURED, §10-3 chunks 2 and 3. --free-rank dropped the per-item rank and left
    length as a batch property the author is explicitly told not to measure (rule
    12: "THAT NUMBER IS NOT YOUR JOB"). Nothing then operationalised it, and chunk
    2 came back with the key longest on 67 of 94 items (71.3%) -- a student who
    reads no stems and picks the longest option scores far above chance. The
    external repair cost 100.7k tokens, 39% of that chunk's budget.

    The fix is not to re-impose the rank (that is the tight constraint --free-rank
    exists to remove, and it cost an author 15-of-21 misses in chunk 7). It is one
    bit, assigned the same way the answer letter is -- and the letter had 100%
    compliance in the same batches that missed on length. Chunk 3 authored against
    this flag came back at 27.7% with NO repair agent.

    True  -> the key may be the longest option; write the four as they should be.
    False -> at least one distractor must be >= the key, given real substance
             (never filler, never by trimming the key -- plan 07 §2.2).
    """
    if not 0.0 <= rate <= 1.0:
        raise SystemExit(f"--key-longest-rate must be in [0,1]; got {rate}")
    k = round(n * rate)
    out = [True] * k + [False] * (n - k)
    random.Random(seed).shuffle(out)
    return out


def longest_letters(letters: List[str], klongest: List[bool],
                    seed: int) -> List[str]:
    """WHICH LETTER holds the longest option -- the same bit as
    `key_longest_flags`, restated as a positive per-item ASSIGNMENT.

    MEASURED, §10-2 chunks 3 and 4. `key_may_be_longest` is still a PROSE RULE:
    to honour "at least one distractor must be >= the key" the author has to
    count characters across four options and compare them -- and rule 12 spends
    a paragraph telling that same author NOT to measure lengths ("THAT NUMBER IS
    NOT YOUR JOB"). The brief asks for a measurement and forbids measuring.
    Chunks 3 and 4 were siblings -- identical payload shape (62 and 60 `false`
    rows), same brief, same model, launched together -- and split 74.4% vs 27.5%
    key-longest. Chunk 3 missed on 46 of 46 `false` rows: not partial drift, a
    rule that simply never engaged. The repair cost 239.3k.

    Summary 05 §3 measured the general form of this years earlier: same model,
    same run, an assigned answer LETTER got 50/50 compliance while the prose
    length rule got ~20% -- "and the agent reported it had verified compliance".
    Mechanical assignments work; prose rules do not.

    So express length the way rule 10 expresses the key: name the letter. The
    author writes option X to be the meatiest of the four BY CONSTRUCTION and
    never counts anything. `LONGEST == answer_letter` on `--key-longest-rate` of
    rows reproduces the same ~25% batch statistic the bit was aiming at, without
    asking anyone to measure it.
    """
    rng = random.Random(seed)
    out: List[str] = []
    for letter, klong in zip(letters, klongest):
        if klong:
            out.append(letter)
        else:
            out.append(rng.choice([k for k in OPTION_KEYS if k != letter]))
    return out


def build_chunk(workorder: Dict, areas: Optional[List[str]], tiers: List[str],
                seed: int, avoid_scope: str, avoid_cap: int,
                free_rank: bool = False,
                key_longest_rate: float = DEFAULT_KEY_LONGEST_RATE) -> List[Dict]:
    rows = workorder["rows"]
    cluster = workorder["meta"]["cluster"]

    if areas:
        keep = {slug(a) for a in areas}
        rows = [r for r in rows if slug(r["instructionalArea"]) in keep]
        missing = keep - {slug(r["instructionalArea"]) for r in rows}
        if missing:
            print(f"  note: no deficit rows for {sorted(missing)}", file=sys.stderr)
    if not rows:
        raise SystemExit("no deficit rows match this chunk — nothing to author")

    levels = {r["level"] for r in rows}
    if len(levels) > 1:
        raise SystemExit(f"chunk spans multiple levels {sorted(levels)}; "
                         "build one slice at a time")
    level = levels.pop()

    # One unit per question owed. The PI is the primary key -- no draw, no allocator.
    units: List[Dict] = []
    for r in sorted(rows, key=lambda r: (r["instructionalArea"], r["performanceIndicator"])):
        for tier in tiers:
            for _ in range(r[f"need_{tier}"]):
                units.append({"row": r, "tier": tier})
    if not units:
        raise SystemExit(f"no {'/'.join(tiers)} questions owed in this chunk")

    # Letters and ranks on independent seed streams so they correlate with neither
    # each other nor PI order (rule 10, rule 12(b)).
    letters = _balanced(OPTION_KEYS, len(units), seed + 11)
    ranks = _balanced(RANKS, len(units), seed + 12)
    # Own seed stream, so the length assignment correlates with neither the letter
    # nor the rank nor PI order.
    klongest = key_longest_flags(len(units), key_longest_rate, seed + 13)
    # The bit, restated as a named letter (see longest_letters()). Its own seed
    # stream again, so WHICH distractor carries the length is uncorrelated with
    # everything else.
    klongest_letters = longest_letters(letters, klongest, seed + 14)
    avoid = build_avoid(cluster, level, avoid_scope, avoid_cap)
    computational = load_computational_pis(cluster)

    prefix = CLUSTER_PREFIX.get(cluster, cluster[:3])
    lvl = level.lower()
    payload: List[Dict] = []
    for i, (u, letter, rank, klong, klongest_letter) in enumerate(
            zip(units, letters, ranks, klongest, klongest_letters), start=1):
        r, tier = u["row"], u["tier"]
        band = BANDS[tier]
        item = {
            # A CANDIDATE id: build_question_bank --pool renumbers on assembly. It
            # only has to be unique within this payload so a returned part can be
            # matched back to its assignment.
            "cand_id": f"{prefix}-{lvl}-pool-cand-{tier[:1]}{i:04d}",
            "cluster": cluster,
            "level": level,
            "instructionalArea": r["instructionalArea"],
            "performanceIndicator": r["performanceIndicator"],
            "difficulty": tier,
            "answer_letter": letter,
            "option_length_band": list(band),
        }
        if not free_rank:
            tl = target_lengths(band, rank)
            item["key_length_rank"] = rank
            item["key_target_len"] = tl["key"]
            item["distractor_target_lens"] = tl["distractors"]
            item["max_top_gap"] = MAX_TOP_GAP
        else:
            # The rank's replacement: one bit, not a per-option puzzle.
            # `key_may_be_longest` is kept for payloads/gates built before
            # `longest_letter` existed; `longest_letter` is the one the author
            # is actually given, because a named letter is an assignment and the
            # bit is a prose comparison (see longest_letters()).
            item["key_may_be_longest"] = klong
            item["longest_letter"] = klongest_letter
            # Advisory per-letter lengths, consistent with longest_letter and
            # gated by nothing -- see option_targets(). The band alone asks the
            # author to measure; this gives them numbers to write to instead.
            item["option_target_lens"] = option_targets(band, klongest_letter,
                                                        seed + 30 + i)
        if tier == "hard":
            # The curated PI pool decides where it exists, the area otherwise. One
            # definition, shared with author_hard.py, and no override -- see
            # hard_route() for why the cluster allow-list that used to sit in front
            # of it was #175.
            item["route"] = hard_route(cluster, r["instructionalArea"],
                                       r["performanceIndicator"], computational)
        sigs = avoid.get(r["performanceIndicator"], [])
        if sigs:
            item["avoid"] = sigs
        payload.append(item)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build one plan-10 chunk's authoring payload from the PI deficit.")
    ap.add_argument("workorder", help="pi_deficit.py --out JSON")
    ap.add_argument("--areas", default=None,
                    help="comma-separated instructional areas (default: all in the work order)")
    ap.add_argument("--tiers", default="easy,medium,hard",
                    help="comma-separated tiers to include (default all). Use "
                         "'--tiers hard' to split the strong/blind-verify path out.")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--avoid-scope", choices=["level", "cluster"], default="level",
                    help="scope of the avoid-context (default level — where a stem "
                         "collision is a hard drop)")
    ap.add_argument("--avoid-n", type=int, default=DEFAULT_AVOID_N,
                    help=f"max avoid signatures per PI (default {DEFAULT_AVOID_N})")
    # NO --route. It is derived per row from the curated PI pool; see
    # author_hard.hard_route(). To change a PI's route, edit
    # data/pi-pools/<cluster>-computational.json, where the change is reviewable
    # and reaches every tool that reads it (#175).
    ap.add_argument("--free-rank", action="store_true",
                    help="omit the per-item key_length_rank and per-option target "
                         "lengths, leaving only the shared option_length_band. Rule "
                         "12(b)'s real target is the BATCH statistic (key-is-longest "
                         "~25%%, the audit_tells bar), and an exact per-item rank is a "
                         "far tighter constraint than that needs: §10-3 chunk 7 had an "
                         "author miss rank on 15 of 21 easy items and re-author the "
                         "whole batch to fix it. With --free-rank the author writes to "
                         "the band only, then `check_authored.py --list-key-longest` "
                         "names the excess items for a targeted length repair — "
                         "repairing ~20%% beats constraining 100%%. Rows carry "
                         "`key_may_be_longest` instead (see --key-longest-rate).")
    ap.add_argument("--key-longest-rate", type=float,
                    default=DEFAULT_KEY_LONGEST_RATE,
                    help="--free-rank only: the share of rows whose key MAY be the "
                         f"longest option (default {DEFAULT_KEY_LONGEST_RATE}, the "
                         "no-information baseline). The rest carry "
                         "`key_may_be_longest: false`, meaning at least one distractor "
                         "must be >= the key. One bit per row, assigned like the answer "
                         "letter — NOT a rank. §10-3 chunk 2 without it: 71.3%% "
                         "key-is-longest and a 100.7k repair; chunk 3 with it: 27.7%% "
                         "and no repair agent.")
    ap.add_argument("--out", required=True, help="write the payload JSON here")
    args = ap.parse_args()

    wo = json.loads(Path(args.workorder).read_text(encoding="utf-8"))
    tiers = [t.strip() for t in args.tiers.split(",") if t.strip()]
    bad = [t for t in tiers if t not in TIERS]
    if bad:
        raise SystemExit(f"--tiers must be from {list(TIERS)}; got {bad}")
    areas = [a.strip() for a in args.areas.split(",")] if args.areas else None

    payload = build_chunk(wo, areas, tiers, args.seed, args.avoid_scope, args.avoid_n,
                          free_rank=args.free_rank,
                          key_longest_rate=args.key_longest_rate)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    by_tier = Counter(p["difficulty"] for p in payload)
    by_area = Counter(p["instructionalArea"] for p in payload)
    letters = Counter(p["answer_letter"] for p in payload)
    ranks = Counter(p["key_length_rank"] for p in payload if "key_length_rank" in p)
    withavoid = sum(1 for p in payload if p.get("avoid"))
    print(f"wrote {len(payload)} candidates -> {out}")
    print(f"  tiers {dict(sorted(by_tier.items()))} · seed {args.seed}")
    klong = sum(1 for p in payload if p.get("key_may_be_longest"))
    rank_note = (dict(sorted(ranks.items())) if ranks
                 else f"FREE — key_may_be_longest on {klong}/{len(payload)} rows "
                      f"({klong / len(payload):.0%}), the rest need distractor >= key")
    print(f"  letters {dict(sorted(letters.items()))} · ranks {rank_note}")
    print(f"  distinct PIs {len({p['performanceIndicator'] for p in payload})} · "
          f"{withavoid} rows carry avoid-context")
    if any(p["difficulty"] == "hard" for p in payload):
        routes = Counter(p.get("route") for p in payload if p["difficulty"] == "hard")
        print(f"  hard routes {dict(sorted(routes.items()))}")
    print(f"  areas ({len(by_area)}):")
    for area, c in by_area.most_common():
        print(f"    {c:>4}  {area}")


if __name__ == "__main__":
    main()
