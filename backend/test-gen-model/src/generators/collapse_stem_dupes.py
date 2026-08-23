"""Collapse duplicate question stems already committed to the bank (issue #34).

The assembler's dedup used to key on stem + options, so re-authoring an existing
stem with a fresh set of distractors walked straight through it. `stem_hash` in
build_question_bank.py closes that door going forward; this closes it backwards,
over what already shipped. No model is called; nothing is rewritten except the
duplicate rows and the manifest entries that count them.

WHAT COUNTS AS COLLAPSIBLE (`--scope slice`, the default)
---------------------------------------------------------
Only twins inside the SAME cluster x level. That is the scope of the actual
defect: `loadCandidates(cluster, level)` is what a generated test, a focus quiz
and a PI drill all draw from, so only same-slice twins can be served to one
student in one sitting -- which is what makes the contradiction visible (the same
question badged Easy once and Medium once) and what double-counts as two
independent observations of one PI in the mastery engine.

Cross-slice twins are reported and left alone. Two clusters legitimately author
the same generic PI (`Explain ethical dilemmas` exists in finance/ICDC and
pbm/Association, one question each), they can never co-occur, and deleting either
would leave that PI with ZERO questions in its cluster x level -- dropping it out
of `pi-inventory.json` and making "Practice this" unlaunchable for it. Removing a
PI's only coverage to fix a duplicate a student cannot see is a worse bug than the
one being fixed. `--scope bank` collapses them anyway; it exists to be explicit,
not to be used casually.

WHICH TWIN SURVIVES
-------------------
The earliest one in bank order (file, then position -- which is id order, since the
assembler numbers in file order). Two reasons, both mechanical rather than
aesthetic: it confines every deletion to the most recently authored wave, which is
the code path that introduced the defect and the one with the fewest logged
attempts pointing at it; and it is reproducible, so a reviewer can re-derive the
exact same survivor set from the same input.

Difficulty is reconciled by that same choice, not by a separate rule. The tag is a
judgment about a (stem, options) pair -- the referee graded each copy against ITS
OWN distractors -- so the tag that stays valid is the one attached to the options
that stay. Inventing a max()/min() across the pair would attach a grade to options
it was never given.

IDS ARE NEVER RENUMBERED. `Attempt` rows in a user's progress log reference bank
ids, and the /review Error Log re-hydrates by id; renumbering would silently
re-point every logged attempt at a different question. Deletion is the supported
operation (resolver.ts: unresolvable ids are simply omitted) -- renumbering is not.

Usage:
    python collapse_stem_dupes.py                       # dry run: report only
    python collapse_stem_dupes.py --apply                # rewrite bank + manifest
    python collapse_stem_dupes.py --apply --receipt r.json   # + removed-id receipt
    python collapse_stem_dupes.py --scope bank           # include cross-slice twins

Then re-verify (the removed ids are what the invariant must be told to expect):
    python verify_bank.py --allow-removed r.json
"""

import argparse
import collections
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from build_question_bank import DIFFICULTY_TIERS, OPTION_KEYS, stem_hash

from bank_paths import BANK_DIR, MANIFEST_PATH, REPO_ROOT  # noqa: E402  the ONE bank path (#203)


def _bank_files() -> List[Path]:
    return sorted(p for p in BANK_DIR.glob("*/*.json") if p.name != "manifest.json")


