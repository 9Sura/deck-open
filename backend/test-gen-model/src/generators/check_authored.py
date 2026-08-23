"""The shared gate an authoring agent runs against its own returned part.

ONE checker, checked in, for every plan-10 chunk. §10-1 method note 3: agents used
to each write their own throwaway checker, and the throwaway checkers disagreed with
the real gate -- most memorably a Haiku batch that reported "17/17 PASS" while
holding 7 keys at the WRONG letter and 71% key-is-longest. A checker the author
writes is a checker the author can satisfy by accident. This one is the same code
`build_question_bank.py` will run at assembly, plus the payload-assignment checks the
assembler cannot make (it never sees the payload), so a part that passes here passes
the real gate.

    python check_authored.py --payload DIR/ops.json --part DIR/ops-part1.json
    python check_authored.py --payload DIR/ops.json --part DIR/*.json --json report.json

RUN THIS BEFORE `assemble_slice.py`, NOT AFTER. It dedups the part against the whole
committed bank including the target pool (see check_part), so once a chunk has been
assembled its items are IN that pool and every one of them re-reports as a stem and
content collision with its own committed copy. A post-assembly run showing "36 of 36
FAILED, stem collision" means the chunk already landed, not that it is broken --
`verify_bank --additive` is the post-assembly check.

Exit code is 0 only when every item passes every HARD check. Soft findings are
printed and counted but never fail the run -- they are the same soft warnings the
assembler emits, and over-scrubbing them is its own defect ([[length-tell-tolerance]]:
a key longest by a few characters is noise, not a tell).

HARD (the item is not shippable as authored):
  * the assembler's own hard errors -- missing fields, not exactly 4 distinct
    options, answer not A-D, all/none-of-the-above, key > 2.2x avg distractor,
    difficulty missing or not a tier
  * cand_id unknown, duplicated, or missing from the part
  * answer letter != the ASSIGNED answer_letter (rule 10)
  * key length rank != the ASSIGNED key_length_rank (rule 12(b))
  * difficulty != the requested tier
  * PI / instructional area rewritten away from the assignment
  * content-hash or same-slice stem-hash collision with the committed bank, or
    with another item in this part

SOFT (reported, not fatal):
  * an option outside its length band, or a per-option target missed
  * top gap over the cap
  * the assembler's soft warnings (1.5x length flag, thin explanation, ...)
  * cross-slice stem twins -- not co-servable, so not a drop (issue #34)
  * STEM PULL: the stem's wording pulls toward the key specifically (see below)
  * OPTION TELLS: an option narrates its own derivation or names the wrong input
    it used, on a computational row (see below)
  * LABEL DIVERGENCE: the four options do not describe the same quantity in the
    same words, so one is distinguishable by reading alone (see below)
  * STEM META-EXCLUSION: the stem tells the READER to disregard a rival option
    instead of stating a scenario fact that rules it out (see below)

NOTE (printed, never a repair candidate):
  * a ratio length soft the row's own AIM LADDER ASSIGNMENT designed, on a rung
    that leaves the gate no headroom to tell author drift from the assignment
    (#139 -- see LADDER_HEADROOM_CH). Reported under `note`, counted separately,
    and dropped by `build_repair_prompt.parse_gate`.

All four of those are measured on EVERY returned row, including rows that already
fail hard. They read the item's own text and owe nothing to the payload, and a row
that fails hard is precisely the row a repair author is about to be handed --
suppressing half its findings is how a repair ships the other half (§10-8, issue #72).

WHAT THE OPTION-LEAK CHECKS CAN AND CANNOT SEE -- say this out loud before reading
a zero as a pass (issue #75; icdc_gate.py keeps the same kind of map for the same
reason). The defect is SEMANTIC: whether one option is distinguishable from the
other three without the stem. Nothing here measures that directly.

    self-narrating options, in §10-10/#73 WORDING     checked (phrase list)
    answerable-by-elimination shape                   checked (differential, but
                                                      only over phrase hits)
    labels that differ in KIND across the four        checked (label divergence --
                                                      vocabulary-free, soft, noisy)
    a shared label told apart by a TRAILING CLAUSE    checked (label divergence's
                                                      remainder branch, #153) --
                                                      but only down to a clause of
                                                      3-4 content words
    ...the same shape in a ONE- OR TWO-WORD clause    NOT CHECKED. Reaching it needs
                                                      a threshold that fires on 48.8%
                                                      of the bank; 3 of §10-14's 12
                                                      known rows are out of reach
    the same defect committed in NEW WORDING          PARTIAL -- caught only if it
                                                      also moves label divergence
    an option that is pickable for a reason with no
    lexical signature at all                          NOT CHECKED

`option tells: 0 of N (0.0%)` therefore means "no row wrote it in the words we have
already seen", never "no row leaks". §10-10's own H1 round-1 repair scored clean on
every deterministic instrument here and a blind solver still answered 3 of 3 by
reading the options. Read the options.

THE SAME MAP FOR THE STEM SIDE (issue #131), which is a shorter and worse one:

    reader-directed exclusions in §10-13 WORDING      checked (phrase list)
    the stem naming what the KEY names                checked (stem pull)
    the stem naming what a DISTRACTOR names           NOT CHECKED -- the obvious
                                                      structural measure was tried
                                                      and REFUTED (see below)
    a scenario fact that merely hints at the answer   NOT CHECKED

`stem meta-exclusion: 0 (0.0%)` carries exactly the caveat above. Read the stems.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

# Same-dir imports: this module lives beside the tools it composes.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_question_bank import (  # noqa: E402
    LENGTH_GIVEAWAY_RATIO,
    OPTION_KEYS,
    REVERSE_TELL_RATIO,
    SOFT_LENGTH_GIVEAWAY_RATIO,
    SOFT_REVERSE_TELL,
    check_question,
    content_hash,
    load_bank_hashes,
    load_bank_stems,
    stem_hash,
)
from repair_options import observed_rank, top_gap  # noqa: E402
from detect_stem_restatement import measure as measure_stem_pull  # noqa: E402

# DELIBERATE ASYMMETRY, resolved 2026-07-28 (plan 10-2 §2d) — do not "fix" by
# aligning these with the brief. authoring-concept.txt rule 12 states the band as a
# hard constraint (easy 15-55, medium 35-85) and names no slack; this gate reports
# only what is MORE than BAND_TOLERANCE chars outside it, and band findings are soft.
# That gap is the point: the author aims at 55 and ordinary authoring noise does not
# trigger a 239k repair, while a genuine over-run (plan-10 chunk 4's worst key ran 47
# chars over) still surfaces. [[length-tell-tolerance]] — only conspicuous outliers
# are real tells, and the actual length-tell control is LONGEST=<letter> plus
# audit_tells' key > 2.2x rule, not this band.
# THE TOLERANCE IS OPERATOR-SIDE AND MUST NOT BE DOCUMENTED IN THE AUTHOR BRIEF: a
# stated slack becomes the new target, which is the failure this margin exists to
# absorb. The strict-band count is printed as an informational line instead, so drift
# is visible to whoever reads the gate without ever being visible to the author.
BAND_TOLERANCE = 5   # chars outside the band before it is worth reporting
DECISIVE_MARGIN = 20  # plan 05 §5a: key visibly clear of every distractor
TARGET_TOLERANCE = 8  # chars off a per-option target before it is worth reporting

# ASSIGNMENT-CAUSED LENGTH SOFTS (#139) -- when the ladder and the gate contradict
# each other, only the ladder is speaking.
#
# THE DEFECT. `build_area.py`'s AIM ladder hands the key whatever rung its rank draws
# and `check_question` then scores the realised ratio, but the two were never checked
# against each other. On four (tier, rung) cells the ratio the ladder DESIGNS is at or
# past a soft's threshold, so the gate fires on an author whose deviation from its
# assignment is zero. §10-14's `mkt-district-pool-cand-e0025` is the clean case: AIM
# D~18 on the easy bottom rung, realised D=18 -- 0ch off -- flagged for a reverse
# length tell. 46 such rows across §10-10 to §10-13, never mentioned in any summary,
# and rows nobody could have authored differently are how a repair round ends up
# scoped to work that does not exist (#127).
#
# THE CELLS, computed from `build_area._ladder` (easy [48,38,28,18], medium
# [77,64,52,39], hard [85,78,70,62]) -- headroom is how far the realised lengths can
# drift before the soft fires:
#
#     cell            designed ratio   soft         headroom
#     easy rung 1          1.714x      giveaway      -6.0ch   FIRES AT ZERO DRIFT
#     easy rung 4          0.474x      reverse       +2.0ch
#     medium rung 1        1.490x      giveaway      +0.5ch
#     medium rung 4        0.606x      reverse      +22.3ch   fine
#     hard rung 1          1.214x      giveaway     +20.0ch   fine
#     easy rung 2          1.213x      giveaway      +9.0ch   fine, and kept
#
# #74 is the precedent and this is its unaddressed half: "a length target aimed at a
# band edge has no headroom in the direction the errors actually go". #74 inset the
# ladder, which moved the easy bottom rung from 0.360x (BELOW 0.45 -- firing on every
# such row by design) to 0.474x, i.e. from "always" to "on 2ch of drift". Insetting
# further cannot finish the job: the key is still handed the smallest number in the
# ladder, and raising the bottom rung compresses the spread the ladder exists to
# create. So the gate defers instead, on the two conditions below.
#
# NOT A THRESHOLD CHANGE, AND NOT A BLANKET EXEMPTION. Both must hold:
#
#   1. the CELL has less headroom than ordinary authoring drift -- LADDER_HEADROOM_CH.
#      A medium rung-4 row keeps its reverse soft (22.3ch of headroom), so a genuine
#      distractor blow-out there still surfaces.
#   2. the AUTHOR wrote the key within TARGET_TOLERANCE of its own assigned target.
#      A key that missed its number is real drift whatever the cell's headroom is.
#
# LADDER_HEADROOM_CH IS MEASURED, NOT PICKED. It is `build_area.LADDER_INSET_TOP`'s own
# figure: over the plan-10 tails of the six closed hospitality/pbm pools, authoring
# error is one-directional (options run long) at a MEDIAN EXCESS OF 8ch on both easy
# and medium. It is also exactly TARGET_TOLERANCE, which this gate already treats as
# the slack around a per-option target -- one number, not two.
#
# WHAT THIS DOES NOT DO. It does not make the flagged rows better, and it does not
# touch `build_question_bank`'s own run at assembly, which has no payload to compare
# against and will still report these rows -- deliberately: the assembler's job is to
# describe the bank as it stands, not to re-litigate an authoring assignment. Nothing
# is silently dropped either; a suppressed soft is re-emitted as a `note` so the
# contradiction stays visible if the ladder later moves.
LADDER_HEADROOM_CH = TARGET_TOLERANCE

# STEM PULL -- an item whose stem's wording points at its own key, so the student
# matches words instead of retrieving the concept. Nothing else in the pipeline
# looks at the stem against the options at all.
#
# THE METRIC IS `differential`, NOT RAW OVERLAP, and that distinction is the whole
# reason this is checkable. Every option shares domain vocabulary with its stem; a
# raw stem<->key overlap therefore fires on healthy items, and worse, a longer
# option shares more words by chance, so raw overlap partly RE-MEASURES THE LENGTH
# TELL (detect_stem_restatement.py's length-confound note). `differential` is
# jaccard(stem, key) minus the best jaccard(stem, distractor): it asks whether the
# stem pulls toward the KEY SPECIFICALLY, which is the only form a student can
# exploit. It is length-normalized on both sides.
#
# WHAT IT CATCHES -- the VERBATIM-ECHO class, and only that:
#     stem: "Which term describes the LIMITED nature of economic RESOURCES compared
#            to UNLIMITED HUMAN WANTS?"
#     key : "LIMITED RESOURCES facing UNLIMITED HUMAN WANTS"        (+0.455)
#     stem: "Which tax form does an employer give an employee to report annual
#            WAGES AND TAXES WITHHELD?"
#     key : "A W-2 form showing WAGES AND TAXES WITHHELD"           (+0.375)
# Both shipped. Both passed every other gate. At the thresholds below the flag
# fires on 143/8400 = 1.7% of the bank and 1.9-3.4% per plan-10 slice -- 2-8 rows
# in a chunk, which is an in-pass fix rather than a repair.
#
# WHAT IT DOES NOT CATCH, MEASURED 2026-07-29 -- SAY THIS OUT LOUD BEFORE TRUSTING
# IT. §10-4 finding 3 hand-fixed 8 items for stem telegraphing, all 8 independently
# flagged by three or more verification agents. Scored against the pre-fix text in
# `output/plan-10/10-4/verify/referee-set.txt` this flag catches ZERO OF THE EIGHT:
# they sit at differential +0.006 to +0.109, against a bank p90 of +0.056. The
# metric does move the right way on all 8 (every one falls post-fix, e.g. item 14
# +0.105 -> -0.048), but no threshold separates them from healthy items -- catching
# 6 of 8 would mean flagging ~15% of the bank.
# The reason is structural and it is in detect_stem_restatement.py's own docstring:
# this is a LEXICAL metric and "it will never make `likely` meet `probability`".
# §10-4's defect was PARAPHRASE -- "take a couch home right away instead of paying
# the full price up front" against a key about owning "before full payment" -- and
# a token-overlap measure cannot see a paraphrase by construction.
# So: this catches a real class nothing else catches, for zero agents. IT IS NOT A
# SUBSTITUTE FOR THE VERIFICATION AGENTS OR THE AUTHOR'S OWN SELF-CHECK 1b, and
# budgeting as though it were is how the paraphrase class ships.
#
# CALIBRATION, on the 8,400-item bank 2026-07-29:
#   differential   mean -0.022 · p50 -0.003 · p90 0.056 · p99 0.174 · max 0.455
#
# DELIBERATELY SOFT, and it must stay soft. The bank's own p99 is a distribution
# cut, not a defect line -- some genuinely good items reuse a stem's noun because
# the concept requires it (a jurisdiction item must say "out-of-state supplier"
# twice). This surfaces candidates for the author's eye at the cost of zero agents;
# it does not adjudicate them ([[length-tell-tolerance]], the same reason the band
# findings are soft).
#
# NOT A REVIVAL OF PLAN-07 LEVER B. That lever asked a different question -- how
# much of the WHOLE BANK is stem-restated -- and its one known-bad ranks only p74
# here, so it stays refused. This is the authoring-time use: flag the top of the
# distribution inside one batch, while the author is still holding it.
STEM_PULL_DIFFERENTIAL = 0.15  # jaccard(stem,key) - best jaccard(stem,distractor)
STEM_PULL_JACCARD = 0.12       # ...and real shared wording, not a small difference
BANK_P99_DIFFERENTIAL = 0.174  # context for the finding, from the calibration above


def stem_pull(items: List[Dict]) -> Dict[str, Dict]:
    """{cand_id: metrics} for items whose stem pulls toward the key. Keyed by cand_id.

    `measure` reports per item and skips anything without a usable answer/stem, so
    it is keyed by the id it is handed rather than by position.
    """
    probe = [dict(q, id=q.get("cand_id")) for q in items]
    return {r["id"]: r for r in measure_stem_pull(probe)
            if r["differential"] >= STEM_PULL_DIFFERENTIAL
            and r["jaccard_stem_key"] >= STEM_PULL_JACCARD}


def assigned_option_targets(spec: Dict) -> Optional[tuple]:
    """`(key target, [distractor targets])` for a payload row, or None if unassigned.

    TWO PAYLOAD SHAPES, and #139's own failure case is the second one, so both count:

      * RANKED -- `key_target_len` + `distractor_target_lens`, written by
        `build_area.target_lengths`.
      * `--free-rank` -- `option_target_lens`, a per-LETTER dict from
        `build_area.option_targets`. These are ADVISORY and gated by nothing, but they
        are still the numbers the author was shown (`AIM D~18`), and an instruction is
        no less the cause of an outcome for being unenforced. `mkt-district-pool-cand-
        e0025` is this shape.

    A row with neither returns None and keeps every soft it earns.
    """
    if "key_target_len" in spec and "distractor_target_lens" in spec:
        dis = [float(n) for n in spec["distractor_target_lens"]]
        return (float(spec["key_target_len"]), dis) if dis else None

    aims = spec.get("option_target_lens")
    ans = str(spec.get("answer_letter", "")).strip().upper()
    if isinstance(aims, dict) and ans in aims:
        dis = [float(n) for k, n in aims.items() if k != ans]
        return (float(aims[ans]), dis) if dis else None
    return None


def assignment_caused_softs(spec: Dict, opts: Dict[str, str], answer: str) -> set:
    """Which ratio-soft markers this row's OWN ladder assignment produced (#139).

    Returns a set of message markers (`SOFT_REVERSE_TELL`, `SOFT_LENGTH_GIVEAWAY_RATIO`)
    to suppress -- empty for any row that carries no assignment, whose key missed its
    assigned target, or whose cell has real headroom. See LADDER_HEADROOM_CH for why
    both conditions are required and where the 8ch comes from.

    HEADROOM IS COMPUTED ON THE TARGETS, NOT ON THE REALISED LENGTHS. The question is
    whether the CELL can distinguish an author's mistake from its own assignment, which
    is a property of the four numbers the ladder handed out. Reading it off what the
    author actually wrote would make the test circular -- a row fires precisely when
    its realised ratio crosses the line, so it would always look like drift.
    """
    targets = assigned_option_targets(spec)
    if targets is None:
        return set()
    key_target, distractor_targets = targets
    mean_target = sum(distractor_targets) / len(distractor_targets)
    if mean_target <= 0 or key_target <= 0:
        return set()

    # Condition 2 first -- it is the cheap one, and it is what makes this a deferral to
    # the assignment rather than an exemption for the cell.
    if answer not in opts:
        return set()
    if abs(len(str(opts[answer]).strip()) - key_target) > TARGET_TOLERANCE:
        return set()

    out = set()
    # The reverse soft is tripped by the DISTRACTORS running long: their mean has to
    # climb to `key / REVERSE_TELL_RATIO` before the key reads as "much shorter".
    if key_target / REVERSE_TELL_RATIO - mean_target < LADDER_HEADROOM_CH:
        out.add(SOFT_REVERSE_TELL)
    # The giveaway soft is tripped by the KEY running long against them.
    if LENGTH_GIVEAWAY_RATIO * mean_target - key_target < LADDER_HEADROOM_CH:
        out.add(SOFT_LENGTH_GIVEAWAY_RATIO)
    return out


# ---------------------------------------------------------------------------
# OPTION TELLS -- the defect class §10-10 proved no gate could see.
#
# §10-10's H1 shipped 9 of 9 items whose options each read "<value>, from <the
# method that produced it>". Two raters and two blind solvers flagged it
# INDEPENDENTLY; both solvers answered 4 of 4 correctly BY READING ALONE. It cost
# 174.5k over two repair rounds, and the first round removed the recipe form while
# leaving the item just as pickable -- so it also cost the blind pass that caught
# that. `stem_pull` scored 0.0% throughout and was right to: it measures
# stem-to-key overlap, and this defect is about whether an option is
# distinguishable FROM THE OTHER THREE.
#
# Three shapes, all deterministic and free:
#   DERIVATION -- the option narrates how its number was produced
#                 ("About 47.7 pounds, from 42 pounds divided by 88% yield").
#   SELF-FLAG  -- the option names the wrong input it used, so it crosses itself
#                 off by reading ("under a budget sized to the COMPARISON revenue
#                 figure"; "$25,000, the full budget, NOT DIVIDED by bookings").
#   ADMISSION  -- the option confesses to a MISTAKE ("$300, mistakenly applying a
#                 15% rate", "$16.00 ADR, misplacing the decimal point"). Nothing
#                 needs to be known to cross it off, and a row carrying two of them
#                 is answerable by elimination with the stem covered.
#
# ADMISSION was added by issue #73 and is the CONCEPT-TIER shape. The first two
# regexes were both derived from §10-10's H1, a hard batch, and they read a
# derivation ("divided by", ", from") rather than a confession -- so they scored
# the tier that already had the rule and under-read the two tiers that did not.
# Measured on the committed bank at the time: 107 rows flagged by the first two
# shapes, 20 further rows flagged only by this one, and the elimination-answerable
# subset was overwhelmingly easy/medium. A detector written from one tier's defect
# is a detector calibrated to one tier's vocabulary; check the census by tier
# before believing a clean read.
#
# SCOPED TO COMPUTATIONAL ROWS ON PURPOSE. Where every option is a number the
# label should be identical across the four and only the figure should differ, so
# any distinguishing prose is a tell. On a concept item the options are SUPPOSED
# to differ in content, and running this there would be noise. The scope test is
# "at least 3 of the 4 options carry a figure", which is the "Calculate ..." shape
# where every measured instance of this defect has lived.
OPTION_NUMERIC = re.compile(r"[$€£]?\d[\d,]*\.?\d*\s*%?")
OPTION_DERIVATION = re.compile(
    r"(,\s*from\s|\bdivided by\b|\bmultiplied by\b|\btimes the\b|\binstead of\b"
    r"|\brather than\b|\bnot divided\b|\bnever divided\b|\bwithout ever\b"
    r"|\bbased on last\b|\bpre-rounding\b)", re.I)
OPTION_SELF_FLAG = re.compile(
    r"(\btheoretical\b|\bfor comparison\b|\bcomparison (revenue|figure)\b"
    r"|\blast quarter'?s\b|\bformula price\b)", re.I)
# Verbs of confession only. "wrong" and "incorrect" are deliberately NOT here:
# a stem may legitimately ask what a wrong figure was ("the manager reports gross
# profit as $30,000 -- what is the error?"), and on that item every option names
# an error because that is the question asked. These stems are rare; a false
# positive on one is a repair author sent to break a sound item.
OPTION_ERROR_ADMISSION = re.compile(
    r"(\bmistak\w+|\bmisplac\w+|\bmisappl\w+|\bmisread\w+|\bmiscount\w+"
    r"|\bmislabel\w+|\bmistaking\b|\bforgetting\b|\bomitting\b|\bignoring\b"
    r"|\bfailing to\b|\boverlooking\b)", re.I)
OPTION_TELL_MIN_NUMERIC = 3


def option_in_scope(opts: Dict[str, str]) -> bool:
    """Is this a computational row -- the only shape the tell detector reads?

    Kept separate from option_tells() so the reported rate has an honest
    denominator: "3 of 41 computational rows", never "3 of 634", which would make
    a real defect look like noise.

    Type-guarded, not just key-guarded. Under the old nesting this only ever ran on
    rows check_question had already validated; it now runs on rows that hard-failed
    it (see check_part), so `options` arrives as whatever the author emitted and
    `set()` of a number raises. Today the batch-wide stem_pull pass happens to die
    on those same shapes first, but that is another function's accident to lose, not
    a guarantee this one should lean on.
    """
    if not isinstance(opts, dict) or set(opts) != set(OPTION_KEYS):
        return False
    n = sum(1 for k in OPTION_KEYS if OPTION_NUMERIC.search(str(opts[k] or "")))
    return n >= OPTION_TELL_MIN_NUMERIC


def option_tells(opts: Dict[str, str]) -> List[str]:
    """Findings for one row's option set. Empty when the row is not computational.

    Returns human-readable strings naming the letter and the offending phrase, so
    a repair scope can hand the author the exact words to remove.
    """
    if not option_in_scope(opts):
        return []
    vals = {k: str(opts[k] or "") for k in OPTION_KEYS}
    out = []
    for k in OPTION_KEYS:
        m = OPTION_DERIVATION.search(vals[k])
        if m:
            out.append(f"option {k} narrates its own derivation ({m.group(0).strip()!r})")
            continue
        m = OPTION_SELF_FLAG.search(vals[k])
        if m:
            out.append(f"option {k} names the wrong input it used ({m.group(0).strip()!r})")
            continue
        m = OPTION_ERROR_ADMISSION.search(vals[k])
        if m:
            out.append(f"option {k} confesses to a mistake ({m.group(0).strip()!r})")
    return out


# ---------------------------------------------------------------------------
# LABEL DIVERGENCE -- the differential the phrase list can never be (issue #75).
#
# THE PHRASE LIST IS OVERFIT AND ALWAYS WILL BE. Every regex above was lifted from
# a batch that had already shipped: OPTION_DERIVATION/OPTION_SELF_FLAG from §10-10's
# H1, OPTION_ERROR_ADMISSION from #73's easy/medium census. They find real rows (107,
# then 119, on the committed bank) and they are worth keeping. What they cannot do is
# fail a batch that commits the SAME defect in words nobody has written yet -- and a
# clean phrase read prints `0.0%`, which reads as a pass. That is exactly how §10-10's
# nine items shipped in the first place, so growing the list one slice at a time is
# chasing the last batch forever.
#
# THIS MEASURES THE RULE INSTEAD OF ITS VOCABULARY. `authoring-hard-bare.txt` and
# `authoring-concept.txt` state it as: ALL FOUR OPTIONS DESCRIBE THE SAME QUANTITY IN
# THE SAME WORDS; ONLY THE NUMBER DIFFERS. That is a property of the four options
# against each other, and it is computable without knowing a single phrase:
#
#   label(option) = its words with every figure removed
#   shared        = |tokens common to all four| / |tokens in any|      1.0 == compliant
#   unique(k)     = tokens in option k that appear in NO other option  0   == compliant
#
# A row is flagged when the labels barely overlap AND at least one option carries
# LABEL_UNIQUE_MIN words of its own -- i.e. an option says something about itself
# that the others do not, whatever the words are.
#
# ...AND BY THE REMAINDER, because the shared fraction alone is blind to a short
# trailing clause (issue #153). A row whose four labels share a LONG core and differ
# only in a SHORT clause scores HIGH on `shared` -- so the measure reads it as
# convergent at exactly the moment the clause is the tell. §10-14 chunk 9 shipped 12
# of 90 rows in that shape, named with quoted phrases by two independent blind shards:
#
#     m0073  A $12,750, the correct total redemption cost after the intern's third calculation  <- KEY
#            B $11,250, the correct total redemption cost for the deal
#            C $127,500, the correct total redemption cost, first attempt
#            D $187,500, the correct total redemption cost, second attempt
#
# shared = 0.33 on that row, so the first branch never saw it, and `option_tells`
# matched 2 of the 14 (the author evaded the banned list by paraphrase -- "the trainee
# first wrote on the price tag", "many shoppers might guess"). BOTH instruments read
# BETTER than the committed bank on a batch carrying the class at 10.8%, which is how
# a reader following the documented method ("read the RATE") concluded it was 2.5x
# cleaner than the bank.
#
# THE SECOND BRANCH ASKS THE SAME QUESTION OF THE REMAINDER INSTEAD: ignore how much
# the labels share, and count how the leftovers are DISTRIBUTED. When three or more of
# the four options each carry wording no other option has, and one of them carries
# LABEL_REMAINDER_MIN words of its own, the options are being told apart by their
# trailing clauses no matter how long the core they share is.
#
# ...AND BY THE ODD ONE OUT, because BOTH of those branches are blind to three
# byte-identical labels beside a single divergent option WHEN THE DIVERGENT ONE IS THE
# KEY (issue #185). Branch 1 needs `shared` LOW and three identical labels drive it
# UP; branch 2 needs the leftovers SPREAD across three of the four and this shape puts
# them all on one. §10-16 chunks 9/10/11 shipped four live rows of it:
#
#     e0032  A 15% of respondents visited exactly twice
#            B 25% of respondents visited exactly twice
#            C 40% of respondents visited exactly twice
#            D 20% of the 150 customers visited exactly twice          <- KEY
#
# THE PERVERSE PROPERTY: the better the author obeys "same quantity, same words" on
# three options, the higher `shared` climbs and the more invisible the fourth becomes.
# The instrument was blinded by PARTIAL COMPLIANCE. And this is #139's shape one level
# in -- `fixtures_label_divergence.py` carried an explicit assertion that this case was
# branch 1's question, and branch 1 structurally cannot answer it: two halves of one
# instrument, each internally consistent, never checked against each other.
#
# THE THIRD BRANCH IS THE ONLY ONE THAT READS THE `answer`, and it has to. The same
# shape with a DISTRACTOR as the odd option is a real but far weaker defect -- crossing
# off the one that reads differently gets a student nowhere -- and it is 219 of the 329
# `spread == 1` rows in the bank. Keying on the KEY is what makes the branch readable:
#
#     bank label rows                                     1,060
#     spread == 1                                           329   31.0% of label rows
#     ...and the lone divergent option IS the key           110   33.4% of those
#
# 33.4% against a 25.0% chance floor, one-sided binomial n=329 p=0.25: p = 3.75e-04.
# A real corpus-wide tell -- unlike #174's declined cents class (29.4%, p=0.34) and
# unlike #131's refuted inverted stem pull. DO NOT REACH IT BY LOWERING
# LABEL_REMAINDER_SPREAD TO 1: that drops the key condition and fires on all 329 rows.
#
# `answer` is OPTIONAL and the branch is silent without it, so a caller measuring
# options alone (every fixture arm that predates this) reads exactly what it read
# before. A None answer never flags.
#
# CALIBRATED ON THREE ADJUDICATED PAIRS, and the second one is still the constraint.
# Each new branch must find its own class WITHOUT breaking §75's negative arm:
#
#     §10-14 chunk 9, the 12 blind-named rows    3 of 12 -> 8 of 12 flagged
#     ...the same 12 rows as repaired            0 of 12 -> 0 of 12
#     §10-10 h1 round 1 (defect, the #75 pair)   7 of 8  -> 7 of 8   (unchanged)
#     §10-10 h1 round 2 (the accepted fix)       0 of 8  -> 0 of 8   (unchanged)
#     committed bank                             19.4%   -> 19.6%
#
# ...and the third branch (#185) against the same three pairs, plus its own:
#
#     §10-16 chunk 10, the 4 rows the blind pass found   0 of 4 -> 4 of 4 flagged
#     ...the same 4 rows as repaired                     0 of 4 -> 0 of 4
#     §10-16 e0059, the one row branch 1 DID catch       1 of 1 -> 1 of 1 (branch 1)
#     §10-14 chunk 9 / §10-10 h1, both arms of each      every number unchanged
#     committed bank                                     16.8%  -> 26.5%
#
# THAT IS A BIG MOVE ON THE PRINTED RATE and it is the branch's whole cost: 103 rows
# of the bank's 1,060 label rows that read clean now read flagged. It is paid because
# the class is measured (p = 3.75e-04) and because the four §10-16 rows were reachable
# by NOTHING deterministic -- the unscoped blind pass found all four.
#
# The verdict a reader gets is what actually moves: chunk 9 goes from 9.4% against a
# quoted 23.9% baseline ("2.5x cleaner than the bank") to 25.0% against 19.6% -- above
# baseline, which is the truth. THE BRANCH IS A UNION, never a replacement: it cannot
# withdraw a row the first branch finds, so no earlier reading is invalidated.
#
# WHY worst >= LABEL_REMAINDER_MIN (4) HERE AND 3 ON THE FIRST BRANCH. The first
# branch has already established the labels barely overlap; this one has not, so it
# needs a higher bar on the divergence itself or it drags the bank baseline to 23.2%
# for the same 8 of 12 -- more noise for no recall. Measured, not chosen.
#
# WHAT IT STILL MISSES, and say it out loud: a clause of one or two content words.
# §10-14's `e0080` ("$40,000, the promotional budget" x3 against "...the promotional
# budget on the draft") carries ONE leftover token, and reaching it needs
# LABEL_UNIQUE_MIN=2, which fires on 48.8% of the bank -- a rate nobody can read.
# Three of the 12 are out of reach for that reason, and chunk 10 (2 defect rows of 40,
# one of them a 2-token clause) still reads below baseline. Read the options.
#
# CALIBRATED AGAINST THE ONE DEFECT/FIX PAIR THAT WAS INDEPENDENTLY ADJUDICATED --
# §10-10's H1, round 1 (`output/plan-10/10-10/parts/h1-deleak.json`: two blind solvers
# still answered it by reading, and the phrase list scores 2 of 9) against round 2
# (`h1-deleak2.json`, the accepted fix). At the thresholds below:
#
#     round 1 (defect, phrase list 2 of 9)   7 of 9 flagged
#     round 2 (accepted fix)                 0 of 9 flagged
#     committed bank                         167 of 700 label rows (23.9%)
#
# SO IT IS SOFT, AND IT IS NOISE-HEAVY BY DESIGN. A quarter of the bank's label rows
# trip it, because "$43,000 in cost of goods sold / $45,000 in COGS / $39,000 total
# COGS" really does violate the rule and really is not answerable from the options.
# The BASELINE is the finding, not the row: a batch at 20% is the bank, a batch at 60%
# was written by an author narrating its options. Do not gate on it, do not repair to
# a rate, and never read it as an adjudication ([[length-tell-tolerance]], same as the
# band and stem-pull findings).
#
# ITS OWN SCOPE, DELIBERATELY TIGHTER THAN option_in_scope(). That predicate asks for
# a figure in 3 of 4 options and OPTION_NUMERIC counts any digit, so "Option 2 is less
# expensive..." is a figure and a prose row about two financing offers is in scope --
# fine for a phrase list, useless here, because on a prose row the options are SUPPOSED
# to diverge. A label row needs three DISTINCT quantities (currency, percent, decimal,
# or 3+ digits) and short labels: a figure with a name after it. Changing
# option_in_scope() instead would move the tell census that §10-17's work order is
# counted in, so the two scopes stay separate and both are reported.
LABEL_STOPWORDS = frozenset("""
a an the of in on at to for per by and or its it his her their this that with from
as is are was were be been than then over under about approximately each every all
both any some no not only just more most less least
""".split())
# A quantity, not merely a digit: $12 · 47.7 · 88% · 1,250 · 240. Deliberately excludes
# the bare 1-2 digit integers that make "Option 2" and "table 4" look computational.
OPTION_QUANTITY = re.compile(r"([$€£]\s?\d|\d[\d,]*\.\d|\d[\d,]*\s*%|\d[\d,]{2,})")
LABEL_MAX_TOKENS = 10     # above this the option is prose, not a figure with a name
LABEL_MIN_QUANTITIES = 3  # distinct quantities among the four -- the key + wrong values
LABEL_SHARED_MAX = 0.25   # share of label wording common to all four
LABEL_UNIQUE_MIN = 3      # ...and one option carrying this many words of its own
# The remainder branch (#153): the labels may share as much as they like, but if the
# leftovers are spread across most of the options AND one is this long, the options
# are told apart by their trailing clauses. Higher than LABEL_UNIQUE_MIN on purpose --
# see the block above; 3 here costs 3.6pp of bank baseline and finds nothing more.
LABEL_REMAINDER_MIN = 4      # words of its own on the worst option...
LABEL_REMAINDER_SPREAD = 3   # ...and this many of the four carrying any at all
# The odd-one-out branch (#185): exactly ONE of the four carries wording of its own,
# and it is the KEY. No word floor beside it -- `spread == 1` already means the other
# three carry nothing, and §10-16's e0032 and e0068 diverge by a single content word
# ("customers", "retailer") which is the whole tell on those rows. There is deliberately
# no LABEL_ODD_KEY_* threshold to tune: the condition is structural, and the thing that
# keeps it readable is the `answer` test, not a number.
LABEL_ODD_SPREAD = 1
# % of the bank's label rows, MEASURED, not chosen -- re-measure it when the bank MOVES.
# This constant has now gone stale THREE times (23.9% at #153, 19.6% at #185, 26.5% at
# §10-17), and the third is the instructive one because it moved for the opposite reason
# from the first two. Those drifted UP as the bank grew and nobody re-measured; this one
# dropped 6.3pp in one commit because §10-17 REPAIRED 80 rows out of the flagged
# population. A gate's baseline is a property of the corpus, so the act of fixing the
# corpus invalidates it -- which means "re-measure when the bank grows" was too narrow,
# and any batch quoting the old number would have been read as far cleaner than it is.
# `slice-tools/fixtures_label_divergence.py` is what catches it; run that fixture before
# quoting this figure anywhere.
BANK_LABEL_DIVERGENCE_RATE = 20.2


def option_label(text: str) -> set:
    """One option's wording with the figures taken out -- its LABEL, as a token set."""
    stripped = OPTION_NUMERIC.sub(" ", str(text or ""))
    words = re.sub(r"[^a-z]+", " ", stripped.lower()).split()
    return {w for w in words if len(w) > 2 and w not in LABEL_STOPWORDS}


