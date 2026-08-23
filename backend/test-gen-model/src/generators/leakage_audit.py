#!/usr/bin/env python3
"""Prove the published banks are not echoing the source corpus back.

WHY THIS EXISTS
---------------
Both pipelines are few-shot: `generate_test.py` shows the model real DECA exam
questions from `data/<cluster>/`, and the roleplay authoring prompt shows it real
roleplays from `data/<CODE>/`. A model shown real text can hand a piece of it
back -- a stem lifted whole, an option set, a sentence out of an official
explanation. Nobody had ever checked whether that happened, which left "our
questions are original" as an assumption sitting underneath a public repository
and a claim on the site.

This turns it into a measurement. It reports the longest verbatim word run
shared between anything we publish and anything in the private corpus, per
question, and exits non-zero if any run reaches the threshold.

WHAT COUNTS AS LEAKAGE, AND WHAT DOES NOT
-----------------------------------------
Short shared runs are unavoidable and meaningless -- "which of the following best
describes the" is English, not copying. Two filters keep those out of the report,
and both matter more than the threshold itself:

1. COMMON PHRASING. A run found in `--max-files` or more DISTINCT source files
   (default 3) is house style, not a fingerprint of one exam. DECA's exams share
   stem furniture and every roleplay carries the same PARTICIPANT INSTRUCTIONS
   and 21st CENTURY SKILLS blocks verbatim by design. One source file is a
   fingerprint; twenty is a genre.

2. PI TEXT. The performance-indicator library is the vocabulary both sides are
   written against, so a PI phrase appearing in an explanation is the tool
   working, not leakage. Every n-gram drawn from `data/pi/` is subtracted from
   the source index before scanning.

What is left is the interesting set: a long run of words that appears in exactly
one real exam and in something we published.

USAGE
-----
    python leakage_audit.py                          # questions, n=8
    python leakage_audit.py --corpus roleplays       # the roleplay bank
    python leakage_audit.py --n 6 --max-files 2      # stricter
    python leakage_audit.py --json report.json       # machine-readable findings

Exit codes: 0 = clean, 1 = findings, 2 = bad usage / missing corpus.

REMEDIATION (the rule this tool serves)
---------------------------------------
A finding is REGENERATED, never edited down to just under the threshold. Trimming
a word off an eight-word match does not make the item original, it makes the
audit blind. Feed the flagged ids back through the authoring loop for their slice
and re-run this until it exits 0.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bank_paths import BANK_DIR, REPO_ROOT  # noqa: E402

TEST_MODEL = REPO_ROOT / "backend" / "test-gen-model"
ROLEPLAY_MODEL = REPO_ROOT / "backend" / "roleplay-gen-model"

WORD = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> List[str]:
    """Words only, lowercased. Punctuation, casing and whitespace are noise here --
    a stem reflowed by the PDF extractor must still match the same stem in a JSON
    field, and neither side's typography carries meaning."""
    return WORD.findall(text.lower())


def grams(words: Sequence[str], n: int) -> Iterable[Tuple[int, str]]:
    for i in range(len(words) - n + 1):
        yield i, " ".join(words[i : i + n])


# --------------------------------------------------------------------- corpus

def source_files(corpus: str) -> List[Path]:
    """The private few-shot corpus for this pipeline. These files are the reason
    the repo is private; this tool is the only one that reads them wholesale."""
    if corpus == "questions":
        return sorted((TEST_MODEL / "data").glob("*/*.txt"))
    return sorted((ROLEPLAY_MODEL / "data").glob("*/*.txt"))


def pi_files(corpus: str) -> List[Path]:
    """The PI library for this pipeline. NOTE the two libraries are separate by
    design and must never be merged -- this reads whichever one matches the corpus
    under audit and nothing else."""
    model = TEST_MODEL if corpus == "questions" else ROLEPLAY_MODEL
    return sorted((model / "data" / "pi").glob("*.txt"))


