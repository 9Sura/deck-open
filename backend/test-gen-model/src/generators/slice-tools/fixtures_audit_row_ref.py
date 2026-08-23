"""Issue #155 fixtures: an audit shard's row is named by ONE string, not two fields.

THE DEFECT. `build_audit_input.py` correctly treats chunk as part of a row's identity --
it stamps every row with its chunk, checks disjointness on the PAIR, and refuses a bare
`--ids` token that matches in more than one chunk. What it could not do is make the MODEL
carry the pair back. The agent read two fields and returned two fields, and one of them it
could get wrong.

§10-14's blind shard 02 held 40 chunk10 rows and 25 chunk9 rows. The agent returned EVERY
finding tagged `chunk9`, including `e0029` and `m0030`, which are chunk10:

    chunk9   mkt-district-pool-cand-e0029   Calculate maintained markup after markdowns
    chunk10  mkt-district-pool-cand-e0029   Calculate sales commission across tiered rates

Both ids exist in both chunks, on different PIs, so the mislabelled finding named a REAL,
SOUND question. Acting on it would have repaired two clean rows and left the two defective
ones shipping. `apply_repair --expect` cannot see it: it takes BARE ids against a list the
caller supplies, so a scope already wrong about which chunk it means passes the guard.

THE FIX is `row_ref` -- `chunk:cand_id`, one opaque string, leading every row, required
back verbatim by the audit prompts. `chunk` and `cand_id` STAY: they are context the
auditor reads and downstream tools take a bare id. What changed is that nothing the model
is asked to RETURN is assembled from two fields any more.

WHY A FIXTURE AND NOT A COMMENT. Fifth guard in this toolchain to be asserted in prose
(#76 GATED_FIELDS, #88 the rule-5 predicate, #89 the COPY THROUGH lookup, #92 probe-chunk
purity, now this). The §10-11 rule stands: when a gate's behaviour is asserted in a
comment, assert it in a fixture too.

NON-VACUITY: the §10-14 collision is replayed with the real ids and chunk names, and the
verify() checks are each shown FAILING on a hand-broken shard, so a regression that drops
`row_ref` from a profile or stops checking it fails here rather than passing silently.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_audit_row_ref.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded -- an absolute path into a session
scratchpad, or into `/Users/.../GNS DECA APP` (the pre-rename directory, now DECK-APP),
dies with the session or the rename and takes the file with it. #157 swept the last
three out of this toolchain; don't reintroduce one.
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


def row(cid, pi, *, answer="B", numeral=False):
    """A minimal authored row -- only the fields the two profiles project."""
    return {
        "cand_id": cid,
        "cluster": "marketing", "level": "District",
        "instructionalArea": "Marketing-Information Management",
        "performanceIndicator": pi,
        "question": f"A retailer reviews {'a 40% markup' if numeral else 'its policy'}.",
        "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
        "answer": answer,
        "explanation": "Because two.",
        "difficulty": "easy",
    }


def write_parts(tmp, spec):
    """spec: {chunk_name: [rows]} -> the part-file paths build_audit_input reads."""
    parts = []
    for chunk, rows in spec.items():
        p = tmp / f"{chunk}-part1.json"
        p.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        parts.append(p)
    return parts


def rows_of(path):
    """A shard's rows. #186 wrapped the file in a `{audit, rows}` object; the ROWS are
    still the pre-#186 array byte-for-byte, and everything below is about the rows."""
    return json.loads(Path(path).read_text(encoding="utf-8"))[bai.ROWS_KEY]


def run_cli(*argv):
    """main() with stdout captured. Returns (text, exit_code)."""
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


# The §10-14 collision, with the real ids and PIs.
C9 = [row("mkt-district-pool-cand-e0029", "Calculate maintained markup after markdowns"),
      row("mkt-district-pool-cand-m0030", "Calculate maintained markup after markdowns"),
      row("mkt-district-pool-cand-e0031", "Explain the nature of marketing research")]
C10 = [row("mkt-district-pool-cand-e0029", "Calculate sales commission across tiered rates",
           numeral=True),
       row("mkt-district-pool-cand-m0030", "Calculate sales commission across tiered rates",
           numeral=True),
       row("mkt-district-pool-cand-e0044", "Describe the use of a sales forecast")]

print("Issue #155 -- an audit row is named by ONE string\n")

