"""Build payloads for, validate, and apply the difficulty-tagging fan-out.

Companion to build_question_bank.py, for plan 03 §3.1. The *judgment* (easy /
medium / hard per the §2 rubric) is made by Sonnet subagents in an offline
fan-out reading `src/prompts/difficulty_tagging.txt`; each agent reads a batch of
questions and emits `{id, difficulty}` labels as a JSON part file. This script is
the deterministic payload builder, validator, and applier. No model is called
here.

Idempotent + re-runnable per file: applying the same labels twice is a no-op, and
a set can be re-tagged by pointing at fresh label files.

THE PAYLOAD BUILDER EXISTS BECAUSE IT DID NOT, TWICE (plan 07 §1.4). The pools'
tags (plan 04) and the sets' tags (plan 06 §2) were both built from ad-hoc
payloads nobody committed — the same defect difficulty_tagging.txt's own "WHY
THIS FILE EXISTS" section is about, one layer down. A distribution produced by a
payload nobody can rebuild is not reproducible, and an irreproducible measurement
cannot referee anything. `--build-payload` is that payload, in the repo.

It is an ALLOWLIST (difficulty_tagging.txt, "THE PAYLOAD"), never a denylist: a
denylist silently passes through any tier-bearing field added to the bank later.
Stripping is then verified against the bytes actually written, three ways, since
a key-only check misses a tier smuggled into a string. Angle 2 matches a bare
tier VALUE and angle 3 matches the `"difficulty":` KEY — never the English word,
because fin-icdc-2-0026 and mkt-icdc-2-0039 legitimately say "difficulty" in
their stems and a check that cries wolf on those is one people learn to ignore.

`--changed-vs REF` selects the items a content pass edited, by diffing `options`
against a git ref — plan 07 §4's "label only the edited items". The selection is
INTRINSIC (§13: route by something intrinsic, never by the batch an agent was
handed). `--at-ref REF` then emits those same ids' content *as it was at REF*,
which is how the pre-change arm of an A/B is built:

    A/B, and why the committed tags cannot serve as the "before". Comparing a
    fresh run against a committed label set measures TWO NOISY DRAWS (§13, and
    difficulty_tagging.txt's MEASURED PROPERTIES). Single-rater kappa is ~0.60
    with the noise concentrated at the easy/medium boundary — which is exactly
    where a length-tell repair is expected to move items, per rubric rule 3. The
    committed tags are also a historical draw from a different fan-out, and
    plan 07 §11 measured that the variance is BETWEEN AGENTS; with ~4 raters an
    arm, that offset does not average out and nothing can estimate it. So the
    "before" is built with --at-ref and rated fresh, by the same instrument in
    the same session, and is never applied to the bank.

THE RATER MUST NOT SEE THE EXISTING TAG. Showing it anchors the judgment to the
value being replaced, and the run looks successful while reproducing the tag it
was meant to discard (plan 04 §3 — the single most important methodological rule
in the tagging work).

Label part shape (either form is accepted):
    [ { "id": "mkt-district-1-0001", "difficulty": "medium" }, ... ]
    { "labels": [ { "id": ..., "difficulty": ... }, ... ] }

Usage:
    python tag_difficulty.py --build-payload OUTDIR --changed-vs 0eaae0c^
    python tag_difficulty.py --build-payload OUTDIR --changed-vs 0eaae0c^ \
                             --at-ref 0eaae0c^          # the pre-change arm
    python tag_difficulty.py --check --payload OUTDIR/payload-manifest.json \
                             --labels-dir parts/
    python tag_difficulty.py <set_file.json> --labels part1.json [part2.json ...]
    python tag_difficulty.py <set_file.json> --labels-dir path/to/parts/
    python tag_difficulty.py <pool_file.json> --labels-dir parts/ --replace

`--replace` is re-tag mode (plan 04): the prior tag is discarded rather than used
as a fallback, so a question with no fresh label is an error and the file is left
untouched. Default mode keeps the prior tag for anything unlabeled, which is the
right mode after a CONTENT edit where only the edited items need relabeling
(plan 07 §4). Apply one file at a time — every run read-modify-writes the shared
manifest.json, so concurrent invocations race. Unlike repair_options.py, THIS
PASS DOES RACE THE MANIFEST (plan 07 §3).
"""

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parents[2]
from bank_paths import BANK_DIR, MANIFEST_PATH  # noqa: E402  the ONE bank path (#203)
REPO_ROOT = BASE_DIR.parents[1]

