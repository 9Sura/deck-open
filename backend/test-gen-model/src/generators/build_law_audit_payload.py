"""Build the PI-selected payload for plan 07 §3c's legal-doctrine audit, and validate
the parts that come back. No model is called here.

WHY A THIRD BUILDER
-------------------
Neither existing builder can select this population. `repair_options --build-payload`
filters on `margin` (or, since §3b, `top_gap`); `tag_difficulty --build-payload
--changed-vs` filters on a git diff. §3c's population is defined by CONTENT --
`performanceIndicator` -- which is the intrinsic axis §13 asks you to route by, and
neither script can see it.

WHY NOT CROSSED, WHICH IS A DEPARTURE
-------------------------------------
`build_audit_payload.py` crosses its raters across two arms, and that design is right
THERE and wrong here. §9 measured a DELTA BETWEEN TWO ARMS, where a strict rater lands
on one arm and reads as an effect; crossing makes strictness common to both arms so it
cancels in the contrast.

§3c has ONE ARM. It is a census, not a comparison. Rater strictness inflates or deflates
the count symmetrically -- it cannot manufacture a defect that is not there, and there is
no contrast for it to contaminate. So there is nothing to cross, and the honest response
to strictness here is to REPORT THE SPREAD (union and intersection), not to design it out.

THE CENSUS IS THE POINT
-----------------------
All 78 items carrying the three law PIs are audited -- every one, not a sample. §13's
"a stratified sample cannot measure a rate" cannot arise, because there is no sampling.
The three items §3 surfaced were found by three agents reading while doing something
else: three findings with NO DENOMINATOR. This pass supplies the denominator.

TWO LENSES, AND WHY ONE RATER WOULD FAIL
----------------------------------------
The known items' keys are NOT broken -- each is the best of its four options, and a
strict "is the key wrong?" audit returns SOUND on all three, correctly. What they fail is
a different axis: the stem's concrete colour is the precise trigger of a real doctrine the
key ignores. So:

    Lens K  -- is the designated key the best of the four options?
    Lens D  -- do the stem's specific facts activate a real rule that makes the key
               arguable or the explanation false?

Lens D is the one that matters. LENS K IS THE CONTROL ON LENS D. A single "is this item
OK?" rater is the design that already failed here: §9's round-1 rater judged three axes at
once and missed both defects the other lens could not structurally see.

THE CONTROL LIVES IN THIS FILE, NOT IN THE PROMPT
-------------------------------------------------
Three items in the census are known-defective. They are NOT named in either prompt and
NOT marked in the payload -- `--report` holds the key, the same way audit-manifest.json
held §9's un-blinding key and the raters never read it.

This is load-bearing. §9's instrument check was VOIDED because both lens prompts described
the seeded defect verbatim, so "both lenses caught it" proved nothing. The first
uncontaminated control ever run then came back NEGATIVE (0/2). §13: a control must be
unlabelled AND undescribed, and a contaminated control is worse than none.

READ THE CONTROL BEFORE THE RATE (`--report` prints it first, and refuses to reorder):
    Lens D flags 3/3 + Lens K calls them sound  -> instrument credible; the rate reads
    Lens D flags 0-1/3                          -> under-detecting; every number is a FLOOR
    Lens K calls any of the 3 broken            -> Lens K is over-calling
    Lens D flags >~40% of 78                    -> over-calling; not a work list

DO NOT TUNE EITHER PROMPT TO MAKE THE CONTROL PASS. That is fitting the instrument to the
answer.

Usage:
    python build_law_audit_payload.py --build --out DIR     # asserts 78 or refuses
    python build_law_audit_payload.py --check --parts-dir DIR --lens d
    python build_law_audit_payload.py --report --parts-dir DIR
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

from bank_paths import BANK_DIR  # noqa: E402  the ONE bank path (#203)

# The population, selected on the intrinsic axis. Changing this list changes the
# census, so it is a constant here rather than a flag: §3c's scope was measured, and a
# scope you can pass on the command line is a scope that drifts between runs.
LAW_PIS = (
    "Describe the nature of legally binding contracts",
    "Explain warranties and guarantees",
    "Explain worker rights",
)

# Measured against the working tree on 2026-07-16. The builder REFUSES on a mismatch
# rather than reporting one: §3's fan-out nearly ran against a 1,008-item scope when it
# meant 2,137, and it would have read as "the method failed" rather than "the scope was
# wrong". A guard that exits is the only reason that was ever caught.
EXPECT_ITEMS = 78
EXPECT_FILES = 42
EXPECT_DIFFICULTY = {"easy": 41, "medium": 21, "hard": 16}

# The auditor needs the whole item: Lens K compares the key against its options, Lens D
# reads the stem's facts against the key AND the explanation the key argues. Fields
# absent here are absent on purpose -- `difficulty` and `instructionalArea` are a
# verdict and a grouping signal respectively, and neither lens's question needs them.
PAYLOAD_FIELDS = ("id", "cluster", "level", "performanceIndicator",
                  "question", "options", "answer", "explanation")

# THE CONTROL. Never written to a payload, never named in a prompt. §3 found these
# three by accident; they are buried in the census undescribed, and --report scores the
# instrument against them BEFORE it scores the bank.
CONTROL_IDS = ("hos-district-pool-0060", "mkt-district-pool-0091", "fin-association-1-0069")

LENS_VERDICTS = {
    "k": {"sound", "broken"},
    "d": {"clean", "flagged"},
}


def _bank_files() -> List[Path]:
    return sorted(p for p in BANK_DIR.glob("*/*.json") if p.name != "manifest.json")


def select() -> List[Dict]:
    """Every item carrying a law PI. A census -- no sampling, no stratification.

    Each item carries a `_file` the payload never sees: route by something intrinsic
    (§13), and the file an item came from is the route Phase B writes back along.
    """
    out = []
    for path in _bank_files():
        for q in json.loads(path.read_text(encoding="utf-8")):
            if (q.get("performanceIndicator") or "").strip() in LAW_PIS:
                out.append({**q, "_file": str(path.relative_to(BANK_DIR))})
    return out


def assert_scope(items: List[Dict]) -> None:
    """Refuse before an agent is spent, not after. §1.5: gate before you spend."""
    problems = []
    if len(items) != EXPECT_ITEMS:
        problems.append(f"expected {EXPECT_ITEMS} items, selected {len(items)}")

    files = {q["_file"] for q in items}
    if len(files) != EXPECT_FILES:
        problems.append(f"expected {EXPECT_FILES} source files, spans {len(files)}")

    per_pi = collections.Counter((q.get("performanceIndicator") or "").strip() for q in items)
    diff = collections.Counter(q.get("difficulty") for q in items)
    if {t: diff.get(t, 0) for t in EXPECT_DIFFICULTY} != EXPECT_DIFFICULTY:
        problems.append(f"expected difficulty {EXPECT_DIFFICULTY}, got {dict(diff)}")

    ids = [q["id"] for q in items]
    if len(ids) != len(set(ids)):
        problems.append("duplicate ids in the selection")

    # The control must BE in the census, or the census cannot check the instrument.
    missing = [c for c in CONTROL_IDS if c not in set(ids)]
    if missing:
        problems.append(f"control items absent from the census: {missing} — "
                        f"§3c's instrument check is free ONLY because they are in scope")

    print(f"  scope: {len(items)} items · {len(files)} files · "
          f"{100 * len(items) / 4500:.2f}% of the bank")
    for pi in LAW_PIS:
        print(f"    {per_pi.get(pi, 0):>3}  {pi}")
    print(f"    difficulty: {dict(diff)}")

    if problems:
        sys.exit("\n  REFUSING TO BUILD — the scope does not reproduce:\n" +
                 "".join(f"    - {p}\n" for p in problems) +
                 "\n  Do NOT fix this by adjusting LAW_PIS or EXPECT_*. A different number "
                 "means\n  the selector is wrong or the bank moved; find out which.\n")


def build(outdir: Path) -> None:
    items = select()
    assert_scope(items)

    payload = [{f: q[f] for f in PAYLOAD_FIELDS if f in q} for q in items]
    # Sorted by id: deterministic, and it carries no grouping or provenance signal a
    # rater could reconstruct a hypothesis from.
    payload.sort(key=lambda r: r["id"])

    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "law-census.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Every rater reads the SAME 78. Two raters per lens, each over the full census:
    # a single rater's absolute rate is unreadable (24.5pp between raters, five
    # occurrences), so the union is the work list and the intersection is the
    # confident core.
    print(f"\n  wrote {path}  ({len(payload)} items)")
    print("  4 raters: lens-k × 2, lens-d × 2 — each over ALL 78. No batching, no crossing.")
    print("  Prompts: src/prompts/audit_key_soundness.txt · src/prompts/audit_doctrine_trip.txt")


def _load_parts(parts_dir: Path, lens: str) -> Dict[str, List[Dict]]:
    """Part files are named <lens><rater>.json, e.g. d1.json, k2.json."""
    out = {}
    for p in sorted(parts_dir.glob(f"{lens}*.json")):
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def check(parts_dir: Path, lens: str) -> int:
    """Validate parts against the payload before any rate is computed."""
    items = select()
    want = {q["id"] for q in items}
    legal = LENS_VERDICTS[lens]
    parts = _load_parts(parts_dir, lens)
    if not parts:
        sys.exit(f"  no {lens}*.json parts in {parts_dir}")

    bad = 0
    for name, rows in parts.items():
        got = {r.get("id") for r in rows}
        problems = []
        if got - want:
            problems.append(f"{len(got - want)} foreign id(s): {sorted(got - want)[:3]}")
        if want - got:
            problems.append(f"{len(want - got)} missing id(s): {sorted(want - got)[:3]}")
        illegal = [r.get("id") for r in rows if r.get("verdict") not in legal]
        if illegal:
            problems.append(f"{len(illegal)} illegal verdict(s) (legal: {sorted(legal)}): "
                            f"{illegal[:3]}")
        # A flag with no reason is not a finding anyone can act on or check.
        unreasoned = [r.get("id") for r in rows
                      if r.get("verdict") in ("flagged", "broken") and not r.get("note")]
        if unreasoned:
            problems.append(f"{len(unreasoned)} flag(s) with no note: {unreasoned[:3]}")

        if problems:
            bad += 1
            print(f"  FAIL {name}: " + "; ".join(problems))
        else:
            n_flag = sum(1 for r in rows if r.get("verdict") in ("flagged", "broken"))
            print(f"  PASS {name}: {len(rows)} rows, {n_flag} flagged")
    return bad


def report(parts_dir: Path) -> None:
    """THE CONTROL FIRST, THEN THE RATE — and never a single number."""
    items = {q["id"]: q for q in select()}
    n = len(items)

    lens_flags = {}
    for lens, flag_verdict in (("d", "flagged"), ("k", "broken")):
        parts = _load_parts(parts_dir, lens)
        lens_flags[lens] = {name: {r["id"] for r in rows if r.get("verdict") == flag_verdict}
                            for name, rows in parts.items()}

    # ---- 1. THE CONTROL. Printed first, deliberately: §2's prediction was written
    # down before the number existed, and reading the rate first is how you end up
    # believing an instrument you never checked.
    print("\n" + "=" * 70)
    print("  [1] THE CONTROL — read this BEFORE the rate")
    print("=" * 70)
    d_union = set().union(*lens_flags["d"].values()) if lens_flags["d"] else set()
    k_union = set().union(*lens_flags["k"].values()) if lens_flags["k"] else set()
    d_hits = [c for c in CONTROL_IDS if c in d_union]
    k_calls = [c for c in CONTROL_IDS if c in k_union]
    for c in CONTROL_IDS:
        raters = [nm for nm, s in lens_flags["d"].items() if c in s]
        print(f"    {c:<26} lens-D: {'FLAGGED by ' + ','.join(raters) if raters else 'MISSED':<22}"
              f" lens-K: {'BROKEN' if c in k_union else 'sound'}")
    print(f"\n    Lens D re-found {len(d_hits)}/3 · Lens K called {len(k_calls)}/3 broken")

    verdict_lines = []
    if len(d_hits) == 3 and not k_calls:
        verdict_lines.append("✅ INSTRUMENT CREDIBLE — Lens D found all 3, Lens K held. "
                             "The rate below is readable as a rate.")
    if len(d_hits) <= 1:
        verdict_lines.append("❌ LENS D IS UNDER-DETECTING (≤1/3). Every number below is a "
                             "FLOOR, not an estimate. PUBLISH NO RATE — the work list and "
                             "the coarse fork are all this pass supports.")
    if k_calls:
        verdict_lines.append(f"⚠ LENS K IS OVER-CALLING — it called {k_calls} broken, but all "
                             f"three keys are the best of their four options. Its census is "
                             f"inflated; re-read §1's table before believing it.")
    if len(d_union) > 0.40 * n:
        verdict_lines.append(f"⚠ LENS D FLAGGED {100 * len(d_union) / n:.0f}% OF THE CENSUS "
                             f"(>40%) — over-calling. A flag rate this high is not a work list.")
    for line in verdict_lines or ["(no prediction matched cleanly — read §2's table by hand)"]:
        print(f"    {line}")

    # ---- 2. Union and intersection. NEVER a single rate: between-agent variance is
    # five occurrences and the distractor auditors spanned 24.5pp on an absolute rate.
    print("\n" + "=" * 70)
    print("  [2] THE WORK LIST — union and intersection, never one number")
    print("=" * 70)
    for lens, label in (("d", "Lens D (doctrine trip)"), ("k", "Lens K (key soundness)")):
        per = lens_flags[lens]
        if not per:
            continue
        union = set().union(*per.values())
        inter = set.intersection(*per.values()) if per else set()
        print(f"\n    {label}   n = {n}")
        for nm, s in sorted(per.items()):
            print(f"      {nm:<8} flagged {len(s):>3}  ({100 * len(s) / n:>4.1f}%)")
        spread = max(len(s) for s in per.values()) - min(len(s) for s in per.values())
        print(f"      {'UNION':<8} {len(union):>11}  ({100 * len(union) / n:>4.1f}%)  <- the work list")
        print(f"      {'INTERSECT':<8} {len(inter):>11}  ({100 * len(inter) / n:>4.1f}%)  <- the confident core")
        print(f"      between-rater spread: {spread} items "
              f"({100 * spread / n:.1f}pp) — report this, do not average it")

    print("\n    The coarse fork this CAN settle: is the law cluster ~4% defective "
          f"(3/78, what\n    was known) or ~30%? Lens D union = {100 * len(d_union) / n:.0f}%.")
    print("    It CANNOT support: a precise rate, a bank-wide claim (78 of 4,500, and this\n"
          "    cluster was selected BECAUSE defects were found in it — the worst case by\n"
          "    construction), or a clean bill for the other 4,422.")

    # ---- 3. The work list itself, for Phase B.
    print("\n" + "=" * 70)
    print("  [3] PHASE B WORK LIST — Lens D union, hard items marked")
    print("=" * 70)
    src = {q["id"]: q for q in select()}
    for qid in sorted(d_union):
        raters = ",".join(sorted(nm for nm, s in lens_flags["d"].items() if qid in s))
        both = "BOTH" if len(raters.split(",")) > 1 else "one "
        print(f"    {qid:<28} {both}  [{raters}]")
    print(f"\n    {len(d_union)} items. Fix by DE-TRIGGERING THE STEM — the key is frozen.")


def build_work_list(findings_path: Path, outdir: Path) -> None:
    """Phase B's payload: the confirmed work list, each item plus its diagnosis.

    The `finding` is what makes the fix a minimal edit rather than a rewrite: it names
    the rule, quotes the trigger, and states the effect, so the agent de-triggers THAT
    fact instead of re-authoring the item.
    """
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    src = {q["id"]: q for q in select()}

    unknown = [f["id"] for f in findings if f["id"] not in src]
    if unknown:
        sys.exit(f"  work list carries ids outside the census: {unknown}")

    payload = []
    for f in findings:
        q = src[f["id"]]
        row = {k: q[k] for k in PAYLOAD_FIELDS if k in q}
        row["difficulty"] = q["difficulty"]      # the fix must PRESERVE it, so it is shown
        row["finding"] = f["finding"]
        if f.get("prescribed_edit"):
            row["prescribed_edit"] = f["prescribed_edit"]
        payload.append(row)

    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "work-list.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {path}  ({len(payload)} items)")
    for r in payload:
        print(f"    {r['id']:<28} {r['difficulty']}")


# Words too common to be a referent. Deliberately short: this check is meant to
# over-report and be read, not to be trusted silently.
_STOP = set(
    "the a an and or of to in for by with on at is are was were be been that this these "
    "those it its as not from than then so if which who whom whose what when where how "
    "all any both each few more most other some such no nor only own same too very can "
    "will just should now they them their there here we you your he she his her him has "
    "have had do does did but into over under about against between during without".split()
)


def _content_words(s: str):
    return {w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in _STOP}


def dangling_referents(before: Dict, after_q: str) -> Dict[str, List[str]]:
    """Options that name a fact the OLD stem stated and the NEW stem dropped.

    THE DEFECT NO OTHER GATE CAN SEE. Lever B cannot edit options, so a stem edit that
    removes a fact strands every option that pointed at it -- and because `options` stay
    byte-identical, the invariant, audit_tells and the collision audit ALL PASS. §3c's
    first Phase B run moved a stem off a goods sale and left three frozen distractors
    referring to a deposit, an object and a price that no longer existed.

    It is LEXICAL and it over-reports by design, so it is a REFUSAL WITH AN OVERRIDE
    rather than a hard gate: a distractor stating a general proposition ("employees may
    waive the premium by agreeing to a flat seasonal rate") legitimately keeps a word the
    stem dropped, because it points at no fact in the stem. That call needs a reader.
    Hence --ack-dangling: the operator must look and say so. §1.2 -- the script is the
    control, but the judgment here is not mechanizable, so the script forces the reading
    instead of pretending to make the call.
    """
    lost = _content_words(before["question"]) - _content_words(after_q)
    out = {}
    for letter, text in (before.get("options") or {}).items():
        hit = sorted(_content_words(str(text)) & lost)
        if hit:
            out[letter] = hit
    return out


def apply_repairs(part_path: Path, ack_dangling: bool = False) -> None:
    """VALIDATE, then write. Never the other way round.

    tag_difficulty --replace already works this way -- an unlabeled question errors and
    the file is NOT written, so a partial run cannot corrupt a file. This matches it.
    The applier is destructive; the check is cheap.
    """
    rows = json.loads(part_path.read_text(encoding="utf-8"))
    src = {q["id"]: q for q in select()}

    problems = []
    seen = set()
    for r in rows:
        qid = r.get("id")
        if qid not in src:
            problems.append(f"{qid}: not in the census")
            continue
        if qid in seen:
            problems.append(f"{qid}: duplicated in the part")
        seen.add(qid)
        extra = set(r) - {"id", "question", "explanation"}
        if extra:
            problems.append(f"{qid}: carries fields it must not write: {sorted(extra)}")
        for f in ("question", "explanation"):
            if not (r.get(f) or "").strip():
                problems.append(f"{qid}: `{f}` missing or empty")
        # A no-op means the agent did not do the work, and it would sail through
        # verify_bank as "content intact". Refuse it rather than report it.
        if (r.get("question") == src[qid]["question"]
                and r.get("explanation") == src[qid]["explanation"]):
            problems.append(f"{qid}: NO-OP — neither `question` nor `explanation` changed")

    if problems:
        sys.exit("\n  REFUSING TO APPLY:\n" + "".join(f"    - {p}\n" for p in problems))

    # The dangling-referent check. Runs BEFORE the write, like everything else here.
    dangling = {}
    for r in rows:
        hits = dangling_referents(src[r["id"]], r["question"])
        if hits:
            dangling[r["id"]] = hits
    if dangling:
        print("\n  ⚠ DANGLING REFERENTS — a frozen option names a fact the new stem dropped:")
        for qid, hits in sorted(dangling.items()):
            print(f"    {qid}")
            for letter, wordlist in sorted(hits.items()):
                print(f"      option {letter}: {wordlist}")
                print(f"        {' '.join(str(src[qid]['options'][letter]).split())}")
        if not ack_dangling:
            sys.exit(
                "\n  REFUSING TO APPLY. No other gate can see this: `options` are\n"
                "  byte-identical, so verify_bank, audit_tells and the collision audit\n"
                "  all pass a stem that stranded its own distractors.\n\n"
                "  READ each option above against its new stem. If it points AT a fact the\n"
                "  stem no longer states, the EDIT is wrong -- find a de-trigger that keeps\n"
                "  the referent (satisfying a rule often beats escaping it), or escalate.\n"
                "  If it is a general proposition that merely shares a word, re-run with\n"
                "  --ack-dangling.\n"
            )
        print("\n  --ack-dangling: operator has read the above and accepts them.")

    by_file: Dict[str, List[Dict]] = collections.defaultdict(list)
    for r in rows:
        by_file[src[r["id"]]["_file"]].append(r)

    for rel, group in sorted(by_file.items()):
        path = BANK_DIR / rel
        items = json.loads(path.read_text(encoding="utf-8"))
        index = {q["id"]: q for q in items}
        for r in group:
            index[r["id"]]["question"] = r["question"]
            index[r["id"]]["explanation"] = r["explanation"]
        path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  {rel}: applied {len(group)}")
    print(f"\n  applied {len(rows)} stem repair(s) across {len(by_file)} file(s)")
    print("  NOW: verify_bank.py --base <pre-3c ref> --allow-fields question,explanation")


def main() -> None:
    ap = argparse.ArgumentParser(description="Plan 07 §3c law-doctrine census payload.")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--work-list", metavar="PATH", type=Path,
                    help="findings JSON -> Phase B payload")
    ap.add_argument("--apply", metavar="PATH", type=Path,
                    help="a repair part -> the bank (validates first)")
    ap.add_argument("--out", metavar="DIR", type=Path)
    ap.add_argument("--parts-dir", metavar="DIR", type=Path)
    ap.add_argument("--lens", choices=sorted(LENS_VERDICTS))
    ap.add_argument("--ack-dangling", action="store_true",
                    help="--apply: the operator has READ the dangling-referent report "
                         "and accepts each hit as a general proposition, not a stranded "
                         "reference")
    args = ap.parse_args()

    if args.build:
        if not args.out:
            sys.exit("  --build needs --out DIR")
        build(args.out)
    elif args.work_list:
        if not args.out:
            sys.exit("  --work-list needs --out DIR")
        build_work_list(args.work_list, args.out)
    elif args.apply:
        apply_repairs(args.apply, ack_dangling=args.ack_dangling)
    elif args.check:
        if not args.parts_dir or not args.lens:
            sys.exit("  --check needs --parts-dir DIR and --lens {k,d}")
        sys.exit(1 if check(args.parts_dir, args.lens) else 0)
    elif args.report:
        if not args.parts_dir:
            sys.exit("  --report needs --parts-dir DIR")
        report(args.parts_dir)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
