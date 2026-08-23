"""Issue #91 fixtures: `assemble_slice.py` must spawn its gates as `sys.executable`.

`assemble_slice.py` is the wrapper that lands a plan-10 chunk in the bank -- it assembles
the pool additively and then runs the three deterministic gates as child processes. It
launched them with the literal name `python`, which is an assumption about the child's
ENVIRONMENT of exactly the class the file already hardened twice (relative --parts that
the child could not open; an assembly that "succeeded" while adding nothing).

Two failure shapes, and the quiet one is the reason this file exists:

  1. NO `python` ON PATH. macOS ships no system `python`, only `python3`, so the name
     resolved at all only while the repo's venv happened to be active. Off it, the child
     raises FileNotFoundError from the middle of the sequence -- possibly AFTER step 5
     has already rewritten the pool, with the two gates that would have judged it unrun.
  2. A DIFFERENT `python` ON PATH. Silent. The wrapper reads the parts, runs
     `check_question` over every pre-existing pool item and computes `added` under one
     interpreter; the three gates then judge that result under another, possibly without
     the repo's dependencies. Nothing prints. Case 5 below shows the substitution
     happening with exit 0 and no diagnostic.

So this pins the contract from both ends, statically and dynamically:

  * the SOURCE (cases 1-3): every child spawn in `assemble_slice.py`, found by parsing
    the file rather than by grepping for a string, carries `PY` as argv[0], and `PY` is
    `sys.executable`. A fourth spawn added later with a bare `"python"` fails case 2.
  * the PROCESS (case 8): `main()` is driven end-to-end over a temp pool with
    `subprocess` recorded instead of executed, so what is asserted is the argv the
    wrapper ACTUALLY issues for all three gates, not what the source appears to say.

Cases 4-5 are the non-vacuity pair -- they demonstrate against the real `subprocess`
that a bare `python` does break and does get silently substituted, so cases 1-3 are
testing something real. Cases 6-7 pin the `OSError` guard that turns an unlaunchable
child into a failed gate instead of a traceback.

WHAT THIS CANNOT CHECK: the sibling shell tools (`gate_slice.sh`, `prep_slice.sh`) also
spawn a bare `python`. They `source venv/bin/activate` on the line above it, so they are
a separate cleanup and are out of scope here. (Both derive their repo root from
`BASH_SOURCE` now; the pre-rename `GNS DECA APP` `cd` this used to name is long gone.)

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_child_interpreter.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded -- an absolute path into a session
scratchpad, or into `/Users/.../GNS DECA APP` (the pre-rename directory, now DECK-APP),
dies with the session or the rename and takes the file with it. #157 swept the last
three out of this toolchain; don't reintroduce one.
"""
import ast
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import assemble_slice  # noqa: E402
from build_question_bank import BANK_DIR, check_question  # noqa: E402

SRC_FILE = GEN / "assemble_slice.py"
SPAWNERS = {"run", "call", "check_call", "check_output", "Popen"}

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


