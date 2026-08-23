#!/usr/bin/env python3
"""Read the blind solvers against each other and against the key. No model.

WHY THIS EXISTS -- issue #172, measured on §10-14
--------------------------------------------------
`build_hard_verify.py --blind` has always run TWO independent solvers, and the whole
value of the second one is that it can disagree with the first. Nothing read that.
The two returns were prose, in two agent replies, compared by whoever happened to be
orchestrating the slice, and `output/plan-10/10-14/verify/` holds exactly two files:
the rater set and the blind set. No solver return was ever an artifact.

§10-14's `h0016` (Calculate cost per rating point) shipped a stem with TWO honest
readings whose answers were BOTH offered as options:

    "A local TV campaign reaches 40 rating points of the target audience with an
     average frequency of 5 exposures, for a total campaign cost of $20,000."

    reading 1  "40 rating points" IS the GRP total  -> 20,000/40  = $500 = option A
    reading 2  40 is reach, GRP = 40 x 5 = 200      -> 20,000/200 = $100 = option B (key)

The student the bank exists for -- the one who knows CPP -- reads it the first way,
computes $500, finds it offered, and is marked wrong. What it survived:

    check_authored (4 lists)              pass, no soft
    check_batch_invariants                pass
    check_key_figures, 100% scope         0.00%
    audit_tells                           pass
    key-coherence audit, --profile full   class 1: 0, class 2: 0
    arithmetic audit, --profile full      clean -- it checked cap/threshold rows for
                                          rival readings and cleared this one
    difficulty rater A                    HARD, "no readable tell"
    difficulty rater B                    MEDIUM
    blind solver 1                        A ($500)
    blind solver 2                        B ($100)

Neither solver reported low confidence about the item's DIFFICULTY, so a confidence
threshold would not have fired either. Solver 1 reported medium confidence about
WHICH QUANTITY THE STEM NAMES -- §10-9's rule (read what a solver is uncertain about,
not how uncertain it is) pointing straight at the class. The signal is the
disagreement itself, and it was free.

A LEXICAL VERSION IS REFUTED IN ADVANCE. Three sit in this repo already -- #131's
inverted stem pull, the chunks 2/3/4 lexical wrong-key detector, the chunks 5-8
shingle detector -- all failing for one reason: a semantic relation between two
fields is not measurable by vocabulary overlap between them. Two readings of one
stem share ALL of their vocabulary; that is what makes them two readings of one
stem. The instrument here is a SECOND SOLVER, not a string comparison.

THREE CLASSES, SEPARATELY COUNTED, NEVER MERGED
------------------------------------------------
The #154 rule, for the same reason it was written there: a merged count either hides
a wrong key among routine candidates or reads a clean batch as several wrong keys.

  A  SOLVERS DISAGREE WITH EACH OTHER      -- the #172 signal. An AMBIGUITY CANDIDATE
     before it is anything else: two competent readers of the same four options
     returning two letters is what a rival reading looks like from outside. It is
     NOT a verdict -- one solver may simply have been wrong -- and the adjudication
     is a human's. Mechanical, free, cannot be forgotten.
     BLIND SPOT: two solvers sharing a misreading agree, and this class is silent.

  B  SOLVERS AGREE, AND THE KEY DIFFERS    -- the pre-existing purpose of the blind
     pass, which also had no tool. Both independent readers derived a letter that is
     not the authored one: the strongest key signal the suite produces.

  C  ONE SOLVER SELF-REPORTS RIVAL READINGS -- two entries in its own `readings` list
     landing on two DIFFERENT offered letters. This is the half that covers class A's
     blind spot, because it fires on a row both solvers agreed about. It is a model
     SELF-REPORT, and this repo's standing finding is that self-reports saturate
     (authors self-certify hard at ~100%; the roleplay side ships
     --enforce-self-report OFF), so it is the second instrument here, never the first.

Class A and class B are ADJUDICATION-REQUIRED and exit 1. Class C is reported and does
not, because it is the noisy self-report arm -- read the rows, do not read the count as
a defect count.

WHAT THIS DOES NOT DO. It does not decide whether a class-A row is ambiguous; two
solvers can disagree because one of them is simply wrong, and the fix for that row is
nothing. It does not see a misreading both solvers share unless one of them writes it
down under `readings`. And it cannot make a model return the shape it asks for -- what
it buys is that a return which does NOT is refused loudly instead of read wrongly.

    python reconcile_solvers.py --key D/verify-key/blind-key.json \\
        --solver D/verify-key/solver-01.json D/verify-key/solver-02.json

An adjudicated row is carried forward with its reason, never with a bare flag:

    --adjudicated cand-h0016:"stem repaired to 40%% of the target audience; rival
                              reading no longer available"
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

# The shape the solver is asked for. `build_hard_verify.blind_head` imports this and
# asserts its prose names every one of them -- the prompt and the parser are one
# contract, checked against each other (#139), not each against its own reasoning.
SOLVER_FIELDS = ("cand_id", "answer", "confidence", "readings", "second_defensible",
                 "pickable", "pickable_cue")
REQUIRED = ("cand_id", "answer", "readings")
LETTERS = ("A", "B", "C", "D")
NONE_TOKENS = ("", "NONE", "N/A", "-", "NULL")


def _red(s: str) -> str:
    return f"\033[31m{s}\033[0m"


def letter(value) -> str:
    """A returned letter, normalised. `""` means the solver named no option.

    A reading that lands nowhere among the four options is the HEALTHY case and the
    solver is told to say so, so `none` must round-trip to a non-letter rather than
    being coerced into one or refused.
    """
    s = str(value or "").strip().upper()
    if s in NONE_TOKENS:
        return ""
    return s


def load_solver(path: Path, ids: List[str]) -> Dict[str, Dict]:
    """One solver's return, keyed by cand_id, verified against the key sidecar's ids.

    Refuses rather than resolves: a return that is missing rows, has invented one, or
    has repeated one is a return whose per-row comparison would be against the wrong
    row. That is the failure #155 documented one tool over -- a finding that names a
    real, unrelated question -- and it is cheaper to refuse it here than to act on it.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"  {path.name} is not valid JSON ({e}).\n"
                 f"    The solver is asked for a JSON array and nothing else; a return "
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
            problems.append(f"{cid} is returned twice — one row, one answer")
        rows[cid] = r

    unknown = [c for c in rows if c not in ids]
    absent = [c for c in ids if c not in rows]
    if unknown:
        problems.append(f"{len(unknown)} cand_id(s) are not in the blind set: "
                        + ", ".join(sorted(unknown)[:5]))
    if absent:
        problems.append(f"{len(absent)} item(s) of the blind set went unanswered: "
                        + ", ".join(absent[:5]))
    for cid, r in rows.items():
        if letter(r.get("answer")) not in LETTERS:
            problems.append(f"{cid}: answer {r.get('answer')!r} is not one of A-D — a "
                            f"blind solve that declines to answer is not a datum")
        rd = r.get("readings")
        if not isinstance(rd, list) or not rd:
            problems.append(f"{cid}: `readings` must be a non-empty list (one entry is "
                            f"the common, healthy answer)")
        elif any(not isinstance(x, dict) or "answer" not in x for x in rd):
            problems.append(f"{cid}: every `readings` entry needs its own `answer` "
                            f"(a letter, or \"none\")")
    if problems:
        print(f"\n  {_red('FAIL')} {path.name} is not a usable solver return")
        for p in problems[:10]:
            print(f"    {p}")
        sys.exit(1)
    return rows


