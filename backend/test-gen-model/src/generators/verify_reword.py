#!/usr/bin/env python3
"""Prove that a bank edit REWORDED committed items and did nothing else.

WHY THIS IS NOT A MODE OF verify_bank.py
----------------------------------------
Every plan-10 depth slice is ADDITIVE: it appends rows, and `verify_bank.py
--additive --base <ref>` proves that every pre-existing item is byte-identical.
A reword edits committed items, so that check fails BY DESIGN -- it is the wrong
gate, not a failing one. Bolting an inverted meaning onto the flag that eight
slices depend on is how a load-bearing check quietly stops being one, so this is
its own ~150 lines instead (§10-17 §6).

WHAT IT PROVES, against a git ref taken before the edit:

  * the id SET is identical -- no adds, no drops, no renumbering. Ids are the join
    key for the account progress log (§10-4): `/review` re-hydrates a missed
    question by id, so a renumber silently rewrites what a student got wrong.
  * per id, every FROZEN field is byte-identical. `answer` and `difficulty` are in
    that set for reasons that are not interchangeable:
      - `answer` because an `Attempt` stores the LETTER the student picked and the
        correctness computed AT ANSWER TIME. Move the key to another letter and
        every stored `correct` for that question becomes a lie, retroactively,
        with no way to detect it.
      - `difficulty` because a tier change is a referee decision and it moves
        `pi_deficit.py`'s floor -- a reword that silently re-tags would re-open a
        slice that reads closed.
  * only `options` and `explanation` differ -- and at least one of them does, on
    every row the run claims to have repaired.

WHAT IT DELIBERATELY DOES NOT PROVE: that the reword WORKED. `option_tells` was
written from this defect, so it scores the shapes already known, and §10-10 proved
a repair can null every deterministic instrument while leaving the item just as
pickable (round 1: stem pull 0.0%, gate clean, blind solver still 3 of 3). Run the
census and a skeptical blind solver separately; this file is the safety check, not
the quality one.

`check_authored.label_divergence()` (issue #75) is the one instrument that is NOT
written from the known wording -- it measures the rule itself, that all four labels
say the same thing in the same words. On §10-10's H1 it separates the accepted fix
(0 of 9) from the round-1 repair a blind solver still beat (7 of 9), which is more
than the phrase list managed (2 of 9). Use it on a reword census. It is still not a
verdict: it is soft, a quarter of the bank's label rows trip it, and an option can
be pickable for reasons no lexical measure has a signature for.

Usage:
    python verify_reword.py --base HEAD --expect-file ids.txt \
        --file frontend/public/question-bank/hospitality/hospitality-icdc-pool.json
    python verify_reword.py --base main --file "<bank>/*/*.json"   # all of them
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

# Everything that says WHICH ROW THIS IS, plus the stem: a reword edits option and
# explanation WORDING. A changed stem is a different item wearing the same id, which
# is exactly what the progress log cannot survive.
FROZEN = ("id", "cluster", "level", "instructionalArea", "performanceIndicator",
          "question", "answer", "difficulty")
MUTABLE = ("options", "explanation")


def at_ref(ref: str, path: str) -> List[Dict]:
    """The committed version of `path` at `ref`, parsed. Empty list if absent."""
    try:
        raw = subprocess.run(["git", "show", f"{ref}:{path}"], check=True,
                             capture_output=True).stdout.decode("utf-8")
    except subprocess.CalledProcessError:
        return []
    return json.loads(raw)


def compare(before: List[Dict], after: List[Dict], path: str) -> Dict:
    """Findings for one file. Every failure names the id, never just a count."""
    bad: List[str] = []
    b_ids = [q.get("id") for q in before]
    a_ids = [q.get("id") for q in after]

    dropped = sorted(set(b_ids) - set(a_ids))
    added = sorted(set(a_ids) - set(b_ids))
    if dropped:
        bad.append(f"{len(dropped)} id(s) DROPPED: {', '.join(map(str, dropped[:8]))}")
    if added:
        bad.append(f"{len(added)} id(s) ADDED: {', '.join(map(str, added[:8]))}")
    # Order is checked separately from membership: a reordered file is not a data
    # loss, but nothing about a reword should move a row, so it is worth a failure
    # rather than a shrug.
    if not dropped and not added and b_ids != a_ids:
        bad.append("the rows are in a different ORDER than before")

    by_id = {q.get("id"): q for q in before}
    reworded, untouched = [], 0
    for q in after:
        qid = q.get("id")
        orig = by_id.get(qid)
        if orig is None:
            continue                      # already reported as an add
        for f in FROZEN:
            if orig.get(f) != q.get(f):
                bad.append(f"{qid}: FROZEN field {f!r} changed\n"
                           f"      was {orig.get(f)!r}\n"
                           f"      now {q.get(f)!r}")
        extra = (set(orig) | set(q)) - set(FROZEN) - set(MUTABLE)
        for f in sorted(extra):
            if orig.get(f) != q.get(f):
                bad.append(f"{qid}: field {f!r} changed, and only "
                           f"{'/'.join(MUTABLE)} may")
        if any(orig.get(f) != q.get(f) for f in MUTABLE):
            reworded.append(qid)
        else:
            untouched += 1
    return {"path": path, "bad": bad, "reworded": reworded, "untouched": untouched}


def main() -> None:
    ap = argparse.ArgumentParser(description="Prove a bank edit only reworded options.")
    ap.add_argument("--base", default="HEAD",
                    help="the git ref holding the PRE-repair bank (default HEAD)")
    ap.add_argument("--file", required=True, nargs="+",
                    help="the bank file(s) the repair touched")
    ap.add_argument("--expect-file", default=None,
                    help="a file of ids, one per line: the rows the repair was scoped "
                         "to. Any OTHER id that moved is a scope breach, and any id "
                         "here that did not move is a repair that silently did nothing")
    args = ap.parse_args()

    expect = None
    if args.expect_file:
        expect = {ln.strip() for ln in Path(args.expect_file).read_text().splitlines()
                  if ln.strip() and not ln.startswith("#")}

    reports = []
    for path in args.file:
        p = Path(path)
        if not p.exists():
            raise SystemExit(f"{p}: no such file")
        before = at_ref(args.base, path)
        if not before:
            raise SystemExit(f"{path}: not present at {args.base} — a reword needs a "
                             f"pre-repair version to compare against")
        reports.append(compare(before, json.loads(p.read_text(encoding="utf-8")), path))

    moved = {qid for r in reports for qid in r["reworded"]}
    bad = [line for r in reports for line in r["bad"]]

    for r in reports:
        print(f"  {Path(r['path']).name}: {len(r['reworded'])} reworded, "
              f"{r['untouched']} untouched")
    if expect is not None:
        stray = sorted(moved - expect)
        inert = sorted(expect - moved)
        if stray:
            bad.append("SCOPE BREACH: %d row(s) changed that were not in scope: %s"
                       % (len(stray), ", ".join(stray)))
        if inert:
            bad.append("%d scoped row(s) did not change at all: %s"
                       % (len(inert), ", ".join(inert)))

    for line in bad:
        print(f"  FAIL  {line}")
    if bad:
        print(f"\n  {len(bad)} violation(s) — the reword invariant does NOT hold.")
        sys.exit(1)
    print(f"\n  reword invariant holds: {len(moved)} row(s) changed, options and "
          f"explanation only, ids and answers frozen.")


if __name__ == "__main__":
    main()