def label_divergence(opts: Dict[str, str], answer: str = "") -> Dict:
    """How far one row's four labels are from 'same quantity, same words'.

    `answer` is the keyed letter and is OPTIONAL: only the third branch (#185)
    reads it, and that branch is silent without it, so a caller that measures
    options alone reads exactly what it read before the branch existed.

    Returns {} when the row is not a label row -- prose options, no quantities,
    or fewer than three distinct ones. Otherwise:
        shared  0.0-1.0, wording common to all four over wording in any
        unique  {letter: words that option uses and no other does}
        worst   the largest of those
        spread  how many of the four carry any wording of their own
        odd     the letter of the lone divergent option, or None
        remainder  the second branch alone (#153), for the finding text
        odd_key    the third branch alone (#185), for the finding text
        flagged any branch -- see the block above; it is a UNION
    """
    if not isinstance(opts, dict) or set(opts) != set(OPTION_KEYS):
        return {}
    vals = {k: str(opts[k] or "") for k in OPTION_KEYS}
    figs = {k: {m.group(0).replace(" ", "") for m in OPTION_QUANTITY.finditer(vals[k])}
            for k in OPTION_KEYS}
    if sum(1 for k in OPTION_KEYS if figs[k]) < OPTION_TELL_MIN_NUMERIC:
        return {}
    if len(set().union(*figs.values())) < LABEL_MIN_QUANTITIES:
        return {}
    labels = {k: option_label(vals[k]) for k in OPTION_KEYS}
    if max(len(v) for v in labels.values()) > LABEL_MAX_TOKENS:
        return {}
    union = set().union(*labels.values())
    if not union:
        return {}  # four bare figures: no label to diverge
    shared = len(set.intersection(*labels.values())) / len(union)
    unique = {k: sorted(labels[k] - set().union(*(labels[j] for j in OPTION_KEYS
                                                  if j != k)))
              for k in OPTION_KEYS}
    worst = max(len(v) for v in unique.values())
    spread = sum(1 for v in unique.values() if v)
    odd = next((k for k in OPTION_KEYS if unique[k]), None) if spread == 1 else None
    # Branch 1 (#75): the labels barely overlap at all.
    barely_shared = shared < LABEL_SHARED_MAX and worst >= LABEL_UNIQUE_MIN
    # Branch 2 (#153): they may overlap as much as they like -- the leftovers are
    # what tells the options apart. Read the block above before moving either number.
    remainder = worst >= LABEL_REMAINDER_MIN and spread >= LABEL_REMAINDER_SPREAD
    # Branch 3 (#185): three labels identical, the fourth different, and the fourth
    # IS the key -- the shape whose `shared` climbs as three of the four comply.
    # Disjoint from branch 2 by construction (spread 1 vs spread >= 3); it can overlap
    # branch 1, and branch 1 keeps the row for the same reason branch 2 defers to it.
    odd_key = odd is not None and odd == str(answer or "").strip().upper()
    return {"shared": shared, "unique": unique, "worst": worst, "spread": spread,
            "odd": odd,
            "remainder": remainder and not barely_shared,
            "odd_key": odd_key and not barely_shared,
            "flagged": barely_shared or remainder or odd_key}


