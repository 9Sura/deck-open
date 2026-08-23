"""Issue #127 fixtures: the repair-round guards and the sharded audit input.

THE DEFECT. §10-13 spent 1,771,328 tokens on 275 of its 695 items. Authoring was the
cheapest of any plan-10 slice (2.15k/item); the repair/audit tail ran 2.00x authoring
against a plan-10 norm of 0.41-1.13x. Four causes, and three of them were rules that
ALREADY EXISTED IN PROSE and were skipped anyway:

  1. four repair rounds on chunk 1 with ONE re-gate, after all four -- and the re-gate
     showed the batch had been clean since round 1
  2. ~33 gate-named rows became 124 repaired rows (45% of everything authored), from
     model audits whose own output says not to read them as a work order
  3. the fixed agent startup paid 10 times instead of 2 (8 rows / 97.7k, 7 rows / 74.9k)
  4. one 192,814-byte audit file handed to two agents, both logging the same
     `prompt_chars` -- ~48k of duplicate ingestion

WHY A FIXTURE. Same reason as #76, #88 and #89: this toolchain's rules survive as code
and evaporate as comments. Guards 1-3 are refusals in `build_repair_prompt.py`; guard 4
is `build_audit_input.py`, whose `--agents` is REQUIRED so that "how many agents read
this file" cannot go unasked again.

NON-VACUITY. Every refusal case is paired with the same call one flag different, so a
guard that has quietly become unconditional fails here rather than passing for the wrong
reason. The blind-profile check runs on the SERIALIZED BYTES, not on the builder's
intent -- dropping a field and proving it is gone are two different claims.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_repair_round_guards.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, never hardcoded.
"""
import io
import json
import os
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import build_audit_input as bai  # noqa: E402
import build_repair_prompt as brp  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# The two row shapes the real tools produce, in miniature. `build_area.py` writes
# the payload; the authoring agent writes the part.
# ---------------------------------------------------------------------------
def payload_row(cid: str) -> dict:
    return {
        "cand_id": cid, "cluster": "entrepreneurship", "level": "ICDC",
        "instructionalArea": "Operations",
        "performanceIndicator": "Apply project-management tools",
        "difficulty": "easy", "answer_letter": "A",
        "option_length_band": [15, 55], "key_may_be_longest": False,
        "longest_letter": "D",
    }


def authored_row(cid: str) -> dict:
    return {
        "cand_id": cid, "cluster": "entrepreneurship", "level": "ICDC",
        "instructionalArea": "Operations",
        "performanceIndicator": "Apply project-management tools",
        "difficulty": "easy",
        "question": "A founder tracking overlapping deadlines needs to see how tasks "
                    "depend on one another. Which document shows that best?",
        "options": {
            "A": "A Gantt chart of task dependencies",
            "B": "A team resource allocation spreadsheet",
            "C": "A project budget summary",
            "D": "A milestone chart marking each deliverable's due date",
        },
        "answer": "A",
        "explanation": "A is correct because a Gantt chart plots dependencies; (B) "
                       "allocates people, (C) tracks money, (D) marks dates only.",
    }


def gate_text(cids) -> str:
    return "".join(
        "  soft  %s  [easy] Apply project-management tools\n"
        "          key is the longest option\n\n" % c for c in cids)


def slice_dir(n_rows: int, n_flagged: int) -> Path:
    """A payload + one part file + a gate report flagging the first n_flagged rows."""
    tmp = Path(tempfile.mkdtemp(prefix="issue127-"))
    cids = ["ent-icdc-pool-cand-e%04d" % i for i in range(1, n_rows + 1)]
    (tmp / "payload.json").write_text(json.dumps([payload_row(c) for c in cids]))
    (tmp / "chunk1-part1.json").write_text(json.dumps([authored_row(c) for c in cids]))
    # The gate is written AFTER the parts, which is the honest order: check_authored
    # reads the parts and its output is redirected into the report.
    time.sleep(0.01)
    (tmp / "gate.txt").write_text(gate_text(cids[:n_flagged]))
    return tmp


def build(tmp: Path, **flags):
    """Run the real tool over real files. Returns (stdout, SystemExit message or '')."""
    argv = sys.argv
    sys.argv = ["build_repair_prompt.py",
                "--payload", str(tmp / "payload.json"),
                "--gate", str(tmp / "gate.txt"),
                "--part", str(tmp / "chunk1-part1.json"),
                "--out", str(tmp / "repair.prompt.txt"),
                "--overlay", str(tmp / "repair.json")]
    for k, v in flags.items():
        sys.argv += ["--" + k.replace("_", "-")] + (v if isinstance(v, list) else [v])
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            brp.main()
        return buf.getvalue(), ""
    except SystemExit as e:
        return buf.getvalue(), str(e)
    finally:
        sys.argv = argv


