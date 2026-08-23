"""§10-14 fixture: the `instructionalArea` paragraph must agree with the GROUP HEADERS.

THE DEFECT. `build_prompt.py` renders two statements about the same fact, ~670 lines
apart, and only one of them was computed:

    line ~42   ...rows whose PI merely *sounded* like a neighbouring area.
               Groups never span areas here.)                        <- STATIC TEXT
    line ~719  INSTRUCTIONAL AREAS VARY IN THIS GROUP — copy each row's own AREA= value
                                                                     <- COMPUTED PER GROUP

Both shipped in §10-14 chunk 10's prompt. The paragraph is the one carrying the REASON
(a prior run inferred one area per group FILE and stamped it across rows whose PI merely
sounded like a neighbouring area -- plan 10-2 §2d), so an author who believes it over the
header reproduces exactly that failure. `--pack-groups` makes the contradiction routine,
but it PREDATES the flag: `group_rows()` returns a single group whenever the whole chunk
fits under `size`, and that group spans every area in the chunk. Case B below is that
latent path, and it is the regression anchor -- it fails against the old static text
without `--pack-groups` being involved at all.

This is #76/#88/#89/#92 again in a different field: a hand-written assertion sitting next
to a computed one, never checked against it. The §10-11 rule -- when a gate's behaviour is
asserted in a comment, assert it in a fixture too -- applies to a PROMPT's assertions for
the same reason, because the prompt is the author's only instruction and nothing
downstream re-reads it.

WHAT THIS FIXTURE ASSERTS. Not the wording -- the AGREEMENT. The prompt must never
contain a group header saying areas vary and a paragraph saying groups never span areas.
Both directions are checked, so a "fix" that flips the paragraph unconditionally (and
would then be false on every ordinary per-area chunk) fails here too.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_mixed_group_area_para.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded -- an absolute path into a session
scratchpad, or into `/Users/.../GNS DECA APP` (the pre-rename directory, now DECK-APP),
dies with the session or the rename and takes the file with it. #157 swept the last
three out of this toolchain; don't reintroduce one.
"""
import io
import json
import re
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import build_prompt as bp  # noqa: E402

REPO = GEN.parents[3]
PLAN10 = GEN.parents[1] / "output" / "plan-10"

VARY = "INSTRUCTIONAL AREAS VARY IN THIS GROUP"
NEVER = "Groups never span areas here."
SPAN = "SOME GROUPS HERE SPAN SEVERAL AREAS"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# A real committed payload is the template. Synthesising rows by hand would
# encode a guess at the payload schema, and the schema is exactly the thing
# build_area.py is free to change (--free-rank already changed it once).
# ---------------------------------------------------------------------------
TEMPLATES = sorted(PLAN10.glob("*/payload/chunk*.json"))
if not TEMPLATES:
    print("  FAIL  no committed payload to template from under %s" % PLAN10)
    sys.exit(1)
TEMPLATE = json.loads(TEMPLATES[0].read_text())


def payload(spec):
    """spec: [(area, n_rows), ...] -- real rows relabelled onto the given areas."""
    out, i = [], 0
    for area, n in spec:
        for _ in range(n):
            r = dict(TEMPLATE[i % len(TEMPLATE)])
            r["instructionalArea"] = area
            r["cand_id"] = "x%04d" % i
            out.append(r)
            i += 1
    return out


def render(spec, pack=False, size=None):
    rows = payload(spec)
    with tempfile.TemporaryDirectory() as td:
        pj, out = Path(td) / "p.json", Path(td) / "p.txt"
        pj.write_text(json.dumps(rows))
        argv = ["build_prompt.py", str(pj), "--out", str(out),
                "--parts-dir", td, "--stem", "fx"]
        if pack:
            argv.append("--pack-groups")
        if size:
            argv += ["--group-size", str(size)]
        saved = sys.argv
        sys.argv = argv
        try:
            with redirect_stdout(io.StringIO()):
                bp.main()
        finally:
            sys.argv = saved
        return out.read_text()


def headers(text):
    """(group number, whether its header says areas vary) for every GROUP block."""
    return [(int(m.group(1)), VARY in m.group(2))
            for m in re.finditer(r"^GROUP (\d+) — .*\n(.*)$", text, re.M)]


def agrees(text):
    """The invariant: the paragraph and the headers say the same thing."""
    any_mixed = any(v for _, v in headers(text))
    return (SPAN in text) == any_mixed and (NEVER in text) == (not any_mixed)


print("§10-14 -- the instructionalArea paragraph vs the group headers\n")

# ---------------------------------------------------------------------------
# A. THE ORDINARY CHUNK. Several areas, more rows than fit one Write, no
#    packing -> group_rows splits per area and no group is mixed. The original
#    sentence is TRUE here and must survive; a fix that flips it unconditionally
#    would make every normal prompt say something false.
# ---------------------------------------------------------------------------
print("A. unpacked, 4 areas, 90 rows (the chunk 9 shape):")
a = render([("Promotion", 25), ("Pricing", 24), ("Business Law", 24),
            ("Product/Service Management", 17)])
check("no group header says areas vary", not any(v for _, v in headers(a)),
      f"{headers(a)}")
check("the paragraph keeps `Groups never span areas here.`", NEVER in a)
check("...and does not claim groups span areas", SPAN not in a)
check("paragraph and headers AGREE", agrees(a))