TIERS = ("easy", "medium", "hard")

# difficulty_tagging.txt, "THE PAYLOAD -- WHAT THE RATER MAY SEE". `answer` is
# included deliberately: judging how hard a key is to FIND requires knowing which
# option it is. `difficulty` is absent by CONSTRUCTION, not by deletion.
PAYLOAD_FIELDS = (
    "id", "level", "instructionalArea", "performanceIndicator",
    "question", "options", "answer",
)
# The fields a content pass edits AND the rater can see, and therefore the ones
# --changed-vs diffs. The rule is that intersection, not a list: an edit can only
# have moved an item's difficulty if it moved something the rater reads.
#
# `explanation` is deliberately NOT diffed, for exactly that reason -- the rater
# never sees it (it is absent from PAYLOAD_FIELDS), so an explanation-only edit
# cannot have moved the item's difficulty.
#
# `question` IS diffed, for the same reason read the other way: the rater does see
# it. It was omitted while `options` was the only field any pass could edit. Plan 07
# §3c is the first STEM pass -- it de-triggers fact patterns and leaves `options`
# byte-identical -- so without `question` here, every item §3c edits would be
# INVISIBLE to this selector, despite a de-triggered stem being precisely the kind
# of edit that moves difficulty. Verified strictly additive when it landed: with no
# stem yet edited, the widened selector reproduced the old selection exactly (88/88
# vs 79edf07^). See slice-tools/fixtures_changed_selector.py.
CHANGED_FIELDS = ("question", "options")
DEFAULT_BATCH_SIZE = 50
PAYLOAD_MANIFEST_NAME = "payload-manifest.json"
# Bump the manifest to v2 the moment any difficulty data lands (per plan 03 §3.3).
MANIFEST_VERSION_V2 = 2
# Sets came first; pools were added later (plan 04 §1.1). A file name resolves
# against either section.
MANIFEST_SECTIONS = ("sets", "pools")


# ----------------------------
# Payload builder (plan 07 §4)
# ----------------------------
def _bank_files() -> List[Path]:
    return sorted(p for p in BANK_DIR.glob("*/*.json") if p.name != "manifest.json")


