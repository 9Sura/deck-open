#!/usr/bin/env python3
"""Rebuild data/pi/ from the 396-file corpus in data/<CODE>/.

Plan 05 §3.2a step 1. Costs no model tokens: every (instructional area,
performance indicator) pair is already in the repo, carried by the
``INSTRUCTIONAL AREA:`` header and ``PERFORMANCE INDICATORS`` block that all
396 corpus files have.

Merge policy is HYBRID (plan 05 OQ1a, decided 2026-08-19):

  * the corpus is authoritative for any area it supplies PIs for -- the
    existing lines for that area are discarded;
  * the existing lines are kept only for an area the corpus supplies ZERO
    for, so no event loses an eligible area to a gap in the corpus;
  * where a PI appears in both and the two disagree about its area, the
    corpus area wins and the library copy is dropped, so a PI string has
    exactly one home. Two homes would make the plan 05 §3 core-quota
    attribution ambiguous, which is the drift D5 exists to eliminate.

Nothing is written without ``--write``. The report is the same either way, and a
second ``--write`` is a no-op: the merge converges, so re-running produces a
byte-identical tree. Note the ``before`` column then reads the previous run's
output rather than the original library.

``backend/test-gen-model/data/pi/`` IS A SEPARATE LIBRARY AND MUST NOT BE
RE-SYNCED TO THIS ONE. The two were byte-for-byte identical on 23 of 24 files
until this harvest -- one was copied from the other and a single later update
(test-gen's 18 ``risk_management`` PIs) was never copied back
(audits/DECA_PI_recheck_report.md, 2026-08-19). This harvest deliberately breaks
that relationship: the roleplay library is now derived from the roleplay corpus
and disagrees with test-gen's on 21 of 24 files by design. Copying either way
would destroy one of them. In particular the 18 ``risk_management`` PIs are
business-risk PIs and do NOT fix PFL, which needs DECA's personal "Managing
Risk" (plan 05 5.2).
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PI_DIR = DATA_DIR / "pi"
EVENTS_JSON = DATA_DIR / "events.json"
PROVENANCE = PI_DIR / "_provenance.json"

AREA_RE = re.compile(r"^INSTRUCTIONAL AREA[S]?:\s*(.+?)\s*$", re.M)
PI_BLOCK_RE = re.compile(
    r"^PERFORMANCE INDICATORS[^\n]*\n(.*?)(?:\n\s*\n)", re.M | re.S
)

# Corpus area headings that need consolidating before use. Recorded here
# rather than applied silently, because a mapping is an editorial decision.
CONSOLIDATE: Dict[str, str] = {
    # ENT/district_2018_1.txt's header is truncated by the scan
    # ("INSTRUCTIONAL AREA: Information Management and" with nothing after).
    # The source PDF prints it over TWO lines -- "Information Management and
    # Marketing-Information Management" -- and the extractor dropped the second
    # (audits/DECA_PI_recheck_report.md, 2026-08-19). So the heading names two
    # areas, not one, and this mapping is a judgement rather than a lookup: its
    # five PIs are marketing-research PIs ("Explain the nature of marketing
    # research", "Interpret statistical findings"), so the block is filed under
    # marketing-information management. There is no area named
    # "information_management_and" and one must never be created.
    "information_management_and": "marketing_information_management",

    # PFL, plan 05 §5.2 step 1. Its ten corpus files declare NINE area headings
    # spanning three DECA renamings; DECA's current PFL list has SIX, and the
    # nine are historical predecessors or combinations of them, not nine extra
    # sections (audits/DECA_PI_recheck_report.md, 2026-08-19). Consolidating is
    # free and it is a prerequisite rather than a tidy-up: the corpus supplies
    # only 30 PIs across the nine, which is 3 per area except Credit and Debt's
    # 6, so four of them yield C(3,3) = ONE distinct core set against a 30-deep
    # shelf and plan 05 §3's quota is unsatisfiable as filed.
    #
    # "spending_and_saving" folds into SPENDING and is not split. One of its
    # three PIs ("Compare the advantages and disadvantages of saving for
    # financial goals.") reads as a Saving PI and an earlier draft of this step
    # proposed splitting the heading across both areas. It is not split, for
    # two reasons: this harvest's unit is the FILE's declared heading and a
    # per-PI override is not expressible in it, and 149 of 578 distinct corpus
    # PIs (25.8%) are filed by DECA under more than one area anyway, so "the
    # area this PI belongs to" is not a question with an answer. The heading is
    # the evidence; the verb is not.
    "credit_and_debt": "managing_credit",
    "employment_and_income": "earning_income",
    "risk_management_and_insurance": "managing_risk",
    "spending_and_saving": "spending",
}

# DECA's six current Personal Financial Literacy instructional areas, in DECA's
# own order. CONSOLIDATE above maps the corpus's nine historical headings onto
# these; `events.json` lists exactly these six for PFL.
PFL_AREAS = [
    "earning_income",
    "spending",
    "saving",
    "investing",
    "managing_credit",
    "managing_risk",
]

# DECA's PUBLISHED PFL performance indicators, extracted by
# `import_pfl_pis.py` from the National Standards for Personal Financial
# Education (2021) -- the document deca.org/compete/personal-financial-literacy
# links as PFL's "Performance Indicators" and the PFL guidelines name as the
# source of its role-play situations. Unioned onto the corpus lines for the six
# PFL areas only.
#
# This file is a SECOND SOURCE, not a second writer: `harvest_pis.py` remains
# the only thing that writes `data/pi/*.txt`, so a re-harvest cannot silently
# drop the imported lines the way two writers over one tree would.
PFL_PUBLISHED = PI_DIR / "_pfl_national_standards_g12.json"


def load_pfl_published() -> Dict[str, List[str]]:
    """The published grade-12 outcomes per PFL area, or {} if not imported yet.

    Absent is not an error: the corpus half of the harvest stands on its own and
    a checkout that has not run `import_pfl_pis.py --write` should still be able
    to rebuild `data/pi/` from the corpus. The report says which half it got.
    """
    if not PFL_PUBLISHED.exists():
        return {}
    payload = json.loads(PFL_PUBLISHED.read_text(encoding="utf-8"))
    topics = payload.get("topics", {})
    unknown = sorted(set(topics) - set(PFL_AREAS))
    if unknown:
        raise ValueError(
            f"{PFL_PUBLISHED.name} carries area(s) that are not PFL areas: "
            f"{', '.join(unknown)}. PFL's six areas are {', '.join(PFL_AREAS)}."
        )
    return {slug: [strip_bullets(ln) for ln in lines if strip_bullets(ln)]
            for slug, lines in topics.items()}


def slugify_area(area: str) -> str:
    """DECA's printed area heading -> a data/pi/ file slug."""
    a = unicodedata.normalize("NFKD", area).strip()
    a = re.sub(r"[^\w\s/&-]", "", a)
    a = a.lower().replace("&", "and").replace("/", " ")
    return re.sub(r"[\s-]+", "_", a).strip("_")