def rival_readings(row: Dict) -> List[str]:
    """The distinct OFFERED letters this solver's own readings land on.

    Two or more is class C. A reading landing on `none` is dropped, not counted as a
    second letter: "this reading produces a number nobody offered" is evidence the
    item is UNAMBIGUOUS in the way that matters here.
    """
    seen: List[str] = []
    for r in row.get("readings") or []:
        lt = letter(r.get("answer"))
        if lt in LETTERS and lt not in seen:
            seen.append(lt)
    return seen


def parse_adjudicated(tokens: List[str]) -> Dict[str, str]:
    """`cand_id:reason` pairs. A bare id is refused — the reason IS the artifact.

    Same shape as build_repair_prompt's --scope-reason and fill_bank's --solo-reason,
    for the same reason: an override that takes a bare flag records that somebody
    silenced a finding and nothing about why, which is exactly the record #127 found
    missing when it had to reconstruct 33-vs-124 from overlay files afterwards.
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


def reconcile(key: Dict, solvers: List[Tuple[str, Dict[str, Dict]]]
              ) -> Tuple[List, List, List, Counter]:
    """The three classes, plus the agreement tally. Order follows the blind set."""
    class_a, class_b, class_c = [], [], []
    tally: Counter = Counter()
    for cid in key["ids"]:
        authored = letter(key["key"].get(cid))
        answers = [(name, letter(rows[cid].get("answer"))) for name, rows in solvers]
        distinct = sorted({a for _, a in answers})
        if len(distinct) > 1:
            tally["split"] += 1
            class_a.append((cid, authored, answers))
        elif distinct and distinct[0] != authored:
            tally["agreed_against_key"] += 1
            class_b.append((cid, authored, answers))
        else:
            tally["agreed_with_key"] += 1
        for name, rows in solvers:
            rivals = rival_readings(rows[cid])
            if len(rivals) > 1:
                class_c.append((cid, name, authored, rivals, rows[cid].get("readings")))
    return class_a, class_b, class_c, tally


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Read the blind solvers against each other and against the key.")
    ap.add_argument("--key", required=True,
                    help="the sidecar written by build_hard_verify.py --blind --key-out")
    ap.add_argument("--solver", required=True, nargs="+", metavar="JSON",
                    help="each solver's return, one file each. TWO OR MORE — a single "
                         "return has nothing to disagree with, which is the instrument")
    ap.add_argument("--adjudicated", nargs="*", default=[], metavar="ID:REASON",
                    help="a class-A or class-B row already settled, WITH ITS REASON. "
                         "Recorded and still printed; it only stops the exit code")
    args = ap.parse_args()

    if len(args.solver) < 2:
        sys.exit("  --solver takes TWO OR MORE returns.\n"
                 "    Independence is the instrument and disagreement is the detector "
                 "(#172); one\n    solver has nothing to disagree with, and its own "
                 "`readings` list is a self-report.")

    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    ids: List[str] = key["ids"]
    solvers = [(Path(p).name, load_solver(Path(p), ids)) for p in args.solver]
    settled = parse_adjudicated(args.adjudicated)

    class_a, class_b, class_c, tally = reconcile(key, solvers)

    named = {cid for cid, *_ in class_a} | {cid for cid, *_ in class_b}
    stray = sorted(set(settled) - named)
    if stray:
        sys.exit(f"  --adjudicated names {len(stray)} row(s) with no class-A or class-B "
                 f"finding: {', '.join(stray[:5])}\n"
                 f"    A reason attached to a row nothing flagged is a record of nothing.")

    print(f"\n  {len(ids)} item(s) · {len(solvers)} solver(s) · "
          f"{key.get('cluster')}/{key.get('level')}")
    print(f"  agreed with the key: {tally['agreed_with_key']} · "
          f"solvers split: {tally['split']} · agreed against the key: "
          f"{tally['agreed_against_key']}")

    # Every class prints its header even at zero. A class with no header reads as a
    # class that was not run -- #154's rule, and it is why that prompt carries two.
    print(f"\n  CLASS A — THE SOLVERS DISAGREE  ({len(class_a)})")
    print("    An AMBIGUITY CANDIDATE, not a verdict: two competent readers of the same")
    print("    four options returning two letters is what a rival reading looks like from")
    print("    outside. One of them may simply be wrong. Read the item, not the count.")
    for cid, authored, answers in class_a:
        mark = "  [adjudicated]" if cid in settled else ""
        print(f"      {cid}   key={authored}   "
              + " · ".join(f"{n}={a}" for n, a in answers) + mark)
        if cid in settled:
            print(f"        reason: {settled[cid]}")

    print(f"\n  CLASS B — THE SOLVERS AGREE, AND THE KEY DIFFERS  ({len(class_b)})")
    print("    Both independent readers derived a letter that is not the authored one.")
    print("    The strongest key signal this suite produces; expect zero.")
    for cid, authored, answers in class_b:
        mark = "  [adjudicated]" if cid in settled else ""
        print(f"      {cid}   key={authored}   both solvers={answers[0][1]}{mark}")
        if cid in settled:
            print(f"        reason: {settled[cid]}")

    print(f"\n  CLASS C — A SOLVER'S OWN READINGS LAND ON TWO OFFERED LETTERS  ({len(class_c)})")
    print("    The self-report arm, and the half that covers class A's blind spot: it fires")
    print("    on rows both solvers AGREED about. Noisy by construction — a model asked to")
    print("    enumerate readings will enumerate. Read the rows; do not read the count.")
    for cid, name, authored, rivals, readings in class_c:
        print(f"      {cid}   key={authored}   {name} reads it {' / '.join(rivals)}")
        for r in readings or []:
            lt = letter(r.get("answer"))
            print(f"        {lt or '—':>2}  {str(r.get('reading', '')).strip()[:96]}")

    # The advisory arm: the older question, kept because it asks something different
    # (two options defensible under ONE reading), reported without a class of its own.
    second = [(cid, n) for cid in ids for n, rows in solvers
              if letter(rows[cid].get("second_defensible")) in LETTERS]
    pickable = [(cid, n, rows[cid].get("pickable_cue"))
                for cid in ids for n, rows in solvers if rows[cid].get("pickable") is True]
    print(f"\n  advisory — `second_defensible` named on {len(second)} solver-row(s); "
          f"`pickable` on {len(pickable)}")
    print("    §10-7: act on pickability only where BOTH solvers cite the same concrete cue")
    print("    AND a rater found it independently. A cue nobody named is not actionable.")
    for cid, name, cue in pickable:
        print(f"      {cid}  {name}  cue: {str(cue or '').strip()[:80] or '<unnamed>'}")

    live = [c for c, *_ in class_a + class_b if c not in settled]
    if live:
        print(f"\n  {_red('ADJUDICATION REQUIRED')} — {len(live)} row(s) in class A or B "
              f"are unsettled.\n    Read each item and either repair it or record why it "
              f"stands:\n      --adjudicated {live[0]}:\"<why this row is settled>\"\n")
        sys.exit(1)
    print("\n  class A and class B are clear (or adjudicated, with reasons recorded).\n")


if __name__ == "__main__":
    main()