def _git_show(rel_path: str, ref: str) -> Optional[List[Dict]]:
    try:
        out = subprocess.run(
            ["git", "show", f"{ref}:{rel_path}"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(out)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _changed_label() -> str:
    return " or ".join(f"`{f}`" for f in CHANGED_FIELDS)


def select_changed(ref: str, paths: List[Path]) -> List[Tuple[Path, Dict]]:
    """Questions whose `question` or `options` differ vs `ref`, in file then file-order.

    Deterministic and intrinsic: the id set is a property of the diff, not of how
    some earlier fan-out was batched (§13). An item that moved on BOTH fields is
    selected once, not twice.
    """
    selected: List[Tuple[Path, Dict]] = []
    for path in paths:
        before = _git_show(_rel(path), ref)
        if before is None:
            sys.exit(f"  cannot read {path.name} at {ref} — is the ref valid?")
        prior = {q.get("id"): q for q in before}
        for q in json.loads(path.read_text(encoding="utf-8")):
            was = prior.get(q.get("id"))
            if was is not None and any(was.get(f) != q.get(f) for f in CHANGED_FIELDS):
                selected.append((path, q))
    return selected


def select_new(ref: str, paths: List[Path]) -> List[Tuple[Path, Dict]]:
    """Questions whose id is ABSENT at `ref` — brand-new items (plan 09 pool expansion).

    The additive-expansion analogue of select_changed. A pool item ADDED since REF
    did not exist there, so --changed-vs (which only matches ids present at REF with
    a changed field) cannot see it — its `prior.get(id)` is None and the item is
    skipped. This selects the complement: ids in the working tree that are not in the
    file at REF. Selection is intrinsic (§13): a property of the id-set diff, not of
    how a fan-out was batched. If a whole file is new (absent at REF), every item in
    it is new.
    """
    selected: List[Tuple[Path, Dict]] = []
    for path in paths:
        before = _git_show(_rel(path), ref)
        prior_ids = {q.get("id") for q in before} if before else set()
        for q in json.loads(path.read_text(encoding="utf-8")):
            if q.get("id") not in prior_ids:
                selected.append((path, q))
    return selected


def _at_ref(selected: List[Tuple[Path, Dict]], ref: str) -> List[Tuple[Path, Dict]]:
    """Swap each selected question for its content at `ref`, same ids, same order."""
    out: List[Tuple[Path, Dict]] = []
    cache: Dict[str, Dict[str, Dict]] = {}
    for path, q in selected:
        rel = _rel(path)
        if rel not in cache:
            old = _git_show(rel, ref)
            if old is None:
                sys.exit(f"  cannot read {path.name} at {ref}")
            cache[rel] = {o.get("id"): o for o in old}
        was = cache[rel].get(q.get("id"))
        if was is None:
            sys.exit(f"  {q.get('id')} does not exist at {ref}; cannot build the pre-change arm")
        out.append((path, was))
    return out


def _payload_item(q: Dict) -> Dict:
    """Allowlist. A field absent from PAYLOAD_FIELDS cannot reach the rater."""
    return {f: q[f] for f in PAYLOAD_FIELDS if f in q}


def _even_batches(n: int, batch_size: int) -> List[int]:
    """Sizes that fill k batches as evenly as possible, k = ceil(n / batch_size).

    Even rather than greedy so per-batch results are comparable: the fan-out's
    spread is read as BETWEEN-AGENT variance (§11), and a greedy tail batch of 17
    against three of 50 would show up as agent noise when it is really n.
    """
    if n <= 0:
        return []
    k = -(-n // batch_size)
    base, rem = divmod(n, k)
    return [base + 1] * rem + [base] * (k - rem)


def strip_check(raw: str, items: List[Dict]) -> List[str]:
    """The three angles difficulty_tagging.txt demands, against the bytes sent.

    Run on the serialized payload, not the extractor's intent. Angles 1 and 3 both
    look for the `difficulty` KEY (parsed, then raw) and angle 2 for a bare tier
    VALUE — never the English word, or fin-icdc-2-0026's stem trips it.
    """
    problems: List[str] = []

    def walk(node, path: str):
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k).strip().lower() == "difficulty":
                    problems.append(f"angle 1: `difficulty` key at {path}.{k}")
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str) and node.strip().lower() in TIERS:
            problems.append(f"angle 2: bare tier value {node.strip()!r} at {path}")

    for i, item in enumerate(items):
        walk(item, f"[{i}]({item.get('id')})")
    for m in re.finditer(r'"difficulty"\s*:', raw):
        problems.append(f"angle 3: `\"difficulty\":` in the raw text at offset {m.start()}")
    return problems


def build_payload(outdir: Path, ref: str, at_ref: Optional[str], batch_size: int,
                  *, new: bool = False) -> Dict:
    if new:
        selected = select_new(ref, _bank_files())
        if not selected:
            sys.exit(f"  no question is new vs {ref}; nothing to tag")
    else:
        selected = select_changed(ref, _bank_files())
        if not selected:
            sys.exit(f"  no question's {_changed_label()} differs vs {ref}; nothing to tag")
    per_file = collections.Counter(p.name for p, _ in selected)
    if at_ref:
        selected = _at_ref(selected, at_ref)

    items = [_payload_item(q) for _, q in selected]
    missing = [i.get("id") for i in items if len(i) != len(PAYLOAD_FIELDS)]
    if missing:
        sys.exit(f"  {len(missing)} item(s) lack a payload field: {missing[:5]}")

    outdir.mkdir(parents=True, exist_ok=True)
    sizes = _even_batches(len(items), batch_size)
    batches, cursor = [], 0
    for n, size in enumerate(sizes, start=1):
        chunk = items[cursor:cursor + size]
        pairs = selected[cursor:cursor + size]
        cursor += size
        name = f"batch{n:02d}.json"
        raw = json.dumps(chunk, indent=2, ensure_ascii=False) + "\n"
        problems = strip_check(raw, chunk)
        if problems:
            # Refuse to write rather than warn: a leaked tag reproduces itself and
            # the run looks successful (plan 04 §3).
            print(f"\n  \033[31mFAIL\033[0m {name}: payload is not tag-stripped")
            for p in problems[:10]:
                print(f"    {p}")
            sys.exit(1)
        (outdir / name).write_text(raw, encoding="utf-8")
        batches.append({
            "batch": name,
            "n": len(chunk),
            "items": [{"id": q.get("id"), "file": _rel(p)} for p, q in pairs],
        })

    manifest = {
        "built_from": {
            ("new_vs" if new else "changed_vs"): ref,
            "at_ref": at_ref,
            "changed_fields": None if new else list(CHANGED_FIELDS),
            "batch_size": batch_size,
            "payload_fields": list(PAYLOAD_FIELDS),
        },
        "total": len(items),
        "batches": batches,
    }
    (outdir / PAYLOAD_MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    arm = f"content AT {at_ref}" if at_ref else "content in the working tree"
    what = f"new vs {ref}" if new else f"with {_changed_label()} changed vs {ref}"
    print(f"\n  {len(items)} question(s) {what} — {arm}")
    for name, n in sorted(per_file.items()):
        print(f"    {n:>4}  {name}")
    print(f"  {len(sizes)} batch(es): {sizes}")
    print(f"  tag-strip check PASSED on all {len(sizes)} written payload(s) (3 angles)")
    print(f"  wrote {outdir}/  (+ {PAYLOAD_MANIFEST_NAME})\n")
    return manifest


# ----------------------------
# Part validator (plan 07 §13 — the applier is destructive)
# ----------------------------
def check_parts(manifest: Dict, label_paths: List[Path]) -> Tuple[List[str], Dict[str, str]]:
    """Validate label parts against the payload BEFORE the destructive apply.

    Count, id set, tier legality, no foreign ids — §13's list. Duplicates are
    fatal rather than last-wins: two raters disagreeing on one id is a routing
    bug, and silently keeping one of them buries it.
    """
    expected = [i["id"] for b in manifest["batches"] for i in b["items"]]
    expected_set = set(expected)
    errors: List[str] = []
    labels: Dict[str, str] = {}
    seen: Dict[str, str] = {}

    for p in label_paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"{p.name}: cannot read: {e}")
            continue
        if isinstance(data, dict) and "labels" in data:
            data = data["labels"]
        if not isinstance(data, list):
            errors.append(f"{p.name}: not a label list")
            continue
        for entry in data:
            if not isinstance(entry, dict):
                errors.append(f"{p.name}: non-object entry {entry!r}")
                continue
            qid = entry.get("id")
            diff = str(entry.get("difficulty", "")).strip().lower()
            if qid not in expected_set:
                errors.append(f"{p.name}: FOREIGN id {qid!r} — not in the payload")
                continue
            if diff not in TIERS:
                errors.append(f"{p.name}: {qid}: illegal tier {entry.get('difficulty')!r}")
                continue
            if qid in seen:
                errors.append(f"{p.name}: duplicate label for {qid} (also in {seen[qid]})")
                continue
            seen[qid] = p.name
            labels[qid] = diff

    unlabeled = [q for q in expected if q not in labels]
    if unlabeled:
        errors.append(
            f"{len(unlabeled)} of {len(expected)} payload id(s) carry no label: "
            + ", ".join(unlabeled[:5]) + (" ..." if len(unlabeled) > 5 else "")
        )
    return errors, labels


def _load_labels(paths: List[Path]) -> Dict[str, str]:
    """Merge label parts into one {id -> difficulty} map, validating tiers."""
    labels: Dict[str, str] = {}
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [error] cannot read {p.name}: {e}")
            continue
        if isinstance(data, dict) and "labels" in data:
            data = data["labels"]
        if not isinstance(data, list):
            print(f"  [error] {p.name} is not a label list; skipping")
            continue
        n = 0
        for entry in data:
            if not isinstance(entry, dict):
                continue
            qid = entry.get("id")
            diff = str(entry.get("difficulty", "")).strip().lower()
            if not qid or diff not in TIERS:
                print(f"  [warn] {p.name}: bad label {entry!r}; skipping")
                continue
            labels[qid] = diff
            n += 1
        print(f"  loaded {n:>3} label(s) from {p.name}")
    return labels


def _with_difficulty(q: Dict, diff: str) -> Dict:
    """Return a copy of q with `difficulty` set, placed just before `verified`."""
    out = {k: v for k, v in q.items() if k != "verified"}
    out["difficulty"] = diff
    if "verified" in q:
        out["verified"] = q["verified"]
    return out


def apply_labels(set_path: Path, labels: Dict[str, str], *, replace: bool = False) -> Dict:
    questions = json.loads(set_path.read_text(encoding="utf-8"))
    if not isinstance(questions, list):
        sys.exit(f"{set_path.name} is not a JSON array of questions")

    if replace:
        # Re-tag mode: the prior tag is the thing being discarded, so falling back
        # to it would silently defeat the run. Fail before writing anything.
        missing = [q.get("id") for q in questions if q.get("id") not in labels]
        if missing:
            print(f"\n  [error] --replace: {len(missing)} of {len(questions)} question(s) "
                  f"have no fresh label in {set_path.name}; refusing to write.")
            for qid in missing[:20]:
                print(f"    {qid}")
            if len(missing) > 20:
                print(f"    ... and {len(missing) - 20} more")
            sys.exit(1)

    tagged = []
    counts = {t: 0 for t in TIERS}
    untagged = 0
    for q in questions:
        qid = q.get("id")
        # Under --replace every id is guaranteed labeled by the check above.
        diff = labels[qid] if replace else (labels.get(qid) or q.get("difficulty"))
        if diff in TIERS:
            counts[diff] += 1
            tagged.append(_with_difficulty(q, diff))
        else:
            untagged += 1
            tagged.append(q)  # left as-is; frontend treats missing as medium

    set_path.write_text(
        json.dumps(tagged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {"counts": counts, "untagged": untagged, "total": len(questions)}


def update_manifest(set_file_name: str, counts: Dict[str, int]) -> bool:
    """Write difficultyCounts onto the matching set/pool entry; bump version -> 2."""
    if not MANIFEST_PATH.exists():
        print("  [warn] manifest.json not found; skipping manifest update")
        return False
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    # Mirror build_question_bank.py: never let an existing higher version regress.
    manifest["version"] = max(manifest.get("version", MANIFEST_VERSION_V2), MANIFEST_VERSION_V2)

    entry = next(
        (
            m
            for section in MANIFEST_SECTIONS
            for m in manifest.get(section, {}).values()
            if m.get("file") == set_file_name
        ),
        None,
    )
    if entry is None:
        print(f"  [warn] no manifest {'/'.join(MANIFEST_SECTIONS)} entry references {set_file_name}")
        return False
    entry["difficultyCounts"] = counts
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return True


def report_section_spread(set_file_name: str) -> None:
    """Print how many distinct difficultyCounts triples the file's section holds.

    The quota defect (plan 04 §0) looked like *every* pool carrying an identical
    triple, so a section that collapses to one triple is the tripwire for a
    re-tag that silently anchored to the tags it was meant to replace. Only
    meaningful once a whole section has been applied; mid-run it just reports.
    """
    if not MANIFEST_PATH.exists():
        return
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    section = next(
        (
            s
            for s in MANIFEST_SECTIONS
            if any(m.get("file") == set_file_name for m in manifest.get(s, {}).values())
        ),
        None,
    )
    if section is None:
        return
    triples = {
        tuple(m["difficultyCounts"].get(t, 0) for t in TIERS)
        for m in manifest[section].values()
        if m.get("difficultyCounts")
    }
    n_entries = len(manifest[section])
    print(f"  section '{section}': {len(triples)} distinct triple(s) across {n_entries} entries")
    if len(triples) == 1 and n_entries > 1:
        print(
            f"  [warn] every '{section}' entry has an identical difficulty split "
            f"{next(iter(triples))} — suspicious. A content-driven tag should vary "
            f"per file; check the labels were not anchored to the prior tag."
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Build, validate, and apply difficulty labels.")
    ap.add_argument("set_file", nargs="?", help="path to question-bank/<cluster>/<file>.json")
    ap.add_argument("--labels", nargs="*", default=[], help="label JSON part files")
    ap.add_argument("--labels-dir", help="directory of label JSON parts")
    ap.add_argument(
        "--replace",
        action="store_true",
        help="re-tag mode: discard prior tags; error if any question lacks a fresh label",
    )
    ap.add_argument("--build-payload", metavar="OUTDIR",
                    help="write tag-stripped rater batches to OUTDIR and stop")
    ap.add_argument("--changed-vs", metavar="REF",
                    help=f"--build-payload: select questions whose {_changed_label()} "
                         f"differs vs this git ref")
    ap.add_argument("--new-vs", metavar="REF",
                    help="--build-payload: select questions whose id is ABSENT at this git "
                         "ref (brand-new items — the additive pool-expansion selector, plan 09)")
    ap.add_argument("--at-ref", metavar="REF",
                    help="--build-payload: emit the selected ids' content AS OF this ref "
                         "(the pre-change arm of an A/B; never applied)")
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                    help=f"--build-payload: questions per rater (default {DEFAULT_BATCH_SIZE})")
    ap.add_argument("--payload", metavar="PATH",
                    help=f"--check: the {PAYLOAD_MANIFEST_NAME} the labels answer")
    ap.add_argument("--check", action="store_true",
                    help="validate label parts against --payload and stop; writes nothing")
    args = ap.parse_args()

    if args.build_payload:
        if bool(args.changed_vs) == bool(args.new_vs):
            sys.exit("  --build-payload requires exactly one of --changed-vs REF or --new-vs REF")
        if args.new_vs and args.at_ref:
            sys.exit("  --new-vs has no pre-change arm: new items do not exist at the ref, so "
                     "--at-ref is meaningless here")
        out = Path(args.build_payload)
        try:
            out.resolve().relative_to(BANK_DIR)
        except ValueError:
            pass
        else:
            sys.exit(f"  refusing to write the payload inside the bank: {out}")
        ref = args.new_vs or args.changed_vs
        build_payload(out, ref, args.at_ref, args.batch_size, new=bool(args.new_vs))
        return

    label_paths = [Path(p) for p in args.labels]
    if args.labels_dir:
        label_paths += sorted(
            p for p in Path(args.labels_dir).glob("*.json") if p.name != PAYLOAD_MANIFEST_NAME
        )

    if args.check:
        if not args.payload:
            sys.exit("  --check requires --payload: without it there is nothing to validate "
                     "the parts against, and the applier is destructive (§13).")
        if not label_paths:
            sys.exit("no label files given (--labels or --labels-dir)")
        manifest = json.loads(Path(args.payload).read_text(encoding="utf-8"))
        errors, labels = check_parts(manifest, label_paths)
        print(f"\nChecking {len(label_paths)} part(s) against {manifest['total']} payload item(s)")
        if errors:
            print(f"\n  \033[31mFAIL\033[0m {len(errors)} problem(s); nothing written")
            for e in errors[:25]:
                print(f"    {e}")
            if len(errors) > 25:
                print(f"    ... and {len(errors) - 25} more")
            print()
            sys.exit(1)
        counts = collections.Counter(labels.values())
        print(f"  \033[32mOK\033[0m {len(labels)}/{manifest['total']} labeled · no foreign ids · "
              f"no duplicates · all tiers legal")
        print(f"  {dict(counts)}")
        by_file = collections.Counter(
            i["file"] for b in manifest["batches"] for i in b["items"]
        )
        print("  apply serially, one file per invocation (this pass races the manifest):")
        for f in sorted(by_file):
            print(f"    python {Path(__file__).name} \"{f}\" --labels-dir {args.labels_dir or '<parts>'}")
        print()
        return

    if not args.set_file:
        sys.exit("nothing to do: pass a set file to apply, --build-payload OUTDIR, or --check")

    set_path = Path(args.set_file)
    if not set_path.exists():
        set_path = BANK_DIR / args.set_file  # allow a bank-relative name
    if not set_path.exists():
        sys.exit(f"set file not found: {args.set_file}")
    set_path = set_path.resolve()  # absolute, so relative_to(REPO_ROOT) is safe

    if not label_paths:
        sys.exit("no label files given (--labels or --labels-dir)")

    mode = " (--replace: prior tags discarded)" if args.replace else ""
    print(f"\nTagging {set_path.name} from {len(label_paths)} label part(s){mode}...")
    labels = _load_labels(label_paths)
    print(f"  {len(labels)} unique label(s) collected\n")

    report = apply_labels(set_path, labels, replace=args.replace)
    ok = update_manifest(set_path.name, report["counts"])

    c = report["counts"]
    total = sum(c.values())
    pct = {t: (100 * c[t] / total) if total else 0 for t in TIERS}
    print(f"  difficultyCounts: easy {c['easy']} · medium {c['medium']} · hard {c['hard']}")
    print(f"  distribution:     easy {pct['easy']:.0f}% · medium {pct['medium']:.0f}%"
          f" · hard {pct['hard']:.0f}%")
    if report["untagged"]:
        print(f"  [warn] {report['untagged']} question(s) left untagged (no label)")
    assert total + report["untagged"] == report["total"]
    print(f"  wrote {set_path.relative_to(REPO_ROOT)}")
    print(f"  manifest {'updated (v2)' if ok else 'NOT updated'}")
    if args.replace and ok:
        report_section_spread(set_path.name)


if __name__ == "__main__":
    main()
