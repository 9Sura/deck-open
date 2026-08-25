"""Plan 03 §5d, prevention half -- deterministic seed axes. No model calls.

The existing originality guard compares a generation against ONE sampled
exemplar and does nothing for day N vs. day N-1. Seed axes attack that from the
other side: before the model writes anything, it is handed a different industry,
company stage, business function and dilemma archetype than the ones this event
used recently.

Deterministic matters twice: a re-run of a day reproduces its axes (so
`fill_buffer.py --dry-run` shows the real plan), and consecutive days differ.

A CORRECTION to the plan's own arithmetic, recorded rather than propagated:
§5d describes "a distinct coprime stride per axis" and claims a period of
40x8x10x12 = 38,400 days. That is not what a per-axis stride gives you. With
index_i = (seed + ordinal * stride_i) mod n_i, the tuple repeats with period
lcm(n_1..n_4) -- for these axis lengths that is 120 days, not 38,400. Rather
than ship a number that does not hold, this module derives each axis index from
an independent SHA-256 of (event_code, date, axis), which makes the axes
independent draws, and then enforces the property the stride was there to
provide -- and enforces it more strongly:

    NO AXIS VALUE REPEATS FOR AN EVENT WITHIN THE RECENCY WINDOW.

Consecutive days differing is then a special case of that rule, guaranteed by
construction rather than by a stride argument. Yesterday is always inside the
window.

SHA-256 rather than hash(): PYTHONHASHSEED randomizes str hashing per process,
so hash() would silently break "a re-run reproduces its axes."
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Dict, List, Sequence

BASE_DIR = Path(__file__).resolve().parents[2]
SEED_AXES_PATH = BASE_DIR / "data" / "seed_axes.json"
SEED_AXES_EVENTS_PATH = BASE_DIR / "data" / "seed_axes_events.json"

# 14 days, matching §5d's "stepped past anything used for that event in 14 days."
RECENCY_DAYS = 14

_AXES_CACHE: Dict[str, List[str]] | None = None
_EVENT_AXES_CACHE: Dict[str, Dict[str, List[str]]] | None = None
_EVENT_FRAMES_CACHE: Dict[str, Dict[str, str]] | None = None

# How `as_context` phrases each axis when an event supplies no `_frames`. These
# are the sentences every landed shelf was authored against, moved out of the
# function body unchanged so that overriding them is a data edit rather than a
# code fork.
#
# `question_shape`'s frame is the ONE that has moved since (plan 06 §4). It read
# "Shape the judge's questions to {}." over values that each began "ask ...", so
# frame and value together handed the author a finished question -- and two cases
# drawing "ask why something in the decision matters, and to whom" both wrote every
# judge question as "Why does X matter, and to whom?". The values are now subjects
# rather than questions and the frame states the subject rather than commanding a
# shape, so the author still has to write the question. A frame override in
# `seed_axes_events.json` must keep that split: it may restate WHAT is probed, never
# supply the interrogative.
DEFAULT_FRAMES: Dict[str, str] = {
    "industry": "Set the scenario in a {}.",
    "company_stage": "The company is {}.",
    "business_function": "The decision turns on {}.",
    "dilemma_archetype": "Build the dilemma around {}.",
    "question_shape": "The judge's questions probe {}.",
    "_closing": (
        "Invent the company name, the people, and the figures yourself. Do not mention "
        "this brief, name these constraints, or label them in the roleplay."
    ),
}


def _load_global_axes() -> Dict[str, List[str]]:
    global _AXES_CACHE
    if _AXES_CACHE is None:
        raw = json.loads(SEED_AXES_PATH.read_text(encoding="utf-8"))
        _AXES_CACHE = {k: v for k, v in raw.items() if not k.startswith("_") and v}
    return _AXES_CACHE


def _load_event_axes() -> Dict[str, Dict[str, List[str]]]:
    """Per-event axis overrides. Missing file means "no event is scoped"."""
    global _EVENT_AXES_CACHE
    if _EVENT_AXES_CACHE is None:
        if SEED_AXES_EVENTS_PATH.exists():
            raw = json.loads(SEED_AXES_EVENTS_PATH.read_text(encoding="utf-8"))
            _EVENT_AXES_CACHE = {
                code: {a: v for a, v in axes.items() if not a.startswith("_") and v}
                for code, axes in raw.items()
                if not code.startswith("_") and isinstance(axes, dict)
            }
        else:
            _EVENT_AXES_CACHE = {}
    return _EVENT_AXES_CACHE


def _load_event_frames() -> Dict[str, Dict[str, str]]:
    """Per-event sentence templates for `as_context`, from each entry's `_frames`.

    Read from the RAW file rather than through `_load_event_axes`, which drops
    every `_`-prefixed key -- that filter is what keeps `_frames` out of the axis
    pools, and it has to stay.
    """
    global _EVENT_FRAMES_CACHE
    if _EVENT_FRAMES_CACHE is None:
        _EVENT_FRAMES_CACHE = {}
        if SEED_AXES_EVENTS_PATH.exists():
            raw = json.loads(SEED_AXES_EVENTS_PATH.read_text(encoding="utf-8"))
            for code, entry in raw.items():
                if code.startswith("_") or not isinstance(entry, dict):
                    continue
                frames = entry.get("_frames")
                if isinstance(frames, dict) and frames:
                    _EVENT_FRAMES_CACHE[code] = dict(frames)
    return _EVENT_FRAMES_CACHE


def load_frames(event_code: str | None = None) -> Dict[str, str]:
    """The sentence templates for an event. Defaults where the event names none."""
    return {**DEFAULT_FRAMES, **_load_event_frames().get(event_code or "", {})}


def load_axes(event_code: str | None = None) -> Dict[str, List[str]]:
    """The axis pools for an event, keys beginning with '_' (comments) dropped.

    DECIDED 2026-08-17. The `industry` pool in `seed_axes.json` is global and
    event-agnostic, which is correct for an event named after a business FUNCTION
    and wrong for one named after an INDUSTRY -- measured, HLM matched hotels on
    2 of 30 and AAM apparel on 4 of 30, while MCS matched marketing on 0 of 30
    and was right to, marketing communications being a function.

    `seed_axes_events.json` overrides an axis for the nine remaining tranche-1
    events whose `event_name` states an industry. THIS IS ADDITIVE BY
    CONSTRUCTION: an event with no entry there gets the global dict itself, with
    the same pools in the same order and therefore the same modulus in
    `_index_for_key` -- so every unscoped event draws exactly what it drew
    before, and units 1-16 remain reproducible. An override REPLACES that axis's
    pool rather than filtering it, so the pool size changes and a scoped event's
    draw changes wholesale. That is the point, and it is why the four LANDED
    shelves in this class (AAM, ASM, FMS, HLM) are not listed: re-drawing them
    would destroy banked work to fix a defect that is recorded.
    """
    base = _load_global_axes()
    override = _load_event_axes().get(event_code or "")
    if not override:
        return base
    return {**base, **{a: v for a, v in override.items() if a in base}}


def check_axis_membership(event_code: str, axes: Dict[str, str]) -> List[str]:
    """Is every recorded axis value one of THIS event's own axis values?

    Plan 04 §3.2 step 4. Deterministic and free, and deliberately NOT a semantic
    domain classifier -- whether the SITUATION honours the axis it was handed is a
    separate and more expensive question that is not asked anywhere (it is in
    `icdc_gate.UNVERIFIED`). What this catches is a candidate whose recorded draw
    could not have come from this event's pools at all: a hand-edited work order, a
    stale axes cache, or an axis pool that moved under a batch mid-flight.

    Resolution goes through `load_axes(event_code)`, which is the SAME merge
    `pick`/`pick_for_bank` draw from, and it has to. `seed_axes_events.json` carries
    only `industry` and `business_function` per event; `company_stage`,
    `dilemma_archetype` and `question_shape` are global by design and live in
    `seed_axes.json`. Checked against the per-event file alone, three of the five
    axes would read as off-list on all 28 events.
    """
    pools = load_axes(event_code)
    issues: List[str] = []
    for axis, value in sorted((axes or {}).items()):
        pool = pools.get(axis)
        if pool is None:
            issues.append(f"axes: '{axis}' is not an axis this event draws from")
        elif value not in pool:
            issues.append(
                f"axes: {axis}={value!r} is not one of {event_code}'s "
                f"{len(pool)} {axis} values"
            )
    missing = [a for a in pools if a not in (axes or {})]
    if missing:
        issues.append(f"axes: no value recorded for {', '.join(sorted(missing))}")
    return issues


def axes_content_hash() -> str:
    """sha256 over BOTH axes files, for `meta.generator.axesHash` (plan 04 §3.2 step 5).

    `check_axis_membership` reads MUTABLE data. Widening a list or correcting an
    entry silently changes the verdict on roleplays banked earlier, in both
    directions, so a banked file records the axes it was actually drawn from.

    BOTH files, for the same reason the check reads both: pinning
    `seed_axes_events.json` alone leaves the global pools unpinned, and
    `question_shape` -- global, and the newest axis -- is the one most likely to be
    edited next.

    IT OVER-TRIGGERS, ON PURPOSE. `seed_axes_events.json` also holds `_frames`, the
    per-event sentence templates (plan 05 §5.2), so editing a FRAME moves the hash
    even though the axis universe did not change. The alternative is parsing the
    file into a canonical subset and hashing that, which makes the pin depend on a
    second piece of code being right about what counts. A moved hash means "the
    axes data moved", never "an axis value moved" -- read the diff, not the hash.
    """
    h = hashlib.sha256()
    for path in (SEED_AXES_PATH, SEED_AXES_EVENTS_PATH):
        h.update(path.name.encode())
        h.update(path.read_bytes() if path.exists() else b"")
    return h.hexdigest()


def _index_for_key(key: str, axis: str, size: int) -> int:
    """SHA-256 of (key, axis) -> an index into that axis's pool.

    `key` is whatever makes a generation unique: `<CODE>:<date>` for a daily run,
    `<CODE>:<BANK_ID>` for a bank entry (§6e). Same construction either way --
    only what identifies the generation changes.
    """
    digest = hashlib.sha256(f"{key}:{axis}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % size


def _index(event_code: str, day: date, axis: str, size: int) -> int:
    return _index_for_key(f"{event_code}:{day.isoformat()}", axis, size)


def pick(event_code: str, day: date, *, recent: Sequence[Dict] = ()) -> Dict[str, str]:
    """Choose one value per axis for (event, day), stepping past recent reuse.

    `recent` is this event's novelty entries; each may carry an `axes` dict. Only
    entries inside RECENCY_DAYS of `day` constrain the choice, so a sparse or
    empty index simply means nothing is excluded -- the first batch is never
    blocked by an index that does not exist yet.
    """
    axes = load_axes(event_code)
    blocked = _blocked_values(day, recent)

    chosen: Dict[str, str] = {}
    for axis, values in axes.items():
        start = _index(event_code, day, axis, len(values))
        used = blocked.get(axis, set())
        # Step forward until the value is unused, or all the way around -- a pool
        # smaller than the window would otherwise loop forever. Falling back to
        # the hashed pick is honest: the constraint cannot be met, so it is not
        # pretended to be.
        for offset in range(len(values)):
            candidate = values[(start + offset) % len(values)]
            if candidate not in used:
                chosen[axis] = candidate
                break
        else:
            chosen[axis] = values[start]
    return chosen


def pick_for_bank(
    event_code: str, bank_id: str, *, shelf_axes: Sequence[Dict[str, str]] = ()
) -> Dict[str, str]:
    """Choose one value per axis for a BANK entry, spread across the whole shelf.

    Plan 03 §4e: under D10 the recency WINDOW disappears. A bank entry has no date
    to be recent relative to, so the comparison set is the entire shelf for this
    event and the rule becomes "spread across the shelf by construction."

    Where the daily `pick()` steps past values used in the last 14 days and falls
    back to the raw hashed pick when everything is blocked, this steps past values
    used ANYWHERE in the shelf and falls back to the LEAST-USED value. That
    fallback is not decoration -- it is the common case. `company_stage` has 8
    values against a depth-30 shelf, so from the 9th entry onward every value is
    already used and a raw-hash fallback would re-cluster on whatever the hash
    happened to like. Least-used keeps the pool even instead.

    Deterministic on `(event_code, bank_id)`, so re-resolving a work order
    reproduces it -- SHA-256 rather than hash() for the reason in the module
    docstring. Note the ordering dependency this creates and does not hide:
    `shelf_axes` is what is ALREADY banked, so authoring HRM-0007 before HRM-0006
    gives each a different draw than the reverse. That is correct (the shelf is
    what it is at the moment you extend it) but it means the axes are reproducible
    per shelf STATE, not per bank id alone.
    """
    axes = load_axes(event_code)
    used: Dict[str, Counter] = {}
    for entry in shelf_axes:
        for axis, value in (entry or {}).items():
            used.setdefault(axis, Counter())[value] += 1

    key = f"{event_code}:{bank_id}"
    chosen: Dict[str, str] = {}
    for axis, values in axes.items():
        start = _index_for_key(key, axis, len(values))
        counts = used.get(axis, Counter())

        rotated = [values[(start + offset) % len(values)] for offset in range(len(values))]
        unused = next((v for v in rotated if v not in counts), None)
        if unused is not None:
            chosen[axis] = unused
            continue
        # Every value is spoken for. Take the least-used, and let the hash-rotated
        # order break ties so the choice stays deterministic rather than
        # dict-insertion-ordered.
        chosen[axis] = min(rotated, key=lambda v: counts[v])
    return chosen


def _blocked_values(day: date, recent: Sequence[Dict]) -> Dict[str, set]:
    blocked: Dict[str, set] = {}
    for entry in recent:
        entry_day = entry.get("date")
        if not entry_day:
            continue
        try:
            delta = abs((day - date.fromisoformat(entry_day)).days)
        except ValueError:
            continue
        if delta > RECENCY_DAYS:
            continue
        for axis, value in (entry.get("axes") or {}).items():
            blocked.setdefault(axis, set()).add(value)
    return blocked


def as_context(axes: Dict[str, str], event_code: str | None = None) -> str:
    """The axes as one `ADDITIONAL CONTEXT / CONSTRAINTS` line.

    Phrased as a brief, not a checklist: these seed the scenario, and naming them
    as requirements invites the model to write them back out as labels. Rides
    build_user_message's existing `extra_context` -- no signature change (§5d).

    `event_code` selects the sentence templates. It is OPTIONAL and defaults to
    the corporate ones every landed shelf was authored against, so an event with
    no `_frames` entry produces a byte-identical line whether or not the code is
    passed. PFL is the one event that supplies its own: its axes are a household
    situation and a personal-finance function, and rendering those through "The
    company is ..." states a company the scenario does not have (plan 05 §5.2
    step 3). The templates are DATA, in `seed_axes_events.json`, because a second
    hard-coded set of sentences is how the first one got copied into a slice tool.

    THE AXIS TUPLE BELOW IS THE WHOLE OF WHAT REACHES THE PROMPT. An axis that is
    picked, recorded in `meta.generator.axes` and left out of it is invisible to
    the author -- so a new axis is three edits, not one: a pool in
    `seed_axes.json` (an event-only key is silently dropped by `load_axes`), a
    `DEFAULT_FRAMES` sentence, and a place in this tuple. `question_shape`
    (plan 05 §6) was added on exactly that path.
    """
    if not axes:
        return ""
    frames = load_frames(event_code)
    parts = [
        frames[axis].format(axes[axis])
        for axis in (
            "industry",
            "company_stage",
            "business_function",
            "dilemma_archetype",
            "question_shape",
        )
        if axis in axes and axis in frames
    ]
    parts.append(frames["_closing"])
    return " ".join(p for p in parts if p)