def option_elimination(opts: Dict[str, str], answer: str) -> List[str]:
    """The subset of option_tells() a student can ACT on with the stem covered.

    A row is answerable by elimination when two or more DISTRACTORS carry a tell
    and the key does not: cross off the ones that describe their own error, and
    what is left is the answer. That is a strictly worse defect than a row where
    the key tells too (there the tells cancel), and it is the shape issue #73
    sampled 5 of 5 true positives from -- so it is what a partial repair pass
    should be ordered by. Returns [] when the row is not in that shape.

    Kept separate from option_tells() rather than folded into it: the finding
    lines are per option and this is a property of the SET, and a repair author
    still needs every tell on the row named, not just the actionable ones.
    """
    if not option_in_scope(opts) or answer not in OPTION_KEYS:
        return []
    found = {k: [t for t in option_tells(opts) if t.startswith(f"option {k} ")]
             for k in OPTION_KEYS}
    if found[answer]:
        return []
    hits = [k for k in OPTION_KEYS if k != answer and found[k]]
    return [t for k in hits for t in found[k]] if len(hits) >= 2 else []


# ---------------------------------------------------------------------------
# STEM META-EXCLUSION -- the defect an AMBIGUITY REPAIR reliably manufactures
# (issue #131).
#
# The standing instruction for a row with two defensible answers is to make the
# stem commit to one reading. The shortest way to comply is to bolt a clause onto
# the stem that NAMES THE RIVAL AND TELLS THE READER TO DISREGARD IT. That does
# cure the ambiguity, and it replaces a knowledge item with a reading item: the
# student no longer has to know the concept, only to match the clause to an option
# and cross it out.
#
# MEASURED. §10-13's chunk 9/10 repair was told to fix 8 ambiguous rows by "adding
# the fact that rules the competitor out" and complied literally on 5 of the 5 rows
# where a stem edit was in scope:
#
#   e0003  "...not just keep a record of their purchases"        -> distractor B
#   e0008  "logging each visitor's inquiry is a secondary side effect"  -> B
#   e0014  "...not on herself"                                   -> distractor D
#   e0029  "-- not the evidence used to prove it --"             -> distractor B
#   m0003  "Setting aside how the access became possible, ..."   -> distractor B
#
# All five passed the FULL gate suite afterwards -- check_authored exit 0, stem pull
# 0.0%, check_batch_invariants 0 blocking, check_key_figures 0 mismatch -- and were
# caught only by a blind survivor-hunt agent, which answered them correctly with no
# business knowledge by reading the clause.
#
# THE STRUCTURAL MEASURE WAS TRIED FIRST AND IS REFUTED. `label_divergence` exists
# because a phrase list can only recognise wording it has seen, so the same upgrade
# was attempted here: a meta-exclusion names a DISTRACTOR, so an INVERTED stem pull
# -- max jaccard(stem, distractor) - jaccard(stem, key) -- should rise on exactly
# these rows. It does not. Against the one adjudicated defect/fix pair this slice
# left behind (`parts/chunk{9,10}-repair.json` round 1 vs `-repair2.json`, the
# accepted fix):
#
#     defect rows   -0.00, 0.043, 0.043, 0.053, -0.002   (bank median 0.004, p90 0.111)
#     FIXED rows    -0.00, -0.00, 0.068, 0.091, -0.001   -- HIGHER than the defect
#
# The clause is short and paraphrases the distractor's CONCEPT rather than its
# wording ("not just keep a record of their purchases" shares one token with "Track
# purchases and follow up with a tailored note"), so it is invisible under a Jaccard
# over the whole stem. Refused on the numbers, per detect_stem_restatement's own
# rule: if it cannot separate them, DO NOT PROCEED ON VIBES.
#
# SO THIS IS A PHRASE LIST, AND IT IS SOFT. Calibrated on the same pair -- 5 of 5
# defect rows flagged, 0 of 5 accepted fixes -- against a committed-bank baseline of
# 0.61% (86 of 14,151 stems). Deliberately NOT gated: the bank's hits are a real mix
# ("...wants to show measurable impact rather than just listing daily tasks" is the
# defect; "Rather than simply increasing its own on-site inventory, the director
# proposes..." is a scenario fact in narrative form), and only a reader can tell
# them apart. Read the RATE against the baseline; treat the rows as candidates.
#
# PHRASES DELIBERATELY LEFT OUT, because a rate nobody can read is worse than no
# rate: bare "rather than" (369 bank rows, 2.61% -- ordinary contrastive prose),
# "regardless of how many" (the canonical fixed-cost stem), and "setting aside"
# followed by money (literal saving, not exclusion). Each is the same trade the
# throwaway-distractor marker list got wrong at §10-11: the list is a finding aid,
# never a score.
STEM_META_EXCLUSION = {
    "excludes a named alternative":
        re.compile(r"\bnot (?:just|merely|simply)\b", re.I),
    "demotes a named alternative":
        re.compile(r"\bis (?:a |merely a |only a )?secondary\b"
                   r"|\bis (?:a|an) (?:side|incidental) (?:effect|benefit|outcome)\b", re.I),
    "excludes a named alternative parenthetically":
        re.compile(r"(?:—|--)\s*not\b[^—-]{0,60}?(?:—|--)", re.I),
    "excludes a named alternative in a trailing clause":
        re.compile(r",\s*not (?:the|on|about|because|whether|its|his|her|their)\b", re.I),
    "instructs the reader to disregard something":
        re.compile(r"\b(?:setting|leaving|putting) aside (?:how|whether|what|why|the question)\b"
                   r"|\bregardless of whether\b|(?:^|[.;] )ignoring\b|\beven ignoring\b"
                   r"|\bas opposed to\b|\bapart from (?:how|whether|what|the question)\b", re.I),
    "contrastive clause aimed at a reading, not at a fact":
        re.compile(r"\brather than (?:just|merely|simply)\b", re.I),
}
BANK_STEM_META_RATE = 0.61  # % of committed bank stems, from the calibration above