print("Issue #127 -- the repair round guards\n")

# ---------------------------------------------------------------------------
# GUARD 1 -- a gate report older than the parts it describes.
# ---------------------------------------------------------------------------
print("guard 1, the stale gate (§10-13 ran 4 rounds on one gate):")
tmp = slice_dir(20, 20)
printed, err = build(tmp)
check("a fresh gate builds normally", not err and "wrote repair prompt" in printed,
      err.splitlines()[0] if err else "20 rows, no refusal")

# apply_repair merged an overlay: the part file is now newer than the report.
time.sleep(0.01)
(tmp / "chunk1-part1.json").write_text((tmp / "chunk1-part1.json").read_text())
check("parts_newer_than_gate sees the merge",
      [p.name for p in brp.parts_newer_than_gate(
          tmp / "gate.txt", [tmp / "chunk1-part1.json"])] == ["chunk1-part1.json"])
printed, err = build(tmp)
check("round 2 off round 1's report is REFUSED",
      "the gate report is OLDER than the parts" in err,
      (err.splitlines() or ["<built anyway>"])[0])
check("...and the refusal prints the re-gate command that costs nothing",
      "check_authored.py" in err and "ZERO tokens" in err)
printed, err = build(tmp, stale_gate_reason="reformatted by hand, no repair merged")
check("--stale-gate-reason gets through, and says so on stdout",
      not err and "GUARD OVERRIDDEN — stale gate" in printed,
      (err.splitlines() or [printed.strip().splitlines()[-2]])[0])
rec = json.loads((tmp / "repair.prompt.scope.json").read_text())
check("the reason is RECORDED, with the files that triggered it",
      rec["guards"]["stale_gate_reason"] == "reformatted by hand, no repair merged"
      and rec["guards"]["parts_newer_than_gate"],
      f"scope record: {rec['guards']['parts_newer_than_gate']}")
# Non-vacuity: re-gating (rewriting the report) clears it without any flag.
time.sleep(0.01)
(tmp / "gate.txt").write_text(gate_text(
    ["ent-icdc-pool-cand-e%04d" % i for i in range(1, 21)]))
printed, err = build(tmp)
check("re-gating clears the guard with no flag at all", not err,
      (err.splitlines() or ["builds clean"])[0])

# ---------------------------------------------------------------------------
# GUARD 2 -- a scope wider than the gate's own list.
# ---------------------------------------------------------------------------
print("\nguard 2, the audit-widened scope (§10-13: ~33 flagged, 124 repaired):")
tmp = slice_dir(30, 20)
flagged = ["ent-icdc-pool-cand-e%04d" % i for i in range(1, 21)]
extra = ["ent-icdc-pool-cand-e0021", "ent-icdc-pool-cand-e0022"]

printed, err = build(tmp, ids=flagged)
check("--ids inside the gate's list needs no reason", not err,
      (err.splitlines() or ["20 gate rows, built"])[0])
printed, err = build(tmp, ids=flagged + extra)
check("--ids naming rows the gate did not flag is REFUSED",
      "--ids names 2 row(s) the gate did NOT flag" in err,
      (err.splitlines() or ["<built anyway>"])[0])
check("...and the refusal names the widened rows, not just the count",
      all(c in err for c in extra))
check("...and says an audit is a finding aid, not a work order",
      "finding aid, not a work order" in err and "§10-11" in err)
printed, err = build(tmp, ids=flagged + extra,
                     scope_reason=">=2 of 3 distractors eliminable with zero "
                                  "business knowledge")
check("--scope-reason gets through", not err and "+ 2 widened by hand" in printed,
      (err.splitlines() or [ln for ln in printed.splitlines() if "ids:" in ln][0])[0:120])
rec = json.loads((tmp / "repair.prompt.scope.json").read_text())
check("the criterion and the widened ids are RECORDED",
      rec["rows"]["widened"] == extra and rec["rows"]["gate_flagged"] == 20
      and "eliminable" in rec["guards"]["scope_reason"],
      f"{rec['rows']['gate_flagged']} flagged + {len(rec['rows']['widened'])} widened")