# ---------------------------------------------------------------------------
# 1. THE §10-14 CASE, replayed. Colliding ids across two chunks, one shard each.
# ---------------------------------------------------------------------------
print("the colliding ids (§10-14 chunks 9/10):")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    parts = write_parts(tmp, {"chunk9": C9, "chunk10": C10})
    out = tmp / "gate"
    text, code = run_cli("--part", *[str(p) for p in parts], "--out", str(out),
                         "--stem", "audit", "--agents", "2", "--per-chunk")
    check("the build succeeds", code == 0, text.strip().splitlines()[-1] if text else "")

    sh1 = rows_of(out / "audit-01.json")
    sh2 = rows_of(out / "audit-02.json")
    idx = json.loads((out / "audit-index.json").read_text())

    check("every row carries row_ref",
          all("row_ref" in r for r in sh1 + sh2))
    check("row_ref is the FIRST key of every row",
          all(next(iter(r)) == "row_ref" for r in sh1 + sh2),
          "an agent reads the first key before it has decided what the row is")
    check("the colliding cand_id gets DISTINCT refs in the two chunks",
          {r["row_ref"] for r in sh1 + sh2 if r["cand_id"].endswith("e0029")}
          == {"chunk9:mkt-district-pool-cand-e0029",
              "chunk10:mkt-district-pool-cand-e0029"},
          "this is the whole finding: the bare id names two real, unrelated questions")
    check("the bare cand_id is NOT unique across the selection",
          len({r["cand_id"] for r in sh1 + sh2}) == 4
          and len({r["row_ref"] for r in sh1 + sh2}) == 6,
          "4 distinct cand_ids over 6 rows — NON-VACUITY: the refs are doing work")
    check("the index's `ids` are the row_refs the shards carry",
          [s["ids"] for s in idx["shards"]]
          == [[r["row_ref"] for r in sh1], [r["row_ref"] for r in sh2]],
          "a finding is resolved against this list, so it must not be a parallel build")
    check("the terminal output tells the reader to require the ref back",
          "row_ref" in text and "VERBATIM" in text and "#155" in text,
          next((ln.strip() for ln in text.splitlines() if "VERBATIM" in ln), "<no line>"))

# ---------------------------------------------------------------------------
# 2. BOTH PROFILES. The blind shard is where §10-14 actually broke, and it is
#    the profile with no committed prompt -- so the field must be on both.
# ---------------------------------------------------------------------------
print("\nboth profiles:")
check("row_ref leads the blind profile", bai.BLIND_FIELDS[0] == "row_ref")
check("row_ref leads the full profile", bai.FULL_FIELDS[0] == "row_ref")
check("chunk and cand_id are KEPT on both",
      all({"chunk", "cand_id"} <= set(f) for f in (bai.BLIND_FIELDS, bai.FULL_FIELDS)),
      "context the auditor reads; downstream tools take a bare id. Only the RETURN moved")
check("the blind profile still withholds the key",
      not ({"answer", "explanation"} & set(bai.BLIND_FIELDS)))

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    parts = write_parts(tmp, {"chunk9": C9, "chunk10": C10})
    out = tmp / "gate"
    _, code = run_cli("--part", *[str(p) for p in parts], "--out", str(out),
                      "--stem", "cohere", "--agents", "1", "--profile", "full")
    full = rows_of(out / "cohere-01.json")
    check("the full profile builds and carries refs",
          code == 0 and all(r["row_ref"] == f"{r['chunk']}:{r['cand_id']}" for r in full))
    check("--ids takes back the exact string a finding returns",
          run_cli("--part", *[str(p) for p in parts], "--out", str(out), "--stem", "re",
                  "--agents", "1", "--profile", "full",
                  "--ids", "chunk10:mkt-district-pool-cand-e0029")[1] == 0
          and [r["row_ref"] for r in rows_of(out / "re-01.json")]
          == ["chunk10:mkt-district-pool-cand-e0029"],
          "the returned ref is the re-audit / repair scope, with no parsing step")
    bare, bcode = run_cli("--part", *[str(p) for p in parts], "--out", str(out),
                          "--stem", "bare", "--agents", "1",
                          "--ids", "mkt-district-pool-cand-e0029")
    check("...and the bare id is still REFUSED as ambiguous",
          bcode != 0 and "more than one chunk" in bare,
          "the input-side guard that already existed — unchanged")

# ---------------------------------------------------------------------------
# 3. THE VERIFY CHECKS FIRE. A guard that cannot fail in either direction is
#    #76's GATED_FIELDS again, so break a shard three ways and watch each one.
# ---------------------------------------------------------------------------
print("\nverify() on hand-broken shards:")