# Leading bullet glyphs to strip off a harvested line. The private-use range
# is not decoration: 30 corpus files from 2020 carry a second, INVISIBLE bullet
# after the ordinary "- " -- U+F0A7, the Wingdings square, left behind by the
# PDF extraction on 161 lines. It survives a plain lstrip of "-*\u2022 \t",
# normalize_pi() strips it from the dedup KEY but not from the spelling that
# gets written, so 40 of them shipped into data/pi/ before this existed.
_BULLET_RE = re.compile(r"^[\s\-*\u00b7\u2010-\u2015\u2022\u25aa\u25cf\u25e6\uf000-\uf8ff]+")


def strip_bullets(line: str) -> str:
    """Drop every leading bullet layer. Idempotent by construction."""
    return _BULLET_RE.sub("", line).strip()


def normalize_pi(pi: str) -> str:
    """Dedup key. Survives the scan noise: apostrophes, trailing periods,
    doubled whitespace, en/em dashes. Never written to disk."""
    p = unicodedata.normalize("NFKD", pi).lower().strip().rstrip(".")
    p = re.sub(r"[^a-z0-9 ]", "", p)
    return re.sub(r"\s+", " ", p).strip()


def read_lines(path: Path) -> List[str]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = strip_bullets(line)
        if line:
            out.append(line)
    return out


