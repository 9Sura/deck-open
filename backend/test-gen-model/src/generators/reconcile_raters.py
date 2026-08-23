#!/usr/bin/env python3
"""Read the two difficulty raters against each other. No model.

WHY THIS EXISTS -- issue #173, measured on §10-14
--------------------------------------------------
Plan-10's headline quality number for a hard batch is "held hard, never authored hard".
It comes from two Sonnet raters, and until #173 two things were missing at once: the
raters were never told what "hard" means (`build_hard_verify.py` stage 1 wrote a
two-line instruction and every slice plan said only *"run 2 Sonnet raters. Reconcile.
Both-medium => demote, honestly."*), and their returns were prose in two agent replies
that nothing on disk ever held. So the number could not be reproduced and its spread
could not be seen.

§10-14, 21 rows, two raters with the same task text, run independently:

    rater      HARD   MEDIUM   DEFECTIVE   agreed HARD with the other
    A            18        1           2                            3
    B             3       16           2                            3

Both re-derived all 21 items and both found the arithmetic sound. NOT a correctness
disagreement -- a rubric disagreement, and total. A counted DEPENDENT OPERATIONS; B
counted OPERATIONS A COMPETENT DISTRICT COMPETITOR ACTUALLY PERFORMS, discounting
drilled chains. Both defensible. The published number, 16 of 21, came from breaking 15
ties on a blind solver's side-question; rater B's own reading is 3 of 21.

TWO HALVES, AND NEITHER SUBSUMES THE OTHER -- the same shape as #172 one instrument over:

  THE COMMITTED RUBRIC (`src/prompts/hard-referee.txt`, written into the referee set by
  build_hard_verify.py) removes the CAUSE. §10-10 measured a written "second operation"
  rule moving rater agreement 6-of-9 to 8-of-9 on a composition-matched batch. It cannot
  prove it worked, because a rubric is prose and two models can still read it apart.

  THIS FILE measures the RESIDUE. It reports the split as a first-class number beside the
  held count, so a number resting on a wide disagreement can never again be read as if it
  rested on a narrow one. It is mechanical, free, and cannot be forgotten.

THE DECISION THIS ENCODES -- publish held-with-split, do NOT mass-demote.
When the raters disagree on more rows than they agree are hard, plan-10 §4.6 now names
the case: report the split, keep the mechanically broken ties, and mark the number soft.
Demoting every disputed row would take §10-14 from 16 to 3 and discard fifteen
arithmetically sound items to fix a REPORTING problem. The number stands; what changes
is that it may never be published bare.

THREE CLASSES, SEPARATELY COUNTED, NEVER MERGED
------------------------------------------------
The #154 rule, for the reason it was written there: a merged count either hides a
defective item among routine disagreements or reads an ordinary split as a broken batch.

  1  VERDICT SPLIT (HARD vs MEDIUM)    -- the #173 signal. Every one of these rows is a
     tie somebody has to break, and before this tool the breaking was invisible.
     Adjudication-required: `--tiebreak-rule` states ONE rule and `--hold` names the rows
     it resolved to hard. Both are recorded and printed.

  2  DEFECTIVE NAMED BY EITHER RATER   -- a defect claim, not a difficulty judgement. One
     rater is not a majority (§10-11: an item shipped with its answer in its own stem,
     one rater caught it and the OTHER RATED IT HARD), so ONE naming is enough to stop
     the batch. Cleared per row with `--adjudicated id:reason`.

  3  RUBRIC DIVERGENCE                 -- the split rows where BOTH raters returned the
     same `skipping_lands_on` letter. They ran the mechanical test and got the same
     structural answer, then disagreed about the verdict anyway: that is a disagreement
     about the RUBRIC and nothing else, which is exactly what §10-14 was. Reported, never
     gating -- it is a diagnosis of the split, not a second finding about the items.

WHAT THIS DOES NOT DO. It does not decide which rater is right; that is the tie-break, and
it is a human's. It does not make two raters share a rubric -- prose cannot be enforced,
only measured. And it cannot detect two raters sharing a WRONG rubric: they agree, the
split is zero, and this file reports a clean batch. That blind spot is real and is why the
rubric is committed and diffable rather than merely written.

    python reconcile_raters.py --ids D/verify/referee-ids.json \\
        --rater D/verify/rater-01.json D/verify/rater-02.json \\
        --tiebreak-rule "blind solver 1's per-item 'two or more dependent operations?'" \\
        --hold cand-h0006 cand-h0009
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

# The shape the rater is asked for. `build_hard_verify.referee_head` asserts the committed
# prompt names every one of them -- the prompt and the parser are one contract, checked
# against each other (#139), not each against its own reasoning. Here the prompt is a FILE,
# so the check also catches an edit to the prompt that the parser was never told about.
RATER_FIELDS = ("cand_id", "verdict", "route", "second_operation", "skipping_lands_on",
                "note")
REQUIRED = ("cand_id", "verdict")
VERDICTS = ("HARD", "MEDIUM", "DEFECTIVE")
LETTERS = ("A", "B", "C", "D")
NONE_TOKENS = ("", "NONE", "N/A", "-", "NULL")

# The minimum a tie-break rule may say. §10-14 broke fifteen ties on one stated rule and
# the rule was never written down anywhere -- it had to be reconstructed from the summary.
MIN_RULE_CHARS = 20


def _red(s: str) -> str:
    return f"\033[31m{s}\033[0m"


def letter(value) -> str:
    """A returned option letter, normalised. `""` means the rater named no option.

    "no offered option is what you get by skipping this step" is the DECISIVE answer to
    the mechanical test, not a missing value, so `none` must round-trip to a non-letter
    rather than being coerced into one or refused.
    """
    s = str(value or "").strip().upper()
    return "" if s in NONE_TOKENS else s


def load_rater(path: Path, ids: List[str]) -> Dict[str, Dict]:
    """One rater's return, keyed by cand_id, verified against the referee set's ids.

    Refuses rather than resolves, for the reason #155 documented one tool over: a return
    whose rows have drifted is compared row-against-wrong-row, and acting on it repairs a
    sound item while shipping the defective one.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"  {path.name} is not valid JSON ({e}).\n"
                 f"    The rater is asked for a JSON array and nothing else; a return "
                 f"wrapped in prose\n    has to be unwrapped by hand before it is parsed, "
                 f"never parsed leniently.")
    if not isinstance(data, list):
        sys.exit(f"  {path.name} is not a JSON array of per-item objects")

    rows: Dict[str, Dict] = {}
    problems: List[str] = []
    for i, r in enumerate(data, start=1):
        if not isinstance(r, dict):
            problems.append(f"entry {i} is not an object")
            continue
        missing = [f for f in REQUIRED if f not in r]
        if missing:
            problems.append(f"entry {i} is missing {', '.join(missing)}")
            continue
        cid = str(r["cand_id"]).strip()
        if cid in rows:
            problems.append(f"{cid} is returned twice — one row, one verdict")
        rows[cid] = r

    unknown = [c for c in rows if c not in ids]
    absent = [c for c in ids if c not in rows]
    if unknown:
        problems.append(f"{len(unknown)} cand_id(s) are not in the referee set: "
                        + ", ".join(sorted(unknown)[:5]))
    if absent:
        problems.append(f"{len(absent)} item(s) of the referee set went unrated: "
                        + ", ".join(absent[:5]))
    for cid, r in rows.items():
        v = str(r.get("verdict", "")).strip().upper()
        if v not in VERDICTS:
            problems.append(f"{cid}: verdict {r.get('verdict')!r} is not one of "
                            f"{'/'.join(VERDICTS)} — a rater that declines to rate is not "
                            f"a datum, and low confidence is a note, not a MEDIUM")
        lands = letter(r.get("skipping_lands_on"))
        if lands and lands not in LETTERS:
            problems.append(f"{cid}: skipping_lands_on {r.get('skipping_lands_on')!r} is "
                            f"neither an option letter nor \"none\"")
    if problems:
        print(f"\n  {_red('FAIL')} {path.name} is not a usable rater return")
        for p in problems[:10]:
            print(f"    {p}")
        sys.exit(1)
    return rows


