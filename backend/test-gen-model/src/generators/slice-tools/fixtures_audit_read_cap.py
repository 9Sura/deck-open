"""Issue #186 fixtures: a shard is bigger than one `Read` returns, and it says so itself.

THE HAZARD. An audit agent that reads ONE PAGE of its shard, finds nothing in it, and
reports a clean batch produces a return that is INDISTINGUISHABLE IN SHAPE from one that
read every row. There is no signal, no artifact, and nothing downstream parses an audit's
return, so the failure would be silent, total, and would read as a clean batch.

THE MEASUREMENT. §10-16 chunk10's AUTHORING agent reported the cap firing, unprompted, as
its reason for exceeding its tool budget: its prompt file "was truncated by the system at
line 615". That file is 793 lines / 67,395 chars, and line 615 lands at 45,035 chars. It
recovered only because the payload's own group structure told it groups 3 and 4 were
missing -- an audit shard is a flat list of independent rows and nothing in row 90 says
rows 91-228 exist. The same slice's shards:

    audit-c91011-cohere-01.json   288,566ch   4,334 lines   (--profile full)
    audit-c91011-blind-01.json    166,480ch   3,194 lines
    audit-c1234-cohere-01.json    243,565ch   3,707 lines
    audit-c5678-cohere-01.json    199,339ch   2,738 lines

Whether the three earlier passes read to the end is NOT RECOVERABLE from any artifact.

THE FIX is two cheap changes and one deliberate omission. A shard is now a `{audit, rows}`
object whose header states `n_rows`, `chars`, `lines`, `read_offsets` and the sentence
requiring the examined-row count back -- the shard is the ONE artifact every auditor
provably reads. The build prints a red OVER THE SINGLE-READ CAP block with those offsets.
NOT done: a checker for the returned count, because nothing parses an audit's return today
(#154's precedent) and a parser is a bigger change than the hazard warrants.

WHAT IS ASSERTED HERE:

  1. The §10-16 shape trips the warning, and the warning names the offsets, not just a size.
  2. The header DESCRIBES THE FILE IT IS INSIDE, exactly -- the counts are self-referential
     and solved to a fixed point, so a byte-level disagreement is a bug, not rounding.
  3. The offsets really page the file: from line 1, strictly increasing, past the last line,
     and no page larger than the measured cap.
  4. verify() FAILS on each way the header can be wrong. A number an auditor reconciles
     against is worse than none if it is stale, so a bare array, a wrong `n_rows`, stale
     size counts, broken offsets and a requirement missing its number each fail.
  5. The ROWS are untouched -- byte-identical to the pre-#186 flat array. The wrapper is
     the change; the audit's actual input is not.
  6. The blind profile is still blind WITH the header. A header is new bytes in a file whose
     blindness is checked on bytes.
  7. Under the cap, the header is still there and still requires the count. A header whose
     shape changes with the file size is one a reader learns to skim.
  8. The prompt and the plan carry the requirement, including for the BLIND passes, which
     have no committed prompt at all -- #173's shape, which is the whole reason the
     requirement moved into the data.
  9. The cap is written down as ONE MEASUREMENT and the page margin as a STATED GUESS,
     everywhere they are written down. This is the assertion most likely to be lost by
     someone tidying the docstring, and it is the same discipline #156's floor carries.

WHAT THIS DOES NOT CHECK -- state it, don't imply coverage:

  * That an agent actually pages through. Nothing here can. What the fix buys is that the
    requirement ARRIVES WITH THE DATA rather than with a per-slice prompt, and that a
    return which reconciles is evidence.
  * That the returned count is checked. Nothing parses an audit's return; the reader does.
  * The exact cap. 45,035 chars is one observation, on English prose at 85 chars/line. The
    real limit is almost certainly counted in tokens, and JSON tokenizes worse per
    character, which is what READ_PAGE_MARGIN is for and why it is called a guess.
  * The shards already on disk. This changes future builds only; §10-16's passes were
    reconciled by hand and their findings are already resolved.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_audit_read_cap.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded -- #157 swept the last absolute paths out
of this toolchain; don't reintroduce one.
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
PROMPT = REPO / "backend/test-gen-model/src/prompts/audit-key-coherence.txt"
PLAN = REPO / "backend/test-gen-model/plans/10-per-pi-review-depth-plan.md"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def row(n, long=False):
    """An authored row. `long` pads the explanation so a modest row count clears the cap
    the way a real full-profile shard does (§10-16 ran ~1,300 chars a row)."""
    return {
        "cand_id": f"mkt-icdc-pool-cand-e{n:04d}",
        "cluster": "marketing", "level": "ICDC",
        "instructionalArea": "Marketing-Information Management",
        "performanceIndicator": "Explain the nature of marketing research",
        "question": "A retailer reviews its policy after a 40% markup on seasonal stock.",
        "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
        "answer": "B",
        "explanation": ("Because two. " * 60).strip() if long else "Because two.",
        "difficulty": "easy",
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


def build(tmp, n_rows, agents=1, profile="full", long=True, stem="audit"):
    p = tmp / f"chunk9-part1.json"
    p.write_text(json.dumps([row(k, long=long) for k in range(n_rows)], indent=2),
                 encoding="utf-8")
    out = tmp / f"gate-{stem}"
    text, code = run_cli("--part", str(p), "--out", str(out), "--stem", stem,
                         "--agents", str(agents), "--profile", profile)
    return text, code, out


print("Issue #186 -- a shard states its own extent and requires the count back\n")

# ---------------------------------------------------------------------------
# 1. THE §10-16 SHAPE. A full-profile shard of this size is several pages long.
# ---------------------------------------------------------------------------
print("a shard over the cap (the §10-16 shape):")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    text, code, out = build(tmp, 228)
    doc = json.loads((out / "audit-01.json").read_text(encoding="utf-8"))
    head = doc[bai.HEADER_KEY]

    check("the build succeeds", code == 0)
    check("the shard really is past the cap — NON-VACUITY for everything below",
          head["chars"] > bai.READ_CAP_CHARS,
          f"{head['chars']:,}ch against a ~{bai.READ_CAP_CHARS:,}ch cap")
    check("the warning fires", "OVER THE SINGLE-READ CAP" in text)
    check("...and names the CONSEQUENCE, not just the size",
          "INDISTINGUISHABLE" in text and "clean batch" in text,
          "the tool always knew the size; the caller had to infer what it meant")
    check("...and prints the offsets, so the reader does not compute them",
          f"offsets {', '.join(str(o) for o in head['read_offsets'])}" in text)
    check("...and credits the measurement", "#186" in text and "truncated" in text)

    # ---- 2. the header describes the file it is inside, to the byte ----
    print("\nthe header describes the file it is inside:")
    raw = (out / "audit-01.json").read_text(encoding="utf-8")
    check("n_rows equals the rows in the file",
          head["n_rows"] == len(doc[bai.ROWS_KEY]) == 228)
    check("chars equals the file's own length", head["chars"] == len(raw),
          "self-referential: writing the header changes the number the header reports")
    check("lines equals the file's own line count", head["lines"] == raw.count("\n"))
    check("the requirement states n_rows, which is the number to reconcile against",
          str(head["n_rows"]) in head["requirement"])
    check("...and says what a short count MEANS",
          "truncated" in head["requirement"] and "MUST equal" in head["requirement"])

    # ---- 3. the offsets really page the file ----
    print("\nthe offsets page the whole file:")
    lines = raw.splitlines(keepends=True)
    offs = head["read_offsets"]
    check("they start at line 1", offs[0] == 1)
    check("they are strictly increasing", offs == sorted(set(offs)))
    check("the last one is inside the file", offs[-1] <= head["lines"])
    bounds = offs + [len(lines) + 1]
    pages = [sum(len(x) for x in lines[bounds[i] - 1:bounds[i + 1] - 1])
             for i in range(len(offs))]
    check("every page fits under the measured cap",
          all(p <= bai.READ_CAP_CHARS for p in pages),
          f"largest page {max(pages):,}ch of ~{bai.READ_CAP_CHARS:,}")
    check("...and the pages cover the file exactly once", sum(pages) == len(raw))

    # ---- 5. the rows are untouched ----
    print("\nthe rows are untouched — the wrapper is the change:")
    flat = json.dumps(doc[bai.ROWS_KEY], indent=2, ensure_ascii=False)
    expect = json.dumps([bai.project({**row(k, long=True), "chunk": "chunk9",
                                      bai.ROW_REF: f"chunk9:mkt-icdc-pool-cand-e{k:04d}"},
                                     bai.FULL_FIELDS) for k in range(228)],
                        indent=2, ensure_ascii=False)
    check("the `rows` array is byte-identical to the pre-#186 flat file", flat == expect,
          "the §10-13 diffability claim survives — it just moved down one key")
    check("the index records lines / reads / offsets, so a PAST pass is auditable",
          all(k in json.loads((out / "audit-index.json").read_text())["shards"][0]
              for k in ("lines", "reads", "read_offsets")),
          "§10-16's three earlier passes left no trace of their size but a terminal line")

# ---------------------------------------------------------------------------
# 6. THE BLIND PROFILE. A header is new bytes in a file checked on its bytes.
# ---------------------------------------------------------------------------
print("\nthe blind profile is still blind with a header in it:")
with tempfile.TemporaryDirectory() as td:
    text, code, out = build(Path(td), 120, profile="blind", stem="blind")
    raw = (out / "blind-01.json").read_text(encoding="utf-8")
    check("it builds", code == 0)
    check("no forbidden token appears anywhere in the file, header included",
          not any(t in raw for t in bai.BLIND_FORBIDDEN),
          ", ".join(bai.BLIND_FORBIDDEN))
    check("the header is present on this profile too",
          bai.HEADER_KEY in json.loads(raw),
          "the blind pass is the one with NO committed prompt — it needs it most")

# ---------------------------------------------------------------------------
# 7. UNDER THE CAP. The header does not change shape with the file size.
# ---------------------------------------------------------------------------
print("\nunder the cap:")
with tempfile.TemporaryDirectory() as td:
    text, code, out = build(Path(td), 4, long=False, stem="small")
    head = json.loads((out / "small-01.json").read_text(encoding="utf-8"))[bai.HEADER_KEY]
    check("no warning", code == 0 and "OVER THE SINGLE-READ CAP" not in text,
          f"{head['chars']:,}ch")
    check("the header is still there, with one offset", head["read_offsets"] == [1])
    check("...and still requires the count back",
          "MUST equal" in head["requirement"] and str(head["n_rows"]) in head["requirement"],
          "a header whose shape tracks the size is one a reader learns to skim")

# ---------------------------------------------------------------------------
# 4. verify() FAILS on each way a header can be wrong. A guard that cannot fail
#    in either direction is #76's GATED_FIELDS again.
# ---------------------------------------------------------------------------
print("\nverify() on hand-broken headers:")


def broken(mutate):
    rows = [{**row(k), "chunk": "chunk9",
             bai.ROW_REF: f"chunk9:mkt-icdc-pool-cand-e{k:04d}"} for k in range(2)]
    shards = [[rows[0]], [rows[1]]]
    raw = [bai.build_shard("audit", i, 2, "blind", sh, bai.BLIND_FIELDS)
           for i, sh in enumerate(shards, start=1)]
    raw = mutate(raw)
    buf = io.StringIO()
    code = 0
    try:
        with redirect_stdout(buf):
            bai.verify(shards, rows, raw, "blind")
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    return buf.getvalue(), code


def rewrite(text, **fields):
    """Change header fields and re-serialize WITHOUT the fixed point — i.e. exactly the
    stale header a future refactor would ship."""
    doc = json.loads(text)
    doc[bai.HEADER_KEY].update(fields)
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


clean, clean_code = broken(lambda raw: raw)
check("a correct pair passes", clean_code == 0 and not clean,
      "NON-VACUITY for the five failures below")

txt, code = broken(lambda raw: [json.dumps(json.loads(raw[0])[bai.ROWS_KEY], indent=2) + "\n",
                                raw[1]])
check("a BARE ARRAY fails — that is the pre-#186 shard, shipping with no requirement",
      code == 1 and "page-through requirement travels in the header" in txt)

txt, code = broken(lambda raw: [rewrite(raw[0], n_rows=99), raw[1]])
check("a WRONG n_rows fails", code == 1 and "worse than none" in txt,
      "an auditor reconciles against this number and passes, having read another shard")

txt, code = broken(lambda raw: [rewrite(raw[0], lines=9), raw[1]])
check("a STALE line count fails", code == 1 and "the offsets are computed from these" in txt)

txt, code = broken(lambda raw: [rewrite(raw[0], read_offsets=[7]), raw[1]])
check("offsets that do not start at line 1 fail",
      code == 1 and "do not page this file" in txt)

txt, code = broken(lambda raw: [rewrite(raw[0], requirement="Read the file."), raw[1]])
check("a requirement with no number in it fails",
      code == 1 and "cannot reconcile against a number it is not given" in txt)

# ---------------------------------------------------------------------------
# 8. THE PROMPT AND THE PLAN. The data carries the requirement; the prompt is
#    still the other half, and the BLIND passes have no committed prompt at all.
# ---------------------------------------------------------------------------
print("\nthe prompt and the plan:")
prompt = " ".join(PROMPT.read_text(encoding="utf-8").split())
check("audit-key-coherence.txt describes the {audit, rows} shape",
      "`audit`, a header describing the file" in prompt and "`rows`, the rows to audit" in prompt)
check("...tells the auditor to read the header FIRST and page by its offsets",
      "READ THE `audit` HEADER FIRST" in prompt and "one Read per offset" in prompt)
check("...says the cap is silent — which is the whole hazard",
      "STOPS WITHOUT TELLING YOU" in prompt)
check("...requires the examined count to equal n_rows",
      "must equal `n_rows`" in prompt)
check("...and says WHY, so it is not the first instruction dropped",
      "INDISTINGUISHABLE" in prompt)
check("the RETURN section names the reconciliation format",
      "rows examined: N of n_rows M" in prompt)

plan = " ".join(PLAN.read_text(encoding="utf-8").split())
check("plan §4 step 6a carries #186", "#186" in plan)
check("...with the measurement that grounds it",
      "truncated by the system at line 615" in plan and "45,035" in plan)
check("...and carries the requirement for the UNCOMMITTED blind prompts",
      "The BLIND passes still have no committed prompt" in plan)
check("...and says the reader must check the count, since nothing parses a return",
      "nothing parses an audit's return" in plan)
check("...and names the tension with the #156 sizing rule directly above it",
      "pushes it further past the cap" in plan,
      "bigger shards are cheaper per row AND further past the cap — one page, both sides")

# ---------------------------------------------------------------------------
# 9. ONE MEASUREMENT, AND IT IS WRITTEN DOWN AS ONE.
# ---------------------------------------------------------------------------
print("\none measurement, stated as one:")
src = " ".join((GEN / "build_audit_input.py").read_text(encoding="utf-8").split())
check("the cap constant is where §10-16 actually truncated",
      bai.READ_CAP_CHARS == 45_000 and "45,035" in src,
      "793 lines / 67,395 chars, cut at line 615")
check("...and is called a CEILING ESTIMATE, not a bracketed limit",
      "CEILING ESTIMATE" in src)
check("...noting the real limit is probably tokens, not characters",
      "counted in tokens" in src or "counted in TOKENS" in src)
check("the page margin is called a STATED GUESS, not a measurement",
      "STATED GUESS and not a measurement" in src)
check("...and carries the one success it is conservative against",
      "~799 lines" in src, "§10-16's blind auditor paged a 3,194-line shard and reconciled")
check("the docstring says the return-count checker was NOT built, and why",
      "NOT DONE: a checker for the returned count" in src and "#154" in src)
check("...and that the tool cannot make an agent page through",
      "make an agent page through. Nothing here can" in src)

# ---------------------------------------------------------------------------
failed = [n for n, ok, _ in results if not ok]
print(f"\n  {len(results) - len(failed)} passed / {len(failed)} failed")
if failed:
    for n in failed:
        print(f"    FAILED: {n}")
sys.exit(1 if failed else 0)
