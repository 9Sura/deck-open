"""Assemble a plan-10 chunk into its pool, additively, then run the three gates.

`build_question_bank.py --pool` does not append -- it REBUILDS the pool file from
exactly the parts it is handed and writes the result over the old one. So the
additive step every plan-10 chunk depends on is "pass the existing pool file as
part 1, then the new parts", and nothing in the pipeline enforces that. Hand it only
the new parts and the pool silently shrinks from 780 questions to the 40 you just
wrote, taking every prior chunk with it. `verify_bank --additive` would catch it
afterwards, but by then the file is already overwritten.

This wrapper makes that ordering structural instead of remembered, and then runs the
three deterministic gates in the order §10-2 §3 lists them, stopping at the first
failure:

    5. assemble   build_question_bank --pool, existing pool first, EXPLICIT paths
    6. tell audit audit_tells --per-slice --max-rate 0.35
    7. verify     verify_bank --additive --base <ref>

    python3 assemble_slice.py finance ICDC --parts DIR/ops-part1.json DIR/ops-part2.json
    python3 assemble_slice.py finance ICDC --parts DIR/*.json --base HEAD --dry-run

EXPLICIT PATHS, NEVER --parts-dir. §10-1 lost a chunk to the glob: an agent's
in-progress `draft.json` sat in the parts directory and `--parts-dir` swept it into
the bank. This script takes only explicit paths and refuses a directory, which is
the same lesson `slice-tools/gate_slice.sh` learned for the repair direction.

PATHS ARE RESOLVED TO ABSOLUTE BEFORE THEY ARE HANDED ON (§10-5, measured 2026-07-29).
The children run with `cwd=REPO_ROOT`, but --parts arrives relative to wherever the
CALLER stood -- normally `backend/test-gen-model`, which is where every plan's command
block is written. §10-5 passed the plan's own documented relative paths, all 7 part
files failed to open inside the child, the pool was rebuilt from the 245 existing
items alone, and this script printed "all three gates green" -- the gates passed
BECAUSE nothing had been added. 173 authored questions were silently discarded and
only a manual pool recount caught it. Two guards now make that unrepresentable:
resolve() every path here, and assert after assembly that the pool actually grew.

THE CHILDREN RUN UNDER `sys.executable`, NEVER A BARE `python` (issue #91). That was
the third assumption in the same three lines, and the only one left unhardened: there
is no system `python` on macOS, so the name resolved at all only while the repo's venv
happened to be active. Off the venv it is a FileNotFoundError traceback partway through
the sequence -- possibly AFTER step 5 has already rewritten the pool -- and, worse, a
`python` that resolves to a DIFFERENT interpreter is silent: this process reads the
parts and runs `check_question` over every pre-existing item under one interpreter and
the three gates then judge the result under another. Every sibling tool in the tree
already spawns `sys.executable`; `slice-tools/fixtures_child_interpreter.py` pins it.
"""
import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bank_paths import REPO_ROOT  # noqa: E402  the ONE bank path (#203)
from build_question_bank import BANK_DIR, VALID_LEVELS, check_question  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[4]
GEN = Path(__file__).resolve().parent

# THE interpreter, not whatever `python` happens to mean on this PATH (issue #91).
PY = sys.executable


