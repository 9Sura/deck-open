"""Issue #94 fixtures. These pin the four guards, and each one must be RED before its guard.

#94 filed four latent gaps and every one of them verified clean on the tree of the day --
which is exactly the problem. "Passes on a clean tree" is a null test for a guard: it
exercises the path where the guard says nothing. A guard is only pinned by a fixture that
INJECTS the fault and watches it fire, and by its complement showing the guard stays quiet
when it should.

That gap is not hypothetical here. The first cut of the #94 fix rewrote the manifest gate's
`count` assertion from "the difficulty tally sums to `count`" to "the row count equals
`count`", which reads like a strictly better check and is not: the two agree only while every
row carries a tier, and both sides of the `difficultyCounts` comparison are clamped to TIERS,
so a row with `difficulty: "expert"` drops out of both and the gate goes green. The pre-#94
code caught it by accident. Nothing in verify_bank.py validates the tier vocabulary, so the
rewrite opened a hole while closing three. Case 2f is that hole.

What is pinned:

  1a  a bank file present at REF and GONE from the working tree FAILS  (#94 (a))
  1b  ...and still fails when its manifest entry is removed too -- the case that was
      TOTALLY silent, since the orphan check in [2] never fires and [1] never looked
  1c  a wholly NEW file on disk is still legal under --additive (the guard is not a
      blanket "the file set must not move")
  1d  a ref-side path the on-disk glob CANNOT match (bank root, or two dirs deep) is NOT
      reported GONE -- `ls-tree -r` recurses to any depth, `_bank_files()` globs exactly
      one, and a mismatch there would be a failure that can never be cleared
  2a  stale areaCounts FAILS            (#94 (b))
  2b  stale letterDistribution FAILS    (#94 (b))
  2c  a bank file with NO manifest entry FAILS
  2d  a bank file with TWO manifest entries FAILS
  2e  a stale `count` FAILS
  2f  a row whose difficulty is outside TIERS FAILS, with the manifest regenerated to
      match -- THE REGRESSION CASE, green under the first cut of the #94 fix
  2g  the clean bank PASSES all of the above (non-vacuity: 2a-2f are not just "always red")
  3a  build_prompt.py has no bare `open()` left  (#94 (c))
  3b  ...and the premise is real: under a C locale a bare write of the prompt's own
      characters raises, and the utf-8 write does not
  4a  --areas recomputes EVERY row-derived counter, hard_met_by_medium included (#94 (d)),
      asserted as self-consistency (meta == recomputation over the exported rows) so it
      does not rot when the bank grows
  4b  ...non-vacuously: the filtered value must actually differ from the whole-slice one

ROOT is derived from __file__ on purpose. The three older fixtures in this directory
hardcode an absolute path under a repo name that no longer exists, and all three now fail
before asserting anything -- a fixture that cannot find the tree it pins is worth less than
no fixture, because the suite still counts it.
"""
import ast
import collections
import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
GEN = ROOT / "backend/test-gen-model/src/generators"
sys.path.insert(0, str(GEN))
import verify_bank  # noqa: E402
import pi_deficit  # noqa: E402

PY = sys.executable
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def item(qid, difficulty="easy", area="Business Law", answer="B"):
    return {
        "id": qid,
        "question": f"Question body for {qid}?",
        "options": {"A": "Alpha", "B": "Bravo", "C": "Charlie", "D": "Delta"},
        "answer": answer,
        "explanation": "Because.",
        "performanceIndicator": "Describe the nature of legally binding contracts",
        "instructionalArea": area,
        "cluster": "finance",
        "level": "association",
        "difficulty": difficulty,
    }


def entry_for(fname, rows, cluster="finance", level="Association"):
    return {
        "cluster": cluster,
        "level": level,
        "file": fname,
        "count": len(rows),
        "areaCounts": dict(collections.Counter(r["instructionalArea"] for r in rows)),
        "letterDistribution": dict(collections.Counter(r["answer"] for r in rows)),
        "difficultyCounts": {t: sum(1 for r in rows if r["difficulty"] == t)
                             for t in verify_bank.TIERS},
    }


def capture(fn, *a, **kw):
    """Run a verify_bank check with its counters zeroed; return (fails, output)."""
    verify_bank.ok_count = 0
    verify_bank.fail_count = 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **kw)
    return verify_bank.fail_count, buf.getvalue()