def verdict(row: Dict) -> str:
    return str(row.get("verdict", "")).strip().upper()


def parse_adjudicated(tokens: List[str]) -> Dict[str, str]:
    """`cand_id:reason` pairs. A bare id is refused — the reason IS the artifact.

    Same shape as reconcile_solvers' --adjudicated and build_repair_prompt's
    --scope-reason: an override that takes a bare flag records that somebody silenced a
    finding and nothing about why.
    """
    out: Dict[str, str] = {}
    for t in tokens:
        if ":" not in t:
            sys.exit(f"  --adjudicated {t!r} has no reason. Write it as "
                     f"`cand_id:why this row is settled` — a bare id records that a "
                     f"finding was silenced and nothing about why.")
        cid, reason = t.split(":", 1)
        if not reason.strip():
            sys.exit(f"  --adjudicated {t!r} has an empty reason")
        out[cid.strip()] = reason.strip()
    return out


def reconcile(ids: List[str], raters: List[Tuple[str, Dict[str, Dict]]]
              ) -> Tuple[List, List, List, Counter]:
    """The three classes, plus the verdict tally. Order follows the referee set."""
    split, defective, divergence = [], [], []
    tally: Counter = Counter()
    for cid in ids:
        verdicts = [(name, verdict(rows[cid])) for name, rows in raters]
        vs = {v for _, v in verdicts}
        if "DEFECTIVE" in vs:
            # A defect claim outranks a difficulty split: the row is not a tie to break,
            # it is an item somebody says is wrong. One naming is enough (§10-11).
            tally["defective"] += 1
            defective.append((cid, verdicts))
            continue
        if len(vs) > 1:
            tally["split"] += 1
            split.append((cid, verdicts))
            lands = [letter(rows[cid].get("skipping_lands_on")) for _, rows in raters]
            if len(set(lands)) == 1:
                divergence.append((cid, verdicts, lands[0],
                                   [(n, str(rows[cid].get("note", "")).strip())
                                    for n, rows in raters]))
        elif vs == {"HARD"}:
            tally["agreed_hard"] += 1
        else:
            tally["agreed_medium"] += 1
    return split, defective, divergence, tally


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Read the two difficulty raters against each other, and report the "
                    "split beside the held count.")
    ap.add_argument("--ids", required=True,
                    help="the sidecar written by build_hard_verify.py stage 1")
    ap.add_argument("--rater", required=True, nargs="+", metavar="JSON",
                    help="each rater's return, one file each. TWO OR MORE — a single "
                         "return has nothing to disagree with, which is the instrument")
    ap.add_argument("--tiebreak-rule", metavar="TEXT",
                    help="the ONE rule every class-1 tie was broken on, stated. Required "
                         "to --hold a split row; recorded and printed on every one")
    ap.add_argument("--hold", nargs="*", default=[], metavar="ID",
                    help="class-1 or class-2 rows that END UP HARD. A split row needs "
                         "--tiebreak-rule; a defective row needs --adjudicated too")
    ap.add_argument("--adjudicated", nargs="*", default=[], metavar="ID:REASON",
                    help="a class-2 row already settled, WITH ITS REASON. Recorded and "
                         "still printed; it only stops the exit code")
    args = ap.parse_args()

    if len(args.rater) < 2:
        sys.exit("  --rater takes TWO OR MORE returns.\n"
                 "    A held-hard count from ONE rater is that rater's rubric with no way "
                 "to see it\n    (#173). Two returns are the minimum that can disagree, "
                 "and the disagreement is\n    the number this tool exists to report.")

    meta = json.loads(Path(args.ids).read_text(encoding="utf-8"))
    ids: List[str] = meta["ids"]
    raters = [(Path(p).name, load_rater(Path(p), ids)) for p in args.rater]
    settled = parse_adjudicated(args.adjudicated)
    hold = list(dict.fromkeys(args.hold))

    split, defective, divergence, tally = reconcile(ids, raters)
    split_ids = {c for c, _ in split}
    defective_ids = {c for c, _ in defective}

    stray = [c for c in hold if c not in split_ids | defective_ids]
    if stray:
        sys.exit(f"  --hold names {len(stray)} row(s) that are not contested: "
                 f"{', '.join(stray[:5])}\n"
                 f"    A row both raters agreed is HARD is already held; naming it here "
                 f"records a\n    tie-break that never happened.")
    stray = sorted(set(settled) - defective_ids)
    if stray:
        sys.exit(f"  --adjudicated names {len(stray)} row(s) with no DEFECTIVE finding: "
                 f"{', '.join(stray[:5])}\n"
                 f"    A reason attached to a row nothing flagged is a record of nothing. "
                 f"A split row\n    is settled by --tiebreak-rule and --hold, not here.")
    if any(c in split_ids for c in hold) and not args.tiebreak_rule:
        sys.exit("  --hold names a SPLIT row and no --tiebreak-rule was given.\n"
                 "    §10-14 broke fifteen ties on one stated rule and wrote it down "
                 "nowhere; it had\n    to be reconstructed from the summary afterwards. "
                 "State the rule — it is the\n    artifact, and it is what makes the held "
                 "number readable by anyone but you.")
    if args.tiebreak_rule and len(args.tiebreak_rule.strip()) < MIN_RULE_CHARS:
        sys.exit(f"  --tiebreak-rule is {len(args.tiebreak_rule.strip())} characters. "
                 f"State the rule, not a label.\n"
                 f"    e.g. \"blind solver 1's per-item 'two or more dependent "
                 f"operations?' answer\".")
    unheld_defective = [c for c in hold if c in defective_ids and c not in settled]
    if unheld_defective:
        sys.exit(f"  --hold names {len(unheld_defective)} DEFECTIVE row(s) with no "
                 f"--adjudicated reason: {', '.join(unheld_defective[:5])}\n"
                 f"    A rater says this item is WRONG. It re-enters the held count by "
                 f"being repaired\n    or refuted, on the record — never by being held "
                 f"over the finding.")

    held = tally["agreed_hard"] + len(hold)
    n = len(ids)
    print(f"\n  {n} item(s) · {len(raters)} rater(s) · "
          f"{meta.get('cluster')}/{meta.get('level')}")
    # THE HEADLINE, and the whole point of #173: the split is a first-class field beside
    # the held count, on the same line, so the number can never be quoted without it.
    print(f"  HELD {held} of {n} · raters AGREED HARD on {tally['agreed_hard']} · "
          f"SPLIT on {tally['split']} · agreed MEDIUM {tally['agreed_medium']} · "
          f"DEFECTIVE named {tally['defective']}")
    for name, rows in raters:
        c = Counter(verdict(rows[cid]) for cid in ids)
        print(f"    {name}: {c['HARD']} HARD · {c['MEDIUM']} MEDIUM · "
              f"{c['DEFECTIVE']} DEFECTIVE")

    # The §10-14 case, named. It does NOT gate: plan-10 §4.6 publishes held-with-split
    # rather than mass-demoting, because demoting every disputed row would take §10-14
    # from 16 to 3 and discard fifteen sound items to fix a reporting problem.
    wide = tally["split"] > tally["agreed_hard"]
    if wide:
        print(f"\n  {_red('WIDE SPREAD')} — the raters split on {tally['split']} row(s) "
              f"and agree on {tally['agreed_hard']}.")
        print("    The held count rests on TIE-BREAKS, not on agreement. Report it as "
              "SOFT and quote")
        print("    the split with it; it is not comparable to a slice whose raters "
              "agreed. §10-14 is")
        print("    the case this names: 18-vs-3 on 21 rows, both raters arithmetically "
              "right.")

    # Every class prints its header even at zero. A class with no header reads as a class
    # that was not run -- #154's rule.
    print(f"\n  CLASS 1 — VERDICT SPLIT, HARD vs MEDIUM  ({len(split)})")
    print("    Every one of these is a tie somebody breaks. Before #173 the breaking was")
    print("    invisible; --tiebreak-rule and --hold are what put it on the record.")
    for cid, verdicts in split:
        mark = "  [held]" if cid in hold else "  [demoted]" if args.tiebreak_rule else ""
        print(f"      {cid}   " + " · ".join(f"{n}={v}" for n, v in verdicts) + mark)

    print(f"\n  CLASS 2 — DEFECTIVE NAMED BY EITHER RATER  ({len(defective)})")
    print("    A defect claim, not a difficulty judgement. ONE naming is enough: §10-11's")
    print("    stem-printed answer was caught by one rater while the other rated it HARD.")
    for cid, verdicts in defective:
        mark = "  [adjudicated]" if cid in settled else ""
        print(f"      {cid}   " + " · ".join(f"{n}={v}" for n, v in verdicts) + mark)
        if cid in settled:
            print(f"        reason: {settled[cid]}")

    print(f"\n  CLASS 3 — RUBRIC DIVERGENCE  ({len(divergence)})")
    print("    Split rows where BOTH raters returned the SAME `skipping_lands_on` letter:")
    print("    they ran the mechanical test, got the same structural answer, and disagreed")
    print("    anyway. That is a disagreement about the RUBRIC and nothing else — the")
    print("    diagnosis of the split, never a second finding about the items.")
    for cid, verdicts, lands, notes in divergence:
        print(f"      {cid}   both read skipping → {lands or 'none'}   "
              + " · ".join(f"{n}={v}" for n, v in verdicts))
        for name, note in notes:
            if note:
                print(f"        {name}: {note[:96]}")

    if args.tiebreak_rule:
        covered = [c for c in hold if c in split_ids]
        print(f"\n  tie-break rule, applied to {len(covered)} of {len(split)} split "
              f"row(s):\n    {args.tiebreak_rule.strip()}")

    live_split = sorted(split_ids - set(hold)) if not args.tiebreak_rule else []
    live_defect = sorted(defective_ids - set(settled))
    if live_split or live_defect:
        print(f"\n  {_red('ADJUDICATION REQUIRED')} — "
              f"{len(live_split)} split row(s) and {len(live_defect)} defective row(s) "
              f"are unsettled.")
        if live_split:
            print("    State the rule you broke the ties on and name the rows it held:")
            print(f"      --tiebreak-rule \"<the one rule>\" --hold {live_split[0]} ...")
        if live_defect:
            print("    Repair or refute each defective row, on the record:")
            print(f"      --adjudicated {live_defect[0]}:\"<repaired how, or why it "
                  f"stands>\"")
        print()
        sys.exit(1)
    print("\n  every contested row is settled, with its rule or its reason recorded.")
    if wide:
        print("  QUOTE THE SPLIT WITH THE NUMBER — "
              f"\"{held} held, raters agreed on {tally['agreed_hard']}, "
              f"split on {tally['split']}\".")
    print()


if __name__ == "__main__":
    main()
