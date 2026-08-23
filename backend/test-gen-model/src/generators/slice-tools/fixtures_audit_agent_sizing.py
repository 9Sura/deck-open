"""Issue #156 fixtures: `--agents` is sized by ROWS PER AGENT, and the advisory is one-sided.

THE DEFECT. `build_audit_input.py` requires `--agents` -- #127's fix, and it works: no shard
is ever ingested twice. But requiring the flag settles only that a number must be given, not
which one, and the help text described what the flag DOES. So the value rode forward from the
previous slice's command block. §10-14 carried a 263-row batch's `2` onto a 130-row batch:

    chunks 5-8 coherence x2   263 rows   132/agent   223.9k   0.85k/row
    chunks 9+10 coherence x2  130 rows    65/agent   168.9k   1.30k/row
    chunks 5-8 blind x2       263 rows   132/agent   223.8k   0.85k/row
    chunks 9+10 blind x2      130 rows    65/agent   156.4k   1.20k/row

Same prompts, same instruments, 41-53% more per row at half the shard, because the ~65k fixed
agent overhead is paid per AGENT. At `--agents 1` those 130 rows read for roughly 221k instead
of 325k -- about 104k, and most of why that slice-half's `tail / authoring` came in at 1.58x
against a 0.41-1.13x norm (#127's own tripwire).

WHAT IS ASSERTED HERE, and why each one is a claim a regression could break:

  1. The advisory FIRES on the §10-14 shape (130 rows, 2 agents) and names `--agents 1`.
  2. It stays QUIET on the shape that was correct (263 rows, 2 agents = 131/agent).
  3. IT IS ONE-SIDED. It fires only when a STRICTLY SMALLER agent count would still leave
     every shard at or above the floor. 200 rows at 2 agents is 100/agent -- under the floor
     -- and stays quiet anyway, because the only alternative is a 200-row shard and NOTHING
     HAS EVER RUN ONE. Rows-per-agent has been sampled at 65 and ~131, full stop. A version
     that "helpfully" advised 1 agent there would be trading a measured shortfall for an
     unmeasured shard, which is not an improvement. This is the assertion most likely to be
     lost by someone tidying the predicate, so it is checked at four shapes.
  4. `--per-chunk` still gets the note, plus the only lever it has (drop `--per-chunk`) --
     silence there would read as approval of a split the caller cannot change.
  5. IT IS ADVISORY. Exit code 0, and the shard/index BYTES are unchanged. The advisory is
     printed beside the duplicate-ingestion line the tool already printed, so both sides of
     the same trade appear together; neither may alter what is written.
  6. The docstring, the help text and the plan all say FLOOR, not knee, and carry the
     confound: the blind arm's `audit-c5678-01`/`-02` are the SAME instrument at 132 and 131
     rows and cost 0.66k vs 1.05k/row -- a 59% spread at fixed shape, tracking tool calls
     (2 vs 6). That is larger than the effect being claimed, and it is §4.7's "shape does not
     predict cost", the finding that retired §4.6 cut A. The coherence arm is the clean
     control. If a later edit restates ~130 as a measured optimum, this check fails.

WHY A FIXTURE AND NOT A COMMENT. Sixth guard in this toolchain asserted in prose (#76
GATED_FIELDS, #88 the rule-5 predicate, #89 the COPY THROUGH lookup, #92 probe-chunk purity,
#155 row_ref, now this). The §10-11 rule stands: when a gate's behaviour is asserted in a
comment, assert it in a fixture too.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_audit_agent_sizing.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded -- several sibling fixture files still point
at `/Users/.../GNS DECA APP`, a directory that was renamed to DECK-APP, so they cannot be run
at all. Don't repeat that.
"""
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import build_audit_input as bai  # noqa: E402

REPO = Path(__file__).resolve().parents[5]
PLAN = REPO / "backend/test-gen-model/plans/10-per-pi-review-depth-plan.md"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def row(n):
    return {
        "cand_id": f"mkt-district-pool-cand-e{n:04d}",
        "cluster": "marketing", "level": "District",
        "instructionalArea": "Marketing-Information Management",
        "performanceIndicator": "Explain the nature of marketing research",
        "question": "A retailer reviews its policy.",
        "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
        "answer": "B", "explanation": "Because two.", "difficulty": "easy",
    }