def _load(path: Path) -> List[Dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def find_groups(scope: str) -> List[List[Tuple[Path, int, Dict]]]:
    """Stem-duplicate groups, each a list of (file, position, question) in bank order."""
    key_fn = (
        (lambda q: (stem_hash(q), q.get("cluster"), q.get("level"))) if scope == "slice"
        else (lambda q: (stem_hash(q),))
    )
    groups: Dict[tuple, List[Tuple[Path, int, Dict]]] = collections.defaultdict(list)
    for path in _bank_files():
        for i, q in enumerate(_load(path)):
            groups[key_fn(q)].append((path, i, q))
    return [g for g in groups.values() if len(g) > 1]


def cross_slice_groups() -> List[List[Tuple[Path, int, Dict]]]:
    """Stem twins that span cluster x level -- reported, never collapsed under `slice`."""
    out = []
    for g in find_groups("bank"):
        if len({(q.get("cluster"), q.get("level")) for _, _, q in g}) > 1:
            out.append(g)
    return out


def refresh_manifest_entry(entry: Dict, questions: List[Dict]) -> None:
    """Re-tally one manifest entry from the file it points at.

    Only keys the entry already carries are rewritten, so a `sets` entry doesn't
    sprout a pools-only field (and `verify_bank.py` check [2] stays the judge of
    whether the numbers agree).
    """
    entry["count"] = len(questions)
    if "areaCounts" in entry:
        areas = collections.Counter(q.get("instructionalArea") for q in questions)
        entry["areaCounts"] = dict(sorted(areas.items(), key=lambda kv: -kv[1]))
    if "letterDistribution" in entry:
        letters = collections.Counter(str(q.get("answer", "")).strip().upper() for q in questions)
        entry["letterDistribution"] = {k: letters.get(k, 0) for k in OPTION_KEYS}
    if "difficultyCounts" in entry:
        diffs = collections.Counter(q.get("difficulty") for q in questions)
        entry["difficultyCounts"] = {t: diffs.get(t, 0) for t in DIFFICULTY_TIERS}


def apply_removals(removals: Dict[Path, set]) -> None:
    """Delete the listed ids from each file and re-tally the manifest entries."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_file = {
        entry["file"]: entry
        for section in ("sets", "pools")
        for entry in manifest.get(section, {}).values()
    }
    for path, ids in sorted(removals.items()):
        kept = [q for q in _load(path) if q.get("id") not in ids]
        _write(path, kept)
        entry = by_file.get(path.name)
        if entry is None:
            print(f"  [warn] {path.name} has no manifest entry; counts not refreshed")
            continue
        refresh_manifest_entry(entry, kept)
    _write(MANIFEST_PATH, manifest)


def main() -> None:
    ap = argparse.ArgumentParser(description="Collapse duplicate stems in the committed bank.")
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    ap.add_argument("--scope", choices=("slice", "bank"), default="slice",
                    help="`slice` (default) collapses twins within one cluster x level only; "
                         "`bank` also collapses cross-cluster twins that can never co-occur")
    ap.add_argument("--receipt", help="write the removed ids to this JSON path "
                                      "(feed it to verify_bank.py --allow-removed)")
    args = ap.parse_args()

    groups = find_groups(args.scope)
    removals: Dict[Path, set] = collections.defaultdict(set)
    receipt: List[Dict] = []

    print(f"\nScanning {BANK_DIR.relative_to(REPO_ROOT)} for duplicate stems "
          f"(scope: {args.scope})\n")
    for g in sorted(groups, key=lambda g: g[0][2].get("id") or ""):
        keep_path, _, keep_q = g[0]
        print(f"  KEEP {keep_q['id']} [{keep_q.get('difficulty')}] {keep_path.name}")
        print(f"       {keep_q['question'][:96]}")
        for path, _, q in g[1:]:
            removals[path].add(q["id"])
            receipt.append({
                "removed": q["id"],
                "file": path.name,
                "kept": keep_q["id"],
                "removedDifficulty": q.get("difficulty"),
                "keptDifficulty": keep_q.get("difficulty"),
                "cluster": q.get("cluster"),
                "level": q.get("level"),
                "performanceIndicator": q.get("performanceIndicator"),
            })
            conflict = (
                f"  (difficulty {q.get('difficulty')} -> {keep_q.get('difficulty')})"
                if q.get("difficulty") != keep_q.get("difficulty") else ""
            )
            print(f"   DROP {q['id']} [{q.get('difficulty')}] {path.name}{conflict}")
        print()

    n = sum(len(ids) for ids in removals.values())
    print(f"  {len(groups)} duplicate group(s) · {n} question(s) to remove "
          f"across {len(removals)} file(s)")

    if args.scope == "slice":
        cross = cross_slice_groups()
        if cross:
            print(f"\n  {len(cross)} cross-cluster stem twin(s) LEFT IN PLACE "
                  f"(never co-servable; see module docstring):")
            for g in cross:
                print("       " + " / ".join(
                    f"{q['id']} ({q.get('cluster')}/{q.get('level')})" for _, _, q in g))

    if args.receipt:
        Path(args.receipt).write_text(
            json.dumps({"removed": [r["removed"] for r in receipt], "detail": receipt},
                       indent=2) + "\n", encoding="utf-8")
        print(f"\n  wrote receipt -> {args.receipt}")

    if not args.apply:
        print("\n  dry run — nothing written. Re-run with --apply.\n")
        return
    if not removals:
        print("\n  nothing to remove.\n")
        return

    apply_removals(removals)
    print(f"\n  rewrote {len(removals)} bank file(s) + {MANIFEST_PATH.name}")
    print("  ids were NOT renumbered — surviving ids are byte-identical.\n")


if __name__ == "__main__":
    main()