# =====================================================================
# (a) + the depth guard -- check_invariant against a throwaway git repo
# =====================================================================
def build_repo(td):
    repo = Path(td) / "repo"
    bank = repo / "frontend/public/question-bank"
    (bank / "finance").mkdir(parents=True)
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "fx@example.com"],
                ["git", "config", "user.name", "fixture"]):
        subprocess.run(cmd, cwd=repo, capture_output=True)
    verify_bank.BANK_DIR = bank
    verify_bank.REPO_ROOT = repo
    return repo, bank


def commit(repo, msg="base"):
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, capture_output=True)


ROWS = [item("fin-0001"), item("fin-0002", "medium")]


def invariant_case(name, arrange, expect_fails, needle, absent=None):
    """Each case gets its OWN repo.

    An earlier draft shared one repo across all four and 1b then inherited 1d's
    commits, so 1b's fail_count read 3 instead of 1 and the case reported a defect
    that belonged to its neighbour. A fixture whose Nth result depends on the N-1th
    is measuring the fixture.
    """
    with tempfile.TemporaryDirectory() as td:
        repo, bank = build_repo(td)
        keep = bank / "finance" / "finance-association-1.json"
        doomed = bank / "finance" / "finance-association-pool.json"
        keep.write_text(json.dumps(ROWS, indent=2), encoding="utf-8")
        doomed.write_text(json.dumps(ROWS, indent=2), encoding="utf-8")
        commit(repo)
        arrange(repo, bank, doomed)
        fails, report = capture(verify_bank.check_invariant, "HEAD", frozenset(), True)
        ok = fails == expect_fails and (needle in report)
        if absent:
            ok = ok and absent not in report
        tail = report.strip().splitlines()[-1] if report.strip() else "no output"
        check(name, ok, f"fail_count={fails} (wanted {expect_fails}) :: {tail}")


# -- 1a: delete the whole file -----------------------------------------
invariant_case("1a. a file present at REF and GONE from the tree FAILS",
               lambda repo, bank, doomed: doomed.unlink(),
               1, "GONE from the working tree")


# -- 1b: delete the file AND its manifest entry ------------------------
# The silent case: [2]'s orphan check keys off the manifest, so dropping the entry
# removes the only pre-#94 signal and [1] is the sole remaining guard. check_invariant
# never reads the manifest, so the arrangement is the same unlink -- what this pins is
# that the GONE finding does NOT depend on a manifest entry existing to point at it.
def _delete_file_and_entry(repo, bank, doomed):
    doomed.unlink()
    man = bank / "manifest.json"
    man.write_text(json.dumps({"version": 1, "sets": {}, "pools": {}}, indent=2),
                   encoding="utf-8")


invariant_case("1b. ...and still FAILS with no manifest entry to notice it (the silent case)",
               _delete_file_and_entry, 1, "GONE from the working tree")


# -- 1c: a brand-new file on disk is legal under --additive ------------
def _add_new_file(repo, bank, doomed):
    (bank / "finance" / "finance-icdc-pool.json").write_text(
        json.dumps([item("fin-9001")], indent=2), encoding="utf-8")


invariant_case("1c. a wholly NEW file on disk is still legal under --additive",
               _add_new_file, 0, "new file")


# -- 1d: ref-side paths the on-disk glob can never match ----------------
# `_bank_files()` globs BANK_DIR/*/*.json exactly. A .json at the bank root or two
# directories down is invisible to it, so enumerating it from the ref would raise a
# GONE that no action on disk could ever clear.
def _out_of_glob_at_ref(repo, bank, doomed):
    (bank / "stray-at-root.json").write_text("[]", encoding="utf-8")
    (bank / "finance" / "nested").mkdir()
    (bank / "finance" / "nested" / "deep.json").write_text("[]", encoding="utf-8")
    commit(repo, "add out-of-glob json")
    (bank / "stray-at-root.json").unlink()
    (bank / "finance" / "nested" / "deep.json").unlink()


invariant_case("1d. ref-side paths OUTSIDE the on-disk glob are not reported GONE",
               _out_of_glob_at_ref, 0, "existing intact", absent="GONE")


