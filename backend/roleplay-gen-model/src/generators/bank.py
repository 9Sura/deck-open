"""The roleplay bank -- shelf layout, identity, and shelf-wide novelty (plan 03 §4b).

NO MODEL CALLS, EVER. This module is the one place that knows where a banked
roleplay lives and what its id is, because TWO drivers need that answer:
`fill_bank.py` (§6e) writes the shelf and `deal_days.py` (§6d, build-order step
13) reads it. They were always going to duplicate this, and a dealer that
disagreed with the author about where a file lives is a silent 404 on a surface
students read.

CANONICAL HOME (decided at build-order step 10, 2026-08-05)

    frontend/public/roleplays/bank/<CODE>/<CODE>-NNNN.json

and NOWHERE else. There is deliberately no `backend/.../data/bank/`. §6c's note
put the choice plainly: two paths holding the same text is exactly the
duplication D9 exists to prevent, and unlike the question bank -- whose canonical
home is backend tooling that predates the frontend -- the roleplay bank has no
prior backend home to mirror from. `data/novelty/` stays the sole backend-side
derived cache, and it now serves only the Ollama day path.

IDENTITY: `<CODE>-<NNNN>`, ASSIGNED BY IDENTITY AND NEVER RENUMBERED.
The question bank's §10-4 rule, adopted for the same reason -- the id is a join
key. Frontend plan 11's phase-D difficulty tap aggregates per roleplay, and
`day.json` stores refs rather than copies (§4b), so renumbering a shelf would
repoint every day that had already been dealt. `next_id` therefore takes the
maximum ordinal ever used rather than a count: deleting HRM-0003 leaves a hole,
and the hole stays.

A BANK ENTRY IS DATE-FREE. The dealer stamps the date when it deals (D11).
`parse_roleplay(..., bank_id=...)` is what produces that shape.

SHELF-WIDE NOVELTY (§4e) -- and one deviation from the plan, recorded rather than
quietly taken. §4e says novelty's window constants become "shelf-wide, all-pairs,
rather than time-windowed", keeping `novelty.py`'s per-event file layout. The
layout survives for the DAY path, which still needs it. For the bank it does not:
`data/novelty/<EVENT>.json` exists because the archive is large, append-only and
time-windowed, so a capped 800-char excerpt is a cheap stand-in for text you
would otherwise re-read. A shelf is finite, small, and already on disk -- so the
shelf IS its own index, compared all-pairs at full length, and a second copy of
it would be a cache that can go stale against the thing it caches.

    CONSEQUENCE, and it matters for build-order step 7: bank similarity is
    computed on FULL situations, while `_cross_day_similarity` compares against a
    TRUNCATED 800-char excerpt. The two numbers are NOT interchangeable. The
    threshold calibrated from tranche 1 is a BANK threshold; do not carry it to
    the day path or back.

The extraction code is reused rather than reimplemented: `novelty.company_names`
carries the hard-won rule that our own output mixes ALL CAPS with Title Case and
that a Title-Case phrase must RECUR to count as a brand.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import icdc_gate as gate  # noqa: E402
import novelty  # noqa: E402
import parse_roleplay as pr  # noqa: E402

BANK_DIRNAME = "bank"
MANIFEST_NAME = "manifest.json"

_BANK_ID = re.compile(r"^([A-Z]+)-(\d{4,})$")


# ----------------------------
# Layout
# ----------------------------
def bank_dir(out_dir: Path) -> Path:
    return out_dir / BANK_DIRNAME


def shelf_dir(out_dir: Path, code: str) -> Path:
    return bank_dir(out_dir) / code.upper()


def entry_path(out_dir: Path, bank_id: str) -> Path:
    m = _BANK_ID.match(bank_id)
    if not m:
        raise ValueError(f"not a bank id: {bank_id!r} (want <CODE>-NNNN)")
    return shelf_dir(out_dir, m.group(1)) / f"{bank_id}.json"


def format_id(code: str, ordinal: int) -> str:
    return f"{code.upper()}-{ordinal:04d}"


def ordinal_of(bank_id: str) -> int:
    m = _BANK_ID.match(bank_id)
    if not m:
        raise ValueError(f"not a bank id: {bank_id!r}")
    return int(m.group(2))


# ----------------------------
# Reading a shelf
# ----------------------------
def load_shelf(out_dir: Path, code: str) -> List[Dict]:
    """Every banked roleplay for one event, ordered by id. [] when the shelf is empty."""
    d = shelf_dir(out_dir, code)
    if not d.is_dir():
        return []
    entries: List[Dict] = []
    for p in sorted(d.glob(f"{code.upper()}-*.json")):
        try:
            entry = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Unlike a derived cache, an unreadable BANK file is a real loss: it is
            # the only copy of that roleplay. Never silently skip it -- a shelf
            # that reads short would hand the same ordinal out twice.
            raise RuntimeError(f"corrupt bank entry: {p}")
        entries.append(entry)
    return sorted(entries, key=lambda e: ordinal_of(e["id"]))


def shelf_depth(out_dir: Path, code: str) -> int:
    d = shelf_dir(out_dir, code)
    return len(list(d.glob(f"{code.upper()}-*.json"))) if d.is_dir() else 0


def highest_on_disk(out_dir: Path, code: str) -> int:
    """The largest ordinal this shelf currently HOLDS. 0 for an empty shelf."""
    d = shelf_dir(out_dir, code)
    highest = 0
    if d.is_dir():
        for p in d.glob(f"{code.upper()}-*.json"):
            try:
                highest = max(highest, ordinal_of(p.stem))
            except ValueError:
                continue
    return highest


def highest_ever(out_dir: Path, code: str) -> int:
    """The largest ordinal this shelf has EVER held -- disk, or the manifest's memory.

    DISK ALONE IS NOT A RECORD OF WHAT HAS BEEN USED, and that is the whole reason
    this function exists. Deleting an INTERIOR entry leaves a hole and the max is
    unchanged, so disk answers correctly. Deleting the HIGHEST entry moves the max
    DOWN, and the next id handed out is the one just retired -- which is exactly
    what plan 06 section 8's discard did to BLTDM-0035, the shelf's high-water mark
    and a member of the discard set. The audit grades roleplays by id, `day.json`
    stores refs rather than copies, and the difficulty tap aggregates per roleplay,
    so a reissued id silently joins new work to an old record.

    The manifest carries the memory (`highestOrdinal`) because deletion is what
    destroys the evidence on disk -- there is nothing left to recompute FROM. Taking
    the max of the two keeps it correct when the manifest is missing, stale, or
    behind a shelf that has since grown.
    """
    return max(highest_on_disk(out_dir, code), recorded_high_water(out_dir).get(code.upper(), 0))


def next_id(out_dir: Path, code: str, *, offset: int = 0) -> str:
    """The next unused bank id for this event.

    From the HIGHEST ORDINAL EVER USED, not the count and not the max on disk --
    ids are never renumbered and never reused, so a gap left by a deleted entry
    stays a gap even when the deleted entry was the last one. `offset` reserves
    ids for a batch being planned before any of it is written.
    """
    return format_id(code, highest_ever(out_dir, code) + 1 + offset)


def write_entry(out_dir: Path, entry: Dict) -> Path:
    p = entry_path(out_dir, entry["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        # Ids are never reused. Overwriting one would rewrite a roleplay that days
        # already dealt are pointing at (D11: a dealt day is immutable).
        raise RuntimeError(f"refusing to overwrite an existing bank entry: {p}")
    p.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


# ----------------------------
# Shelf-wide novelty (§4e)
# ----------------------------
def shelf_axes(shelf: Sequence[Dict]) -> List[Dict[str, str]]:
    """The seed axes already spent on this shelf, for `seed_axes.pick_for_bank`."""
    return [((e.get("meta") or {}).get("generator") or {}).get("axes") or {} for e in shelf]


def shelf_similarity(situation: str, shelf: Sequence[Dict]) -> Tuple[float, Optional[str]]:
    """Max situation-vs-situation similarity across the whole shelf, all pairs.

    Full text on both sides -- see the module docstring on why this is not the
    same measurement as the day path's truncated-excerpt comparison.
    """
    best, nearest = 0.0, None
    for entry in shelf:
        other = entry.get("situation") or ""
        if not other:
            continue
        score = difflib.SequenceMatcher(None, situation, other).ratio()
        if score > best:
            best, nearest = score, entry.get("id")
    return best, nearest


# A corporate designator -- the last word of a name like "GreenTech Solutions" or
# "Bright Future Inc". This list is what makes company reuse SAFE TO ENFORCE.
#
# MEASURED, not assumed (2026-08-05, on the 7 post-K3-fix bake-off situations).
# `novelty.company_names` alone extracted 21 names of which 7 were companies --
# ~33% precision. The other 14 were people ("Sarah Thompson"), job titles ("Vice
# President", "Marketing Manager"), org units ("Finance Department") and bare
# acronyms ("CRM", "ROI"). That is fine for the DAY path, where reuse is logged
# and never rejects. It is NOT fine here: "Vice President" recurs in almost every
# roleplay, so an enforcing rule built on the raw extractor would collide on the
# second entry and make every shelf UN-FILLABLE PAST DEPTH 1.
#
# Requiring a designator scored 6 of 6 true companies with 0 false positives on
# that sample. Note the deliberate error direction: PBM's company was missed
# entirely by the extractor, and a MISS IS SAFE HERE (it declines to block) while
# a false positive discards a good roleplay. Precision over recall, on purpose.
#
# RECALL IS GENUINELY POOR AND THAT IS ACCEPTED, NOT UNNOTICED. Across the 8
# probe roleplays this finds a brand for only 5; "Bright Fields Greenhouse &
# Nursery, LLC" defeats the underlying Title-Case regex (a comma before the
# designator, and more than four tokens). So the shelf-wide company rule catches
# SOME collisions, never all, and must not be described as guaranteeing distinct
# company names. Tranche 1 produces ~840 real situations -- the first corpus big
# enough to tune recall against. Do it there rather than guessing here.
_CORPORATE_DESIGNATORS = frozenset("""
    inc inc. llc llp ltd ltd. co co. corp corp. corporation company incorporated
    solutions services systems technologies technology industries enterprises
    group holdings partners associates ventures capital financial bank brands
    labs laboratories works manufacturing distributors distribution supply
    logistics foods foodservice entertainment media health healthcare hospitality
    motors farms bakery brewery outfitters apparel goods retail markets market
    consulting advisors agency studios networks communications international
    global worldwide