# ---- 1-3: the source ------------------------------------------------------
# Found by PARSING, not grepping: a spawn is any call to run/subprocess.* whose first
# argument is a list literal. That is what makes a future fourth gate fail this file
# instead of slipping past a string search for "python".
def _callee(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""


def _argv0_is_py(elt: ast.expr) -> bool:
    """PY, or sys.executable spelled out."""
    if isinstance(elt, ast.Name):
        return elt.id == "PY"
    if isinstance(elt, ast.Attribute):
        return elt.attr == "executable"
    return False


tree = ast.parse(SRC_FILE.read_text(encoding="utf-8"))
spawns = [n for n in ast.walk(tree)
          if isinstance(n, ast.Call) and _callee(n) in SPAWNERS
          and n.args and isinstance(n.args[0], ast.List) and n.args[0].elts]

check("1. the parse finds every child spawn (>= 3: assemble, tell audit, verify)",
      len(spawns) >= 3, f"found {len(spawns)} at lines {[n.lineno for n in spawns]}")

named = [(n.lineno, n.args[0].elts[0].value) for n in spawns
         if isinstance(n.args[0].elts[0], ast.Constant)
         and isinstance(n.args[0].elts[0].value, str)]
check("2. no spawn launches an interpreter BY NAME",
      not named,
      f"bare-name argv[0] at {named}" if named else "")

check("3. every spawn's argv[0] resolves to sys.executable",
      all(_argv0_is_py(n.args[0].elts[0]) for n in spawns),
      f"offending lines={[n.lineno for n in spawns if not _argv0_is_py(n.args[0].elts[0])]}")

check("3b. the module's PY constant IS this interpreter",
      getattr(assemble_slice, "PY", None) == sys.executable,
      f"PY={getattr(assemble_slice, 'PY', None)!r} sys.executable={sys.executable!r}")

# ---- 4-5: the bug is real (against the REAL subprocess) -------------------
with tempfile.TemporaryDirectory() as td:
    td = Path(td)

    empty = td / "empty-path"
    empty.mkdir()
    env_bare = {"PATH": str(empty), "HOME": os.environ.get("HOME", "/tmp")}

    raised = None
    try:
        subprocess.run(["python", "-c", "pass"], env=env_bare, capture_output=True)
    except OSError as exc:
        raised = exc
    same = subprocess.run([sys.executable, "-c", "pass"], env=env_bare, capture_output=True)
    check("4. with no `python` on PATH, a bare name raises and sys.executable does not "
          "(this is the bug)",
          isinstance(raised, FileNotFoundError) and same.returncode == 0,
          f"bare raised={raised!r} sys.executable rc={same.returncode}")

    # An impostor `python` earlier on PATH. Nothing about this is loud: exit 0, no
    # stderr, and the gates would have run under it.
    impostor_dir = td / "impostor"
    impostor_dir.mkdir()
    impostor = impostor_dir / "python"
    impostor.write_text("#!/bin/sh\necho IMPOSTOR-INTERPRETER\nexit 0\n", encoding="utf-8")
    impostor.chmod(impostor.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    env_imp = {"PATH": f"{impostor_dir}:{os.environ.get('PATH', '')}",
               "HOME": os.environ.get("HOME", "/tmp")}
    r_bare = subprocess.run(["python", "-c", "print('REAL')"], env=env_imp,
                            capture_output=True, text=True)
    r_py = subprocess.run([sys.executable, "-c", "print('REAL')"], env=env_imp,
                          capture_output=True, text=True)
    check("5. a DIFFERENT `python` earlier on PATH is silently preferred, exit 0 "
          "(the quiet failure)",
          "IMPOSTOR-INTERPRETER" in r_bare.stdout and r_bare.returncode == 0
          and r_py.stdout.strip() == "REAL",
          f"bare stdout={r_bare.stdout.strip()!r} rc={r_bare.returncode} :: "
          f"sys.executable stdout={r_py.stdout.strip()!r}")

    # ---- 6-7: run() reports an unlaunchable child as a FAILED GATE --------
    missing = td / "no-such-binary"
    crashed = None
    ok_missing = None
    try:
        ok_missing = assemble_slice.run([str(missing), "x"], "fixture: missing child")
    except BaseException as exc:  # noqa: BLE001 -- a traceback here IS the defect
        crashed = exc
    check("6. run() on an unlaunchable child returns False rather than raising",
          crashed is None and ok_missing is False,
          f"raised={crashed!r} returned={ok_missing!r}")

    check("7. run() still reports a real child by its exit code (0 -> True, 3 -> False)",
          assemble_slice.run([sys.executable, "-c", "pass"], "fixture: exit 0") is True
          and assemble_slice.run([sys.executable, "-c", "raise SystemExit(3)"],
                                 "fixture: exit 3") is False)

    # ---- 8: end-to-end — what main() ACTUALLY launches --------------------
    # Real bank items, so the pre-existing-item gate inside main() behaves as it does in
    # production; a temp BANK_DIR, so nothing here can touch the committed bank.
    real_pool = BANK_DIR / "entrepreneurship" / "entrepreneurship-district-pool.json"
    source_items = json.loads(real_pool.read_text(encoding="utf-8"))
    existing = [q for q in source_items if not check_question(q, require_difficulty=True)[0]][:2]

    if len(existing) < 2:
        check("8. main() launches all three gates as sys.executable", False,
              "SKIPPED: fewer than 2 committed pool items pass the current gate — "
              "fix the pool, then re-run this fixture")
    else:
        bank = td / "bank" / "entrepreneurship"
        bank.mkdir(parents=True)
        pool = bank / "entrepreneurship-district-pool.json"
        pool.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        new_item = dict(existing[0])
        new_item["id"] = "fixture-new-0001"
        new_item["question"] = "Which fixture item stands in for a freshly authored row?"
        part = td / "chunk1.json"
        part.write_text(json.dumps([new_item], indent=2), encoding="utf-8")

        launched = []

        class Recorder:
            """subprocess, recorded not executed.

            The first call stands in for `build_question_bank --pool`, so it writes the
            grown pool -- otherwise main()'s "ASSEMBLY ADDED NOTHING" guard stops the
            run before the two gates whose argv this case exists to read.
            """

            @staticmethod
            def run(cmd, cwd=None, **kw):
                launched.append(list(cmd))
                if len(launched) == 1:
                    pool.write_text(json.dumps(existing + [new_item], indent=2),
                                    encoding="utf-8")
                return SimpleNamespace(returncode=0, args=cmd)

        saved = (assemble_slice.BANK_DIR, assemble_slice.REPO_ROOT,
                 assemble_slice.subprocess, sys.argv)
        exit_exc = None
        try:
            assemble_slice.BANK_DIR = td / "bank"
            assemble_slice.REPO_ROOT = td      # only for the progress line's relative_to
            assemble_slice.subprocess = Recorder
            sys.argv = ["assemble_slice.py", "entrepreneurship", "District",
                        "--parts", str(part)]
            assemble_slice.main()
        except SystemExit as exc:
            exit_exc = exc
        finally:
            (assemble_slice.BANK_DIR, assemble_slice.REPO_ROOT,
             assemble_slice.subprocess, sys.argv) = saved

        # NON-VACUOUS: if main() bailed early, three empty argv lists would "pass" a
        # naive all()-over-nothing. It must have reached all three gates, in order.
        scripts = [Path(c[1]).name if len(c) > 1 else "" for c in launched]
        check("8a. main() reached all three gates, in order",
              exit_exc is None
              and scripts == ["build_question_bank.py", "audit_tells.py", "verify_bank.py"],
              f"exit={exit_exc!r} launched={scripts}")
        check("8b. all three were launched as THIS interpreter",
              bool(launched) and all(c[0] == sys.executable for c in launched),
              f"argv[0]s={[c[0] for c in launched] or 'nothing launched'}")

print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
