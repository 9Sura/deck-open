"""Issue #187 fixtures: TURN OVERRUN is an AUTHORING verdict, and repair turns are free.

THE DEFECT. `agent_cost report` printed a confidently-worded verdict --

    TURN OVERRUN — 1 agent(s) spent at least twice the tool calls their
    group count budgets (1 Read + one Write per group + a final message):
      repair-c91011          69 calls vs  7 budgeted ( 10x)   8.12k/item
    Those calls bought nothing the gate does not do for free, and the batch
    that spent the most of them is the one that shipped five wrong keys.

-- on a POOLED REPAIR agent. The budget is an authoring model and the code says so in its
own comment. The carve-out for everything else worked by proxy ("a `groups` of 1 on a
non-authoring agent makes the budget nominal"), and that proxy fails in BOTH directions:

  * a pooled repair agent records `groups` = the number of repair prompts it was handed
    (5 here), so its budget computed to 7 and it was scored exactly like an author;
  * a 6-call audit against a nominal 3 fired anyway -- §10-13's `audit-answer-opsecon` and
    §10-14's `audit-c5678-02` -- which is the "4-vs-3 line is noise" the proxy was written
    to prevent.

And the closing sentence names §10-14 chunk3, an AUTHORING agent that spent 161 calls
self-validating. Attached to a repair agent it asserts a link between tool calls and item
quality that nothing has measured on that path.

THE LEDGER CONTAINS ITS OWN REFUTATION. Four pooled repair rounds across three groups of
§10-16, and the rate does not move with the turns:

    repair-r1-c1234        29 rows    8 calls   8.06k/row
    repair-c5678-pooled    52 rows   16 calls   6.21k/row
    repair-c91011          41 rows   69 calls   8.12k/row
    repair2-c91011          7 rows    8 calls  17.27k/row

8.6x the turns between rows 1 and 3, same rate to within 1%. The reads are the tool's own
contract -- `apply_repair` requires FULL copy-through rows, so repairing one field means
first reading every other field of that row verbatim -- and they are cache hits against a
prefix the agent already carries, which is also why `T_REINGEST` overshot that agent
(389.3k predicted against 333.1k measured). What the rate DOES track, on all four points,
is the denominator.

WHAT IS ASSERTED HERE, and why each is a claim a regression could break:

  1. TURN OVERRUN fires for `kind == authoring` and NOTHING else. §10-14's chunk3 at 161
     calls still fires; §10-16's repair-c91011 at 69 does not.
  2. THE WRONG-KEYS SENTENCE TRAVELS WITH IT. It is a claim about an authoring agent, so
     it may not appear in a report whose only over-budget rows are repair agents.
  3. The repair table needs NO `prompt_chars`. Two of the four rounds above carry none,
     which is why the comparison that refutes the verdict was invisible to the tool that
     printed it. The two-theory table still requires prompt_chars; the turn reading must
     not.
  4. The repair section is sorted by ROWS, not by turns, and prints whenever repair rounds
     exist. The comparison IS the finding -- a section that only appeared on an overrun
     would show one row and no denominator.
  5. INFERENCE IS ONE-SIDED. Ledgers predate `--kind`, so kind is guessed from the label;
     the guess never returns `authoring` for a label it does not recognise. Guessing
     `authoring` wrong re-creates #187. Guessing it missing costs one line under a header
     that asks for `--kind`.
  6. A repair marker beats an audit marker. §10-12's `audit-repair` / `audit-repair-pooled`
     are repair agents named for the audit that scoped them; its own note says so ("7 rows
     across 3 chunks in ONE agent").
  7. An explicit `--kind` always beats the label.
  8. An over-budget row of UNKNOWN kind is reported as unknown, with no verdict attached --
     §10-11's `chunk3-tail`/`chunk4-tail` audited AND repaired and are neither.

WHY A FIXTURE AND NOT A COMMENT. Seventh guard in this toolchain asserted in prose (#76
GATED_FIELDS, #88 the rule-5 predicate, #89 the COPY THROUGH lookup, #92 probe-chunk
purity, #155 row_ref, #156 agent sizing, now this). The §10-11 rule stands: when a gate's
behaviour is asserted in a comment, assert it in a fixture too.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_agent_cost_kinds.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import agent_cost as ac  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def row(label, items, groups, calls, total, prompt_chars=None, kind=None):
    e = {"label": label, "items": items, "groups": groups, "tool_calls": calls,
         "total": total, "effort": "default", "model": "sonnet"}
    if prompt_chars is not None:
        e["prompt_chars"] = prompt_chars
    if kind is not None:
        e["kind"] = kind
    return e


def report(entries):
    buf = io.StringIO()
    with redirect_stdout(buf):
        ac.cmd_report(entries)
    return buf.getvalue()


# §10-16's real rows, verbatim from output/plan-10/10-16/cost.json. Note that
# repair-r1-c1234 and repair-c5678-pooled carry NO prompt_chars -- that is assertion 3.
TEN_SIXTEEN = [
    row("chunk10", 93, 4, 6, 272601, 67425),
    row("chunk11", 58, 7, 8, 210791, 62017),
    row("cohere-c91011", 228, 0, 13, 195849, 288566),
    row("blind-c91011", 228, 0, 6, 160943, 210000),
    row("repair-r1-c1234", 29, 4, 8, 233639),
    row("repair-c5678-pooled", 52, 7, 16, 323139),
    row("repair-c91011", 41, 5, 69, 333055, 186000),
    row("repair2-c91011", 7, 3, 8, 120909, 40000),
]

print("Issue #187 -- TURN OVERRUN is an authoring verdict\n")

# ---------------------------------------------------------------------------
# 1-3. THE §10-16 REPORT. The agent the issue was filed about.
# ---------------------------------------------------------------------------
print("§10-16's ledger, the report that mis-fired:")
text = report(TEN_SIXTEEN)
check("no TURN OVERRUN — the only over-budget agent is a repair agent",
      "TURN OVERRUN" not in text)
check("...so the wrong-keys sentence is not printed either",
      "five wrong keys" not in text,
      "it is a claim about §10-14 chunk3, an AUTHORING agent")
check("repair-c91011 is not indicted", "69 calls vs" not in text)
check("REPAIR TURNS prints instead", "REPAIR TURNS" in text)
check("...naming all four rounds, including the two with no prompt_chars",
      all(f"{lbl:<20}" in text for lbl in
          ("repair-r1-c1234", "repair-c5678-pooled", "repair-c91011", "repair2-c91011")),
      "the two-theory table needs prompt_chars; a turn budget does not")
check("...with the rates that refute the verdict",
      "8.06k/row" in text and "8.12k/row" in text and "6.21k/row" in text
      and "17.27k/row" in text)
check("...sorted by ROWS, not by turns",
      [t.strip().split()[0] for t in text.splitlines() if "rows" in t and "calls" in t]
      == ["repair-c5678-pooled", "repair-c91011", "repair-r1-c1234", "repair2-c91011"])
check("...saying why the reads exist (apply_repair's copy-through rows)",
      "copy-through" in text)
check("...and refusing the lever outright", "measured and refuted" in text)
check("...pointing at the lever that IS supported", "SIZE of the round" in text)

# ---------------------------------------------------------------------------
# 4. THE COMPARISON IS THE POINT. It prints with no overrun at all.
# ---------------------------------------------------------------------------
print("\nthe repair table is a comparison, not an alarm:")
quiet = report([row("chunk1", 49, 2, 3, 184632, 50120),
                row("repair-a", 40, 3, 4, 240000),
                row("repair-b", 8, 2, 3, 130000)])
check("it prints with zero rounds past budget", "REPAIR TURNS" in quiet)
check("...and says so rather than counting an overrun",
      "2 repair round(s)." in quiet and "past an authoring" not in quiet)
solo = report([row("repair-a", 40, 3, 4, 240000)])
check("a single round still prints — one point is still a denominator reading",
      "REPAIR TURNS" in solo)

# ---------------------------------------------------------------------------
# 5. THE AUTHORING VERDICT IS UNTOUCHED. §10-14 chunk3 is the case it was built for.
# ---------------------------------------------------------------------------
print("\nthe authoring verdict still fires (§10-14 chunk3, 161 calls vs 5):")
auth = report([row("chunk3-author", 90, 3, 161, 233000, 47000),
               row("chunk6-author", 62, 3, 11, 221000, 47000),
               row("chunk4-author", 41, 3, 4, 150000, 47000)])
check("TURN OVERRUN prints", "TURN OVERRUN" in auth)
check("...says AUTHORING agent(s) in the header", "authoring agent(s)" in auth)
check("...names chunk3-author at 161 calls", "161 calls vs  5 budgeted" in auth)
check("...and the 11-vs-5 sibling, which is also >=2x", "11 calls vs  5 budgeted" in auth)
check("...not the 4-call one", " 4 calls vs  5 budgeted" not in auth)
check("...and keeps the wrong-keys sentence, where it is true", "five wrong keys" in auth)

# ---------------------------------------------------------------------------
# 6. THE AUDIT NOISE THE OLD PROXY LET THROUGH.
# ---------------------------------------------------------------------------
print("\nthe 4-vs-3 audit line the group-count proxy was supposed to suppress:")
noise = report([row("audit-answer-opsecon", 30, 1, 6, 31500, 20000),
                row("audit-c5678-02", 131, 1, 6, 137000, 20000)])
check("neither audit is indicted", "TURN OVERRUN" not in noise)
check("...and no repair section is invented for them", "REPAIR TURNS" not in noise)

# ---------------------------------------------------------------------------
# 7. INFERENCE. One-sided, and explicit always wins.
# ---------------------------------------------------------------------------
print("\ninfer_kind is one-sided — `authoring` is never a fallback:")
LABELS = [
    ("chunk1", "authoring", "the bare shape"),
    ("chunk10", "authoring", "two digits"),
    ("h1", "authoring", "the hard batch"),
    ("h1a", "authoring", "§10-12 split H1 in two"),
    ("topup", "authoring", "§10-5's 64-item easy top-up"),
    ("chunk2-author-r2", "authoring", "allow-listed suffixes only"),
    ("chunk3-attempt1-DISCARDED", "authoring", "case-insensitive"),
    ("chunk8-reauthor", "authoring", "not 'repair' — it wrote the batch again"),
    ("chunk1-repair", "repair", "the common form"),
    ("repair-c5678-pooled", "repair", "leading marker"),
    ("audit-repair-pooled", "repair", "§10-12: an audit-SCOPED repair agent"),
    ("audit-repair", "repair", "repair beats audit, in that order"),
    ("chunk5-balance-fix", "repair", "§10-10 named one repair round this"),
    ("h1-deleak", "repair", "it edited authored rows"),
    ("cohere-c91011", "audit", "coherence"),
    ("recohere-c5678", "audit", "the re-check"),
    ("blind-c91011", "audit", "blind"),
    ("arith-c6", "audit", "arithmetic"),
    ("h1-rater-01", "audit", "a referee writes nothing"),
    ("h1-blind-solver-2", "audit", "so does a blind solver"),
    ("survivor-hunt", "audit", "and a survivor hunt"),
    ("chunk1-cohere", "audit", "an audit named for its chunk is still an audit"),
    ("chunk3-tail", None, "§10-11: audited AND repaired. Neither. Say so."),
    ("chunk4-tail", None, "same"),
    ("some-new-agent", None, "UNRECOGNISED IS NEVER AUTHORING — this is the whole rule"),
    ("chunk9-experiment", None, "a chunk stem does not license the guess on its own"),
    ("", None, "no label, no guess"),
]
for label, want, why in LABELS:
    got = ac.infer_kind(label)
    check(f"{label or '(empty)':<26} -> {str(want):<9}", got == want,
          why + ("" if got == want else f"   GOT {got!r}"))

print("\nan explicit --kind always beats the label:")
check("a repair-looking label recorded as authoring is scored as authoring",
      ac.agent_kind({"label": "chunk1-repair", "kind": "authoring"}) == "authoring")
check("...and an authoring-looking label recorded as repair is not indicted",
      "TURN OVERRUN" not in report([row("chunk1", 40, 2, 40, 200000, 47000,
                                        kind="repair")]))
check("`--kind` is restricted to the three the report can act on",
      ac.KINDS == ("authoring", "repair", "audit"))

# ---------------------------------------------------------------------------
# 8. UNKNOWN KIND IS REPORTED AS UNKNOWN, WITH NO VERDICT.
# ---------------------------------------------------------------------------
print("\n§10-11's tails — over budget, kind unknown, no verdict:")
tails = report([row("chunk3-tail", 47, 1, 71, 356000, 47000),
                row("chunk4-tail", 47, 1, 94, 353000, 47000)])
check("they are not indicted as authors", "TURN OVERRUN" not in tails)
check("...and not silently dropped either", "KIND NOT RECORDED" in tails)
check("...both named", "chunk3-tail" in tails and "chunk4-tail" in tails)
check("...with the budget shown but no claim about what it bought",
      "94 calls vs  3 budgeted" in tails and "bought nothing" not in tails)
check("...and the fix stated", "Record `--kind`" in tails)

# ---------------------------------------------------------------------------
# 9. RECORD ROUND-TRIPS THE FIELD.
# ---------------------------------------------------------------------------
print("\n--kind round-trips through `record`:")
import json  # noqa: E402
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    led = Path(td) / "cost.json"
    saved = sys.argv
    sys.argv = ["agent_cost.py", "--ledger", str(led), "record", "--label", "chunk1",
                "--kind", "authoring", "--items", "49", "--groups", "2",
                "--tool-calls", "3", "--total", "184632"]
    try:
        with redirect_stdout(io.StringIO()):
            ac.main()
    finally:
        sys.argv = saved
    e = json.loads(led.read_text(encoding="utf-8"))[0]
    check("the field is written", e.get("kind") == "authoring")
    check("...and nothing else moved",
          e["items"] == 49 and e["groups"] == 2 and e["tool_calls"] == 3)

    sys.argv = ["agent_cost.py", "--ledger", str(led), "record", "--label", "bogus",
                "--kind", "referee", "--items", "1"]
    code = None
    try:
        with redirect_stdout(io.StringIO()):
            ac.main()
    except SystemExit as ex:
        code = ex.code
    finally:
        sys.argv = saved
    check("an unknown kind is refused rather than stored", code not in (0, None),
          "a free-text kind would silently opt an agent out of the verdict")

# ---------------------------------------------------------------------------
# 10. THE PROSE CARRIES THE MEASUREMENT, WHERE THE NEXT READER FINDS IT.
# ---------------------------------------------------------------------------
print("\nthe refutation is recorded in the source, not only in the issue:")
src = " ".join((GEN / "agent_cost.py").read_text(encoding="utf-8").split())
check("the four-point denominator series is in the code",
      "52 -> 6.21k, 41 -> 8.12k, 29 -> 8.06k, 7 -> 17.27k" in src)
check("...with the turn ratio it refutes", "8.6x the turns" in src)
check("...and the T_REINGEST overshoot that explains why the reads are cheap",
      "389.3k against a measured 333.1k" in src)
check("...and the proxy's other failure direction, so it is not re-introduced",
      "audit-answer-opsecon" in src and "audit-c5678-02" in src)
check("the budget is described as an AUTHORING model", "AUTHORING agent's turn budget" in src
      or "authoring model" in src.lower())

# ---------------------------------------------------------------------------
failed = [n for n, ok, _ in results if not ok]
print(f"\n  {len(results) - len(failed)} passed / {len(failed)} failed")
if failed:
    for n in failed:
        print(f"    FAILED: {n}")
sys.exit(1 if failed else 0)