def run_cli(*argv):
    saved = sys.argv
    sys.argv = ["build_audit_input.py", *argv]
    buf = io.StringIO()
    code = 0
    try:
        with redirect_stdout(buf):
            bai.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if isinstance(e.code, str):
            buf.write(e.code)
    finally:
        sys.argv = saved
    return buf.getvalue(), code


def build(tmp, n_rows, agents, chunks=1, extra=()):
    """n_rows spread over `chunks` part files. Returns (stdout, exit code, out dir)."""
    parts, i = [], 0
    per = n_rows // chunks
    for c in range(chunks):
        take = per if c < chunks - 1 else n_rows - i
        p = tmp / f"chunk{c + 9}-part1.json"
        p.write_text(json.dumps([row(k) for k in range(i, i + take)], indent=2),
                     encoding="utf-8")
        parts.append(p)
        i += take
    out = tmp / f"gate{n_rows}-{agents}-{len(extra)}"
    text, code = run_cli("--part", *[str(p) for p in parts], "--out", str(out),
                         "--stem", "audit", "--agents", str(agents), *extra)
    return text, code, out


print("Issue #156 -- --agents is sized by rows per agent\n")

# ---------------------------------------------------------------------------
# 1. THE §10-14 SHAPE. 130 rows over 2 agents is the batch that overpaid.
# ---------------------------------------------------------------------------
print("the §10-14 shape (130 rows, --agents 2):")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    text, code, out = build(tmp, 130, 2)
    check("the build still succeeds — the advisory is ADVISORY", code == 0)
    check("it fires", "NOTE:" in text)
    check("...naming the rows-per-agent it actually got", "65 rows each" in text)
    check("...and the smaller agent count", "`--agents 1`" in text)
    check("...and the issue that measured it", "#156" in text)
    check("the duplicate-ingestion line is STILL printed beside it — both sides of "
          "the trade", "duplicate ingestion" in text and "NOTE:" in text)
    # #127's line says sharding SAVES; #156's says it COSTS. Printing one without the
    # other is how a slice reads half a trade-off and sizes on it.
    i_waste, i_note = text.index("duplicate ingestion"), text.index("NOTE:")
    check("...in that order, cost after saving", i_waste < i_note)

    # The bytes are the contract: an advisory that changed a shard would be a gate.
    ref_text, ref_code, ref_out = build(tmp, 130, 1)
    check("the recommended --agents 1 builds clean", ref_code == 0)
    check("...and reads the same 130 rows",
          len(json.loads((ref_out / "audit-01.json").read_text())[bai.ROWS_KEY]) == 130)
    check("...with no advisory of its own — 130/agent clears the floor",
          "NOTE:" not in ref_text)

# ---------------------------------------------------------------------------
# 2. THE SHAPE THAT WAS RIGHT. 263 rows over 2 agents is 131 each.
# ---------------------------------------------------------------------------
print("\nthe shape that was already correct (263 rows, --agents 2):")
with tempfile.TemporaryDirectory() as td:
    text, code, out = build(Path(td), 263, 2)
    check("no advisory", code == 0 and "NOTE:" not in text)
    check("...and the shards really are ~131 each",
          [s["n"] for s in json.loads((out / "audit-index.json").read_text())["shards"]]
          == [132, 131])

# ---------------------------------------------------------------------------
# 3. ONE-SIDED. The floor is a floor; nothing has run a shard above ~132 rows.
# ---------------------------------------------------------------------------
print("\none-sided — it never advises a shard bigger than any that has been measured:")
SHAPES = [
    # rows, agents, fires?, suggested, why
    (130, 2, True, 1, "the §10-14 batch — 1 agent is 130 rows, inside measured range"),
    (90, 2, True, 1, "45/agent, and 90 rows is a shard smaller than §10-14's own"),
    (275, 3, True, 2, "91/agent, and 2 agents is ~137 each — still near measured"),
    (400, 4, True, 3, "100/agent, and 3 agents is ~133 each"),
    (200, 2, False, None, "100/agent IS under the floor, but 1 agent means a 200-row "
                          "shard nobody has run — quiet on purpose"),
    (250, 2, False, None, "125/agent, same reason"),
    (260, 2, False, None, "exactly 130/agent — the floor is met, not missed"),
    (520, 4, False, None, "130/agent"),
    (130, 1, False, None, "there is no smaller count than 1"),
]
for rows, agents, fires, suggested, why in SHAPES:
    note = bai.sizing_note(rows, agents, False)
    ok = bool(note) == fires
    if fires and note:
        ok = ok and f"`--agents {suggested}`" in note
    check(f"{rows:>3} rows / {agents} agents ({rows // agents:>3} each) -> "
          f"{'fires, suggests ' + str(suggested) if fires else 'quiet'}", ok, why)

