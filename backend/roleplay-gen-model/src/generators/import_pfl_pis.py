"""Plan 05 §5.2 step 2 -- extract DECA's published Personal Financial Literacy
performance indicators into ``data/pi/_pfl_national_standards_g12.json``.

WHY THIS TOOL EXISTS AND WHY IT IS NOT A HAND ENTRY. Plan 05 §5.2 recorded PFL's
PI list as "the only external data entry in either plan", on the reading that
DECA publishes it somewhere the repo does not hold. It does hold it, one link
away: deca.org/compete/personal-financial-literacy links "Performance
Indicators" straight at the *National Standards for Personal Financial
Education* (2021), and the PFL guidelines say in as many words that the exam
items and role-play situations "are selected from a list of performance
indicators identified in the National Standards for Personal Financial
Education, developed by the Council for Economic Education and the Jump$tart
Coalition for Personal Financial Literacy." Its six Topics ARE the six PFL
instructional areas, in DECA's own order:

    Earning Income · Spending · Saving · Investing · Managing Credit · Managing Risk

So the list is published, structured and machine-readable, and typing it by hand
would introduce transcription error into the one artifact everything else is
checked against.

GRADE 12 ONLY, STATED RATHER THAN ASSUMED. The document carries Learning
Outcomes at grades 4, 8 and 12 (62 / 110 / 204). PFL is a high-school event, so
this takes grade 12. It does NOT take grade 8, and that is a real exclusion
rather than a tidy one: 10 of the 30 PIs the corpus harvest recovered from real
PFL role-plays are verbatim National Standards outcomes and at least one of them
("Describe how a credit card user can minimize interest charges on their credit
card purchases.") is an 8th-grade outcome, 8-4b. Nothing is lost by it, because
the corpus lines are unioned in by ``harvest_pis.py`` on their own authority --
the grade-8 outcomes DECA has actually USED arrive through the corpus, and the
other 100 do not arrive at all.

THE WRITER IS ``harvest_pis.py``, NOT THIS TOOL. This writes exactly one file,
the JSON. ``data/pi/*.txt`` has a single writer, so "harvest --write after
import --write" cannot silently drop the imported lines.

COPYRIGHT. The National Standards are Copyright (c) 2021, Council for Economic
Education and Jump$tart Coalition for Personal Financial Literacy, and are
reproducible for noncommercial educational and research purposes with the notice
carried. The notice rides in the JSON's ``_source`` block, because a
``data/pi/*.txt`` file has no comment syntax -- ``load_pi_by_area`` reads every
non-blank line as a PI.

Usage (the PDF is not committed; pass the copy you downloaded):

    python3 src/generators/import_pfl_pis.py --pdf /path/to/standards.pdf
    python3 src/generators/import_pfl_pis.py --pdf /path/to/standards.pdf --write
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parents[2]
PI_DIR = BASE_DIR / "data" / "pi"
OUT_PATH = PI_DIR / "_pfl_national_standards_g12.json"

SOURCE_URL = (
    "https://cdn.prod.website-files.com/635c470cc81318fc3e9c1e0e/"
    "639a9fad2477fc3c1a9d9bbf_HS_Performance_Indicators_Personal_Finance.pdf"
)
SOURCE_TITLE = "National Standards for Personal Financial Education (2021)"
SOURCE_COPYRIGHT = (
    "Copyright (c) 2021, Council for Economic Education, 122 East 42 Street, "
    "Suite 1012, New York, NY 10168; and Jump$tart Coalition for Personal "
    "Financial Literacy, 1001 Connecticut Ave. NW, Suite 640, Washington, D.C. "
    "20036. All rights reserved. The Standards and Benchmarks in this document "
    "may be reproduced for noncommercial educational and research purposes. "
    "Notice of copyright must appear on all pages."
)
SOURCE_SHA256_NOTE = "sha256 of the PDF this extraction was taken from"

# 0-indexed PDF pages holding each Topic's GRADE 12 Learning Outcomes table, and
# the running label printed on those pages. The label is not decoration: it is
# the trailing word(s) the extractor picks up after the last outcome on a page,
# and trimming it needs the exact string.
TOPIC_PAGES: Dict[str, Dict] = {
    "earning_income": {"pages": [13, 14], "label": "Earning Income"},
    "spending": {"pages": [18, 19], "label": "Spending"},
    "saving": {"pages": [23, 24], "label": "Saving"},
    "investing": {"pages": [28, 29, 30], "label": "Investing"},
    "managing_credit": {"pages": [34, 35], "label": "Managing Credit"},
    "managing_risk": {"pages": [39, 40], "label": "Managing Risk"},
}

# Outcome codes render as "12-7a." and, where the layout breaks the line, as
# "12. 2b." -- both forms are real and both appear in the 2021 typesetting.
CODE_RE = re.compile(r"\b12\s*[.\-]\s*(\d{1,2})\s*([a-h])\.\s*")

RUNNING_FOOTER = "National Standards for Personal Financial Education"


def clean(text: str) -> str:
    """Repair the artifacts the PDF's typesetting leaves in an outcome.

    U+0007 is the bullet glyph the extractor emits for the document's list
    marker; "e. g." and "checking/ savings" are letter-spacing the extractor
    reads as word breaks. Every substitution here was read off the output, not
    assumed -- see the module docstring's standing rule about reading the output
    rather than trusting the number.
    """
    t = text.replace("\x07", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\be\.\s+g\.\s*", "e.g. ", t)
    t = re.sub(r"(\w)/\s+(\w)", r"\1/\2", t)
    return t.strip()


def extract(pdf_path: Path) -> Dict[str, List[str]]:
    try:
        import fitz  # PyMuPDF  # noqa: PLC0415
    except ImportError:  # pragma: no cover
        raise SystemExit(
            "PyMuPDF is required to extract the PDF: pip install pymupdf"
        )

    doc = fitz.open(pdf_path)
    out: Dict[str, List[str]] = {}
    for slug, spec in TOPIC_PAGES.items():
        seen = set()
        items: List[str] = []
        for page_no in spec["pages"]:
            raw = doc[page_no].get_text().replace(RUNNING_FOOTER, "")
            page = clean(raw)
            hits = list(CODE_RE.finditer(page))
            for i, m in enumerate(hits):
                end = hits[i + 1].start() if i + 1 < len(hits) else len(page)
                body = page[m.end():end].strip()
                # The last outcome on a page runs into the running label and the
                # page number; both are fixed and both are trimmed off the tail.
                body = re.sub(re.escape(spec["label"]) + r"\s*$", "", body).strip()
                body = re.sub(r"\s*\d{1,3}\s*$", "", body).strip()
                key = (int(m.group(1)), m.group(2))
                if key in seen:
                    continue
                seen.add(key)
                items.append(body)
        out[slug] = items
    return out


def verify(topics: Dict[str, List[str]]) -> List[str]:
    """Structural checks on the extraction. A silent bad parse is the failure
    mode here, so these run every time and are reported, not assumed."""
    problems: List[str] = []
    for slug, items in topics.items():
        if not items:
            problems.append(f"{slug}: extracted nothing")
        for pi in items:
            if len(pi) < 15:
                problems.append(f"{slug}: implausibly short outcome: {pi!r}")
            if not pi.endswith("."):
                problems.append(f"{slug}: outcome does not end in a period: {pi!r}")
            if CODE_RE.search(pi):
                problems.append(f"{slug}: outcome swallowed a later code: {pi!r}")
            if RUNNING_FOOTER in pi:
                problems.append(f"{slug}: outcome carries the running footer: {pi!r}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", required=True, type=Path,
                    help="local copy of the National Standards PDF")
    ap.add_argument("--write", action="store_true",
                    help=f"write {OUT_PATH.name} (default: report only)")
    args = ap.parse_args()

    if not args.pdf.exists():
        print(f"no such file: {args.pdf}")
        return 1

    import hashlib
    digest = hashlib.sha256(args.pdf.read_bytes()).hexdigest()

    topics = extract(args.pdf)
    problems = verify(topics)

    print(f"{'AREA':<20} {'GRADE-12 OUTCOMES':>18}")
    for slug, items in topics.items():
        print(f"{slug:<20} {len(items):>18}")
    print(f"{'TOTAL':<20} {sum(len(v) for v in topics.values()):>18}")
    print(f"\nsource sha256: {digest}")

    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems:
            print(f"  {p}")
        return 1

    if not args.write:
        print("\nreport only -- pass --write to update "
              f"data/pi/{OUT_PATH.name}")
        return 0

    payload = {
        "_source": {
            "title": SOURCE_TITLE,
            "url": SOURCE_URL,
            "linked_from": "https://www.deca.org/compete/personal-financial-literacy",
            "grades_taken": "12 only -- see import_pfl_pis.py's docstring",
            "sha256": digest,
            "sha256_note": SOURCE_SHA256_NOTE,
            "copyright": SOURCE_COPYRIGHT,
        },
        "topics": topics,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"\nwrote {OUT_PATH.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