# The default path (no --ids) can only ever narrow, so it must never trip this.
printed, err = build(tmp)
check("the no---ids default is exempt by construction", not err,
      (err.splitlines() or ["gate list only"])[0])
printed, err = build(tmp, fail_only=[])
# This gate report carries only `soft` findings, so --fail-only selects nothing and the
# pre-existing empty-repair refusal fires first. That IS the point: the flag can only
# ever remove rows, so it must not be able to reach guard 2 by any path.
check("--fail-only narrows and cannot reach the widening guard",
      "did NOT flag" not in err,
      (err.splitlines() or ["built"])[0])

# ---------------------------------------------------------------------------
# GUARD 3 -- the pooling floor.
# ---------------------------------------------------------------------------
print(f"\nguard 3, the pooling floor of {brp.POOL_FLOOR} "
      f"(§10-13 ran 8 rows for 97.7k, 7 rows for 74.9k):")
check(f"POOL_FLOOR sits above §10-13's two worst agents (8 and 7 rows)",
      brp.POOL_FLOOR > 8, f"POOL_FLOOR = {brp.POOL_FLOOR}")
check("...and at or below its efficient ones (19 rows and up, 3-6k/row)",
      brp.POOL_FLOOR <= 19, f"POOL_FLOOR = {brp.POOL_FLOOR}")

tmp = slice_dir(30, 30)
small = ["ent-icdc-pool-cand-e%04d" % i for i in range(1, brp.POOL_FLOOR)]
printed, err = build(tmp, ids=small)
check(f"a {len(small)}-row round is REFUSED",
      "under the pooling floor" in err, (err.splitlines() or ["<built anyway>"])[0])
check("...and the refusal forbids padding the list to clear the floor",
      "never pad the list" in err and "ONE agent" in err,
      "the fix is pooling the round, never a wider scope")
printed, err = build(tmp, ids=small, solo_reason="final round, everything else assembled")
check("--solo-reason gets through and is recorded",
      not err
      and json.loads((tmp / "repair.prompt.scope.json").read_text())
              ["guards"]["solo_reason"].startswith("final round"),
      (err.splitlines() or ["built"])[0])
at_floor = ["ent-icdc-pool-cand-e%04d" % i for i in range(1, brp.POOL_FLOOR + 1)]
printed, err = build(tmp, ids=at_floor)
check(f"exactly {brp.POOL_FLOOR} rows is fine — the floor is not exclusive", not err,
      (err.splitlines() or [f"{len(at_floor)} rows built"])[0])

# --pooled-with: THE GUARD USED TO FORBID ITS OWN REMEDY.
#
# The refusal says to build every chunk's prompt and hand them to one agent. `--payload`
# takes ONE payload, so a pooled round is necessarily several prompts, each counting only
# its own rows -- and every one of them is refused. §10-14 hit this at 11 + 15 + 8 = 34
# rows across three prompts. The only escape was `--solo-reason`, whose text is "why this
# agent runs ALONE"; using it would have written a false statement into the scope record,
# which is the one artifact issue #127 created so that 33-vs-124 is legible afterwards.
print("\n  --pooled-with (the round the guard tells you to run):")
short = brp.POOL_FLOOR - 4
part = ["ent-icdc-pool-cand-e%04d" % i for i in range(1, short + 1)]

printed, err = build(tmp, ids=part)
check(f"a {short}-row prompt alone is still REFUSED",
      "under the pooling floor" in err, (err.splitlines() or ["<built anyway>"])[0])
check("...and the refusal now NAMES the flag, so the remedy is discoverable",
      "--pooled-with" in err,
      "a guard that forbids its own remedy is the defect this closes")

printed, err = build(tmp, ids=part, pooled_with="10")
check(f"{short} rows + 10 declared pooled clears the floor", not err,
      (err.splitlines() or [f"{short} + 10 built"])[0])
check("...and it is NOT reported as a guard override — the floor is MET",
      "GUARD OVERRIDDEN" not in printed and "pooled round:" in printed,
      [ln.strip() for ln in printed.splitlines() if "pooled" in ln][0][:100])
rec = json.loads((tmp / "repair.prompt.scope.json").read_text())
check("the pooled claim is RECORDED, like every other scope fact",
      rec["guards"]["pooled_with"] == 10 and rec["guards"]["solo_reason"] is None,
      f"scope record: pooled_with={rec['guards']['pooled_with']}")