# ---------------------------------------------------------------------------
# 4. --per-chunk. The note must name the only lever the caller has.
# ---------------------------------------------------------------------------
print("\n--per-chunk (--agents is pinned to the chunk count):")
with tempfile.TemporaryDirectory() as td:
    text, code, out = build(Path(td), 130, 2, chunks=2, extra=("--per-chunk",))
    check("the build succeeds", code == 0)
    check("the advisory still prints — silence would read as approval", "NOTE:" in text)
    check("...and names the only lever: dropping --per-chunk", "--per-chunk pins" in text)
    check("...and says what dropping it costs (topical coherence)",
          "topical coherence" in text)

# ---------------------------------------------------------------------------
# 5. BYTES UNCHANGED. The advisory is stdout; a shard is a contract.
# ---------------------------------------------------------------------------
print("\nadvisory means advisory:")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    _, _, a = build(tmp, 130, 2)
    saved_floor = bai.ROWS_PER_AGENT_FLOOR
    try:
        # Move the floor so the advisory's firing state flips, and assert the written
        # bytes do not move with it.
        bai.ROWS_PER_AGENT_FLOOR = 1
        _, _, b = build(tmp, 130, 2)
    finally:
        bai.ROWS_PER_AGENT_FLOOR = saved_floor
    same = all((a / f).read_bytes() == (b / f).read_bytes()
               for f in ("audit-01.json", "audit-02.json", "audit-index.json"))
    check("the floor does not touch a single written byte", same)
    check("...and the index records no advisory state",
          "floor" not in (a / "audit-index.json").read_text().lower())

# ---------------------------------------------------------------------------
# 6. FLOOR, NOT KNEE — in every place the number is written down.
# ---------------------------------------------------------------------------
print("\nfloor, not knee, and the confound travels with the number:")
# Whitespace-collapsed, because every one of these phrases is prose inside a wrapped
# docstring and a reflow is not a regression. Matching the raw text would fail the day
# someone rewraps a paragraph, which trains the next reader to delete the assertion.
src = " ".join((GEN / "build_audit_input.py").read_text(encoding="utf-8").split())
plan = " ".join(PLAN.read_text(encoding="utf-8").split()) if PLAN.exists() else ""

check("the docstring says the sampled values were 65 and ~131",
      "65 and ~131" in src)
check("...that nothing has run larger", "nothing has run above" in src.lower()
      or "no shard has ever run larger" in src)
check("...and carries the blind arm's 0.66 vs 1.05 confound",
      "0.66k" in src and "1.05k" in src)
check("...crediting it to the finding that retired cut A",
      "shape does not predict cost" in src)
check("...and says why a floor survives here: an audit agent WRITES nothing",
      "WRITES nothing" in src)
check("the advisory itself repeats the caveat where it is read",
      "floor, not an optimum" in bai.sizing_note(130, 2, False))

parser_help = ""
saved = sys.argv
sys.argv = ["build_audit_input.py", "--help"]
buf = io.StringIO()
try:
    with redirect_stdout(buf):
        bai.main()
except SystemExit:
    parser_help = buf.getvalue()
finally:
    sys.argv = saved
check("--agents help says to size by ROWS PER AGENT", "ROWS PER AGENT" in parser_help)
check("...gives the floor", str(bai.ROWS_PER_AGENT_FLOOR) in parser_help)
check("...and says to recompute it per batch", "recompute" in parser_help.lower())

check("plan §4 step 6a's command block says its `2` is not a default",
      "RECOMPUTE --agents FOR YOUR BATCH" in plan)
check("...and the plan states the floor with the same caveat",
      "FLOOR, not a knee" in plan or "floor, not a knee" in plan.lower())

# ---------------------------------------------------------------------------
failed = [n for n, ok, _ in results if not ok]
print(f"\n  {len(results) - len(failed)} passed / {len(failed)} failed")
if failed:
    for n in failed:
        print(f"    FAILED: {n}")
sys.exit(1 if failed else 0)