def run(cmd: List[str], label: str) -> bool:
    print(f"\n{'=' * 74}\n  {label}\n{'=' * 74}")
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT)
    except OSError as exc:
        # A child that cannot be LAUNCHED is a failed gate, not a traceback out of the
        # middle of the sequence: the caller's SystemExit names which step stopped and
        # the pool is left exactly as the step before it wrote it.
        print(f"\n  [error] could not launch {cmd[0]}: {exc}")
        return False
    return proc.returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Additively assemble a plan-10 chunk and run the three gates.")
    ap.add_argument("cluster")
    ap.add_argument("level")
    ap.add_argument("--parts", required=True, nargs="+",
                    help="explicit authored part paths (never a directory)")
    ap.add_argument("--base", default="HEAD",
                    help="git ref for verify_bank --additive (default HEAD)")
    ap.add_argument("--max-rate", default="0.35", help="audit_tells bar (default 0.35)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be assembled and stop")
    args = ap.parse_args()

    level = args.level.capitalize() if args.level.lower() != "icdc" else "ICDC"
    if level not in VALID_LEVELS:
        raise SystemExit(f"level must be one of {sorted(VALID_LEVELS)}; got '{args.level}'")

    pool = BANK_DIR / args.cluster / f"{args.cluster}-{level.lower()}-pool.json"
    if not pool.is_file():
        raise SystemExit(f"no existing pool at {pool} — plan 10 is additive by definition")

    parts: List[Path] = []
    for p in args.parts:
        path = Path(p)
        if path.is_dir():
            raise SystemExit(f"'{p}' is a directory — pass explicit part paths "
                             "(a stray draft.json in a parts dir reached the bank once)")
        if not path.is_file():
            raise SystemExit(f"part not found: {p}")
        if path.resolve() == pool.resolve():
            continue  # the pool is prepended below; don't let it in twice
        # ABSOLUTE, always: the children run from REPO_ROOT, not from here.
        parts.append(path.resolve())
    if not parts:
        raise SystemExit("no new part files given")

    existing = json.loads(pool.read_text(encoding="utf-8"))
    new_items = []
    for path in parts:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise SystemExit(f"{path}: expected a JSON array")
        new_items.extend(data)

    # Every pre-existing item must survive the CURRENT gate, or the assembler drops
    # it, every later id shifts, and `verify_bank --additive` reports a wall of
    # failures whose cause is nowhere near the chunk being added. Gates have been
    # tightened since these items were authored (the 2.2x length drop, stem dedup),
    # so this is worth knowing BEFORE the file is overwritten.
    stale = []
    for q in existing:
        hard, _ = check_question(q, require_difficulty=True)
        if hard:
            stale.append((q.get("id"), hard))
    if stale:
        print(f"\n  WARNING: {len(stale)} pre-existing pool item(s) fail the current gate")
        print("  and would be DROPPED, shifting every id after them:")
        for qid, reasons in stale[:10]:
            print(f"    {qid}: {'; '.join(reasons)}")
        print("  Resolve these before assembling — this is not a plan-10 defect.\n")
        raise SystemExit(1)

    wrong = Counter()
    for q in new_items:
        if q.get("cluster") != args.cluster or q.get("level") != level:
            wrong[f"{q.get('cluster')}/{q.get('level')}"] += 1
    if wrong:
        raise SystemExit(f"new parts contain items for another slice: {dict(wrong)}")

    print(f"\n  pool          {pool.relative_to(REPO_ROOT)}  ({len(existing)} existing)")
    print(f"  new parts     {len(parts)} file(s), {len(new_items)} item(s)")
    print(f"  after         {len(existing) + len(new_items)} (minus anything the gate drops)")
    tiers = Counter(q.get("difficulty") for q in new_items)
    print(f"  new by tier   {dict(sorted(tiers.items()))}")
    if args.dry_run:
        print("\n  --dry-run: stopping before assembly.\n")
        return

    # THE ADDITIVE ORDERING: existing pool first so its items keep ids 0001..N and
    # the new work appends after them.
    ok = run([PY, str(GEN / "build_question_bank.py"), args.cluster, level, "--pool",
              str(pool.resolve()), *[str(p) for p in parts]],
             f"[5] assemble — {len(existing)} existing + {len(new_items)} new")
    if not ok:
        raise SystemExit("assembly failed")

    # DID IT ACTUALLY LAND? build_question_bank returns 0 even when it could not open
    # a part file -- it just assembles the ones it managed to read. That is how §10-5
    # rebuilt a pool from its existing items and reported success. The pool on disk is
    # the only witness that cannot be talked out of the truth, so re-read it.
    after = json.loads(pool.read_text(encoding="utf-8"))
    added = len(after) - len(existing)
    if added <= 0:
        raise SystemExit(
            f"ASSEMBLY ADDED NOTHING: pool still holds {len(after)} item(s) after being "
            f"handed {len(new_items)} new one(s).\n"
            "  The parts were almost certainly unreadable from the child's cwd — check\n"
            "  the '[error] cannot read ...' lines in the [5] output above. NOTHING was\n"
            "  added and the gates below would have passed for exactly that reason.")
    if added != len(new_items):
        print(f"\n  NOTE: pool grew by {added}, not the {len(new_items)} handed in — "
              f"{len(new_items) - added} item(s) were dropped by the assembler's gate.\n"
              "  That is legitimate only if the [5] output named them; otherwise stop.")

    if not run([PY, str(GEN / "audit_tells.py"), "--per-slice",
                "--max-rate", args.max_rate], "[6] tell audit"):
        raise SystemExit("tell audit failed — do not proceed")

    if not run([PY, str(GEN / "verify_bank.py"), "--additive", "--base", args.base],
               f"[7] verify additive vs {args.base}"):
        raise SystemExit("additive verify failed — pre-existing items were altered")

    print(f"\n  all three gates green. Re-run pi_deficit.py {args.cluster} {level} "
          f"to see what the chunk closed.\n")


if __name__ == "__main__":
    main()