def stem_meta_exclusion(question: str) -> List[str]:
    """The shapes one row's stem matched, each quoting the clause that matched it.

    THE TEST THE PHRASES ONLY APPROXIMATE, and the one a reader applies to each hit:
    delete the clause. If no fact about the scenario changed, it was an instruction
    to the reader about the options and the item is not fixed -- put a concrete
    scenario fact in its place that makes the rival option wrong on the merits.
    """
    text = str(question or "")
    if not text:
        return []
    out = []
    for shape, rx in STEM_META_EXCLUSION.items():
        m = rx.search(text)
        if m:
            out.append(f"{shape} ({m.group(0).strip()!r})")
    return out


def check_part(payload: List[Dict], items: List[Dict],
               post_referee: bool = False) -> Dict:
    by_cand = {p["cand_id"]: p for p in payload}
    results: List[Dict] = []
    seen_cand: Counter = Counter()

    # Dedup context: the ENTIRE committed bank, the target pool very much included.
    #
    # `build_question_bank --pool` excludes the pool's own file here, and copying
    # that would be a silent hole. It excludes it because --pool REBUILDS the pool
    # from the parts it is handed, so the existing pool arrives as part 1 and
    # re-seeds the dedup sets as it is processed -- the file is excluded only to
    # keep it from matching itself. Plan-10 authoring is the opposite situation:
    # these items are NEW, and the pool they are about to join is the single most
    # likely thing for them to collide with (issue #34 found 10 such twins inside
    # one finance pool). So: no exclusion.
    bank_hashes = load_bank_hashes()
    bank_stems = load_bank_stems()
    part_hashes: Dict[str, str] = {}
    part_stems: Dict[str, str] = {}

    # Batch-wide, up front: the metric is per item and needs no cross-item context,
    # but computing it once keeps it off the per-item path.
    pulls = stem_pull(items)
    tell_rows: Dict[str, List[str]] = {}
    scope_rows: set = set()
    elim_rows: set = set()
    label_rows: set = set()
    div_rows: Dict[str, Dict] = {}
    meta_rows: Dict[str, List[str]] = {}

    for q in items:
        cand = q.get("cand_id")
        hard: List[str] = []
        soft: List[str] = []
        # Findings this row EARNED FROM ITS OWN ASSIGNMENT rather than from anything
        # the author did (#139). Reported, never counted as work -- see the
        # LADDER_HEADROOM_CH block.
        notes: List[str] = []
        # Read once, up here, because the option-tell block below runs for every
        # row and not just the ones that reach the payload comparison.
        opts = q.get("options") or {}

        spec = by_cand.get(cand)
        if spec is None:
            hard.append(f"cand_id '{cand}' is not in the payload")
        else:
            seen_cand[cand] += 1
            if seen_cand[cand] > 1:
                hard.append(f"cand_id '{cand}' returned {seen_cand[cand]} times")

        # The assembler's own gate, run here so nothing is a surprise at assembly.
        a_hard, a_soft = check_question(q, require_difficulty=True)
        hard += a_hard
        # A ratio soft the row's own AIM ladder designed is not a finding about this
        # author (#139). It moves to `notes` rather than vanishing: the assembler will
        # still report it, and if the ladder later moves, this line is where the
        # contradiction is visible. Only the two RATIO softs are ever eligible -- the
        # 2.2x drop and the >=20ch margin are unreachable from any shipped rung.
        caused = (assignment_caused_softs(spec, opts,
                                          str(q.get("answer", "")).strip().upper())
                  if spec is not None else set())
        for msg in a_soft:
            hit = next((m for m in caused if m in msg), None)
            if hit is None:
                soft.append(msg)
            else:
                notes.append(f"{msg} — ASSIGNMENT-CAUSED, not a repair candidate: the "
                             f"AIM ladder's own targets sit within {LADDER_HEADROOM_CH}ch "
                             f"of this threshold and the key hit its target")

        if spec is not None and not a_hard:
            ans = str(q.get("answer", "")).strip().upper()
            if ans != spec["answer_letter"]:
                hard.append(f"answer '{ans}' != assigned letter '{spec['answer_letter']}'")
            if q.get("difficulty") != spec["difficulty"]:
                # Before the referee runs, a tier mismatch means the author ignored
                # the assignment. After it runs, a mismatch is the POINT: "the
                # payload requests a tier; the referee decides what landed"
                # (author_pool.py). A demotion is the honest outcome the whole
                # hard-tier method depends on, so --post-referee downgrades this to
                # a note rather than forcing the tag back up to fill a quota.
                msg = (f"difficulty '{q.get('difficulty')}' != requested "
                       f"'{spec['difficulty']}'")
                (soft if post_referee else hard).append(
                    msg + (" (refereed)" if post_referee else ""))
            if q.get("performanceIndicator") != spec["performanceIndicator"]:
                hard.append("performanceIndicator was rewritten away from the assignment")
            if q.get("instructionalArea") != spec["instructionalArea"]:
                hard.append("instructionalArea was rewritten away from the assignment")

            if ans in OPTION_KEYS and set(opts) == set(OPTION_KEYS):
                rank, tied = observed_rank(opts, ans)
                # A payload built with `build_area.py --free-rank` carries no per-item
                # rank or per-option target: rule 12(b)'s real target is the BATCH
                # key-is-longest rate, and constraining every item to an exact rank
                # costs full re-authors when the author misses (§10-3 chunk 7: 15 of 21
                # easy items missed, whole batch rewritten). Under --free-rank the band
                # is still enforced and the aggregate is reported below, so the excess
                # key-longest items can be repaired individually instead.
                if "key_length_rank" in spec:
                    if rank != spec["key_length_rank"]:
                        hard.append(f"key_length_rank {rank} != assigned "
                                    f"{spec['key_length_rank']}")
                    elif tied:
                        soft.append(f"{tied} distractor(s) tie the key's length "
                                    f"(counts as 'among the longest')")
                elif "longest_letter" in spec:
                    # The bit restated as an assignment (build_area.longest_letters).
                    # Report it the same way as the letter rule so a miss is legible
                    # as a missed ASSIGNMENT. Still soft, for the reason below: a few
                    # characters must not bounce an otherwise shippable batch.
                    lens = {k: len(str(opts[k]).strip()) for k in OPTION_KEYS}
                    want = spec["longest_letter"]
                    winners = [k for k, n in lens.items() if n == max(lens.values())]
                    if winners != [want]:
                        if want in winners:
                            soft.append(
                                f"option {want} ties for longest with "
                                f"{', '.join(k for k in winners if k != want)} "
                                f"— assigned LONGEST={want}")
                        else:
                            soft.append(
                                f"longest option is {'/'.join(winners)} "
                                f"({max(lens.values())}ch), but this row was assigned "
                                f"LONGEST={want} ({lens[want]}ch)"
                                + (" — repair candidate" if want != ans and ans in winners
                                   else ""))
                elif rank == 1:
                    # --free-rank rows carry `key_may_be_longest` instead of a rank
                    # (build_area.key_longest_flags). False means the author was told
                    # to put at least one distractor at or above the key, so a rank-1
                    # here is a missed ASSIGNMENT, not just an unlucky draw -- and it
                    # is the batch's whole key-longest budget being overspent. Still
                    # soft: length is statistical ([[length-tell-tolerance]]) and a
                    # hard fail would bounce a shippable batch over a few characters.
                    if spec.get("key_may_be_longest") is False:
                        soft.append("key is the longest option, but this row was "
                                    "assigned key_may_be_longest=false (a distractor "
                                    "should be >= the key) — repair candidate")
                    else:
                        soft.append("key is the longest option (allowed on this row)")

                lo, hi = spec["option_length_band"]
                for k in OPTION_KEYS:
                    n = len(str(opts[k]).strip())
                    if n < lo - BAND_TOLERANCE or n > hi + BAND_TOLERANCE:
                        soft.append(f"option {k} is {n}ch, outside band {lo}-{hi}")

                key_len = len(str(opts[ans]).strip())
                if "key_target_len" in spec and \
                        abs(key_len - spec["key_target_len"]) > TARGET_TOLERANCE:
                    soft.append(f"key is {key_len}ch vs target {spec['key_target_len']}")

                gap, holder = top_gap(opts)
                if "max_top_gap" in spec and gap > spec["max_top_gap"]:
                    soft.append(f"top gap {gap}ch (option {holder}) over the "
                                f"{spec['max_top_gap']}ch cap")

        # Dedup -- front-running the assembler's drop so a collision is re-authored
        # here rather than silently vanishing at assembly.
        if not a_hard:
            ch, sh = content_hash(q), stem_hash(q)
            if ch in bank_hashes:
                hard.append("content-hash collision with the committed bank")
            if ch in part_hashes:
                hard.append(f"content-hash collision with '{part_hashes[ch]}' in this part")
            part_hashes.setdefault(ch, cand or "?")
            twins = bank_stems.get(sh, [])
            same_slice = [t for t in twins if t.get("cluster") == q.get("cluster")
                          and t.get("level") == q.get("level")]
            if same_slice:
                hard.append(f"stem collision with committed {same_slice[0].get('id')} "
                            f"(same cluster x level — a hard drop at assembly)")
            elif twins:
                soft.append(f"stem twin of {twins[0].get('id')} in another "
                            f"cluster x level (not co-servable)")
            if sh in part_stems:
                hard.append(f"stem collision with '{part_stems[sh]}' in this part")
            part_stems.setdefault(sh, cand or "?")

        # Option tells -- soft, and NOT gated on `spec is not None and not a_hard`,
        # for the same reason the stem-pull block below is not (§10-8, f5c5c97): a
        # row that already fails hard is exactly the row a repair author is about to
        # be handed, so suppressing half its findings is how the repair ships the
        # other half. Nesting it there dropped the tell from the row's finding list
        # AND from `--list-option-tells` AND from `scope_rows`, so the summary line
        # lost its denominator too and read as "no computational rows" rather than
        # "1 of 1 flagged". `option_in_scope()` already requires four well-formed
        # options and three figures among them -- that is the whole precondition the
        # measurement has; the payload is not part of it, because this metric reads
        # the options against EACH OTHER and never against the assignment.
        tells = option_tells(opts)
        if tells:
            soft.extend(tells)
            tell_rows[cand] = tells
            if option_elimination(opts, str(q.get("answer", "")).strip().upper()):
                soft.append("ANSWERABLE BY ELIMINATION: two or more distractors "
                            "describe their own error and the key does not — cover "
                            "the stem and the row still solves")
                elim_rows.add(cand)
        if option_in_scope(opts):
            scope_rows.add(cand)

        # Label divergence -- the same defect measured without a phrase list, so a
        # reworded leak cannot read clean (issue #75). Two findings come out of it:
        # the flag itself, and the CONTEXT it gives a phrase hit. The phrase list is
        # per option and absolute; the rule is differential, so a row whose four
        # labels are parallel ("...divided by available rooms" on all four) hits the
        # regex four times while no option is distinguishable. Saying so on the row is
        # what keeps a repair author from being sent to break a sound item. Both
        # conditions are required and neither is enough alone: the note needs ALL FOUR
        # options to carry the phrase AND the labels to stay parallel, because §10-10's
        # H1 hit ", from" on all four and was still answerable 4 of 4 by reading -- what
        # made it pickable was that each option narrated a DIFFERENT method, which is
        # divergence. The tell itself is never withdrawn.
        #
        # The `answer` is passed for the third branch alone (#185), which asks
        # whether the ONE option that reads differently is the keyed one. Every
        # other reading here is deliberately blind to the key.
        div = label_divergence(opts, str(q.get("answer", "")).strip().upper())
        if div:
            label_rows.add(cand)
            if div["flagged"]:
                div_rows[cand] = div
                # ONE line per row, whichever branch fired: `finding_scope` adds
                # `options` for every gate line it cannot place (issue #77), and both
                # readings are the same repair -- make every label identical.
                #
                # The remainder branch (#153) states the LEFTOVERS, not the shared
                # fraction: on those rows `shared` is HIGH by construction (m0073 was
                # 33% common and still readable), so quoting it as "only 33% is
                # common" would hand the author the number that hid the defect. Its
                # option list also drops to any leftover at all, because a 1-word
                # clause beside a 4-word one is the same trailing-clause habit.
                #
                # The odd-one-out branch (#185) takes the same floor of 1 as the
                # remainder branch, and for a sharper reason: on `spread == 1` only
                # ONE option has any leftover at all, and on two of §10-16's four
                # rows that leftover is a single word. A floor of LABEL_UNIQUE_MIN
                # there would print a finding naming no option.
                floor = 1 if (div["remainder"] or div["odd_key"]) else LABEL_UNIQUE_MIN
                worst = [f"{k} ({len(v)}: {', '.join(v[:4])})"
                         for k, v in sorted(div["unique"].items(),
                                            key=lambda kv: -len(kv[1]))
                         if len(v) >= floor]
                if div["odd_key"]:
                    # Deliberately does NOT quote `shared`, on the remainder branch's
                    # precedent and more so: here a HIGH shared fraction is the three
                    # compliant options, so printing it would hand the author the
                    # number that hid the defect as though it were reassurance.
                    soft.append(
                        f"options do not describe the same quantity in the same words "
                        f"— three of the four labels carry no wording of their own and "
                        f"THE ODD ONE IS THE KEY: option {'; '.join(worst)}. Cover the "
                        f"stem and the row still solves — pick the option that reads "
                        f"differently. Make every label identical and let only the "
                        f"number differ")
                elif div["remainder"]:
                    soft.append(
                        f"options do not describe the same quantity in the same words "
                        f"— they share a label ({div['shared']:.0%} of the wording is "
                        f"common to all four) and are then told apart by what trails "
                        f"it: option {'; '.join(worst)}. Delete the trailing clauses; "
                        f"make every label identical and let only the number differ")
                else:
                    soft.append(
                        f"options do not describe the same quantity in the same words "
                        f"(only {div['shared']:.0%} of the label wording is common to "
                        f"all four; option {'; '.join(worst)}) — an option a student "
                        f"can tell apart by reading; make every label identical and "
                        f"let only the number differ")
            elif len(tells) == len(OPTION_KEYS):
                soft.append(
                    f"...though ALL FOUR options carry that phrase and their labels "
                    f"stay parallel ({div['shared']:.0%} of the wording is common to "
                    f"all four), so it is shared vocabulary and singles no option out "
                    f"— there is no one option here to hand a repair author")

        # Stem pull -- soft, and named so the fix is obvious: the repair is to stop
        # the STEM naming what the key names, never to shorten the key (the key is
        # the one option that must stay precisely true).
        #
        # NOT gated on `not a_hard`, and that was a real bug (§10-8). A row can carry
        # BOTH a length giveaway and a stem pull -- §10-5's e0017 did -- and gating
        # this on a_hard dropped the pull from the row's finding list while the
        # --list-stem-pull section below still named it, so the two disagreed. The
        # repair prompt builds its per-row instructions from the finding list, so the
        # author was told to fix the giveaway and never told about the pull, with and
        # without --fail-only; the missing half had to be re-added by hand. A hard
        # finding elsewhere on the row does not invalidate the measurement -- an
        # unusable stem/answer is already skipped by stem_pull() itself, so
        # `pull is not None` is the whole guard this needs.
        pull = pulls.get(cand)
        if pull is not None:
            soft.append(
                f"stem pulls toward the key (differential +{pull['differential']:.3f} "
                f"vs bank p99 +{BANK_P99_DIFFERENTIAL:.3f}, stem/key overlap "
                f"{pull['jaccard_stem_key']:.2f}) — the stem may be naming what the "
                f"key names; rewrite the STEM, not the key")

        # Stem meta-exclusion -- soft, on the same terms as the three above and for
        # the same §10-8 reason: measured on every returned row, never nested under
        # a hard-pass. Named with the fix in the finding, because the wrong fix
        # (delete the clause and restore the ambiguity) is the obvious one.
        # ONE finding line, not one per shape. build_repair_prompt derives a row's
        # scope from its gate lines and adds `options` for every line it cannot
        # place (issue #77), so a second, unprefixed guidance line would silently
        # widen a stem repair into an option repair. The shapes ride inside the one
        # line that STEM_FINDINGS can match.
        metas = stem_meta_exclusion(q.get("question", ""))
        if metas:
            meta_rows[cand] = metas
            soft.append(
                "stem meta-exclusion — " + "; ".join(metas) + " — the stem may be "
                "telling the READER to disregard an option instead of stating a fact "
                "that rules it out. Delete the clause: if no FACT about the scenario "
                "changed, it was never a commitment to a reading — put in its place a "
                "scenario fact that makes the rival option wrong on the merits")

        results.append({"cand_id": cand, "hard": hard, "soft": soft, "notes": notes,
                        "pi": q.get("performanceIndicator"),
                        "area": q.get("instructionalArea"),
                        "difficulty": q.get("difficulty"),
                        "stem_pull": (round(pull["differential"], 4)
                                      if pull is not None else None),
                        "option_tells": tell_rows.get(cand),
                        "option_scope": cand in scope_rows,
                        "option_elimination": cand in elim_rows,
                        "option_label_row": cand in label_rows,
                        "option_label_shared": (round(div["shared"], 3)
                                                if div else None),
                        "option_divergence": cand in div_rows,
                        # Which branch fired (#153). Recorded rather than re-derived,
                        # because `shared` alone no longer says: a remainder row is
                        # HIGH-shared and flagged, which reads as a contradiction in
                        # the listing unless the branch is named beside it.
                        "option_label_remainder": bool(div and div.get("remainder")),
                        "option_label_odd_key": bool(div and div.get("odd_key")),
                        "stem_meta": meta_rows.get(cand),
                        "part": q.get("_part")})

    missing = [c for c in by_cand if seen_cand[c] == 0]
    return {"results": results, "missing": missing, "requested": len(by_cand),
            "returned": len(items)}


