"""Build the CROSSED, BLINDED two-arm payload for a Lens-B distractor audit.

Plan 07 §9's quality baseline. The judgment (is each distractor sound?) is made
by Sonnet subagents in an offline fan-out reading
`src/prompts/audit_distractor_soundness.txt`; this script is the deterministic
payload builder and part validator. No model is called here.

It exists because the fan-out it serves had no committed payload builder --
plan 07 §1.4's SIXTH occurrence, after the pools' tags, the sets' tags, the
length rule, and the letter rule. The slice gate's Lens B (summary
07-slice-gate §8) was built ad hoc and its 100 ids are unrecoverable, which is
exactly why its 3% cannot be re-used as an arm and this pass has to buy both
arms fresh.

WHY CROSSED, AND NOT ONE ARM PER RATER
--------------------------------------
The obvious design gives raters 1-2 the post-repair content and raters 3-4 the
pre-repair content. It does not work here. §11's between-agent variance has now
shown up THREE times (rank-1 no-ops 8/8, 11/11, 4/10; the §4 re-tag's per-batch
deltas -9.5, -33.3, -11.9, +26.8pp; the tagger's own committed-vs-fresh -14.4pp
on byte-identical content). With two raters an arm, ONE strict rater IS half an
arm, and "the repair degraded quality" and "rater 3 is strict" produce the same
number with nothing to separate them. That is §4's defect wearing new clothes:
an instrument difference read as an effect.

So every rater rates BOTH arms. The 167 items are quartered; each rater gets one
quarter's pre-content and a different quarter's post-content, interleaved:

    rater 1:  Q1 pre  + Q2 post          rater 3:  Q3 pre  + Q4 post
    rater 2:  Q1 post + Q2 pre           rater 4:  Q3 post + Q4 pre

Every item is judged exactly once in each arm; every rater contributes equally to
both arms, so rater strictness is common to the two arms and CANCELS in the
contrast. The unit of analysis is the WITHIN-rater delta, and there are four of
them -- which is the structure that let §4 discover its own headline was noise.
Same four agents as the parallel design. The confound is designed out rather
than estimated.

BLINDING
--------
A batch carries no arm field, no ordering signal, and no id appears twice in it
(a rater sees each item in one arm only). The un-blinding key lives in
audit-manifest.json, which the raters never read. `authoring.txt`-style prose
about what a repair did MUST NOT reach the prompt: a control must be unlabelled
AND UNDESCRIBED (§13). Naming the failure mode is what voided the slice gate's
instrument check -- both lens prompts quoted the seeded defect verbatim, so
"both lenses caught it" measured nothing.

THE PAYLOAD carries no `explanation`, inheriting tag_difficulty.PAYLOAD_FIELDS.
That is deliberate and structural, not an oversight: Lens B judges distractor
soundness ONLY. A rater that has decided an item's explanation is true is primed
on the next axis (§13 -- one rater judging three axes found 1 defect in 30; two
single-axis lenses over 100 found 3, and 2 were invisible to the other lens by
construction). The field allowlist is what makes "do not ask one agent three
questions" a mechanical constraint rather than a prose rule (§1.1).

VERDICTS -- one axis, two tails
-------------------------------
Per distractor, exactly one of:

    sound           clearly wrong; rejecting it requires knowing the material
    defensible      an informed student could argue for it (the key may still
                    be better) -- the "too good" tail
    true_irrelevant true, but not responsive to the stem -- the "too good" tail
    nonsensical     eliminable on sight, without knowing the material -- the
                    "too bad" tail (authoring.txt rule 3's throwaway)

`defensible` + `true_irrelevant` is the slice gate's Lens B category and is what
its 3% is comparable to. `nonsensical` is NEW and is not comparable to anything;
it is here because it costs nothing (the rater reads every distractor either way)
and because it measures the COMPETING hypothesis for why the bank is 61% easy.
§5 triggers lever B off a symptom (`easy` is high) and assumes a cause (stems
restate their keys) that nothing has tested; summary 07-slice-gate §9 names a
rival cause with a work list already attached (fin-icdc-1-0051's option C, "a
risk mainly to the client's phone battery life", which the item's own explanation
calls "a nonsensical distractor unrelated to the actual risk"). The pre arm is
the unrepaired bank, so its `nonsensical` rate is that rival measured for free.

Both tails are read on both arms by the same instrument, so the pre/post contrast
is valid for each of them regardless of how the absolute rates compare to 3%.

WHAT THIS CAN AND CANNOT SUPPORT -- stated here, now, rather than discovered
later (§13). At a ~3% base rate over n=167 an arm this is a CATASTROPHE
DETECTOR, not a rate comparator: it resolves pre 3% vs post 15% and it does NOT
resolve 3% vs 6%. Separating those needs n in the thousands, which is not
buyable. That is sufficient, because the fork it feeds is coarse -- does the
repair method materially degrade distractors before it is pointed at 2,088 more
items -- and a fork can survive a number that cannot (§13).

Usage:
    python build_audit_payload.py --pre DIR --post DIR --out DIR [--raters 4]
    python build_audit_payload.py --check --payload DIR/audit-manifest.json \
                                  --parts-dir parts/
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BASE_DIR.parents[1]

AUDIT_MANIFEST_NAME = "audit-manifest.json"
DEFAULT_RATERS = 4
DEFAULT_SEED = 707

OPTION_KEYS = ("A", "B", "C", "D")
VERDICTS = ("sound", "defensible", "true_irrelevant", "nonsensical")
# The "too good" tail -- an informed student could pick it. This is the slice
# gate's Lens B category and the only one comparable to its 3%.
TOO_GOOD = ("defensible", "true_irrelevant")
# The "too bad" tail -- eliminable without knowing the material. New here.
TOO_BAD = ("nonsensical",)

# Frozen across arms by plan 07 §3's invariant. A repair may only move `options`
# (never options[answer]) and `explanation`; `explanation` is not in the payload.
FROZEN_FIELDS = (
    "id", "level", "instructionalArea", "performanceIndicator",
    "question", "answer",
)

ARMS = ("pre", "post")


def _red(s: str) -> str:
    return f"\033[31m{s}\033[0m"


def _load_arm(outdir: Path) -> List[Dict]:
    """Read a tag_difficulty --build-payload directory back as one item list."""
    manifest_path = outdir / "payload-manifest.json"
    if not manifest_path.exists():
        sys.exit(f"  {outdir} has no payload-manifest.json -- is it an arm dir?")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items: List[Dict] = []
    for batch in manifest["batches"]:
        items.extend(json.loads((outdir / batch["batch"]).read_text(encoding="utf-8")))
    return items


def verify_arms(pre: List[Dict], post: List[Dict]) -> None:
    """The arms must differ in `options` and NOTHING else. Verified, not assumed.

    §4 checked this by hand and said so; a pass that reads a contrast off two
    files it never compared is measuring whatever else drifted between them.
    """
    if len(pre) != len(post):
        sys.exit(f"  arms differ in size: pre={len(pre)} post={len(post)}")
    if [q["id"] for q in pre] != [q["id"] for q in post]:
        sys.exit("  arms do not carry the same ids in the same order")

    problems: List[str] = []
    for a, b in zip(pre, post):
        for f in FROZEN_FIELDS:
            if a.get(f) != b.get(f):
                problems.append(f"{a['id']}: `{f}` differs across arms")
        if a.get("options") == b.get("options"):
            problems.append(f"{a['id']}: `options` identical -- not an edited item")
        ans = a.get("answer")
        if a.get("options", {}).get(ans) != b.get("options", {}).get(ans):
            problems.append(f"{a['id']}: options[answer] differs -- the key is frozen")
    if problems:
        print(f"\n  {_red('FAIL')} the two arms are not a clean contrast")
        for p in problems[:10]:
            print(f"    {p}")
        sys.exit(1)
    print(f"  arm contrast verified: {len(pre)} items, `options` differs, "
          f"{len(FROZEN_FIELDS)} frozen fields + options[answer] byte-identical")


def _quarters(ids: List[str], k: int, seed: int) -> List[List[str]]:
    """Split ids into k groups as evenly as possible, shuffled first.

    Shuffled so a group does not track file or file-order: the 167 arrive as
    75 finance-icdc-1 then 59 finance-icdc-2 then 33 finance-icdc-pool, and
    unshuffled quarters would hand one rater a single file and confound rater
    with file (the pool runs a different tell rate from the sets).
    """
    shuffled = list(ids)
    random.Random(seed).shuffle(shuffled)
    return [shuffled[i::k] for i in range(k)]


def _crossed_assignment(k_groups: int) -> List[List[Tuple[int, str]]]:
    """rater -> [(group_index, arm)]. Each rater gets both arms; each (group,
    arm) cell is served exactly once.

    Raters are paired: rater 2j takes (Q_2j pre, Q_2j+1 post) and rater 2j+1
    takes the complement. With k groups = k raters and k even, every item is
    judged once per arm and every rater is 50/50 across arms.
    """
    if k_groups % 2:
        sys.exit(f"  need an even rater count for the crossed design, got {k_groups}")
    out: List[List[Tuple[int, str]]] = []
    for j in range(0, k_groups, 2):
        out.append([(j, "pre"), (j + 1, "post")])
        out.append([(j, "post"), (j + 1, "pre")])
    return out


def build(pre_dir: Path, post_dir: Path, outdir: Path, raters: int, seed: int) -> Dict:
    pre, post = _load_arm(pre_dir), _load_arm(post_dir)
    verify_arms(pre, post)

    by_arm = {"pre": {q["id"]: q for q in pre}, "post": {q["id"]: q for q in post}}
    ids = [q["id"] for q in pre]
    groups = _quarters(ids, raters, seed)
    assignment = _crossed_assignment(raters)

    outdir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed + 1)
    batches, key = [], []
    for n, cells in enumerate(assignment, start=1):
        chunk = [(qid, arm) for gi, arm in cells for qid in groups[gi]]
        # Interleave so the two arms are not contiguous blocks. A rater who can
        # see the seam can see the design.
        rng.shuffle(chunk)
        items = [by_arm[arm][qid] for qid, arm in chunk]

        raw = json.dumps(items, indent=2, ensure_ascii=False) + "\n"
        problems = blind_check(raw, items, chunk)
        if problems:
            print(f"\n  {_red('FAIL')} batch{n:02d}.json is not blinded")
            for p in problems[:10]:
                print(f"    {p}")
            sys.exit(1)

        name = f"batch{n:02d}.json"
        (outdir / name).write_text(raw, encoding="utf-8")
        batches.append({
            "batch": name,
            "n": len(items),
            "n_pre": sum(1 for _, a in chunk if a == "pre"),
            "n_post": sum(1 for _, a in chunk if a == "post"),
        })
        key.append({"batch": name, "items": [{"id": q, "arm": a} for q, a in chunk]})

    manifest = {
        "built_from": {
            "pre_dir": str(pre_dir), "post_dir": str(post_dir),
            "design": "crossed: every rater rates both arms; unit of analysis is "
                      "the within-rater delta",
            "raters": raters, "seed": seed,
            "verdicts": list(VERDICTS),
            "too_good": list(TOO_GOOD), "too_bad": list(TOO_BAD),
        },
        "total_items": len(ids),
        "total_judgments": len(ids) * len(ARMS),
        "batches": batches,
        # The un-blinding key. The raters never read this file.
        "key": key,
    }
    (outdir / AUDIT_MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"\n  {len(ids)} items x {len(ARMS)} arms = {len(ids) * 2} judgments, "
          f"{raters} raters")
    for b in batches:
        print(f"    {b['batch']}  n={b['n']:>3}  ({b['n_pre']} pre / {b['n_post']} post)")
    print(f"  blinding check PASSED on all {len(batches)} payload(s)")
    print(f"  wrote {outdir}/  (+ {AUDIT_MANIFEST_NAME} -- the un-blinding key, "
          f"NOT for the raters)\n")
    return manifest


def blind_check(raw: str, items: List[Dict], chunk: List[Tuple[str, str]]) -> List[str]:
    """Refuse to write a batch a rater could de-blind. Checked on the bytes sent.

    tag_difficulty.strip_check is the model: run it on the serialized payload,
    not on the builder's intent.
    """
    problems: List[str] = []
    for i, item in enumerate(items):
        for k in item:
            if str(k).strip().lower() in ("arm", "pre", "post", "repaired", "version"):
                problems.append(f"angle 1: `{k}` key at [{i}]({item.get('id')})")
    for token in ('"arm"', '"repaired"', '"pre_repair"', '"post_repair"'):
        if token in raw:
            problems.append(f"angle 2: {token} in the raw payload text")
    seen = [q for q, _ in chunk]
    if len(seen) != len(set(seen)):
        dupes = {q for q in seen if seen.count(q) > 1}
        problems.append(f"angle 3: {len(dupes)} id(s) appear twice in one batch "
                        f"-- the rater sees both arms of {sorted(dupes)[:3]}")
    if len({a for _, a in chunk}) < 2:
        problems.append("angle 4: batch is single-arm -- the crossed design is not built")
    return problems


def check_parts(manifest: Dict, part_paths: List[Path],
                exclude: Tuple[str, ...] = ()) -> List[str]:
    """Validate returned parts against the payload BEFORE any rate is computed.

    §13: a subagent's self-verification is a hypothesis, never a measurement --
    run the gate yourself over every part, always, even when the report says 0/0.
    Twice now an agent has reported programmatic verification of the exact
    property it had violated.
    """
    errors: List[str] = []
    expected: Dict[str, str] = {}
    for b in manifest["key"]:
        for it in b["items"]:
            if it["id"] in exclude:
                continue
            expected[f"{it['id']}|{it['arm']}"] = b["batch"]

    seen: Dict[str, Path] = {}
    for p in part_paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"{p.name}: unreadable -- {e}")
            continue
        rows = data.get("items") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            errors.append(f"{p.name}: not a JSON array (or {{items: [...]}})")
            continue

        batch = _batch_of(manifest, p)
        if batch is None:
            errors.append(f"{p.name}: cannot map to a batch -- name it batchNN*.json")
            continue
        arm_of = {it["id"]: it["arm"]
                  for b in manifest["key"] if b["batch"] == batch
                  for it in b["items"]}

        for row in rows:
            qid = row.get("id")
            if qid is None:
                errors.append(f"{p.name}: a row has no id")
                continue
            if qid in exclude:
                continue
            if qid not in arm_of:
                errors.append(f"{p.name}: foreign id {qid} (not in {batch})")
                continue
            k = f"{qid}|{arm_of[qid]}"
            if k in seen:
                errors.append(f"{qid} judged twice ({seen[k].name}, {p.name})")
                continue
            seen[k] = p
            errors.extend(_check_row(p.name, qid, row))

    missing = sorted(set(expected) - set(seen))
    if missing:
        errors.append(f"{len(missing)} judgment(s) missing, e.g. {missing[:5]}")
    return errors


def _batch_of(manifest: Dict, part: Path) -> str:
    for b in manifest["batches"]:
        if b["batch"].removesuffix(".json") in part.name:
            return b["batch"]
    return None


def _check_row(part: str, qid: str, row: Dict) -> List[str]:
    errors: List[str] = []
    ds = row.get("distractors")
    if not isinstance(ds, dict):
        errors.append(f"{part}: {qid} has no `distractors` object")
        return errors
    if len(ds) != 3:
        errors.append(f"{part}: {qid} judged {len(ds)} distractor(s), expected 3")
    for letter, verdict in ds.items():
        if letter not in OPTION_KEYS:
            errors.append(f"{part}: {qid} has a non-option letter {letter!r}")
        v = verdict.get("verdict") if isinstance(verdict, dict) else verdict
        if v not in VERDICTS:
            errors.append(f"{part}: {qid}.{letter} illegal verdict {v!r}")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pre", metavar="DIR", help="tag_difficulty payload dir, --at-ref arm")
    ap.add_argument("--post", metavar="DIR", help="tag_difficulty payload dir, working-tree arm")
    ap.add_argument("--out", metavar="DIR", help="where to write the crossed batches")
    ap.add_argument("--raters", type=int, default=DEFAULT_RATERS,
                    help=f"even; default {DEFAULT_RATERS}")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--check", action="store_true", help="validate parts and stop")
    ap.add_argument("--payload", metavar="PATH", help=f"{AUDIT_MANIFEST_NAME} to check against")
    ap.add_argument("--parts-dir", metavar="DIR", help="directory of returned part files")
    ap.add_argument("--exclude", nargs="*", default=[], metavar="ID",
                    help="drop these ids from BOTH arms. An exclusion is a "
                         "deliberate, recorded act -- never a silent fixup in "
                         "an analysis script. Say why in the summary.")
    args = ap.parse_args()

    if args.check:
        if not (args.payload and args.parts_dir):
            sys.exit("  --check needs --payload and --parts-dir")
        manifest = json.loads(Path(args.payload).read_text(encoding="utf-8"))
        parts = sorted(p for p in Path(args.parts_dir).glob("*.json")
                       if p.name != AUDIT_MANIFEST_NAME)
        if not parts:
            sys.exit(f"  no part files in {args.parts_dir}")
        errors = check_parts(manifest, parts, tuple(args.exclude))
        if errors:
            print(f"\n  {_red('FAIL')} {len(errors)} problem(s) across {len(parts)} part(s)")
            for e in errors[:20]:
                print(f"    {e}")
            sys.exit(1)
        n = manifest["total_judgments"] - 2 * len(args.exclude)
        print(f"\n  {len(parts)} part(s) validated against {AUDIT_MANIFEST_NAME}: "
              f"{n} judgments, ids + arms + verdicts all legal")
        if args.exclude:
            print(f"  EXCLUDED from both arms: {', '.join(args.exclude)}")
        print()
        return

    if not (args.pre and args.post and args.out):
        sys.exit("  need --pre, --post and --out (or --check)")
    build(Path(args.pre), Path(args.post), Path(args.out), args.raters, args.seed)


if __name__ == "__main__":
    main()