def harvest_corpus(event_codes: Set[str]) -> Tuple[
    Dict[str, Dict[str, collections.Counter]], List[str]
]:
    """area slug -> {dedup key -> Counter of the spellings seen}."""
    found: Dict[str, Dict[str, collections.Counter]] = collections.defaultdict(
        lambda: collections.defaultdict(collections.Counter)
    )
    skipped: List[str] = []
    for path in sorted(DATA_DIR.glob("*/*.txt")):
        code = path.parent.name
        if code not in event_codes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        areas = AREA_RE.findall(text)
        block = PI_BLOCK_RE.search(text)
        if not areas:
            skipped.append(f"{code}/{path.name}: no INSTRUCTIONAL AREA header")
            continue
        if not block:
            skipped.append(f"{code}/{path.name}: no PERFORMANCE INDICATORS block")
            continue
        if len(areas) > 1:
            skipped.append(
                f"{code}/{path.name}: {len(areas)} INSTRUCTIONAL AREA headers"
            )
            continue
        slug = slugify_area(areas[0])
        slug = CONSOLIDATE.get(slug, slug)
        for line in block.group(1).splitlines():
            pi = strip_bullets(line)
            if pi:
                found[slug][normalize_pi(pi)][pi] += 1
    return found, skipped


def canonical(spellings: collections.Counter) -> str:
    """Most-frequent spelling; ties broken alphabetically so the output is
    byte-stable across runs."""
    top = max(c for c in spellings.values())
    return sorted(s for s, c in spellings.items() if c == top)[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="write data/pi/*.txt and _provenance.json (default: report only)")
    args = ap.parse_args()

    events = json.loads(EVENTS_JSON.read_text(encoding="utf-8"))["events"]
    codes = {cfg["data_folder"] for cfg in events.values()}

    corpus, skipped = harvest_corpus(codes)
    for line in skipped:
        print(f"  [warn] {line}", file=sys.stderr)

    existing: Dict[str, List[str]] = {}
    for path in sorted(PI_DIR.glob("*.txt")):
        existing[path.stem] = read_lines(path)

    # --- cross-area conflicts: the corpus area wins -----------------------
    corpus_home: Dict[str, Set[str]] = collections.defaultdict(set)
    for slug, pis in corpus.items():
        for key in pis:
            corpus_home[key].add(slug)

    conflicts: List[Tuple[str, str, str]] = []   # (library area, corpus areas, PI)
    for slug, lines in existing.items():
        for line in lines:
            key = normalize_pi(line)
            homes = corpus_home.get(key)
            if homes and slug not in homes:
                conflicts.append((slug, "/".join(sorted(homes)), line))

    # --- hybrid merge -----------------------------------------------------
    result: Dict[str, List[str]] = {}
    kept_areas: List[str] = []
    for slug in sorted(set(corpus) | set(existing)):
        if slug in corpus and corpus[slug]:
            result[slug] = sorted(canonical(sp) for sp in corpus[slug].values())
        else:
            # corpus supplies nothing for this area: keep what is there so no
            # event loses an eligible area to a gap in the corpus.
            keep = [ln for ln in existing.get(slug, [])
                    if slug in corpus_home.get(normalize_pi(ln), {slug})]
            result[slug] = sorted(set(keep))
            if keep:
                kept_areas.append(slug)

    # --- PFL: union DECA's published list onto the corpus lines -----------
    # Corpus spelling wins a collision: it is the wording DECA actually printed
    # on a role-play, and 10 of the 30 corpus PFL PIs are verbatim National
    # Standards outcomes already, so the overlap is real rather than theoretical.
    published = load_pfl_published()
    added: Dict[str, int] = {}
    for slug in PFL_AREAS:
        lines = published.get(slug, [])
        if not lines:
            continue
        have = {normalize_pi(ln) for ln in result.get(slug, [])}
        fresh = []
        for ln in lines:
            key = normalize_pi(ln)
            if key in have:
                continue
            have.add(key)
            fresh.append(ln)
        if fresh:
            result[slug] = sorted(result.get(slug, []) + fresh)
            added[slug] = len(fresh)

    # --- report -----------------------------------------------------------
    print(f"corpus files scanned: "
          f"{sum(1 for p in DATA_DIR.glob('*/*.txt') if p.parent.name in codes)}"
          f"  |  skipped: {len(skipped)}")
    print(f"distinct corpus areas: {len(corpus)}  |  cross-area conflicts resolved "
          f"to the corpus: {len(conflicts)}")
    print()
    print(f"{'area':<36} {'before':>6} {'after':>6} {'delta':>6}  source")
    for slug in sorted(result):
        before, after = len(existing.get(slug, [])), len(result[slug])
        if slug in corpus and corpus[slug]:
            src = "corpus"
        elif after:
            src = "existing (corpus supplies none)"
        else:
            src = "EMPTY"
        if slug in added:
            src = f"{src} + published ({added[slug]})"
        tag = "  [PFL]" if slug in PFL_AREAS else ""
        print(f"{slug:<36} {before:>6} {after:>6} {after - before:>+6}  {src}{tag}")
    tot_b, tot_a = sum(len(v) for v in existing.values()), sum(len(v) for v in result.values())
    print(f"{'TOTAL':<36} {tot_b:>6} {tot_a:>6} {tot_a - tot_b:>+6}")

    if published:
        print(f"\nPFL published list: {sum(len(v) for v in published.values())} "
              f"grade-12 outcomes read from {PFL_PUBLISHED.name}, "
              f"{sum(added.values())} new after dedup against the corpus.")
    else:
        print(f"\nPFL published list: {PFL_PUBLISHED.name} is ABSENT -- the six PFL "
              f"areas carry corpus lines only. Run import_pfl_pis.py --write "
              f"(plan 05 §5.2).")

    if conflicts:
        print(f"\ncross-area conflicts (library copy dropped, corpus area kept):")
        for lib, corp, pi in sorted(conflicts):
            print(f"  {lib:<32} -> {corp:<32} | {pi}")

    # A CONSOLIDATE source can never be produced again by construction, so its
    # file is an orphan rather than an empty area -- leaving a zero-line
    # `credit_and_debt.txt` on disk would keep it eligible for `events.json` and
    # would trip plan 05 D7's raise the moment someone listed it. Other empty
    # files are left alone: they are areas the corpus simply has nothing for.
    retired = sorted(slug for slug in CONSOLIDATE if (PI_DIR / f"{slug}.txt").exists())
    for slug in retired:
        result.pop(slug, None)

    empty = [s for s, v in result.items() if not v]
    if empty:
        print(f"\nareas resolving to ZERO PIs: {', '.join(empty)}")
        print("  plan 05 D7: an eligible area with no PIs comes off the event "
              "rather than silently contributing nothing.")

    if retired:
        print(f"\nretired (consolidated away, file deleted): {', '.join(retired)}")

    if not args.write:
        print("\n(report only -- pass --write to update data/pi/)")
        return 0

    for slug in retired:
        (PI_DIR / f"{slug}.txt").unlink()

    for slug, lines in result.items():
        (PI_DIR / f"{slug}.txt").write_text(
            "".join(f"{ln}\n" for ln in lines), encoding="utf-8"
        )
    PROVENANCE.write_text(json.dumps({
        "generated_by": "src/generators/harvest_pis.py",
        "plan": "05-pi-selection-and-regeneration-plan.md §3.2a step 1",
        "merge_policy": "hybrid (OQ1a, decided 2026-08-19)",
        "corpus_files": sum(1 for p in DATA_DIR.glob("*/*.txt") if p.parent.name in codes),
        "consolidated_area_slugs": CONSOLIDATE,
        "pfl_areas": PFL_AREAS,
        "pfl_published_source": (
            json.loads(PFL_PUBLISHED.read_text(encoding="utf-8")).get("_source")
            if PFL_PUBLISHED.exists() else None
        ),
        "pfl_published_lines_added": {s_: n for s_, n in sorted(added.items())},
        "areas_kept_from_the_existing_library": sorted(kept_areas),
        "cross_area_conflicts_resolved_to_the_corpus": [
            {"library_area": a, "corpus_area": b, "pi": c}
            for a, b, c in sorted(conflicts)
        ],
        "areas_with_zero_pis": sorted(empty),
        "retired_area_files": retired,
        "do_not_resync_with": {
            "path": "backend/test-gen-model/data/pi/",
            "why": (
                "a separate library that was byte-identical on 23 of 24 files before this "
                "harvest; the roleplay library is now corpus-derived and diverges by design. "
                "Copying either way destroys one of them. test-gen's 18 risk_management PIs "
                "are business-risk PIs and do not fix PFL."
            ),
        },
        "pi_counts": {s: len(v) for s, v in sorted(result.items())},
    }, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {len(result)} files to {PI_DIR} and {PROVENANCE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