def key_longest_scope(offenders: List[tuple], longest: int, batch_size: int,
                      target_rate: float, min_margin: Optional[int]
                      ) -> tuple:
    """Which key-is-longest rows `--list-key-longest` hands back, and the rate budget.

    `offenders` is `(margin, cand_id, answer, key_len, runner_len)` per row whose key
    is longest; `margin` is key minus the longest distractor, which IS plan 05 §5a's
    decisive quantity. Returns `(scoped, budget)`, worst margin first.

    TWO selectors, unioned -- they answer different questions and issue #93 was the
    gate only asking the first:

      * the RATE budget, `longest - target_rate * batch_size`, which asks "how many
        rows must go for this BATCH to read acceptable". It is a distribution repair.
      * the MARGIN floor, every row at or above `min_margin`, which asks "which
        individual ROWS are a tell on their own". It is a row repair.

    A chunk already under `target_rate` gets budget 0, so before the floor existed a
    +29ch key shipped silently as long as its neighbours were tame (§10-11 chunks 3
    and 7, both budget 0, both carrying a decisive row). The floor is opt-in: with
    `min_margin` None this is exactly the old rate-only behaviour.

    Dedup is by `cand_id`, which is safe HERE and only here: `check_part` hard-fails a
    duplicated or payload-absent cand_id, and `offenders` is built from `ok_items`, so
    every id in it is present and unique. Do not lift this keying somewhere the rows
    have not been through that gate -- cand_ids collide across chunks (§10-11).
    """
    budget = max(0, longest - int(target_rate * batch_size))
    by_margin = sorted(offenders, key=lambda o: o[0], reverse=True)
    rate_scope = by_margin[:budget]
    floor_scope = ([o for o in by_margin if o[0] >= min_margin]
                   if min_margin is not None else [])
    scoped_by_id = {o[1]: o for o in rate_scope + floor_scope}
    scoped = sorted(scoped_by_id.values(), key=lambda o: o[0], reverse=True)
    return scoped, budget