# ---------------------------------------------------------------------------
# B. THE LATENT PATH -- REGRESSION ANCHOR. group_rows() returns ONE group when
#    the whole chunk fits under `size`, and that group spans every area. No
#    --pack-groups anywhere. This is the case that proves the defect is not the
#    flag's: against the old static paragraph this prompt asserted both things.
# ---------------------------------------------------------------------------
print("\nB. unpacked, 3 areas, 12 rows -- one group, no flag (REGRESSION ANCHOR):")
b = render([("Selling", 5), ("Marketing", 4), ("Channel Management", 3)])
check("the whole chunk is ONE group", len(headers(b)) == 1, f"{headers(b)}")
check("that group's header says areas vary", headers(b)[0][1])
check("the paragraph no longer says groups never span areas", NEVER not in b,
      "the old static text asserted this while the header above said the opposite")
check("the paragraph names the mixed case", SPAN in b)
check("paragraph and headers AGREE", agrees(b))

# ---------------------------------------------------------------------------
# C. THE PACKED CHUNK -- §10-14 chunk 10's shape. Six small areas bin-packed.
# ---------------------------------------------------------------------------
print("\nC. --pack-groups, 6 areas, 40 rows (the chunk 10 shape):")
c = render([("Selling", 13), ("Market Planning", 8), ("Strategic Management", 5),
            ("Marketing", 5), ("Channel Management", 5),
            ("Human Resources Management", 4)], pack=True)
check("packs into 2 groups", len(headers(c)) == 2, f"{headers(c)}")
check("every group's header says areas vary", all(v for _, v in headers(c)))
check("the paragraph names the mixed case", SPAN in c and NEVER not in c)
check("it tells the author never to stamp one area across a file",
      # matched newline-tolerantly: the paragraph is hard-wrapped, so an exact
      # substring test breaks on a re-wrap that changes nothing.
      re.search(r"never\s+stamp\s+one\s+area\s+across\s+a\s+file", c) is not None)
check("paragraph and headers AGREE", agrees(c))

# ---------------------------------------------------------------------------
# D. THE FLAG IS NOT THE TRIGGER. --pack-groups on a single-area payload
#    produces no mixed group, so the original sentence must come back. The
#    paragraph keys off the REALISED groups, not off the flag.
# ---------------------------------------------------------------------------
print("\nD. --pack-groups on ONE area, 60 rows:")
d = render([("Pricing", 60)], pack=True)
check("no group header says areas vary", not any(v for _, v in headers(d)),
      f"{headers(d)}")
check("the paragraph keeps `Groups never span areas here.`", NEVER in d and SPAN not in d)
check("paragraph and headers AGREE", agrees(d))

# ---------------------------------------------------------------------------
# E. AREA= IS RENDERED ON THE ROWS OF A MIXED GROUP. The paragraph now tells the
#    author to copy each row's own AREA= value; if compact() were not passed
#    show_area, that instruction would point at a field that is not on the page.
# ---------------------------------------------------------------------------
print("\nE. the rows of a mixed group carry AREA=:")
for tag, text, want in (("B", b, True), ("C", c, True), ("A", a, False), ("D", d, False)):
    n_area = text.count("AREA=")
    check(f"{tag}: AREA= on rows is {'present' if want else 'absent'}",
          (n_area > 0) == want, f"{n_area} occurrence(s)")

# ---------------------------------------------------------------------------
# F. THE INVARIANT OVER EVERY COMMITTED PAYLOAD, both flag settings. Cheap, and
#    it is the check that survives a rewording of either string -- as long as
#    the two constants above are the ones the code emits.
# ---------------------------------------------------------------------------
print("\nF. every committed plan-10 payload, packed and unpacked:")
bad = []
n = 0
for p in sorted(PLAN10.glob("*/payload/chunk*.json")):
    rows = json.loads(p.read_text())
    if any(r.get("difficulty") == "hard" for r in rows):
        continue  # a hard payload must carry authoring-hard-bare.txt; not this test's axis
    spec = [(a, sum(1 for r in rows if r["instructionalArea"] == a))
            for a in dict.fromkeys(r["instructionalArea"] for r in rows)]
    for pack in (False, True):
        n += 1
        t = render(spec, pack=pack)
        if not agrees(t):
            bad.append(f"{p.parent.parent.name}/{p.name} pack={pack}: "
                       f"headers={headers(t)} SPAN={SPAN in t} NEVER={NEVER in t}")
check(f"paragraph and headers agree on all {n} renderings", not bad,
      "\n          ".join(bad[:5]) if bad else f"{n // 2} payload(s) x 2 settings")

# ---------------------------------------------------------------------------
# NON-VACUITY. `agrees()` must be able to FAIL, or every check above is free.
# Replay the old static paragraph against case C's headers.
# ---------------------------------------------------------------------------
print("\nnon-vacuity:")
old = c.replace(SPAN, "zzz").replace("never stamp one area across a file",
                                     "x") + "\n" + NEVER
check("`agrees()` rejects the OLD paragraph on a mixed-group prompt", not agrees(old),
      "the defect, reproduced")
check("`headers()` actually finds groups", len(headers(a)) == 4, f"{len(headers(a))} group(s)")

# ---------------------------------------------------------------------------
# What this fixture does NOT check -- state it, don't imply coverage.
#
#  * Whether an AUTHOR obeys either statement. The §10-14 chunk 10 run is the
#    first packed batch with the ledger filled; `check_authored` verifying
#    instructionalArea verbatim is what actually catches a mis-stamp.
#  * Whether --pack-groups is CHEAPER. That is agent_cost.py's ledger, not this.
#  * The rest of the prompt. Only the area paragraph and the group headers are
#    compared; assert_assignments_rendered() covers the per-row assignments.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