# NON-VACUITY. It must not be a blanket off-switch: a claim too small to reach the floor
# still fails, and the refusal shows the arithmetic rather than repeating the bare count.
printed, err = build(tmp, ids=part, pooled_with="1")
check(f"{short} rows + a 1-row claim is STILL refused — not an off-switch",
      "under the pooling floor" in err, (err.splitlines() or ["<built anyway>"])[0])
check("...and the refusal shows the sum it actually tested",
      f"{short + 1}" in err and "declared pooled" in err,
      (err.splitlines() or ["<no arithmetic>"])[0])

# A round is pooled or it is solo. Claiming both is incoherent and must not silently
# pick one -- the scope record would then describe a round that never existed.
printed, err = build(tmp, ids=part, pooled_with="10",
                     solo_reason="final round, everything else assembled")
check("--pooled-with and --solo-reason together are REFUSED as contradictory",
      "contradict" in err, (err.splitlines() or ["<accepted both>"])[0])

# The default is unchanged, so nothing about a normal build moves.
printed, err = build(tmp, ids=at_floor)
check("with no --pooled-with the record says 0 and behaviour is identical",
      not err
      and json.loads((tmp / "repair.prompt.scope.json").read_text())
              ["guards"]["pooled_with"] == 0
      and "pooled round:" not in printed,
      (err.splitlines() or ["built, nothing printed about pooling"])[0])

# ---------------------------------------------------------------------------
# The scope record itself. Written on EVERY build, not only on an override -- the
# slice ledger records what an agent cost and nothing about what it was asked to fix,
# which is why §10-13's 33-vs-124 had to be reconstructed from overlay files.
# ---------------------------------------------------------------------------
print("\nthe scope record:")
rec = json.loads((tmp / "repair.prompt.scope.json").read_text())
check("a clean build writes one too, with no reasons set",
      rec["guards"]["scope_reason"] is None and rec["guards"]["solo_reason"] is None
      and rec["rows"]["total"] == brp.POOL_FLOOR)
check("it names the prompt, the overlay, the gate and the parts it was built from",
      all(rec[k] for k in ("prompt", "overlay", "gate", "payload", "parts")))
check("it lists the ids, so a later audit does not need the overlay files",
      rec["ids"] == at_floor)

# ---------------------------------------------------------------------------
# GUARD 4 -- the sharded audit input.
# ---------------------------------------------------------------------------
print("\nguard 4, the audit input (§10-13 sent 192,814 chars to BOTH agents):")


def audit(tmp: Path, *args):
    argv = sys.argv
    sys.argv = ["build_audit_input.py"] + list(args)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            bai.main()
        return buf.getvalue(), ""
    except SystemExit as e:
        return buf.getvalue(), str(e)
    finally:
        sys.argv = argv


tmp = Path(tempfile.mkdtemp(prefix="issue127-audit-"))
cids = ["ent-icdc-pool-cand-e%04d" % i for i in range(1, 11)]
for ch in ("chunk1", "chunk2"):
    (tmp / f"{ch}-part1.json").write_text(json.dumps([authored_row(c) for c in cids]))
parts = [str(tmp / "chunk1-part1.json"), str(tmp / "chunk2-part1.json")]

printed, err = audit(tmp, "--part", *parts, "--out", str(tmp / "gate"),
                     "--stem", "audit-answer", "--agents", "2")
check("2 agents get 2 files", not err
      and (tmp / "gate" / "audit-answer-01.json").exists()
      and (tmp / "gate" / "audit-answer-02.json").exists(),
      (err.splitlines() or ["wrote 2 shards"])[0])
# #186 wrapped a shard in a `{audit, rows}` object; the ROWS below are unchanged.
a = json.loads((tmp / "gate" / "audit-answer-01.json").read_text())[bai.ROWS_KEY]
b = json.loads((tmp / "gate" / "audit-answer-02.json").read_text())[bai.ROWS_KEY]
check("the shards are DISJOINT and complete",
      len(a) == len(b) == 10
      and not ({(r["chunk"], r["cand_id"]) for r in a}
               & {(r["chunk"], r["cand_id"]) for r in b}),
      f"{len(a)} + {len(b)} rows, no overlap")
check("every row carries its chunk — cand_ids collide across chunks",
      {r["chunk"] for r in a} and {r["chunk"] for r in b}
      and all("chunk" in r for r in a + b),
      f"shard 1 {sorted({r['chunk'] for r in a})} · shard 2 {sorted({r['chunk'] for r in b})}")