def _print_repair_scope(cand_ids: List[str], part_of: Dict[str, str],
                        batch_size: int) -> None:
    """Name the FILES a repair touches, and how much of the batch that is.

    Plan 10-2 §2d priced the in-context repair at 239.3k -- worse than the ~90-100k
    fresh agent the cut was supposed to avoid -- and named the mechanism: the author
    "re-emitted all three part files in full (82 items, ~24k of output) because a
    part file is a JSON array that cannot be patched in place", taking 13 tool calls
    to re-read its own work and copy untouched items through.
    Handing back a flat list of cand_ids is what forces that. Naming the files (and
    only them) lets the author re-emit one group of ~31 instead of a whole chunk,
    and `apply_repair.py` removes even that: the author writes ONLY the fixed items
    to an overlay and the overlay is merged deterministically.
    """
    by_part: Dict[str, List[str]] = {}
    for cid in cand_ids:
        by_part.setdefault(part_of.get(cid) or "<unknown>", []).append(cid)
    total = len(cand_ids)
    print(f"  repair scope: {total} item(s) in {len(by_part)} part file(s) "
          f"of a {batch_size}-item batch")
    for path, cids in sorted(by_part.items()):
        print(f"      {path}  ({len(cids)}): {', '.join(cids)}")
    print("      hand the author ONLY these ids; it writes ONLY the fixed items to an "
          "overlay\n      file, then: python apply_repair.py --overlay OVERLAY.json "
          "--part <the file(s) above>")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Gate an authored part against its payload + the committed bank.")
    ap.add_argument("--payload", required=True, help="build_area.py --out JSON")
    ap.add_argument("--part", required=True, nargs="+", help="authored part JSON(s)")
    ap.add_argument("--post-referee", action="store_true",
                    help="the difficulty referee has already run: a tier that differs "
                         "from the requested one is a demotion, not an author error")
    ap.add_argument("--partial", action="store_true",
                    help="an in-progress batch: do not fail on payload candidates "
                         "that have not been authored yet")
    ap.add_argument("--list-key-longest", action="store_true",
                    help="name the items to hand back for a length repair so the batch "
                         "reaches --target-rate, worst key-vs-runner-up margin first. "
                         "The companion to `build_area.py --free-rank`.")
    ap.add_argument("--target-rate", type=float, default=0.25,
                    help="key-is-longest rate --list-key-longest repairs down to "
                         "(default 0.25 = rule 12(b)'s balanced quarter)")
    ap.add_argument("--min-margin", type=int, default=None,
                    help="with --list-key-longest, also list every row whose key "
                         "stands this many chars clear of every distractor, regardless "
                         "of --target-rate (20 = plan 05 §5a's decisive band)")
    ap.add_argument("--list-option-tells", action="store_true",
                    help="name the computational rows whose options narrate their own "
                         "derivation or flag the wrong input they used — the defect two "
                         "raters and two blind solvers caught in §10-10 and no gate "
                         "could. A PHRASE LIST: it names rows written in wording already "
                         "seen, so an empty list is not a clean batch (issue #75). Pair "
                         "it with --list-option-divergence.")
    ap.add_argument("--list-option-divergence", action="store_true",
                    help="name the rows whose four option LABELS differ in kind, least "
                         "shared wording first — the vocabulary-free half of the option "
                         "leak, so it fires on rewordings --list-option-tells cannot "
                         "see (issue #75). Soft and noisy: a quarter of the bank trips it.")
    ap.add_argument("--list-stem-pull", action="store_true",
                    help="name the rows whose stem pulls toward the key (§10-4 finding "
                         "3's hand-fixed defect), worst pull first, scoped to the part "
                         "files that hold them")
    ap.add_argument("--list-stem-meta", action="store_true",
                    help="name the rows whose stem tells the READER to disregard an "
                         "option instead of stating a scenario fact that rules it out "
                         "— what an ambiguity repair manufactures if left to itself "
                         "(issue #131, §10-13's 5 of 5). A PHRASE LIST over stems, and "
                         "a noisy one: read the hits, do not repair to the rate.")
    ap.add_argument("--list-longest-miss", action="store_true",
                    help="name the rows whose longest option is not at the assigned "
                         "LONGEST= letter, biggest shortfall first, scoped to the part "
                         "files that hold them. The rate is a slice bar (~97%%) but "
                         "nothing named the rows before §10-7. Ties count as misses.")
    ap.add_argument("--json", default=None, help="write the full report here")
    ap.add_argument("--quiet", action="store_true", help="only print failures")
    args = ap.parse_args()
    if args.min_margin is not None and not args.list_key_longest:
        ap.error("--min-margin requires --list-key-longest")
    if args.min_margin is not None and args.min_margin < 0:
        ap.error("--min-margin must be non-negative")

    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    items: List[Dict] = []
    for p in args.part:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise SystemExit(f"{p}: expected a JSON array of questions")
        # Stamp the source file so every repair list can be scoped to the files it
        # actually touches (plan 10-2 §2d: the dominant cost of a repair is
        # re-emitting untouched items, and an author handed a flat list of cand_ids
        # re-read and re-wrote all three parts to find them). Stripped before the
        # part is ever written back -- see apply_repair.py.
        for q in data:
            q["_part"] = str(p)
        items.extend(data)

    report = check_part(payload, items, post_referee=args.post_referee)
    # cand_id -> the part file that holds it, stamped by check_part. Every repair list
    # scopes itself with this, so it is built once here rather than per list.
    part_of = {r["cand_id"]: r.get("part") for r in report["results"]}

    failed = [r for r in report["results"] if r["hard"]]
    softed = [r for r in report["results"] if r["soft"] and not r["hard"]]
    noted = [r for r in report["results"] if r.get("notes")]

    for r in failed:
        print(f"  FAIL  {r['cand_id']}  [{r['difficulty']}] {r['pi']}")
        for msg in r["hard"]:
            print(f"          hard: {msg}")
        for msg in r["soft"]:
            print(f"          soft: {msg}")
    if not args.quiet:
        for r in softed:
            print(f"  soft  {r['cand_id']}  [{r['difficulty']}] {r['pi']}")
            for msg in r["soft"]:
                print(f"          {msg}")
        # Printed AFTER the softs and labelled differently, because the one thing a
        # note must not do is read like a work order -- that is the defect (#139).
        for r in noted:
            print(f"  note  {r['cand_id']}  [{r['difficulty']}] {r['pi']}")
            for msg in r["notes"]:
                print(f"          {msg}")

    if report["missing"] and not args.partial:
        print(f"\n  MISSING {len(report['missing'])} requested candidate(s):")
        for c in report["missing"][:20]:
            print(f"          {c}")
        if len(report["missing"]) > 20:
            print(f"          ... and {len(report['missing']) - 20} more")
    elif report["missing"]:
        print(f"\n  ({len(report['missing'])} candidate(s) not yet authored — --partial)")

    n = report["returned"]
    print(f"\n  requested {report['requested']} · returned {n} · "
          f"passed {n - len(failed)} · FAILED {len(failed)} · "
          f"soft-only {len(softed)}"
          + (f" · assignment-caused notes {len(noted)}" if noted else ""))

    # The tell the whole pipeline is measured on, reported up front so a batch that
    # drifts is caught before audit_tells sees it at slice scale.
    ok_items = [q for q, r in zip(items, report["results"]) if not r["hard"]]
    longest = 0
    offenders: List[tuple] = []
    for q in ok_items:
        opts = q.get("options") or {}
        ans = str(q.get("answer", "")).strip().upper()
        if ans in OPTION_KEYS and set(opts) == set(OPTION_KEYS):
            key = len(str(opts[ans]).strip())
            runner = max(len(str(opts[k]).strip())
                         for k in OPTION_KEYS if k != ans)
            if key >= max(len(str(opts[k]).strip()) for k in OPTION_KEYS):
                longest += 1
                offenders.append((key - runner, q.get("cand_id"), ans, key, runner))
    if ok_items:
        rate = 100.0 * longest / len(ok_items)
        decisive = [o for o in offenders if o[0] >= DECISIVE_MARGIN]
        # Printed as a RATE over the whole batch, like every other soft instrument in
        # this gate, because "9 decisive" against a "1.3%" baseline is two different
        # quantities and the reader has to divide by hand to compare them. The two
        # denominators still are not the same population and the line says so: the
        # baseline counts COMMITTED rows, which are post-repair, while this counts the
        # candidates in front of you, which are not. A chunk reading above 1.3% before
        # its repair pass is ordinary; what to act on is the named rows below, not the
        # ratio. [[length-tell-tolerance]] — over-scrubbing is its own defect.
        dec_rate = 100.0 * len(decisive) / len(ok_items)
        print(f"  key-is-longest {longest}/{len(ok_items)} "
              f"({rate:.1f}%) — slice bar is 35%")
        print(f"      of those, {len(decisive)} decisive (key >={DECISIVE_MARGIN}ch clear of "
              f"every distractor): {len(decisive)}/{len(ok_items)} ({dec_rate:.1f}%) of this "
              "batch, against 1.3% of the committed bank")
        # Compliance with the per-row assignment, when the payload carries one. This
        # is the number that says whether the flag WORKED, as distinct from whether
        # the batch happened to land under the bar.
        assigned = [p for p in payload if "key_may_be_longest" in p]
        if assigned:
            allowed = sum(1 for p in assigned if p["key_may_be_longest"])
            by_cand = {q.get("cand_id"): q for q in ok_items}
            broke = [p["cand_id"] for p in assigned
                     if p["key_may_be_longest"] is False
                     and p["cand_id"] in by_cand
                     and any(o[1] == p["cand_id"] for o in offenders)]
            print(f"  key_may_be_longest assigned on {allowed}/{len(assigned)} row(s) "
                  f"· {len(broke)} row(s) assigned false came back key-longest")
        # LONGEST=<letter> compliance -- the assignment form of the same constraint.
        # Read this next to the letter rule's compliance: they are the same KIND of
        # instruction, so a gap between them is the prose-vs-assignment effect
        # (summary 05 §3) and not an author being careless.
        lspec = [p for p in payload if "longest_letter" in p]
        if lspec:
            by_cand = {q.get("cand_id"): q for q in ok_items}
            hit = miss = 0
            # (cand_id, assigned, actual-letters, assigned-len, max-len) for --list-longest-miss
            longest_misses: List[tuple] = []
            for p in lspec:
                q = by_cand.get(p["cand_id"])
                if not q:
                    continue
                opts = q.get("options") or {}
                if set(opts) != set(OPTION_KEYS):
                    continue
                lens = {k: len(str(opts[k]).strip()) for k in OPTION_KEYS}
                top = [k for k, n in lens.items() if n == max(lens.values())]
                want = p["longest_letter"]
                if top == [want]:
                    hit += 1
                else:
                    miss += 1
                    longest_misses.append((p["cand_id"], want, "".join(sorted(top)),
                                           lens.get(want, 0), max(lens.values())))
            if hit + miss:
                print(f"  LONGEST=<letter> honoured on {hit}/{hit + miss} row(s) "
                      f"({100.0 * hit / (hit + miss):.1f}%) · {miss} miss(es)")
            # The companion to --list-key-longest. The RATE has always been printed and is
            # a slice bar (~97%), but until §10-7 nothing named the offending rows, so a
            # repair scope for it had to be reconstructed by hand with a throwaway script.
            # A TIE counts as a miss here exactly as it does in the rate above -- that is
            # the difference between 7 and 8 on §10-7 chunk 1.
            if args.list_longest_miss and longest_misses:
                print(f"  LONGEST= misses: {len(longest_misses)} row(s) — lengthen the option "
                      f"at the ASSIGNED letter (a rank test, not a margin test):")
                for cid, want, top, wlen, mlen in sorted(
                        longest_misses, key=lambda r: r[4] - r[3], reverse=True):
                    tie = " (ties)" if want in top else ""
                    print(f"      {cid}  assigned {want} ({wlen}ch) but longest is "
                          f"{top} ({mlen}ch){tie}")
                _print_repair_scope([m[0] for m in longest_misses], part_of, len(ok_items))
        # STRICT band drift — informational, never a pass/fail input. The soft findings
        # above apply BAND_TOLERANCE; this line applies the brief's literal band, so the
        # two together say how much of the batch is living in the tolerance. Chunk 3
        # finished with zero band findings while 21 options sat outside 15-55, and the
        # only way anyone learned that was by measuring the parts by hand.
        strict_out = strict_keys = 0
        by_cand_all = {q.get("cand_id"): q for q in ok_items}
        for p in payload:
            q = by_cand_all.get(p["cand_id"])
            if not q or "option_length_band" not in p:
                continue
            opts = q.get("options") or {}
            if set(opts) != set(OPTION_KEYS):
                continue
            lo, hi = p["option_length_band"]
            ans = str(q.get("answer", "")).strip().upper()
            for k in OPTION_KEYS:
                n = len(str(opts[k]).strip())
                if n < lo or n > hi:
                    strict_out += 1
                    if k == ans and n > hi:
                        strict_keys += 1
        if strict_out:
            print(f"  band (strict, no tolerance): {strict_out} option(s) outside the "
                  f"assigned band, {strict_keys} of them a KEY over the ceiling "
                  f"— informational, the gate enforces ±{BAND_TOLERANCE}ch")

        # The repair-targeting list for a --free-rank batch: which items to hand back,
        # worst margin first. Repairing the excess is cheaper than constraining every
        # item to an exact rank up front (see build_area.py --free-rank).
        if args.list_key_longest and offenders:
            scoped, budget = key_longest_scope(
                offenders, longest, len(ok_items), args.target_rate, args.min_margin)
            floor_note = (f" plus every margin >= {args.min_margin}ch"
                          if args.min_margin is not None else "")
            print(f"  repair {len(scoped)} item(s): {budget} to reach "
                  f"{args.target_rate:.0%}{floor_note} (worst margin first):")
            for margin, cid, ans, key, runner in scoped:
                print(f"      {cid}  key {ans} {key}ch vs runner-up {runner}ch "
                      f"(+{margin})")
            _print_repair_scope([c for _, c, _, _, _ in scoped], part_of, len(ok_items))

    # STEM PULL -- the batch line, then the repair list. Printed after the length
    # numbers because it is the same shape of finding: a statistical flag whose
    # unit of action is a handful of named rows, not a pass/fail verdict.
    pulled = [r for r in report["results"] if r.get("stem_pull") is not None]
    if report["results"]:
        # Denominator is every row RETURNED, not just the ones that passed: the
        # metric reads the item's own text and does not care whether some other
        # check failed it (post-assembly, every row hard-fails on its own committed
        # twin and ok_items is empty -- see the module docstring).
        print(f"  stem pull: {len(pulled)} row(s) over differential "
              f"+{STEM_PULL_DIFFERENTIAL} "
              f"({100.0 * len(pulled) / len(report['results']):.1f}%) "
              f"— bank baseline is 1.7%")
    if args.list_stem_pull and pulled:
        print("  rewrite the STEM on these (worst pull first) — never the key:")
        for r in sorted(pulled, key=lambda r: -r["stem_pull"]):
            print(f"      {r['cand_id']}  differential +{r['stem_pull']:.3f}  {r['pi']}")
        _print_repair_scope([r["cand_id"] for r in pulled],
                            {r["cand_id"]: r.get("part") for r in report["results"]},
                            len(report["results"]))

    # STEM META-EXCLUSION -- the other stem finding, printed next to stem pull
    # because they are the two ways a stem can hand the item away: pull names what
    # the KEY names, this names what a DISTRACTOR names (issue #131).
    metaed = [r for r in report["results"] if r.get("stem_meta")]
    if report["results"]:
        print(f"  stem meta-exclusion: {len(metaed)} row(s) "
              f"({100.0 * len(metaed) / len(report['results']):.1f}%) — bank "
              f"baseline {BANK_STEM_META_RATE:.2f}%; the stem may be telling the "
              f"READER to\n      disregard an option instead of stating a fact that "
              f"rules it out. PHRASE LIST, so 0.0%\n      means 'not in the wording "
              f"we already know' — and the hits are a real mix, so read\n      them "
              f"as candidates, never as a work order.")
    if args.list_stem_meta and metaed:
        print("  read the STEM on these — delete the clause, and if no scenario fact "
              "changed,\n  replace it with one that makes the rival option wrong on "
              "the merits:")
        for r in metaed:
            print(f"      {r['cand_id']}  {r['pi']}")
            for t in r["stem_meta"]:
                print(f"          {t}")
        _print_repair_scope([r["cand_id"] for r in metaed],
                            {r["cand_id"]: r.get("part") for r in report["results"]},
                            len(report["results"]))

    # OPTION TELLS -- same shape again: a rate, then the named rows. Scoped to
    # computational rows, so the denominator is those rows and not the batch --
    # but it counts every computational row RETURNED, passing or failing, exactly
    # as the stem-pull denominator does. `scope_rows` used to be filled inside the
    # payload block, so a hard-failing row left the denominator too and a batch
    # whose only computational row failed printed nothing at all (issue #72).
    telled = [r for r in report["results"] if r.get("option_tells")]
    elim = [r for r in telled if r.get("option_elimination")]
    scope_n = sum(1 for r in report["results"] if r.get("option_scope"))
    if scope_n:
        print(f"  option tells: {len(telled)} of {scope_n} computational row(s) "
              f"({100.0 * len(telled) / scope_n:.1f}%) — an option names its own "
              f"derivation, its wrong input, or its own mistake")
        # Printed even at zero, because zero is the number worth seeing: it says the
        # tells that ARE here at least cancel across the four options rather than
        # pointing at the key.
        print(f"      of those, {len(elim)} answerable by elimination "
              f"(>=2 distractors tell, key does not) — repair these first")
        # ...and the sentence that stops a zero being read as a pass (issue #75).
        # This line is the whole reason the number is trustworthy: it is a PHRASE
        # LIST, every entry of it lifted from a batch that had already shipped, so
        # it can only recognise the defect in the words it has already seen.
        print("      MEASURED BY PHRASE LIST, so 0 means 'not written in the wording "
              "we already know',\n      not 'no row leaks' — the defect is semantic "
              "and this instrument is lexical. Read\n      the options; see the "
              "coverage map in this file's docstring.")
    # LABEL DIVERGENCE -- the vocabulary-free half of the same question, on its own
    # (tighter) scope, with the bank baseline printed beside it because the rate is
    # only meaningful against that baseline.
    label_n = sum(1 for r in report["results"] if r.get("option_label_row"))
    diverged = [r for r in report["results"] if r.get("option_divergence")]
    if label_n:
        rem = [r for r in diverged if r.get("option_label_remainder")]
        odd = [r for r in diverged if r.get("option_label_odd_key")]
        print(f"  label divergence: {len(diverged)} of {label_n} label row(s) "
              f"({100.0 * len(diverged) / label_n:.1f}%) — bank baseline "
              f"{BANK_LABEL_DIVERGENCE_RATE:.1f}%; the four options do not describe "
              f"the same\n      quantity in the same words. Soft and noisy: read the "
              f"RATE against that baseline,\n      not the row count as a work order.")
        # Split out, because the three branches ask different questions and a reader
        # who sees only the total cannot tell which one is carrying it (#153, #185).
        if rem:
            print(f"      of those, {len(rem)} share a label and are told apart by a "
                  f"TRAILING CLAUSE — the shape\n      §10-14 shipped 12 of while this "
                  f"instrument read 2.5x cleaner than the bank")
        if odd:
            print(f"      of those, {len(odd)} have THREE IDENTICAL LABELS AND A "
                  f"DIVERGENT KEY — cover the stem and\n      pick the odd one out. "
                  f"§10-16 shipped 4 while this instrument read ABOVE baseline;\n"
                  f"      a rate above baseline is no more a coverage statement than "
                  f"0.0% is")
        # ...and the limit, on the same terms as the phrase list's caveat above: a
        # clause of one or two content words is under every readable threshold.
        print("      A ONE- OR TWO-WORD trailing clause is BELOW this instrument "
              "('...the budget on the\n      draft'): 3 of §10-14's 12 known rows are "
              "out of reach. Read the options.")
    if args.list_option_divergence and diverged:
        print("  labels differ in kind on these (least shared wording first) — make "
              "all four\n  labels identical and let only the number differ:")
        for r in sorted(diverged, key=lambda r: r.get("option_label_shared") or 0.0):
            # The branch, named on the row. An odd-one-out row sorts LAST here (its
            # shared fraction is high by construction) and reads as a contradiction
            # without the tag -- "shared 0.75" beside a divergence finding.
            tag = ("  <== ODD ONE OUT, AND IT IS THE KEY"
                   if r.get("option_label_odd_key")
                   else "  <== TRAILING CLAUSE" if r.get("option_label_remainder")
                   else "")
            print(f"      {r['cand_id']}  shared {r['option_label_shared']:.2f}  "
                  f"{r['pi']}{tag}")
        _print_repair_scope([r["cand_id"] for r in diverged],
                            {r["cand_id"]: r.get("part") for r in report["results"]},
                            len(report["results"]))
    if args.list_option_tells and telled:
        print("  rewrite the OPTIONS on these — say WHAT the number is, never how "
              "it was produced, and keep all four labels identical\n  (these are the "
              "rows that matched a KNOWN phrase; --list-option-divergence names the "
              "rest):")
        for r in sorted(telled, key=lambda r: not r.get("option_elimination")):
            flag = "  <== ELIMINABLE" if r.get("option_elimination") else ""
            print(f"      {r['cand_id']}  {r['pi']}{flag}")
            for t in r["option_tells"]:
                print(f"          {t}")
        _print_repair_scope([r["cand_id"] for r in telled],
                            {r["cand_id"]: r.get("part") for r in report["results"]},
                            len(report["results"]))

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  report -> {out}")

    raise SystemExit(1 if (failed or (report["missing"] and not args.partial)) else 0)


if __name__ == "__main__":
    main()