def broken(mutate):
    """Run verify() over a two-row selection after mutating the written bytes."""
    rows = [{**C9[0], "chunk": "chunk9", "row_ref": "chunk9:" + C9[0]["cand_id"]},
            {**C10[0], "chunk": "chunk10", "row_ref": "chunk10:" + C10[0]["cand_id"]}]
    shards = [[rows[0]], [rows[1]]]
    raw = [bai.build_shard("audit", i, len(shards), "blind", sh, bai.BLIND_FIELDS)
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


clean, clean_code = broken(lambda raw: raw)
check("a correct pair of shards passes", clean_code == 0 and not clean,
      "NON-VACUITY for the three failures below")

txt, code = broken(lambda raw: [raw[0].replace('"row_ref"', '"was_row_ref"'), raw[1]])
check("a shard with row_ref DROPPED fails",
      code == 1 and "nothing unambiguous to return" in txt,
      next((ln.strip() for ln in txt.splitlines() if "row_ref" in ln), "<no line>"))

txt, code = broken(lambda raw: [raw[0].replace("chunk9:mkt", "chunk10:mkt"), raw[1]])
check("a row_ref that DISAGREES with its own chunk/cand_id fails",
      code == 1 and "does not match its own" in txt,
      "exactly the §10-14 mislabel, caught at build time instead of in a repair scope")

txt, code = broken(lambda raw: [raw[0], raw[1].replace("chunk10:mkt", "chunk9:mkt")])
check("a row_ref that names TWO rows fails",
      code == 1 and "names two rows names neither" in txt)

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    p = tmp / "chunk9-part1.json"
    p.write_text(json.dumps([row("mkt:district:e0001", "Explain marketing")]), encoding="utf-8")
    txt, code = run_cli("--part", str(p), "--out", str(tmp / "g"), "--stem", "s",
                        "--agents", "1")
    check("a cand_id containing ':' is refused at load, not silently made ambiguous",
          code != 0 and "row_ref separator" in txt,
          "row_ref splits on the FIRST colon, exactly as --ids does")

# ---------------------------------------------------------------------------
# 4. THE PROMPT AND THE PLAN. The tool cannot make a model return the ref; the
#    prompt is the other half, and the blind passes have no committed prompt at
#    all -- which is why the plan has to carry the instruction for them.
# ---------------------------------------------------------------------------
print("\nthe prompt and the plan:")
prompt = PROMPT.read_text(encoding="utf-8")
head, ret = prompt.split("RETURN\n---", 1) if "RETURN\n---" in prompt else (prompt, "")
check("audit-key-coherence.txt tells the reader row_ref is the identity",
      "`row_ref` IS THE ROW'S IDENTITY" in head)
check("...and forbids reconstructing it from the two fields",
      "never assemble it from the" in head and "Never reconstruct it" in head)
check("both RETURN classes ask for row_ref COPIED VERBATIM",
      ret.count("`row_ref` COPIED VERBATIM") == 2,
      "one per class — a class that names rows differently is the same defect")
check("neither RETURN class asks for chunk or cand_id any more",
      "chunk, cand_id" not in ret,
      "the pair is what the model got wrong; it is no longer what it is asked for")
check("the prompt says WHY, with the measured collision density",
      "143 of them in more than one chunk" in ret,
      "a requirement with no reason attached is the first thing an agent drops")

plan = PLAN.read_text(encoding="utf-8")
check("plan-10 step 6a carries the requirement for the UNCOMMITTED blind prompts",
      "#155" in plan and "no committed prompt" in plan
      and "assembled per slice" in plan)
check("...and says to resolve returned refs against the index",
      "-index.json`'s `ids`" in plan)
check("...and says why apply_repair --expect does not cover it",
      "takes BARE ids against a" in plan)

# ---------------------------------------------------------------------------
# What this fixture does NOT check -- state it, don't imply coverage.
#
#  * That a model actually copies the ref. It cannot; that is a model behaviour.
#    What the fix buys is DETECTABILITY -- a returned ref either appears in the
#    index's `ids` or it does not, where a returned (chunk, cand_id) pair could be
#    wrong and still name a real row. The resolve step is still a human/agent step.
#  * The blind audit PROMPTS, which do not exist in the repo. They are written per
#    slice, so the only enforceable home for the instruction is the plan doc, and a
#    slice that writes its own prompt can still omit it.
#  * Whether the §10-14 shards on disk get rebuilt. They do not — this changes
#    future builds only, and those shards' findings were already resolved by hand.
#  * Cost. `row_ref` adds ~40 chars per row (~1.5% of a shard); nothing here measures
#    what that costs against the repair it prevents.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