def build_index(files: Sequence[Path], n: int) -> Tuple[Dict[str, int], List[str]]:
    """gram -> bitmask of the source files it appears in.

    A bitmask rather than a set per gram: 73 exam files fit in one int, and the
    per-gram set version of this costs a few hundred MB for no extra information.
    The mask is also what identifies WHICH exam a run came from -- AND the masks
    along a run and whatever bits survive are the files containing all of it."""
    index: Dict[str, int] = {}
    names: List[str] = []
    for bit, path in enumerate(files):
        names.append(str(path.relative_to(REPO_ROOT)))
        words = tokens(path.read_text(encoding="utf-8", errors="replace"))
        flag = 1 << bit
        for _, gram in grams(words, n):
            index[gram] = index.get(gram, 0) | flag
    return index, names


def subtract_pi_text(index: Dict[str, int], corpus: str, n: int) -> int:
    """Drop every n-gram that the PI library also produces. Removed, not merely
    ignored at report time, so it cannot come back through the run-extension pass."""
    removed = 0
    for path in pi_files(corpus):
        words = tokens(path.read_text(encoding="utf-8", errors="replace"))
        for _, gram in grams(words, n):
            if index.pop(gram, None) is not None:
                removed += 1
    return removed


# ----------------------------------------------------------------- published

def published_units(corpus: str) -> List[dict]:
    """Everything we publish, flattened to {source, id, field, text} records.

    Only fields a reader actually sees are scanned. Tag fields (cluster, level,
    instructional area, performance indicator) are excluded deliberately: they are
    SUPPOSED to match the corpus word for word, and including them would bury the
    report in the one class of match that is by design."""
    units: List[dict] = []
    if corpus == "questions":
        for path in sorted(BANK_DIR.glob("*/*.json")):
            if path.name == "manifest.json":
                continue
            rel = str(path.relative_to(REPO_ROOT))
            for item in json.loads(path.read_text(encoding="utf-8")):
                qid = item.get("id", "?")
                units.append({"source": rel, "id": qid, "field": "question",
                              "text": item.get("question", "")})
                for letter, opt in (item.get("options") or {}).items():
                    units.append({"source": rel, "id": qid, "field": f"option {letter}",
                                  "text": opt or ""})
                units.append({"source": rel, "id": qid, "field": "explanation",
                              "text": item.get("explanation", "")})
        return units

    sys.path.insert(0, str(ROLEPLAY_MODEL / "src" / "generators"))
    from parse_roleplay import DEFAULT_OUT  # noqa: E402  (canonical roleplay root)
    import bank as rp_bank  # noqa: E402

    for path in sorted(rp_bank.bank_dir(DEFAULT_OUT).glob("*/*.json")):
        if path.name == "manifest.json":
            continue
        rel = str(path.relative_to(REPO_ROOT))
        entry = json.loads(path.read_text(encoding="utf-8"))
        rid = entry.get("id", "?")
        for field in ("participantInstructions", "situation", "judgeCharacterization"):
            units.append({"source": rel, "id": rid, "field": field,
                          "text": entry.get(field) or ""})
        for i, q in enumerate(entry.get("judgeQuestions") or [], 1):
            units.append({"source": rel, "id": rid, "field": f"judgeQuestion {i}",
                          "text": q if isinstance(q, str) else json.dumps(q)})
    return units


# --------------------------------------------------------------------- scan

def scan(units: Sequence[dict], index: Dict[str, int], names: Sequence[str],
         n: int, max_files: int) -> Tuple[List[dict], int]:
    """Longest verbatim run per unit, with common phrasing filtered out.

    Hits at consecutive start positions are one run, not several: an eleven-word
    lift produces four overlapping 8-gram hits, and reporting it four times would
    make one problem look like four."""
    findings: List[dict] = []
    common = 0

    for unit in units:
        words = tokens(unit["text"])
        if len(words) < n:
            continue

        hits: Dict[int, int] = {}
        for i, gram in grams(words, n):
            mask = index.get(gram)
            if mask is None:
                continue
            if bin(mask).count("1") >= max_files:
                common += 1
                continue
            hits[i] = mask

        if not hits:
            continue

        # A run only extends while SOME single source file still contains all of
        # it. Without that check, four overlapping 8-gram hits drawn from four
        # DIFFERENT exams report as one 11-word lift that exists in no exam at
        # all -- the scariest line in the report would be an artefact.
        best = None
        start = None
        prev = None
        mask = 0
        for i in sorted(hits):
            if prev is not None and i == prev + 1 and mask & hits[i]:
                mask &= hits[i]
            else:
                if start is not None:
                    best = _keep(best, words, start, prev, n, mask)
                start, mask = i, hits[i]
            prev = i
        best = _keep(best, words, start, prev, n, mask)

        run_len, text, run_mask = best
        findings.append({
            "file": unit["source"],
            "id": unit["id"],
            "field": unit["field"],
            "words": run_len,
            "text": text,
            "sources": [names[b] for b in range(len(names)) if run_mask >> b & 1],
        })

    findings.sort(key=lambda f: (-f["words"], f["file"], str(f["id"])))
    return findings, common


