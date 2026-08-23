#!/usr/bin/env python3
"""Plan 03 D5 -- deterministic text -> JSON parser for generated roleplays.

NO MODEL CALLS, EVER. D5 keeps the model emitting plain text so
`validate_roleplay()` stays byte-untouched (its verbatim-PI substring check and
its difflib situation slice both operate on text); this module is the other half
of that decision -- everything the archive and the browser see is produced here,
deterministically, from that text.

The output shape is `frontend/lib/roleplay/types.ts` (frontend plan 11 §2b), and
the two files must be changed together. The archive is PERMANENT: a field added
after the buffer fills means regenerating every day already on disk.

Since D10 this module produces TWO shapes from the same code path -- a dated DAY
entry (`date=`) and a date-free BANK entry (`bank_id=`). See `parse_roleplay`'s
docstring; the difference is two fields and it is deliberate. The frontend's
`loadRoleplay` learns to resolve a day's ref to a bank file at plan 11 phase E
(backend build-order step 14), so until then the bank is written and gated but
not yet served.

Four things about the real output that this parser exists to absorb -- all four
were found by reading `output/bake-off/icdc/no-example/*.txt`, not assumed:

  1. Judge questions carry NO heading. They are bare numbered lines trailing the
     JUDGE ROLE-PLAY CHARACTERIZATION prose. A naive section splitter files them
     under the characterization and the run surface loses its reveal step.
  2. The exhibit sits INSIDE the situation today, with prose on both sides. The
     K3 fix (build-order step 3) moves it out to its own section between
     PERFORMANCE INDICATORS and the situation. BOTH shapes parse here, and the
     exhibit is lifted out of whatever section it landed in either way -- so it
     is a first-class field before the prompt fix, not after it.
  3. CAREER CLUSTER is conditional. PFL is the sole event with
     `career_cluster: null` and none of its 10 corpus files carry the header
     (§3h). Absent field, never the string "General".
  4. The PARTICIPANT INSTRUCTIONS boilerplate is unreliable: it says "no time
     for judge questions" and then three judge questions follow. Timings come
     from the event config, never from that prose. Recorded as a defect below
     rather than papered over.

`meta` (frontend F10) keeps the model's self-report tail as structured metadata.
It is the model's own claim, only PARTIALLY falsifiable by Python, and it is
never rendered as roleplay text. Backend §5b said to strip it; summary 03
recommendation #4 revised that, and deciding it now is what stops a regeneration
of the whole archive later.

Usage:
    # one roleplay -> stdout. --pi-record is the driver's selection record for that
    # roleplay, [{area, pi, role}, ...]; without it the PIs have no provenance (D5).
    python parse_roleplay.py --text output/bake-off/icdc/no-example/hrm.txt \\
        --event HRM --date 2026-07-28 --pi-record hrm-pis.json --stdout

    # --fixtures is DISABLED (plan 05 D5/OQ5) -- the 7 day fixtures are regenerated
    # through the real pipeline at plan 05 §7 step 7, not rebuilt from here.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

BASE_DIR = Path(__file__).resolve().parents[2]          # backend/roleplay-gen-model
REPO_ROOT = BASE_DIR.parents[1]                          # repo root
EVENTS_CONFIG_PATH = BASE_DIR / "data" / "events.json"
DEFAULT_OUT = REPO_ROOT / "frontend" / "public" / "roleplays"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icdc_gate as gate  # noqa: E402  (path shim above)

# 2 = plan 05 D5: `performanceIndicators` is a list of {area, pi, role} objects and
# `instructionalArea` is the DECLARED area rather than a plurality label computed
# after the fact. A shape change, not an added field, so the number moves.
SCHEMA_VERSION = 2


# What `parse_roleplay` itself runs when a driver names nothing. Both are this
# module's own calls, a few lines apart: `check_icdc_shape` gates, and the F2/F5
# self-report cross-check is recorded and does NOT gate (03-plan §5c) -- which is
# why `icdc_gate.UNVERIFIED` says so beside it.
DEFAULT_GATE_CHECKS: Tuple[str, ...] = ("icdc_shape", "self_report")


class PIProvenanceError(ValueError):
    """An authored PI that is not in the selection record it was drawn from.

    Raised rather than defaulting `area` to "": the selection record is the ONLY
    source of a PI's instructional area -- 25.8% of corpus PIs are filed by DECA
    under more than one, so the mapping is unrecoverable from the string afterwards
    (plan 05 §3.2b) -- and a default would write fabricated provenance into the one
    field D5 exists to make auditable. It is the same argument that made OQ5
    regenerate the day fixtures instead of hand-migrating them.
    """


def _pi_key(pi: str) -> str:
    """Comparison key for joining an AUTHORED PI back onto the selected one.

    The exact string is tried first. This is the fallback, and it is cosmetic only
    -- case, whitespace and a trailing full stop -- because verbatim reproduction is
    already an acceptance criterion checked upstream (`validate_roleplay`), so the
    only differences that reach here are ones the driver already accepted.
    """
    return " ".join(pi.lower().split()).rstrip(".")


def _pi_objects(
    authored: Sequence[str], pi_items: Sequence[Dict[str, str]], code: str
) -> List[Dict[str, str]]:
    """Authored PI strings + the selection record -> D5's {area, pi, role} objects.

    The AUTHORED spelling is kept as `pi` (it is what a competitor reads); `area`
    and `role` come from the record. Order is the authored order, which the prompt
    asks to be the selected one -- core first, adjacent after (plan 05 §3.1 step 4).
    """
    exact = {it["pi"]: it for it in pi_items}
    loose = {_pi_key(it["pi"]): it for it in pi_items}
    out: List[Dict[str, str]] = []
    for pi in authored:
        rec = exact.get(pi) or loose.get(_pi_key(pi))
        if rec is None:
            raise PIProvenanceError(
                f"{code}: authored performance indicator is not in the selection "
                f"record, so its instructional area is unknown: {pi!r}. The record "
                f"holds {len(pi_items)} PI(s); an extra or reworded one has to be "
                "rejected, not filed under a guessed area."
            )
        out.append({"area": rec["area"], "pi": pi, "role": rec.get("role", "")})
    return out

# Section labels, exactly as generate_roleplay's prompt asks for them. CAREER
# CLUSTER and INSTRUCTIONAL AREA carry their value inline on the same line;
# everything else opens a block.
_INLINE_HEADERS: Tuple[str, ...] = ("CAREER CLUSTER", "INSTRUCTIONAL AREA")
_BLOCK_HEADERS: Tuple[str, ...] = (
    "PARTICIPANT INSTRUCTIONS",
    "21st CENTURY SKILLS",
    "PERFORMANCE INDICATORS",
    "EVENT SITUATION",
    "CASE STUDY SITUATION",
    "JUDGE ROLE-PLAY CHARACTERIZATION",
    # Not a DECA section: the authoring prompt's own quality checklist, which the
    # model sometimes copies into its answer (2 of the 7 bake-off outputs). It is
    # captured so it can be split off and DISCARDED -- never archived, never shown.
    "QUALITY BAR",
)

_BULLET = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s+")
_TABLE_RULE = re.compile(r"^[\s|:+-]*-[\s|:+-]*$")
_EXHIBIT_PREFIX = re.compile(r"^EXHIBIT\s*\d*\s*[:.–—-]?\s*", re.I)
# Matches BOTH namespaces on purpose: `F\d` is the live ICDC tier (F1-F8) and
# `K\d` is the retired ICDC+ tier, still present in the meta of every roleplay
# banked under gateVersion <= 4. A parser that recognised only the live ids would
# silently read every old artifact as "no knobs failed".
_KNOB = re.compile(r"^([FK]\d(?:\s*/\s*[FK]\d)*)\s*:")

# §2a note 4 / plan-11 OQ4 -- the boilerplate denies judge questions and then asks
# them. A content defect in the generator, recorded per-roleplay so it is countable
# when someone fixes the prompt.
_DENIES_QUESTIONS = (
    "no time for judge questions",
    "no judge question",
    "no questions will be asked",
    "there will be no judge questions",
    "no judge questions are included",
)


# ----------------------------
# Event config
# ----------------------------
def load_events() -> Dict[str, Dict]:
    return json.loads(EVENTS_CONFIG_PATH.read_text(encoding="utf-8"))["events"]


_FORMAT_RANK = {"series": 0, "principles": 1, "team": 2}


def event_order(events: Dict[str, Dict]) -> List[str]:
    """Canonical code order: format, then alphabetical.

    Mirrors `EVENTS` in frontend/lib/data/events.ts, which groups series ->
    principles -> team and runs alphabetically inside each group. `day.json`
    lists codes in this order so the board renders without re-sorting.
    """
    return sorted(
        events,
        key=lambda code: (_FORMAT_RANK.get(events[code].get("format", "series"), 9), code),
    )


# ----------------------------
# Text -> sections
# ----------------------------
def _paragraphs(lines: Sequence[str]) -> str:
    """Join wrapped lines into paragraphs; blank lines separate paragraphs.

    The model emits one line per paragraph today, but the two-pass expansion is
    free to hard-wrap, so this normalizes both into the same prose.
    """
    out: List[str] = []
    current: List[str] = []
    for raw in lines:
        line = raw.strip()
        if line:
            current.append(line)
        elif current:
            out.append(" ".join(current))
            current = []
    if current:
        out.append(" ".join(current))
    return "\n\n".join(out)


def _bullets(lines: Sequence[str]) -> List[str]:
    """Bullet/numbered list items, markers stripped, wrapped lines rejoined.

    ONE definition, in `icdc_gate`: `validate_roleplay` compares the 21st Century
    Skills block VERBATIM against events.json (plan 04 §2.3) while this stores it,
    and two copies could disagree about where an item begins -- which would bank a
    file under a different string than the one that passed the comparison.
    """
    return gate.list_items(lines)


def _exhibit_rows(lines: Sequence[str], heading_index: int) -> Tuple[List[str], int]:
    """Display rows under an exhibit heading, plus the index one past the last one.

    WHERE the block ends is `icdc_gate.exhibit_block`'s decision, not this
    module's -- the two used to answer that question differently and the gate's
    answer was looser, so K3 could be credited numerics that never reached a
    competitor's screen. This function only normalizes the rows the gate counted:
    trailing whitespace trimmed, list markers stripped, markdown table rules
    dropped. Pipes are LEFT IN so a renderer can split cells if it wants; nothing
    here parses cells (frontend plan 11 §2b).
    """
    raw, end = gate.exhibit_block(lines, heading_index)
    rows = [
        _BULLET.sub("", line.strip()).strip() if _BULLET.match(line.strip()) else line.strip()
        for line in raw
        if not _TABLE_RULE.match(line.strip())
    ]
    return rows, end


def _locate_exhibit(
    lines: Sequence[str], body: str, defects: List[str]
) -> Tuple[Optional[str], List[str], Optional[range]]:
    """(title, rows, line span) for the exhibit, or (None, [], None).

    WHICH block counts as the exhibit is decided by `icdc_gate.find_exhibit`, not
    re-derived here. The gate is the shipping bar; a parser that disagreed with it
    about what the exhibit is would publish a roleplay whose exhibit the gate
    never scored.
    """
    heading, _ = gate.find_exhibit(body)
    if heading is None:
        return None, [], None

    for i, line in enumerate(lines):
        if line.strip().rstrip(":").strip() != heading:
            continue
        rows, end = _exhibit_rows(lines, i)
        title = _EXHIBIT_PREFIX.sub("", heading).strip() or heading
        return title, rows, range(i, end)

    # The gate scored an exhibit this parser could not locate. Should be
    # unreachable -- both read the same lines -- so it is recorded rather than
    # swallowed: silent drift here publishes a roleplay whose exhibit the student
    # never sees but the gate credited.
    defects.append("exhibit-heading-mismatch")
    return None, [], None


def _split_sections(lines: Sequence[str], skip: Optional[range]) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """Split body lines into (block sections, inline header values).

    Anything before the first recognized header is dropped: the model opens with
    a title line or two ("HRM - ICDC Event", then the event name in caps) that no
    surface renders, and the event name is authoritative in events.json anyway.

    Repeated headers accumulate rather than overwrite -- the situation is one
    section even when the exhibit was lifted out of its middle.
    """
    blocks: Dict[str, List[str]] = {}
    inline: Dict[str, str] = {}
    current: Optional[str] = None

    for i, raw in enumerate(lines):
        if skip is not None and i in skip:
            continue
        matched = False

        for header in _INLINE_HEADERS:
            m = re.match(rf"^\s*{re.escape(header)}\s*:\s*(.*)$", raw, flags=re.I)
            if m:
                inline.setdefault(header, m.group(1).strip())
                current, matched = None, True
                break
        if matched:
            continue

        for header in _BLOCK_HEADERS:
            if re.match(rf"^\s*{re.escape(header)}\s*:?\s*$", raw, flags=re.I):
                blocks.setdefault(header, [])
                current, matched = header, True
                break
        if matched:
            continue

        if current is not None:
            blocks[current].append(raw)

    return blocks, inline


def _slice(text: str, start_label: str, end_label: str) -> str:
    """Text from one section header to the next, line-anchored.

    Same derivation `check_icdc_shape` applies when it is not handed slices, so
    `meta.situationWords` is the number the F7 verdict was reached on.
    """
    start = re.search(rf"^{re.escape(start_label)}\s*:?\s*$", text, re.M | re.I)
    if not start:
        return ""
    end = re.search(rf"^{re.escape(end_label)}\s*:?\s*$", text, re.M | re.I)
    return text[start.start() : end.start() if end else len(text)]


def _knobs(issues: Sequence[str]) -> List[str]:
    """Knob ids out of gate issue strings ("F2/F5: ..." -> F2, F5), deduped."""
    found: List[str] = []
    for issue in issues:
        m = _KNOB.match(issue)
        for knob in (m.group(1).split("/") if m else []):
            knob = knob.strip()
            if knob not in found:
                found.append(knob)
    return sorted(found)


# ----------------------------
# The parser
# ----------------------------
def parse_roleplay(
    text: str,
    event_cfg: Dict,
    *,
    date: Optional[str] = None,
    bank_id: Optional[str] = None,
    pi_items: Sequence[Dict[str, str]],
    declared_area: str = "",
    level: str = "ICDC",
    tier: str = "icdc",
    model: str = "",
    passes: int = 2,
    extra_issues: Sequence[str] = (),
    checks: Optional[Sequence[str]] = None,
) -> Dict:
    """One generation's raw text -> the archived JSON object. No model call.

    `pi_items` is the SELECTION RECORD -- the `{area, pi, role}` list the driver
    drew before the model ran (plan 05 D5). It is required and has no default,
    because the areas cannot be recovered from the authored text: nothing in a
    roleplay says which instructional area a PI came from, and re-mapping the
    strings through `data/pi/*.txt` is ambiguous for 25.8% of them (§3.2b). Each
    authored PI is joined back onto it, and an authored PI that is not in the record
    raises `PIProvenanceError` rather than being filed under a guessed area.
    `declared_area` is the area the selection DECLARED; the model's own
    INSTRUCTIONAL AREA line is recorded as a defect when the two disagree, since it
    is an echo of the prompt and the record is what the quota was drawn under.

    `checks` is the list of criteria that ACTUALLY RAN on this roleplay, recorded
    into `meta.gate.checks` (plan 04 §5). It CANNOT be a constant here: this module
    runs `check_icdc_shape` and `check_self_report` itself and is handed everything
    else through `extra_issues`, and the two drivers run different sets --
    `fill_bank.py` adds prompt-leak, participant-voice and the shelf-wide criteria,
    `fill_buffer.py` does not. A hard-coded list would state checks that did not run
    on the day path, which is the exact defect §5 exists to fix, one level in. The
    default is therefore only what this module can vouch for on its own.

    `extra_issues` is where the driver passes what this module cannot see:
    `validate_roleplay()` needs the selected PI list and the sampled exemplar, and
    cross-day similarity needs the novelty index. Both belong to the driver, which
    stays the authority on whether a roleplay publishes -- this only records the
    verdict it is handed alongside the countable ICDC-tier shape it can check itself.

    TWO IDENTITY MODES (plan 03 §4b, D10):

      `date=` -> a DAY entry. `id` is "<date>-<CODE>" and `date` is a field. This
                 is what `fill_buffer.py` writes and what the 7 committed fixtures
                 carry.
      `bank_id=` -> a BANK entry. `id` is the bank id and THERE IS NO `date` FIELD
                 AT ALL. A banked roleplay is date-free by design: the dealer
                 (§6d) stamps the date when it deals the entry into a day, and the
                 same entry re-dealt in a later cycle must not acquire a second
                 identity. Bank ids are assigned by identity and NEVER renumbered
                 -- the question bank's §10-4 rule, adopted here for the same
                 reason: the id is the join key, and frontend plan 11's phase-D
                 difficulty tap aggregates against exactly one stable key per
                 roleplay.

    Exactly one of the two is required. Defaulting a missing date to today would
    silently stamp a bank entry with the day it happened to be authored, which is
    the precise confusion between "when it was written" and "when it was served"
    that the bank exists to remove.
    """
    if (date is None) == (bank_id is None):
        raise ValueError("parse_roleplay needs exactly one of date= (a day entry) or bank_id= (a bank entry)")

    code = event_cfg["event_code"]
    fmt = event_cfg.get("format", "series")
    defects: List[str] = []

    body, report = gate.split_self_report(text)
    lines = body.splitlines()

    title, rows, span = _locate_exhibit(lines, body, defects)
    blocks, inline = _split_sections(lines, span)

    # The label this format is supposed to use, and the one `check_icdc_shape`
    # will slice on regardless of what the model actually wrote.
    gate_sit_label = "CASE STUDY SITUATION" if fmt == "team" else "EVENT SITUATION"
    sit_header, other_header = gate_sit_label, (
        "EVENT SITUATION" if fmt == "team" else "CASE STUDY SITUATION"
    )
    if sit_header not in blocks and other_header in blocks:
        defects.append(f"wrong-situation-header:{other_header}")
        sit_header = other_header

    if "QUALITY BAR" in blocks:
        # The authoring prompt's checklist, echoed back. Split off above, dropped here.
        defects.append("prompt-leak:QUALITY BAR")

    situation_lines = blocks.get(sit_header)
    if situation_lines is None:
        # Degrade to text rather than to a blank card (plan 11 §8.1): keep whatever
        # prose exists so the run surface still has something to show.
        defects.append(f"missing-section:{sit_header}")
        situation_lines = [ln for ln in lines if not gate._is_heading(ln)]

    judge_lines = blocks.get("JUDGE ROLE-PLAY CHARACTERIZATION", [])
    if not judge_lines:
        defects.append("missing-section:JUDGE ROLE-PLAY CHARACTERIZATION")

    # Judge questions have no heading of their own -- the numbered lines simply
    # begin. Everything above the first one is the characterization. The opener
    # test is `icdc_gate`'s, not a second copy: a boundary this module drew
    # differently from the gate would file questions the gate counted under the
    # characterization, and the run surface would lose its reveal step.
    first_q = next(
        (i for i, ln in enumerate(judge_lines) if gate._QUESTION_OPENER.match(ln.strip())),
        len(judge_lines),
    )
    questions = gate.judge_questions("\n".join(judge_lines[first_q:]))

    participant_instructions = _paragraphs(blocks.get("PARTICIPANT INSTRUCTIONS", []))
    if questions and any(p in participant_instructions.lower() for p in _DENIES_QUESTIONS):
        defects.append("boilerplate:denies-judge-questions")

    for header in ("PARTICIPANT INSTRUCTIONS", "PERFORMANCE INDICATORS"):
        if not blocks.get(header):
            defects.append(f"missing-section:{header}")
    if bool(event_cfg.get("includes_21st_century_skills")) and not blocks.get("21st CENTURY SKILLS"):
        defects.append("missing-section:21st CENTURY SKILLS")

    career_cluster = inline.get("CAREER CLUSTER")
    if event_cfg.get("career_cluster") and not career_cluster:
        defects.append("missing-section:CAREER CLUSTER")
    if not event_cfg.get("career_cluster") and career_cluster:
        # §3h in reverse: a model inventing a cluster for PFL, which DECA has none for.
        defects.append("unexpected-career-cluster")
        career_cluster = None

    # THE DECLARED AREA WINS OVER THE MODEL'S ECHO (plan 05 §4.2). `instructionalArea`
    # used to be whatever the model wrote back, which was in turn a plurality label the
    # old selector computed after sampling. It is now the area the draw DECLARED, so it
    # cannot disagree with the areas on the PIs beneath it; a model that wrote something
    # else is recorded as a defect rather than silently believed.
    echoed_area = inline.get("INSTRUCTIONAL AREA", "")
    area = declared_area or echoed_area
    if declared_area and echoed_area and echoed_area.strip().lower() != declared_area.lower():
        defects.append(f"area-echo-mismatch:{echoed_area.strip()}")

    performance_indicators = _pi_objects(
        _bullets(blocks.get("PERFORMANCE INDICATORS", [])), pi_items, code
    )

    # The gate runs on the ORIGINAL text, exhibit still inline and slices derived
    # its own way, so the recorded verdict is the same one fill_buffer.py would
    # reach on the same generation.
    situation_slice = _slice(body, gate_sit_label, "JUDGE ROLE-PLAY CHARACTERIZATION")
    icdc_issues = gate.check_icdc_shape(body, event_cfg)
    report_issues = gate.check_self_report(body, report)

    claimed = {
        "stakeholders": (report or {}).get("STAKEHOLDERS", []),
        "constraints": (report or {}).get("CONSTRAINTS", []),
        "conflicts": (report or {}).get("CONFLICTS", []),
        # Kept because it is the one claim Python can flatly contradict: an exhibit
        # claim with `corroborated.exhibit: false` is a FABRICATION, and that is a
        # different failure from simply having written no exhibit at all. Summary 03
        # caught 3/3 of these on the first slice.
        **({"exhibit": (report or {}).get("EXHIBIT", [""])[0]} if (report or {}).get("EXHIBIT") else {}),
    }
    if report is None:
        defects.append("self-report:missing")

    body_lower = " ".join(body.lower().split())
    corroborated = {
        "stakeholders": [
            s for s in claimed["stakeholders"] if gate._claim_supported(s.split(" - ")[0], body_lower)
        ],
        "constraints": [c for c in claimed["constraints"] if gate._claim_supported(c, body_lower)],
        "exhibit": title is not None,
    }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "id": bank_id if bank_id else f"{date}-{code}",
        # A bank entry carries NO date -- the dealer stamps it (§4b). Omitted
        # rather than nulled: `types.ts` types `date` as a required string, so a
        # null would be a contract violation where an absent key is a documented
        # difference the dealer fills in.
        **({"date": date} if date else {}),
        "code": code,
        "format": fmt,
        "level": level,
        "tier": tier,
        **({"careerCluster": career_cluster} if career_cluster else {}),
        "instructionalArea": area,
        "performanceIndicators": performance_indicators,
        "twentyFirstCenturySkills": _bullets(blocks.get("21st CENTURY SKILLS", [])),
        "participantInstructions": participant_instructions,
        "situation": _paragraphs(situation_lines),
        **({"exhibit": {"title": title, "rows": rows}} if title is not None else {}),
        "judgeCharacterization": _paragraphs(judge_lines[:first_q]),
        "judgeQuestions": questions,
        "meta": {
            "claimed": claimed,
            "corroborated": corroborated,
            "gate": {
                "passed": not icdc_issues and not extra_issues,
                "failedKnobs": _knobs([*icdc_issues, *report_issues]),
                "issues": [*icdc_issues, *extra_issues],
                # WHAT RAN, and what did not (plan 04 §5). 720 of 720 banked files
                # read `"passed": true` with nothing beside it, and an outside
                # reader took that as a quality verdict.
                "checks": list(checks) if checks is not None else list(DEFAULT_GATE_CHECKS),
                "unverified": list(gate.UNVERIFIED),
            },
            "situationWords": gate.situation_word_count(situation_slice),
            "generator": {"model": model, "passes": passes},
            "defects": defects,
        },
    }


# ----------------------------
# Archive writing (§6c layout)
# ----------------------------
def write_day(out_dir: Path, date: str, roleplays: Sequence[Dict], all_codes: Sequence[str]) -> Dict:
    """Write `YYYY/MM/DD/{day,<code>}.json` and return the RoleplayDay."""
    year, month, dom = date.split("-")
    day_dir = out_dir / year / month / dom
    day_dir.mkdir(parents=True, exist_ok=True)

    present = {r["code"] for r in roleplays}
    day = {
        "date": date,
        "events": [c for c in all_codes if c in present],
        # Everything the day does not carry, named. §6b: a visibly missing event is
        # honest; silently rendering 24 cards and letting a competitor wonder where
        # their event went is not.
        "missing": [c for c in all_codes if c not in present],
    }

    for roleplay in roleplays:
        _write_json(day_dir / f"{roleplay['code'].lower()}.json", roleplay)
    _write_json(day_dir / "day.json", day)
    return day


def write_index(out_dir: Path, days: Sequence[Dict]) -> None:
    """Write `index.json` plus a `months/YYYY-MM.json` shard per month.

    Sharded on purpose (§6c): one flat index reaches ~10,220 entries a year and
    would be rewritten on every batch.
    """
    ordered = sorted(days, key=lambda d: d["date"])
    months: Dict[str, List[Dict]] = {}
    for day in ordered:
        months.setdefault(day["date"][:7], []).append(day)

    (out_dir / "months").mkdir(parents=True, exist_ok=True)
    for month, entries in months.items():
        _write_json(out_dir / "months" / f"{month}.json", entries)

    _write_json(
        out_dir / "index.json",
        {
            "version": SCHEMA_VERSION,
            # May be a FUTURE date -- the buffer is filled ahead and the client
            # clamps to its own local today (plan 11 F1). Do not treat as "today".
            "latest": ordered[-1]["date"] if ordered else "",
            "months": sorted(months),
            "totals": {"days": len(ordered), "roleplays": sum(len(d["events"]) for d in ordered)},
        },
    )


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ----------------------------
# Fixtures (frontend plan 11 §2d)
# ----------------------------
# Real generated output, not hand-written scenarios, split across three days so the
# UI is built against the degraded states it must actually survive:
#   2026-07-28  a full-pass day: a markdown-table exhibit (HRM), bullet exhibits,
#               and all three formats
#   2026-07-29  PFL -- no CAREER CLUSTER, no exhibit at all, and a self-report that
#               CLAIMS one (the fabrication the cross-check exists to catch)
#   2026-08-01  BLTDM alone, FUTURE-DATED on purpose: the day is physically on disk
#               and must not be revealed until the client's own local date reaches
#               it. One roleplay, 27 missing.
FIXTURE_DAYS: Dict[str, List[str]] = {
    "2026-07-28": ["HRM", "PBM", "MTDM"],
    "2026-07-29": ["SEM", "ACT", "PFL"],
    "2026-08-01": ["BLTDM"],
}
# Deliberately the SUMMARY-03 outputs, not the post-K3-fix ones sitting alongside
# in `no-example-k3fix/`. The three fixture days were chosen to exercise degraded
# states the UI must survive (a fabricated exhibit claim, a missing exhibit, a
# future-dated day); rebuilding them from post-fix output would make every fixture
# well-formed and quietly delete that coverage. Their `meta.gate` verdicts are
# expected to show K3 failures — those generations pre-date the fix, and recording
# that honestly is the point.
FIXTURE_SOURCE = BASE_DIR / "output" / "bake-off" / "icdc" / "no-example"
FIXTURE_MODEL = "qwen2.5:14b-instruct"


def build_fixtures(out_dir: Path) -> None:
    """DISABLED by plan 05 D5. The 7 committed fixtures are REGENERATED, not rebuilt.

    This rebuilt the fixture days from `output/bake-off/icdc/no-example/*.txt`, which
    were authored before plan 05 §3's area-first selection existed. Under D5 every PI
    needs its SOURCE AREA, and those texts have no selection record behind them any
    more -- re-resolving one now draws a different bundle, and re-mapping the strings
    is ambiguous for 25.8% of them (§3.2b). Either route writes provenance nobody
    measured into the 7 files a reader is most likely to open.

    OQ5 resolves it: the fixtures are regenerated through the real pipeline at plan 05
    §7 step 7, with the `/changelog` entry that user-facing change takes. Raising here
    is the honest failure -- the alternative is a command that silently produces the
    old shape and a loader that silently drops it.
    """
    raise SystemExit(
        "--fixtures is disabled (plan 05 D5/OQ5): the bake-off texts it rebuilt from "
        "predate area-first PI selection, so their PIs have no recorded instructional "
        "area and no honest way to acquire one. The 7 day fixtures are REGENERATED "
        "through the real pipeline at plan 05 §7 step 7, not rebuilt from here."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Plan 03 D5 roleplay text -> JSON parser (no model calls)")
    ap.add_argument("--text", type=Path, help="a generated roleplay .txt")
    ap.add_argument("--event", help="event code, e.g. HRM")
    ap.add_argument("--date", help="publish date, YYYY-MM-DD")
    ap.add_argument("--level", default="ICDC")
    ap.add_argument("--tier", default="icdc")
    ap.add_argument("--model", default="", help="recorded in meta.generator.model")
    ap.add_argument("--passes", type=int, default=2, choices=(1, 2))
    ap.add_argument(
        "--pi-record",
        type=Path,
        help="JSON list of the selected PIs, [{area, pi, role}, ...], as the driver "
             "resolved them. REQUIRED: a PI's instructional area exists nowhere in the "
             "roleplay text and cannot be recovered from the string (plan 05 D5).",
    )
    ap.add_argument("--declared-area", default="", help="the area the selection declared")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--stdout", action="store_true", help="print the JSON instead of writing it")
    ap.add_argument("--fixtures", action="store_true",
                    help="DISABLED (plan 05 D5/OQ5) -- see build_fixtures")
    args = ap.parse_args()

    if args.fixtures:
        build_fixtures(args.out)
        return

    if not (args.text and args.event and args.date and args.pi_record):
        ap.error("--text, --event, --date and --pi-record are required")

    events = load_events()
    if args.event not in events:
        ap.error(f"unknown event {args.event!r}")

    roleplay = parse_roleplay(
        args.text.read_text(encoding="utf-8"),
        events[args.event],
        date=args.date,
        pi_items=json.loads(args.pi_record.read_text(encoding="utf-8")),
        declared_area=args.declared_area,
        level=args.level,
        tier=args.tier,
        model=args.model,
        passes=args.passes,
    )

    if args.stdout:
        print(json.dumps(roleplay, indent=2, ensure_ascii=False))
        return

    write_day(args.out, args.date, [roleplay], event_order(events))
    print(f"wrote {args.out / args.date.replace('-', '/') / (args.event.lower() + '.json')}")


if __name__ == "__main__":
    main()