# =====================================================================
# (b) -- check_manifest against a throwaway bank
# =====================================================================
POOL = [item(f"fin-p{i:04d}", ["easy", "medium", "hard"][i % 3],
             ["Business Law", "Operations"][i % 2], "ABCD"[i % 4]) for i in range(12)]
SET = [item(f"fin-s{i:04d}", ["easy", "medium"][i % 2],
            ["Economics", "Operations"][i % 2], "ABCD"[i % 4]) for i in range(8)]


def manifest_bank(td, mutate_manifest=None, mutate_rows=None, extra_file=None):
    bank = Path(td) / "question-bank"
    (bank / "finance").mkdir(parents=True, exist_ok=True)
    pool, sett = list(POOL), list(SET)
    if mutate_rows:
        mutate_rows(pool)
    (bank / "finance" / "finance-association-pool.json").write_text(
        json.dumps(pool, indent=2), encoding="utf-8")
    (bank / "finance" / "finance-association-1.json").write_text(
        json.dumps(sett, indent=2), encoding="utf-8")
    man = {
        "version": 1,
        "sets": {"finance-association-1": entry_for("finance-association-1.json", sett)},
        "pools": {"finance-association-pool": entry_for("finance-association-pool.json", pool)},
    }
    if extra_file:
        (bank / "finance" / extra_file).write_text(json.dumps(sett, indent=2), encoding="utf-8")
    if mutate_manifest:
        mutate_manifest(man)
    (bank / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    verify_bank.BANK_DIR = bank
    verify_bank.MANIFEST_PATH = bank / "manifest.json"
    return bank


def manifest_case(name, ok_expect, needle, **kw):
    with tempfile.TemporaryDirectory() as td:
        manifest_bank(td, **kw)
        fails, report = capture(verify_bank.check_manifest)
        hit = (fails == 0) if ok_expect else (fails >= 1 and needle in report)
        tail = report.strip().splitlines()[-1] if report.strip() else "no output"
        check(name, hit, f"fail_count={fails} :: {tail[:160]}")


manifest_case("2g. the clean synthetic bank PASSES (2a-2f are not always-red)",
              True, "")
manifest_case("2a. stale areaCounts FAILS", False, "areaCounts",
              mutate_manifest=lambda m: m["pools"]["finance-association-pool"]["areaCounts"]
              .__setitem__("Operations", 999))
manifest_case("2b. stale letterDistribution FAILS", False, "letterDistribution",
              mutate_manifest=lambda m: m["pools"]["finance-association-pool"]["letterDistribution"]
              .__setitem__("A", 999))
manifest_case("2e. stale count FAILS", False, "count",
              mutate_manifest=lambda m: m["pools"]["finance-association-pool"]
              .__setitem__("count", 999))
manifest_case("2c. a bank file with NO manifest entry FAILS", False, "no manifest entry",
              extra_file="finance-association-2.json")
manifest_case("2d. a bank file with TWO manifest entries FAILS", False, "manifest entries",
              mutate_manifest=lambda m: m["sets"].__setitem__(
                  "finance-association-dupe",
                  dict(m["pools"]["finance-association-pool"])))


# 2f -- THE REGRESSION. One row goes to a difficulty outside TIERS and the manifest is
# regenerated from the mutated rows, so difficultyCounts, areaCounts, letterDistribution
# and count all agree. Every clamped comparison reads equal; only an explicit tier-
# vocabulary assertion can see it.
def _untier(rows):
    rows[0] = dict(rows[0], difficulty="expert")


def _regen(m):
    pass


with tempfile.TemporaryDirectory() as td:
    bank = manifest_bank(td, mutate_rows=_untier)
    rows = json.loads((bank / "finance" / "finance-association-pool.json").read_text())
    man = json.loads((bank / "manifest.json").read_text())
    man["pools"]["finance-association-pool"] = entry_for("finance-association-pool.json", rows)
    (bank / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    fails, report = capture(verify_bank.check_manifest)
    check("2f. an untiered row FAILS even with the manifest regenerated (THE REGRESSION)",
          fails >= 1 and "outside" in report and "expert" in report,
          f"fail_count={fails} :: {report.strip().splitlines()[-1][:170] if report.strip() else 'no output'}")


# =====================================================================
# (c) -- no bare open() in build_prompt.py, and the premise behind it
# =====================================================================
src = (GEN / "build_prompt.py").read_text(encoding="utf-8")
opens = [n for n in ast.walk(ast.parse(src))
         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"]
bare = [n.lineno for n in opens
        if not any(k.arg == "encoding" for k in n.keywords) and len(n.args) < 4]
check("3a. build_prompt.py has no bare open() left",
      len(opens) >= 4 and not bare,
      f"{len(opens)} open() call(s) found, bare at lines {bare or 'none'}")

probe = ("import sys\n"
         "try:\n"
         "    open(sys.argv[1], 'w').write('\\u00a7 \\u2014 \\u00b1')\n"
         "    print('BARE-OK')\n"
         "except UnicodeEncodeError:\n"
         "    print('BARE-RAISED')\n"
         "open(sys.argv[2], 'w', encoding='utf-8').write('\\u00a7 \\u2014 \\u00b1')\n"
         "print('UTF8-OK')\n")
with tempfile.TemporaryDirectory() as td:
    r = subprocess.run([PY, "-X", "utf8=0", "-c", probe,
                        str(Path(td) / "a.txt"), str(Path(td) / "b.txt")],
                       capture_output=True, text=True,
                       env={"LC_ALL": "C", "PATH": "/usr/bin:/bin", "PYTHONCOERCECLOCALE": "0"})
    out = r.stdout
    check("3b. ...and the premise holds: bare write RAISES under a C locale, utf-8 does not",
          "BARE-RAISED" in out and "UTF8-OK" in out,
          f"probe said: {out.split() or r.stderr.strip()[:120]}")


# =====================================================================
# (d) -- --areas must recompute every row-derived counter
# =====================================================================
DERIVED = ("pis_needing_work", "need_easy", "need_medium", "need_hard",
           "need_total", "hard_met_by_medium")

slice_found = None
for cluster in ("finance", "pbm", "hospitality", "entrepreneurship"):
    for level in ("District", "Association", "ICDC"):
        try:
            wo = pi_deficit.build_deficit(cluster, level, honest_hard=True)
        except Exception:
            continue
        if wo["meta"].get("hard_met_by_medium", 0) > 0 and len(
                {r["instructionalArea"] for r in wo["rows"]}) > 1:
            slice_found = (cluster, level, wo)
            break
    if slice_found:
        break

if not slice_found:
    check("4a/4b. --areas recomputes every row-derived counter", False,
          "no slice with hard_met_by_medium>0 and >1 area -- fixture could not run "
          "non-vacuously; do not read this as a pass")
else:
    cluster, level, wo = slice_found
    whole = dict(wo["meta"])
    area = sorted({r["instructionalArea"] for r in wo["rows"]
                   if r.get("hard_met_by_medium", 0) > 0})[0]
    keep = {pi_deficit.slug(area)}
    kept = [r for r in wo["rows"] if pi_deficit.slug(r["instructionalArea"]) in keep]
    m = dict(whole)
    m.update(pi_deficit._summarize(kept))

    recomputed = {
        "pis_needing_work": len({r["performanceIndicator"] for r in kept}),
        "need_easy": sum(r["need_easy"] for r in kept),
        "need_medium": sum(r["need_medium"] for r in kept),
        "need_hard": sum(r["need_hard"] for r in kept),
        "need_total": sum(r[f"need_{t}"] for r in kept for t in pi_deficit.TIERS),
        "hard_met_by_medium": sum(r.get("hard_met_by_medium", 0) for r in kept),
    }
    drift = [k for k in DERIVED if m[k] != recomputed[k]]
    check("4a. --areas: every row-derived meta counter matches the filtered rows",
          not drift,
          f"{cluster}/{level} area={area!r}; drifted={drift or 'none'}")
    check("4b. ...non-vacuously: the filtered hard_met_by_medium actually MOVED",
          m["hard_met_by_medium"] != whole["hard_met_by_medium"],
          f"whole-slice={whole['hard_met_by_medium']} filtered={m['hard_met_by_medium']}")

    # The counter list is derived from _summarize itself, so a counter added there later
    # cannot quietly escape this fixture the way hard_met_by_medium escaped the filter.
    check("4c. _summarize returns exactly the counters this fixture checks",
          set(pi_deficit._summarize(kept)) == set(DERIVED),
          f"_summarize keys={sorted(pi_deficit._summarize(kept))}")

print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
