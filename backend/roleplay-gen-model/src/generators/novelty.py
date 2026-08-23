"""Plan 03 §5d, detection half -- the cross-day novelty index. No model calls.

State is `data/novelty/<EVENT>.json`, 28 files, NOT one index. §5d's reasoning,
recorded because it is the kind of thing a later refactor undoes: a single file
would be 1-4 MB rewritten on every batch -- unreadable churn in git history.
28 files makes each batch 28 tiny appends with readable diffs.

The stored excerpt is capped at EXCERPT_CHARS because the full text already
lives in the archive. That makes this a DERIVED CACHE, which is what
`--rebuild-index` exists for: it regenerates all 28 files from the archive with
zero model calls, so a corrupted or deleted index is never a lost artifact.

Entries are keyed by date and REPLACED, never appended (§6b idempotency), so
`--force` corrects a day rather than double-counting it.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence

BASE_DIR = Path(__file__).resolve().parents[2]
NOVELTY_DIR = BASE_DIR / "data" / "novelty"

# §5d: excerpt capped because the archive holds the real text.
EXCERPT_CHARS = 800
# §5d: 90-day prune-on-write keeps each file ~45 KB.
PRUNE_DAYS = 90
# §5d: "today's scenario against the last 30 days for this event only."
COMPARE_DAYS = 30
# §5d: company-name reuse is rejected over a longer window than the plot
# comparison -- difflib scores a name swap as barely-different, so the name is
# the one signal that survives a full re-skin.
COMPANY_DAYS = 90

# Section labels and other structural all-caps text that is not a company name.
_NOT_A_NAME = frozenset(
    """CAREER CLUSTER INSTRUCTIONAL AREA PARTICIPANT INSTRUCTIONS PERFORMANCE
    INDICATORS EVENT SITUATION CASE STUDY JUDGE ROLE-PLAY CHARACTERIZATION
    CENTURY SKILLS EXHIBIT SELF-REPORT END QUALITY BAR DECA ICDC THE AND FOR
    YOU NOT ALL ANY ONE TWO CEO CFO COO CTO HR VP""".split()
)

_ALLCAPS = re.compile(r"\b[A-Z][A-Z&'\-]{2,}(?:[^\S\n]+[A-Z][A-Z&'\-]{1,})*\b")
# `[^\S\n]` (whitespace that is not a newline), NOT `\s`. With `\s` the joiner
# crossed line breaks and glued the last word of one line to the first words of
# the next: a paragraph ending "...Operations" above a line opening "John Smith"
# extracted as the single name "Operations John Smith". A company name does not
# span a line break, and a fabricated one is worse than a missed one here --
# `bank.reused_companies` REJECTS on these.
_TITLECASE = re.compile(r"\b(?:[A-Z][a-z]+){1,}(?:[^\S\n]+(?:[A-Z][a-z]+|&)){0,3}\b")


def path_for(code: str) -> Path:
    return NOVELTY_DIR / f"{code.upper()}.json"


def load(code: str) -> List[Dict]:
    p = path_for(code)
    if not p.is_file():
        return []
    try:
        entries = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # A derived cache that cannot be read is a rebuild, not a crash.
        return []
    return entries if isinstance(entries, list) else []


def recent(code: str, day: date, *, days: int = COMPARE_DAYS) -> List[Dict]:
    """This event's entries within `days` before `day`, newest first.

    Entries dated ON or AFTER `day` are excluded: when a batch regenerates a day
    that is already on disk, its own previous entry must not be compared against
    itself, and future days in the same batch are not yet published context for
    an earlier one.
    """
    cutoff = day - timedelta(days=days)
    out = [
        e for e in load(code)
        if e.get("date") and cutoff <= _as_date(e["date"], day) < day
    ]
    return sorted(out, key=lambda e: e["date"], reverse=True)


def _as_date(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return fallback


def entry_for(
    code: str,
    day: date,
    *,
    situation: str,
    axes: Dict[str, str],
    similarity: float = 0.0,
    nearest: Optional[str] = None,
    passed: bool = True,
) -> Dict:
    """Build one index entry. `situation` is the situation slice, not the full text."""
    return {
        "code": code.upper(),
        "date": day.isoformat(),
        "excerpt": " ".join(situation.split())[:EXCERPT_CHARS],
        "axes": axes,
        "companies": company_names(situation),
        "similarity": round(similarity, 4),
        "nearest": nearest,
        "passed": passed,
    }


def record(code: str, entry: Dict) -> Path:
    """Write one entry, REPLACING any entry for the same date, then prune."""
    entries = [e for e in load(code) if e.get("date") != entry["date"]]
    entries.append(entry)
    return write_all(code, entries)


def write_all(code: str, entries: Sequence[Dict]) -> Path:
    """Sort, prune to PRUNE_DAYS from the newest entry, and write."""
    ordered = sorted(entries, key=lambda e: e.get("date", ""))
    if ordered:
        newest = _as_date(ordered[-1]["date"], date.min)
        cutoff = newest - timedelta(days=PRUNE_DAYS)
        ordered = [e for e in ordered if _as_date(e["date"], newest) >= cutoff]

    NOVELTY_DIR.mkdir(parents=True, exist_ok=True)
    p = path_for(code)
    p.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


# ----------------------------
# Company-name reuse (§5d)
# ----------------------------
def company_names(text: str) -> List[str]:
    """Candidate company names in a situation slice.

    §5d says "the corpus writes company names in ALL CAPS" -- true of the real
    DECA corpus, and only PARTLY true of our own output, which mixes ALL CAPS
    with Title Case ("ClearSky Financial Services", "TechTrends"). Matching only
    all-caps would therefore miss most of our own names, so both shapes are
    collected, and a Title-Case phrase has to RECUR to count -- a company name
    is mentioned repeatedly; a person's name mentioned once is not a brand.
    """
    names = {
        m.strip()
        for m in _ALLCAPS.findall(text)
        if m.strip() and not _is_structural(m)
    }

    counts = Counter(m.strip() for m in _TITLECASE.findall(text) if " " in m)
    names.update(
        name for name, n in counts.items()
        if n >= 2 and not _is_structural(name) and len(name) > 6
    )
    return sorted(names)


def _is_structural(name: str) -> bool:
    words = name.upper().replace("-", " ").split()
    return not words or all(w in _NOT_A_NAME for w in words)


def reused_company(code: str, day: date, situation: str) -> List[str]:
    """Company names this event already used within COMPANY_DAYS. [] = novel."""
    current = set(company_names(situation))
    if not current:
        return []
    seen: set = set()
    for entry in recent(code, day, days=COMPANY_DAYS):
        seen.update(entry.get("companies") or [])
    return sorted(current & seen)


# ----------------------------
# --rebuild-index (§6b)
# ----------------------------
def rebuild(archive_dir: Path, codes: Sequence[str]) -> Dict[str, int]:
    """Regenerate every novelty file from the archive. Zero model calls.

    Reads the archived roleplay JSON rather than the raw generations, because the
    archive is the permanent artifact and the raw .txt files are not committed.
    """
    per_code: Dict[str, List[Dict]] = {c.upper(): [] for c in codes}

    for day_file in sorted(archive_dir.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/day.json")):
        day_dir = day_file.parent
        try:
            day = json.loads(day_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        day_key = day.get("date", "")
        if not day_key:
            continue

        for code in day.get("events", []):
            rp_path = day_dir / f"{code.lower()}.json"
            if not rp_path.is_file():
                continue
            try:
                roleplay = json.loads(rp_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            meta = roleplay.get("meta") or {}
            per_code.setdefault(code.upper(), []).append(
                entry_for(
                    code,
                    _as_date(day_key, date.min),
                    situation=roleplay.get("situation", ""),
                    axes=(meta.get("generator") or {}).get("axes", {}),
                    passed=bool((meta.get("gate") or {}).get("passed")),
                )
            )

    written: Dict[str, int] = {}
    for code, entries in per_code.items():
        if entries:
            write_all(code, entries)
            written[code] = len(entries)
        elif path_for(code).is_file():
            # An event with nothing in the archive gets an empty file rather than
            # a stale one -- the index must not outlive what it derives from.
            write_all(code, [])
            written[code] = 0
    return written