def _keep(best, words, start, end, n, mask):
    """Fold one run into the best-so-far for this unit. Run length is the window
    plus one word per additional consecutive start."""
    length = n + (end - start)
    candidate = (length, " ".join(words[start : end + n]), mask)
    return candidate if best is None or length > best[0] else best


# --------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", choices=("questions", "roleplays"), default="questions",
                    help="which pipeline to audit (default: questions)")
    ap.add_argument("--n", type=int, default=8,
                    help="verbatim run length that counts as leakage (default: 8 words)")
    ap.add_argument("--max-files", type=int, default=3,
                    help="a run in this many DISTINCT source files is common phrasing, "
                         "not leakage (default: 3)")
    ap.add_argument("--skip-fields", nargs="*", default=[], metavar="FIELD",
                    help="fields to leave out of the scan, e.g. participantInstructions. "
                         "Use ONLY for text we reproduce deliberately and have decided "
                         "about -- a field skipped to quiet the report is a field nobody "
                         "is auditing.")
    ap.add_argument("--top", type=int, default=20, help="findings to print (default: 20)")
    ap.add_argument("--json", type=Path, help="write the full report here")
    args = ap.parse_args()

    if args.n < 4:
        print("--n below 4 reports English, not leakage", file=sys.stderr)
        return 2

    sources = source_files(args.corpus)
    if not sources:
        print(f"no source corpus found for --corpus {args.corpus}.\n"
              f"This tool reads the private few-shot corpus under backend/*/data/, "
              f"which is not published. It cannot run in the public mirror.",
              file=sys.stderr)
        return 2
    print(f"[leakage] corpus  : {len(sources)} source file(s), n={args.n}, "
          f"max-files={args.max_files}")
    index, names = build_index(sources, args.n)
    print(f"[leakage] index   : {len(index):,} distinct {args.n}-gram(s)")
    removed = subtract_pi_text(index, args.corpus, args.n)
    print(f"[leakage] pi text : dropped {removed:,} gram(s) shared with the PI library")

    units = published_units(args.corpus)
    if args.skip_fields:
        skip = set(args.skip_fields)
        dropped = sum(1 for u in units if u["field"].split()[0] in skip)
        units = [u for u in units if u["field"].split()[0] not in skip]
        print(f"[leakage] skipped : {dropped:,} field(s) via --skip-fields "
              f"({', '.join(sorted(skip))})")
    published = len({(u["source"], u["id"]) for u in units})
    print(f"[leakage] published: {published:,} item(s), {len(units):,} scanned field(s)")

    findings, common = scan(units, index, names, args.n, args.max_files)
    print(f"[leakage] filtered: {common:,} common-phrasing hit(s) in "
          f"{args.max_files}+ source files")

    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "corpus": args.corpus,
        "params": {"n": args.n, "maxFiles": args.max_files,
                   "skipFields": args.skip_fields},
        "sourceFiles": len(sources),
        "publishedItems": published,
        "scannedFields": len(units),
        "commonPhrasingHits": common,
        "findings": findings,
    }
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"[leakage] report  : {args.json}")

    if not findings:
        print(f"\nOK -- no verbatim run of {args.n}+ words is shared with a single "
              f"source file.")
        return 0

    items = len({(f["file"], f["id"]) for f in findings})
    print(f"\n{len(findings)} finding(s) across {items} published item(s). "
          f"Longest run: {findings[0]['words']} words.\n")
    for f in findings[: args.top]:
        print(f"  {f['words']:>3}w  {f['id']}  ({f['field']})")
        print(f"        \"{f['text']}\"")
        print(f"        also in: {', '.join(f['sources'])}")
    if len(findings) > args.top:
        print(f"\n  ... and {len(findings) - args.top} more (--top / --json for all)")

    print("\nRegenerate these items -- do not edit them below the threshold.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