""".split())


def corporate_names(text: str) -> List[str]:
    """The high-precision subset of `novelty.company_names` -- names shaped like a
    brand rather than like a person or a job title.

    A name qualifies when it ends in a corporate designator, or is a multi-word
    ALL-CAPS phrase (how the DECA corpus itself writes company names). A bare
    acronym is excluded: "CRM" and "ROI" are vocabulary, not brands.
    """
    out: List[str] = []
    for name in novelty.company_names(text):
        words = name.replace(",", " ").split()
        # A DESIGNATOR ALONE IS NOT A NAME. Measured on the probe: "Bright Fields
        # Greenhouse & Nursery, LLC" has a comma before its designator, which
        # breaks the Title-Case match, so the all-caps pass picked up a bare
        # "LLC" -- which then looked corporate and would have collided with every
        # other roleplay containing an LLC, discarding good work. Two words
        # minimum, always.
        if len(words) < 2:
            continue
        if words[-1].lower().strip(".") in _CORPORATE_DESIGNATORS:
            out.append(name)
        elif all(w.isupper() for w in words if w.isalpha()):
            out.append(name)
    return sorted(set(out))


def shelf_companies(shelf: Sequence[Dict], *, strict: bool = True) -> Dict[str, str]:
    """Company name -> the bank id that already used it, across the whole shelf."""
    extract = corporate_names if strict else novelty.company_names
    seen: Dict[str, str] = {}
    for entry in shelf:
        for name in extract(entry.get("situation") or ""):
            seen.setdefault(name, entry.get("id", "?"))
    return seen


def reused_companies(
    situation: str, shelf: Sequence[Dict], *, strict: bool = True
) -> Dict[str, str]:
    """Names in `situation` already used anywhere in the shelf. {} = novel.

    §4e's rule is absolute -- "no reuse ANYWHERE in the shelf" -- and unlike
    similarity it is an exact match rather than a calibrated threshold, which is
    why `fill_bank.py` enforces this one while similarity stays log-only.

    `strict=True` (the default, and what the enforcing path uses) runs on
    `corporate_names`. `strict=False` runs on the raw extractor and is the
    ADVISORY read: it surfaces repeated people and repeated job titles, which are
    worth a human's attention across a shelf but must never auto-discard.
    """
    extract = corporate_names if strict else novelty.company_names
    seen = shelf_companies(shelf, strict=strict)
    return {name: seen[name] for name in extract(situation) if name in seen}


# ----------------------------
# Manifest
# ----------------------------
def manifest_path(out_dir: Path) -> Path:
    return bank_dir(out_dir) / MANIFEST_NAME


def read_manifest(out_dir: Path) -> Dict:
    """The manifest as it stands, or `{}` if there is not one yet or it is unreadable.

    Never raises: the manifest is a derived artifact everywhere except
    `highestOrdinal`, so a missing or corrupt one must not stop a bank write. The
    one remembered field degrades to the disk maximum, which is the pre-fix
    behaviour rather than a new failure mode.
    """
    p = manifest_path(out_dir)
    if not p.is_file():
        return {}
    try:
        loaded = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def recorded_high_water(out_dir: Path) -> Dict[str, int]:
    """`{CODE: highest ordinal ever used}` as the manifest remembers it.

    Tolerates every shape a hand-edit can leave behind -- a missing block, a
    non-mapping, a non-integer, a negative -- by dropping just that entry. A shelf
    that drops out falls back to its disk maximum in `highest_ever`.
    """
    block = read_manifest(out_dir).get("highestOrdinal")
    if not isinstance(block, dict):
        return {}
    out: Dict[str, int] = {}
    for code, value in block.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            continue
        out[str(code).upper()] = value
    return out


def build_manifest(out_dir: Path, codes: Sequence[str]) -> Dict:
    """Derived wholly from the shelves on disk -- never incrementally updated,
    WITH ONE DELIBERATE EXCEPTION named below.

    A counter that is written alongside the thing it counts drifts the first time
    a write half-fails. Recomputing is cheap and cannot disagree with reality.

    `highestOrdinal` IS THE EXCEPTION, and it has to be, because it is the one
    fact about a shelf that DELETION DESTROYS. Every other field here answers "what
    is on disk now" and can be recomputed from disk forever. `highestOrdinal`
    answers "what has this shelf ever held", and once the highest entry is deleted
    there is nothing on disk left to recompute it from -- which is how plan 06
    section 8's discard of BLTDM-0035 handed 0035 straight back out as the next id
    (see `highest_ever`). It is therefore MONOTONIC: every rebuild takes the max of
    what disk shows and what the manifest already remembered, so it survives a
    deletion and can never move backwards. That also bounds the drift the docstring
    above warns about -- a half-failed write can leave this field too LOW, never too
    high, and the next successful write repairs it.
    """
    shelves = {code: shelf_depth(out_dir, code) for code in codes}
    # Read ONCE, before anything is written: `highestOrdinal` is built from the
    # manifest this call is about to replace, so re-reading it per shelf would be
    # 28 reads of a file whose content cannot change mid-build.
    remembered = recorded_high_water(out_dir)
    present = {c: n for c, n in shelves.items() if n}
    authors = sorted({
        ((e.get("meta") or {}).get("generator") or {}).get("model", "")
        for code in present
        for e in load_shelf(out_dir, code)
    } - {""})
    return {
        "schemaVersion": pr.SCHEMA_VERSION,
        "gateVersion": gate.GATE_VERSION,
        "authoredBy": authors,
        "totals": {"events": len(present), "roleplays": sum(shelves.values())},
        # The number that can actually run out: a day needs ONE roleplay from
        # EVERY event, so the runway is the THINNEST shelf, not the total (§7).
        "thinnestShelf": min(shelves.values()) if shelves else 0,
        "shelves": {c: shelves[c] for c in sorted(shelves)},
        # MONOTONIC, and the only remembered field here -- see this function's
        # docstring. Recorded for every code passed in, including shelves that are
        # empty today, because an empty shelf that once held entries still owes
        # their ids a hole. A 0 means "has never held one", which is why the
        # comprehension keeps zeros rather than filtering them out the way
        # `present` does above.
        "highestOrdinal": {
            c: max(highest_on_disk(out_dir, c), remembered.get(c.upper(), 0))
            for c in sorted(shelves)
        },
    }


def write_manifest(out_dir: Path, codes: Sequence[str]) -> Dict:
    manifest = build_manifest(out_dir, codes)
    p = manifest_path(out_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