check("the blind profile drops answer AND explanation from the BYTES",
      not any(t in (tmp / "gate" / "audit-answer-01.json").read_text()
              for t in bai.BLIND_FORBIDDEN),
      f"forbidden tokens: {', '.join(bai.BLIND_FORBIDDEN)}")
check("the blind field list is §10-13's own, in its own key order",
      list(a[0]) == list(bai.BLIND_FIELDS), f"{list(a[0])}")
check("the run prints what one shared file would have re-sent",
      "duplicate ingestion" in printed,
      [ln.strip() for ln in printed.splitlines() if "duplicate" in ln][0][:110])

idx = json.loads((tmp / "gate" / "audit-answer-index.json").read_text())
check("the index says which file is whose",
      len(idx["shards"]) == 2 and idx["total_rows"] == 20
      and all(s["ids"] for s in idx["shards"]))

printed, err = audit(tmp, "--part", *parts, "--out", str(tmp / "gate"),
                     "--stem", "audit-arith", "--agents", "1", "--profile", "full")
full = json.loads((tmp / "gate" / "audit-arith-01.json").read_text())[bai.ROWS_KEY]
check("the full profile (arithmetic audit only) DOES carry the key",
      not err and full[0]["answer"] == "A" and "explanation" in full[0]
      and list(full[0]) == list(bai.FULL_FIELDS))

# The refusals.
printed, err = audit(tmp, "--part", *parts, "--out", str(tmp / "gate"),
                     "--stem", "x", "--agents", "40")
check("more agents than rows is refused, not silently emptied",
      "some shard would be empty" in err, (err.splitlines() or ["<wrote it>"])[0])
printed, err = audit(tmp, "--part", parts[0], parts[0], "--out", str(tmp / "gate"),
                     "--stem", "x", "--agents", "1")
check("the same part file twice is refused",
      "appears in both" in err, (err.splitlines() or ["<audited twice>"])[0])
printed, err = audit(tmp, "--part", *parts, "--out", str(tmp / "gate"),
                     "--stem", "x", "--agents", "1", "--ids", cids[0])
check("a bare cand_id living in two chunks is refused, never resolved",
      "match more than one chunk" in err, (err.splitlines() or ["<guessed>"])[0])
printed, err = audit(tmp, "--part", *parts, "--out", str(tmp / "gate"),
                     "--stem", "x", "--agents", "1", "--ids", f"chunk2:{cids[0]}")
check("...and the chunk-scoped form works",
      not err and json.loads(
          (tmp / "gate" / "x-01.json").read_text())[bai.ROWS_KEY][0]["chunk"] == "chunk2")
printed, err = audit(tmp, "--part", *parts, "--out", str(tmp / "gate"),
                     "--stem", "x", "--agents", "3", "--per-chunk")
check("--per-chunk with the wrong --agents is refused",
      "--agents says 3" in err, (err.splitlines() or ["<wrote it>"])[0])

# `--agents` is the whole fix: it must be impossible to omit.
argv = sys.argv
sys.argv = ["build_audit_input.py", "--part", parts[0], "--out", str(tmp / "gate"),
            "--stem", "x"]
try:
    with redirect_stdout(io.StringIO()), open(os.devnull, "w") as devnull:
        stderr, sys.stderr = sys.stderr, devnull
        try:
            bai.main()
            code = 0
        finally:
            sys.stderr = stderr
except SystemExit as e:
    code = e.code
finally:
    sys.argv = argv
check("--agents cannot be omitted — that is the §10-13 defect in one flag", code == 2,
      f"argparse exit {code}")

# ---------------------------------------------------------------------------
# What these fixtures do NOT check -- state it, don't imply coverage.
#
#  * That a pooled agent is CHEAPER. POOL_FLOOR comes from §10-13's ledger (3.1k/row at
#    58 rows vs 10-12k/row at 7-8), one slice, unreplicated. It separates two measured
#    populations; it is not a fitted threshold and should move if a later slice's ledger
#    disagrees.
#  * That the repair scope is CORRECT. Guard 2 asks for a criterion; nothing here can
#    tell a good criterion from "the audit flagged it". §10-11's rule -- a stated,
#    row-testable predicate -- is the bar, and only a reader enforces it.
#  * Whether re-gating between rounds actually shortens a round. It costs zero tokens
#    and §10-13's one re-gate cut a 4-round chunk's list to 1 row, which is an argument,
#    not a measurement.
#  * Anything about the AUDIT AGENTS' judgement. This shards their input; it does not
#    read their output.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
