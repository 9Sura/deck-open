"""Deterministic ICDC-tier gate. No model call, ever.

THE BAR IS DECA'S OWN FORMAT (plan 05 successor; the ICDC+ tier is retired). The
previous ICDC+ bar was validated on an inverted rule -- "an instrument that can't
score real District material as FAILING isn't measuring anything", recorded at
**0 of 396 real DECA roleplays passing**. Under a brief that says *follow DECA's
format*, that inversion is the DEFECT, not the proof. The acceptance test is now
the other way round: this gate must ACCEPT real published DECA material, and the
knob set below is derived from measurements over those same 396 corpus files.

What the corpus actually says, measured, and what each fact became:

    exhibits / data blocks              0 of 396   -> F3 BANS one
    judge questions: 2                302 of 396   -> F6 allows 2-3, nothing else
    judge questions: 3                 89 of 396
    situation length                   per-event   -> F7 band, 0.8x-1.4x the
                                                      event's OWN corpus mean
                                                      (81% of real cases inside;
                                                      the old 1.4x-1.8x held 5%)
    situation paragraphs        4 principles / 5 series / 6 team (medians)

Coverage map -- what this module can count is the whole of what gets enforced,
and what it cannot count ships unverified BY DESIGN (plan 03 D4 dropped the
model referee):

    F3 no exhibit / no data block                 checked here
    F6 2-3 judge questions                        checked here
    F7 per-event situation word band              checked here
    F8 BLATANT telegraphs                         checked here (phrase list)
    F2 roles not a named cast                     partial -- self-report cross-check
    F5 >=2 defensible options with real costs     partial -- self-report cross-check
    F1 one scenario, one judge                    NOT VERIFIED
    F4 decidable from the given facts             NOT VERIFIED
    F8 SUBTLE telegraphs                          NOT VERIFIED

    PROMPT LEAKAGE (not a knob)                   checked here -- check_prompt_leak

Do not mistake an empty issue list for "this roleplay is good." It means "nothing
countable is wrong with it." Difficulty comes from the authoring prompt
(src/prompts/icdc.txt); this module only ever measured compliance.

The self-report cross-check is deliberately NOT a verdict -- a model certifying
its own work is worthless. It is structured extraction that Python CONTRADICTS:
it catches "claimed two courses of action, only one is in the prose." It cannot
catch "two options that aren't really a trade-off."
"""

import re
from typing import Dict, List, Optional, Sequence, Tuple

# Which bar a roleplay was measured against, recorded in the bank manifest so a
# shelf authored under an older gate is identifiable rather than assumed current.
#   1  K3/K6/K7/K8-blatant + the K1/K2 self-report cross-check (the daily gate)
#   2  ...plus check_prompt_leak (plan 03 §4f) -- a BANK acceptance criterion,
#      deliberately NOT folded into check_icdc_shape: it is not a difficulty knob,
#      and adding it there would silently move the DAY publish bar that
#      fill_buffer.py's measured pass rate was derived from.
# 2 = + check_prompt_leak (§4f). 3 = + check_participant_voice (§6e, the OQ9 read).
# Both are BANK acceptance criteria that live beside check_icdc_shape rather than
# inside it, so the DAY publish bar this version does not describe is unmoved.
#   4  Plan 05 §7 step 3. K7 becomes the per-EVENT word BAND and fails in BOTH
#      directions (D10, superseding plan 04 D1 -- see situation_word_band below);
#      plus check_pi_quota (§3's quota, read off the artifact), the declared-area
#      echo and the verbatim 21st Century Skills comparison (plan 04 §2) in
#      validate_roleplay, seed_axes.check_axis_membership (plan 04 §3.2 step 4)
#      pinned by meta.generator.axesHash (step 5), and meta.gate.checks /
#      meta.gate.unverified (plan 04 §5).
#   5  THE ICDC+ TIER IS RETIRED. The knob set is replaced by F1-F8, DECA's own
#      format: F3 BANS the exhibit K3 required, F6 caps judge questions at the
#      corpus's 2-3 where K6 floored them at 3 analytic ones, F1/F2 replace K1's
#      ">=3 named stakeholders with incompatible interests" with the corpus's
#      role-not-cast shape, K2's numeric-collision floor is gone, and F7's band
#      is re-derived (below). A shelf recording gateVersion <= 4 was measured
#      against the ICDC+ bar and is NOT comparable to one recording 5.
GATE_VERSION = 5

# F7 -- the per-event situation word BAND. Still 
# `multiplier x the mean length of the event's OWN corpus situations` (events.json
# carries that mean as a measured number per event), and still computed rather than
# stored so the two ends cannot drift from the mean they come from. What changed is
# the multipliers, and they are now measured rather than chosen:
#
#   real corpus situations falling inside the band, over all 396 files
#     1.4x - 1.8x  (the retired ICDC+ band)     20/396 =  5%
#     0.8x - 1.4x  (this one)                  319/396 = 81%
#     0.7x - 1.5x                              376/396 = 95%
#
# 0.8-1.4 is the band that CONTAINS the corpus while still sitting at its upper
# half -- the old FLOOR becomes the new CEILING, so an ICDC case lands at the long
# end of what DECA actually prints for this event instead of past every case of it.
# Widening to 0.7-1.5 buys 14 points of coverage by admitting situations shorter
# than any competitor benefits from; that is the trade this pair declines.
BAND_LO_MULT = 0.8
BAND_HI_MULT = 1.4


def situation_word_band(event_cfg: Dict) -> Tuple[int, int]:
    """(lo, hi) authored word band for this event's situation section.

    0.8x-1.4x the event's measured corpus mean -- see BAND_LO_MULT for why those
    two numbers and not the retired tier's.

    Raises on an event with no measured mean rather than falling back to a
    per-format number: a silent fallback would re-introduce the per-format rule
    D9 exists to replace, under a per-event heading, and nothing downstream could
    tell the two apart (plan 05 §8.3's own objection to a fallback).
    """
    mean = event_cfg.get("authentic_situation_mean")
    if not mean:
        raise ValueError(
            f"{event_cfg.get('event_code', '?')} has no authentic_situation_mean in "
            "events.json, so its F7 length band cannot be computed. Measure it from "
            "the event's corpus files (plan 05 §9's last one-liner) and add it there."
        )
    return round(BAND_LO_MULT * mean), round(BAND_HI_MULT * mean)

# F7 issue markers. Named here, beside the code that emits them, because the day
# path matches on the STRING to decide whether to run its expansion pass -- and
# that pass only ever makes a situation LONGER. A band fails in BOTH directions,
# and an over-long situation handed to the expansion pass would be rewritten in
# exactly the wrong direction. Match on `f7_too_short`, never on the knob id.
# (Question-bank precedent, project CLAUDE.md §10-10: when a gate's behaviour is
# depended on elsewhere, name the marker beside the emitter.)
#
# Under the ICDC+ band this fired constantly in the SHORT direction. Under a band
# whose ceiling is the old floor it will fire mostly LONG, which the expansion
# pass must never see -- hence the direction test, not a knob-id prefix.
F7_SHORT = "below the band floor"
F7_LONG = "above the band ceiling"


def f7_too_short(issues: Sequence[str]) -> bool:
    """Did F7 fail because the situation is SHORT (the only failure expansion fixes)?"""
    return any(i.startswith("F7") and F7_SHORT in i for i in issues)


# ----------------------------
# Plan 05 §3 -- the PI quota, read off the ARTIFACT
# ----------------------------
# Plan 05 §3.1's core quota, keyed by `pi_count` rather than by format -- which is
# what plan 05 §9's own satisfiability script does, and it is what keeps PFL (the
# one principles event with pi_count 3) out of the code as a special case. It lives
# HERE rather than in generate_roleplay so the selector and the gate read one
# number: generate_roleplay imports it back, and icdc_gate cannot import
# generate_roleplay (that direction is the cycle).
CORE_MINIMUM_BY_PI_COUNT: Dict[int, int] = {3: 3, 4: 3, 5: 3, 7: 4}


def check_pi_quota(
    pi_items: Sequence[Dict[str, str]], declared_area: str, event_cfg: Dict
) -> List[str]:
    """Is §3's quota PROVABLE from this roleplay's own recorded provenance?

    `select_event_pis` already guarantees the quota structurally, so this is not a
    second copy of the selector -- it is the D5 claim that the guarantee survives
    into the artifact. It therefore takes exactly the shape a BANKED FILE carries:
    `performanceIndicators` (a list of `{area, pi, role}`) and `instructionalArea`.
    Hand it those two off a banked JSON and it audits a whole shelf, which
    re-mapping PI strings to areas could never do -- 25.8% of corpus PIs are filed
    by DECA under more than one area (plan 05 §3.2b), so that mapping is ambiguous
    by construction.
    """
    issues: List[str] = []
    pi_count = event_cfg["pi_count"]
    core_min = CORE_MINIMUM_BY_PI_COUNT.get(pi_count)
    if core_min is None:
        return [
            f"quota: pi_count {pi_count} is not in plan 05 §3.1's table "
            f"({sorted(CORE_MINIMUM_BY_PI_COUNT)}); the core minimum is undefined"
        ]

    if len(pi_items) != pi_count:
        issues.append(
            f"quota: {len(pi_items)} performance indicator(s) recorded, "
            f"this event's pi_count is {pi_count}"
        )

    core = [it for it in pi_items if (it.get("role") or "") == "core"]
    if len(core) < core_min:
        issues.append(
            f"quota: {len(core)} core performance indicator(s), "
            f"floor is {core_min} (pi_count {pi_count})"
        )

    # A core PI filed under an area other than the declared one is the quota
    # failing silently: the count would still read core_min while the bundle it
    # certifies is scattered, which is the exact defect §3 exists to close.
    if declared_area:
        stray = [it["pi"] for it in core if (it.get("area") or "") != declared_area]
        if stray:
            issues.append(
                f"quota: {len(stray)} core performance indicator(s) are not filed "
                f"under the declared area '{declared_area}'"
            )
    else:
        issues.append("quota: no declared instructional area recorded")

    return issues


# ----------------------------
# What the gate does NOT check (plan 04 §5, from 03-plan §5c)
# ----------------------------
# Recorded into `meta.gate.unverified` on every roleplay, because 720 of 720 banked
# files read `"gate": {"passed": true}` and an outside reader took that as a quality
# verdict. `passed` means "the countable criteria in `checks` found nothing" and
# nothing more; these are the criteria nobody ran.
UNVERIFIED: Tuple[str, ...] = (
    "F2 (roles not a named cast; at most two parties beyond the judge) -- "
    "self-report cross-check only, recorded and NOT gating",
    "F5 (>=2 defensible options, each with a real cost) -- self-report "
    "cross-check confirms the options were WRITTEN, not that they trade off",
    "F1 (one scenario, one judge) -- unverified, needs a judge",
    "F4 (decidable from the given facts) -- unverified, needs a judge",
    "F8 subtle telegraphs -- unverified; only the blatant phrase list is checked",
    "difficulty -- NOT refereed (03-plan D4); no string may claim verified difficulty",
    "whether the SITUATION honours its seed axes -- only the recorded axis VALUES "
    "are checked for membership (plan 04 §3.2 step 4)",
)


# ----------------------------
# List items -- one definition
# ----------------------------
_BULLET = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s+")


def section_lines(text: str, header: str) -> List[str]:
    """The body lines under one DECA section header ([] if the header is absent).

    Ends at the next DECA section header or at a model-invented all-caps heading,
    whichever comes first -- the same two boundaries `exhibit_block` respects.
    `parse_roleplay._split_sections` splits the WHOLE document by its own header
    list to build the artifact; this answers the narrower question the gate asks of
    one section, and both boundaries are drawn from `_KNOWN_HEADERS`, so the two
    agree about where the 21st Century Skills block stops.
    """
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(rf"^\s*{re.escape(header)}\s*:?\s*$", ln, flags=re.I):
            start = i + 1
            break
    if start is None:
        return []
    out: List[str] = []
    for ln in lines[start:]:
        if _is_section_header(ln) or _is_heading(ln):
            break
        out.append(ln)
    return out


def list_items(lines: Sequence[str]) -> List[str]:
    """Bullet/numbered list items, markers stripped, wrapped lines rejoined.

    Shared rather than duplicated: `parse_roleplay` uses it to STORE the 21st
    Century Skills block and `generate_roleplay.validate_roleplay` uses it to
    COMPARE that block verbatim against events.json. Two copies could disagree
    about where an item begins, and then a file would pass the comparison and be
    banked under a different string than the one that was compared.
    """
    items: List[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if _BULLET.match(line):
            items.append(_BULLET.sub("", line).strip())
        elif items:
            items[-1] = f"{items[-1]} {line}"
        else:
            items.append(line)
    return [i for i in items if i]


# F6 -- judge questions, a RANGE, not a floor. Measured over the corpus: 2 in 302
# of 396 files, 3 in 89, and 4-or-more in 5 (one of which has 16, an extraction
# artefact). The retired K6 floored this at 3 AND demanded every question open
# with an evaluative verb AND that one name a stakeholder and quote their
# position -- a rubric item's register, which is why 396 of 396 real roleplays
# failed it. There is no analytic-verb test any more and there must not be one.
MIN_JUDGE_QUESTIONS = 2
MAX_JUDGE_QUESTIONS = 3

# F2/F5 floors (self-report cross-check). PARTIES has a CEILING, not a floor:
# "at least three named stakeholders with mutually incompatible interests" was
# the single biggest driver of the over-complication this tier exists to undo.
MAX_PARTIES = 2
MIN_OPTIONS = 2

SELF_REPORT_START = "=== SELF-REPORT ==="
SELF_REPORT_END = "=== END SELF-REPORT ==="

# The tail's keys, and the whole of what Python can contradict. STAKEHOLDERS /
# CONFLICTS / EXHIBIT are gone with the ICDC+ tier that needed them; OPTIONS is
# new and is the only structured handle on F5, the knob this tier's difficulty
# actually rests on. Keep this in sync with the tail spec in src/prompts/icdc.txt
# -- a key the prompt emits and this set omits is silently dropped.
SELF_REPORT_KEYS = ("PARTIES", "CONSTRAINTS", "OPTIONS")

# F8 -- blatant resolutions. Every one of these hands the participant the answer.
# This list is the ENTIRE F8 enforcement; subtle telegraphing is unverified (D4).
# Plan 03 §5a notes the question-bank equivalent recurred three times after the
# warning went into the prompt, so expect this list to earn its keep.
TELEGRAPH_PHRASES: Tuple[str, ...] = (
    "the obvious choice",
    "the obvious option",
    "the obvious answer",
    "the obvious solution",
    "obviously the best",
    "clearly the best",
    "clearly the right",
    "the best option is",
    "the best choice is",
    "the best course of action is",
    "the right decision is",
    "the correct decision is",
    "the correct choice is",
    "the only real option",
    "the only viable option",
    "there is really only one",
    "there is only one option",
    "it is evident that",
    "it is clear that you should",
    "of course, the",
    "naturally, the best",
    "needless to say",
    "goes without saying",
    "the smart move is",
    "the sensible choice is",
    "any reasonable person would",
)

# The retired K6's ANALYTIC_MARKERS and COUNTER_MARKERS lists are DELETED, not
# commented out. They encoded "every question must open with justify/weigh/defend"
# and "one question must name a stakeholder and quote their position back" -- the
# register of a scoring rubric, absent from all 396 corpus roleplays, and the
# largest single contributor to the retired bar's 0-of-396. F6 counts questions and
# nothing else. Do not reintroduce a verb list here.

# Section labels that are DECA structure, not a K3 data exhibit. A heading has to
# be something the model invented for its numbers to count.
_KNOWN_HEADERS: Tuple[str, ...] = (
    "CAREER CLUSTER", "INSTRUCTIONAL AREA", "PARTICIPANT INSTRUCTIONS",
    "21ST CENTURY SKILLS", "PERFORMANCE INDICATORS", "EVENT SITUATION",
    "CASE STUDY SITUATION", "JUDGE ROLE-PLAY CHARACTERIZATION",
    "SELF-REPORT", "END SELF-REPORT",
)

# K3 -- an exhibit heading has to ANNOUNCE data. Without this, any all-caps line
# qualifies as a data label: the corpus's own event-name title line ("PERSONAL
# FINANCIAL LITERACY") was scoring as an exhibit because the participant
# instructions beneath it mention "10 minutes" twice, which passed all 396
# District roleplays on a knob none of them actually meet. The authoring prompt
# tells the model to head its block "EXHIBIT 1: ...", so requiring the label is
# fair as well as countable.
_EXHIBIT_KEYWORDS: Tuple[str, ...] = (
    "EXHIBIT", "TABLE", "APPENDIX", "DATA", "FIGURES", "METRICS", "STATISTICS",
    "BREAKDOWN", "SUMMARY", "PROJECTION", "PROJECTIONS", "FORECAST", "COMPARISON",
    "RESULTS", "BUDGET", "COSTS", "PRICING", "REVENUE", "MARGIN", "MARGINS",
    "SALES", "INVENTORY", "SURVEY", "SCHEDULE", "FINANCIALS", "PERFORMANCE DATA",
    "KEY NUMBERS", "AT A GLANCE", "SNAPSHOT", "OVERVIEW OF", "SELECTED",
)

# K3 -- headings that would fit ANY scenario. The authoring prompt shows the
# exhibit's shape with <slots>, and a model handed a shape will sometimes copy
# the shape's own words instead of filling them: the first run after the K3 fix
# emitted "EXHIBIT 1: WHAT THE FIGURES SHOW" verbatim. Plan 03 §5a records that
# the question-bank's telegraph warning recurred THREE TIMES after being added
# to the prompt, so a prompt rule alone is not the control -- this list is.
# Matched after the "EXHIBIT n:" prefix is stripped.
_GENERIC_EXHIBIT_HEADINGS: Tuple[str, ...] = (
    "WHAT THE FIGURES SHOW", "THE FIGURES", "FIGURES", "DATA", "THE DATA",
    "KEY FIGURES", "KEY NUMBERS", "KEY DATA", "NUMBERS", "RELEVANT DATA",
    "RELEVANT FIGURES", "FINANCIAL DATA", "SUPPORTING DATA", "DATA BLOCK",
    "QUANTITATIVE DATA", "QUANTITATIVE EXHIBIT", "EXHIBIT", "TABLE",
    "IN CAPITALS", "SUMMARY", "OVERVIEW", "STATISTICS", "METRICS",
)

_EXHIBIT_LABEL = re.compile(r"^EXHIBIT\s*\d*\s*[:.–—-]?\s*", re.I)

_NUMERIC = re.compile(r"(?<![A-Za-z])[$]?\d[\d,]*(?:\.\d+)?%?")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_STOPWORDS = frozenset(
    "the a an and or but of to in on at by for with from as is are was were be been "
    "being that this these those it its their his her they he she you your our we us "
    "not no than then so if when while must may can will would should could have has "
    "had do does did each per about into over under more most less least own same".split()
)


# ----------------------------
# Self-report tail (§5b)
# ----------------------------
def split_self_report(text: str) -> Tuple[str, Optional[Dict[str, List[str]]]]:
    """Split a generation into (roleplay_body, parsed_self_report_or_None).

    The tail is stripped from the body here so it never reaches the archive, the
    similarity guard, or a competitor's screen. Returns None for the report when
    the model omitted the tail entirely.
    """
    start = text.find(SELF_REPORT_START)
    if start == -1:
        return text.strip(), None

    body = text[:start].strip()
    end = text.find(SELF_REPORT_END, start)
    tail = text[start + len(SELF_REPORT_START) : end if end != -1 else len(text)]

    report: Dict[str, List[str]] = {}
    for line in tail.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().upper()
        if key not in SELF_REPORT_KEYS:
            continue
        report[key] = [p.strip() for p in value.split("|") if p.strip()]

    return body, (report or None)


def _content_words(s: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(s) if len(w) >= 4 and w.lower() not in _STOPWORDS]


def _claim_supported(claim: str, body_lower: str) -> bool:
    """Is a claimed stakeholder/constraint actually present in the prose?

    Verbatim first, then a content-word overlap fallback -- a model will often
    write "capped at $40,000" in the prose and report it as "budget cap of
    $40,000". Requiring a literal match would flag honest claims, so we require
    the claim's distinctive words (and its numbers, which are the load-bearing
    part of a K2 constraint) to be present.
    """
    normalized = " ".join(claim.lower().split())
    if normalized and normalized in body_lower:
        return True

    # Every number in the claim must appear in the prose -- an invented figure is
    # exactly the failure this check exists to catch.
    for num in _NUMERIC.findall(claim):
        if num.lower().lstrip("$") not in body_lower:
            return False

    words = _content_words(claim)
    if not words:
        return False
    hits = sum(1 for w in words if w in body_lower)
    return hits / len(words) >= 0.6


def check_self_report(body: str, report: Optional[Dict[str, List[str]]]) -> List[str]:
    """Falsify the author's own F2/F5 claims against the prose it wrote.

    NOT a verdict on whether the two options are genuinely a trade-off -- only on
    whether the things it says it wrote are actually there.

    The direction of the PARTIES test is INVERTED from the retired tier's. K1
    demanded at least three named stakeholders with incompatible interests and
    this function enforced the floor; F2 caps the cast instead, because the floor
    is what produced four-body cases for an event a competitor presents to one
    judge. A case with one interested party besides the judge is correct here.
    """
    if report is None:
        return ["F2/F5: self-report tail missing (cannot cross-check parties/options)"]

    issues: List[str] = []
    body_lower = " ".join(body.lower().split())

    parties = report.get("PARTIES", [])
    if len(parties) > MAX_PARTIES:
        issues.append(
            f"F2: {len(parties)} interested parties beyond the judge, ceiling is "
            f"{MAX_PARTIES} -- this event is presented to one judge"
        )
    # The role is the reliable half of "<role> - <interest>".
    absent = [x for x in parties if not _claim_supported(x.split(" - ")[0], body_lower)]
    if absent:
        issues.append(
            f"F2: {len(absent)}/{len(parties)} reported part(ies) not found in the prose: "
            + "; ".join(a.split(" - ")[0][:40] for a in absent)
        )

    constraints = report.get("CONSTRAINTS", [])
    absent_c = [c for c in constraints if not _claim_supported(c, body_lower)]
    if absent_c:
        issues.append(
            f"F5: {len(absent_c)}/{len(constraints)} reported constraint(s) not found in the prose: "
            + "; ".join(c[:40] for c in absent_c)
        )

    options = report.get("OPTIONS", [])
    if len(options) < MIN_OPTIONS:
        issues.append(
            f"F5: {len(options)} course(s) of action reported, need >= {MIN_OPTIONS} "
            "-- a case with one defensible option has no decision in it"
        )
    absent_o = [o for o in options if not _claim_supported(o, body_lower)]
    if absent_o:
        issues.append(
            f"F5: {len(absent_o)}/{len(options)} reported option(s) not found in the prose: "
            + "; ".join(o[:40] for o in absent_o)
        )

    return issues


# ----------------------------
# Countable knobs (F3/F6/F7/F8)
# ----------------------------
def _is_heading(line: str) -> bool:
    """A model-invented all-caps label line (K3's exhibit heading)."""
    s = line.strip().rstrip(":").strip()
    if len(s) < 4 or len(s) > 90:
        return False
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 3 or not all(c.isupper() for c in letters):
        return False
    return not any(s.upper().startswith(h) for h in _KNOWN_HEADERS)


def _announces_data(heading: str) -> bool:
    """Does this all-caps label announce a data block (vs. being a title)?"""
    up = heading.upper()
    return any(re.search(rf"(?<![A-Z]){re.escape(k)}(?![A-Z])", up) for k in _EXHIBIT_KEYWORDS)


def _is_section_header(line: str) -> bool:
    """A DECA structural header line -- the thing `_is_heading` deliberately excludes.

    `_is_heading` answers "did the model invent this label", so it returns False
    for EVENT SITUATION and friends. A block scan needs the opposite question, and
    needs it since the K3 fix: the exhibit now sits directly ABOVE the situation
    header, so without this the scan runs straight through it into the prose.
    """
    s = line.strip().rstrip(":").strip().upper()
    return any(s.startswith(h) for h in _KNOWN_HEADERS)


def exhibit_block(lines: Sequence[str], heading_index: int) -> Tuple[List[str], int]:
    """Rows under an exhibit heading, plus the index one past the last one.

    ONE definition of "the exhibit block", used by the gate to count numerics and
    by parse_roleplay to build the rows a competitor sees. They were separate, and
    the gate's was looser -- it read past a single blank line, so HRM's block
    swallowed the paragraph after the table and K3 was credited 9 numerics for a
    6-numeric table. Over-counting was tolerable while K3 was failing for lack of
    any block at all; it is not tolerable now that the prompt promotes the exhibit
    to its own section, because a heading with no real rows would pass K3 on the
    numbers in the situation underneath it.

    The block therefore ends at the first blank line after it starts, at another
    invented heading, or at a DECA section header -- whichever comes first.
    """
    rows: List[str] = []
    i = heading_index + 1
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            if rows:
                break
            i += 1
            continue
        if _is_heading(line) or _is_section_header(line):
            break
        rows.append(line)
        i += 1
    return rows, i


def find_exhibit(text: str) -> Tuple[Optional[str], int]:
    """Return (exhibit heading, numeric count in the block beneath it).

    Scans every candidate heading and keeps the richest block, so a roleplay with
    both "EXHIBIT 1" and a stray label isn't judged on the wrong one.
    """
    lines = text.splitlines()
    best_heading: Optional[str] = None
    best_count = 0

    for i, line in enumerate(lines):
        if not _is_heading(line) or not _announces_data(line):
            continue
        rows, _ = exhibit_block(lines, i)
        count = len(_NUMERIC.findall("\n".join(rows)))
        if count > best_count:
            best_heading, best_count = line.strip().rstrip(":").strip(), count

    return best_heading, best_count


def is_generic_heading(heading: str) -> bool:
    # DEAD UNDER F3 and kept only because deleting it would take
    # `_GENERIC_EXHIBIT_HEADINGS` with it. `check_icdc_shape` no longer calls this:
    # under the retired K3 an exhibit had to exist and be well named, and now it
    # must not exist at all, so "is this heading generic" has nothing to decide.
    """Would this exhibit heading fit any scenario at all?

    An exhibit whose heading names nothing is a labelled block in form only: the
    competitor learns what the figures measure from the rows or not at all, and
    K3 exists to put the decision's numbers somewhere legible.
    """
    label = _EXHIBIT_LABEL.sub("", heading.strip()).strip().rstrip(":").strip().upper()
    return not label or label in _GENERIC_EXHIBIT_HEADINGS


def exhibit_placement(text: str, event_cfg: Dict) -> Optional[str]:
    # DEAD UNDER F3, same reason as is_generic_heading: there is no correct place
    # for a block that must not be written. `find_exhibit` stays live as the
    # DETECTOR that F3 reads.
    """None when the exhibit sits where SECTION ORDER puts it, else what's wrong.

    The authoring prompt fixes the exhibit between PERFORMANCE INDICATORS and the
    situation header so the situation can refer back to it. Measured on the first
    post-fix run: the model instead appended the block AFTER the judge section,
    below the numbered questions -- which satisfies "there is a labelled block"
    while leaving the student reading a situation whose figures appear after the
    judge's script. Countable, so it is counted rather than hoped for.
    """
    heading, _ = find_exhibit(text)
    if heading is None:
        return None  # absence is K3's own failure, reported there

    lines = text.splitlines()
    at = next(
        (i for i, ln in enumerate(lines) if ln.strip().rstrip(":").strip() == heading), None
    )
    if at is None:
        return None

    def _header_line(*labels: str) -> Optional[int]:
        for i, ln in enumerate(lines):
            s = ln.strip().rstrip(":").strip().upper()
            if any(s == lb for lb in labels):
                return i
        return None

    pis = _header_line("PERFORMANCE INDICATORS")
    sit = _header_line(
        "CASE STUDY SITUATION" if event_cfg.get("format") == "team" else "EVENT SITUATION",
        "EVENT SITUATION",
        "CASE STUDY SITUATION",
    )
    judge = _header_line("JUDGE ROLE-PLAY CHARACTERIZATION")

    if judge is not None and at > judge:
        return "after the judge section"
    if sit is not None and at > sit:
        return "inside or below the situation"
    if pis is not None and at < pis:
        return "above PERFORMANCE INDICATORS"
    return None


# F6 -- how a numbered judge question can open. THE SECOND TIME this knob has
# been blind to correctly-written questions: summary 03 found the counter-argument
# marker list missing "<Name> argues that... Defend your recommendation", and a
# bare `^\d+[.)]` numbering test then scored MTDM at 0 questions when it had
# written three textbook ones as `- **Question 1:** Justify which option...`.
# Markdown bullets, a bold wrapper, and a "Question"/"Q" label are all formatting
# the spec never forbade, so counting them is fixing the instrument, not lowering
# the bar. Only ever applied to the judge section, where a numbered bullet is a
# question by construction.
_QUESTION_OPENER = re.compile(
    r"""^\s*
        (?:[-*•–]\s*)?          # optional markdown bullet
        (?:\*\*|__)?\s*         # optional bold opener
        (?:Question|Q)?\s*      # optional "Question 1" / "Q1" label
        \(?\d+\)?\s*
        (?:\*\*|__)?\s*         # optional bold closer (before OR after the separator)
        [.):]\s*
        (?:\*\*|__)?\s*         # optional bold closer
    """,
    re.X | re.I,
)


def judge_questions(judge_section: str) -> List[str]:
    """Numbered questions in the judge section, joined across wrapped lines."""
    questions: List[str] = []
    current: Optional[List[str]] = None
    for raw in judge_section.splitlines():
        line = raw.strip()
        if _QUESTION_OPENER.match(line):
            if current:
                questions.append(" ".join(current))
            current = [_QUESTION_OPENER.sub("", line).strip().rstrip("*").strip()]
        elif current is not None:
            if not line:
                questions.append(" ".join(current))
                current = None
            else:
                current.append(line)
    if current:
        questions.append(" ".join(current))
    return [q for q in questions if q.strip()]


def situation_word_count(situation_slice: str) -> int:
    """Words in the situation, excluding its own header line."""
    lines = situation_slice.splitlines()
    if lines:
        first = lines[0].strip().upper().rstrip(":").strip()
        if first in ("EVENT SITUATION", "CASE STUDY SITUATION") or _is_heading(lines[0]):
            lines = lines[1:]
    return len(_WORD.findall("\n".join(lines)))


# ----------------------------
# Prompt leakage (plan 03 §4f) -- NOT a knob
# ----------------------------
# A roleplay must contain the SCENARIO and nothing about how it was commissioned.
# The committed fixtures prove this is live rather than theoretical: 2 of the 7
# bake-off outputs echoed system.txt's own "QUALITY BAR" checklist back into the
# answer, and `parse_roleplay` records it as `meta.defects: ["prompt-leak:QUALITY
# BAR"]` -- a defect it can only DESCRIBE, because nothing gated it.
#
# Under a daily batch that shipped one bad day. Under a BANK it is served for the
# shelf's entire lifetime, which is why §4f says to add this before the first
# tranche rather than after it.
#
# Two design rules this list follows, both learned on K3 and K6:
#
#   1. MARKERS MUST BE OURS, NOT DECA'S. "PERFORMANCE INDICATORS" and "EXHIBIT 1:"
#      are legitimate output; only strings that could ONLY have come from the
#      authoring apparatus belong here. Every entry below is validated at 0 hits
#      across the 396 real District corpus roleplays -- an instrument that flags
#      real DECA material is measuring the wrong thing (§5c's honesty rule).
#   2. A PROMPT RULE IS NOT A CONTROL. icdc.txt already says "do not announce,
#      label, number, or otherwise refer to these floors"; the leak happened anyway.
#      This list is the control.
_PROMPT_LEAK_MARKERS: Tuple[Tuple[str, str], ...] = (
    # Unsubstituted template tokens. build_icdc_system_prompt substitutes these;
    # reaching the output means either the substitution failed or the model copied
    # the literal token. Both are defects and neither is subtle.
    # The live tier's four tokens come first; the two retired ones stay because an
    # older artifact being re-scored must still trip on them.
    ("template placeholder", r"SITUATION_WORD_MIN|SITUATION_WORD_MAX|SITUATION_PARA_WORDS|"
                             r"SITUATION_PARA_HINT|SITUATION_WORD_FLOOR|SITUATION_WORD_TARGET"),
    # <slot> placeholders from the self-report tail spec. The exhibit-shape slots
    # ("the figure", "three to six words") went with K3; the tail's own slots did not.
    ("unfilled <slot>", r"<\s*(?:role|constraint|their interest|course of action|"
                       r"the figure|what the \w+ figure|three to six words|name/role|"
                       r"what conflicts)"),
    # Our own prompt's section labels, as headings. All-caps and anchored to a line
    # so a sentence mentioning "the quality bar for suppliers" cannot trip it.
    ("prompt section label", r"^\s*(?:QUALITY BAR|DIFFICULTY OVERRIDE|SECTION ORDER|"
                            r"REQUIRED STRUCTURE|CORE RULES|ABOUT THE EXAMPLE ROLEPLAY|"
                            r"SELF-REPORT TAIL|FORMATTING REMINDER|ORIGINALITY REMINDER|"
                            r"DIFFICULTY REMINDER|ADDITIONAL CONTEXT|"
                            r"PERFORMANCE INDICATORS TO ASSESS|EXAMPLE ROLEPLAY)"
                            r"\s*[:/]?\s*$"),
    # A knob id printed with its own name -- "K3 — QUANTITATIVE EXHIBIT". The knob
    # id alone is deliberately NOT matched: "K3" is a plausible product code, and a
    # gate that rejects a scenario for naming a part number is worse than the leak.
    ("knob id", r"\b[FK][1-8]\s*[—–:-]\s*(?:ONE SCENARIO|ROLES, NOT A CAST|NO EXHIBIT|"
                r"LENGTH|NO TELEGRAPHING|STAKEHOLDERS|HARD CONSTRAINTS|QUANTITATIVE EXHIBIT|"
                r"DECIDABLE|NO DOMINANT OPTION|JUDGE QUESTIONS|DENSITY|DO NOT RESOLVE)"),
    # The worked example's OWN content. K3's shape example says "invent entirely
    # different figures ... never reuse these labels or numbers"; copying it is the
    # exact failure mode that produced "EXHIBIT 1: WHAT THE FIGURES SHOW".
    ("copied worked example", r"DELIVERY COSTS BY REGION|(?:Northern|Southern) route, cost per delivery|"
                              r"Contracted rate ceiling per delivery"),
    # Meta-instruction prose. Each of these exists only in our prompts.
    ("meta-instruction", r"materially harder|shows FORMAT ONLY|the example roleplay|"
                         r"District-level scenario|ICDC\+|countable floors|countable rules|"
                         r"396 corpus roleplays|0 of 396|corpus roleplays|"
                         r"this event is presented to one judge|"
                         r"do not mention this brief|machine-checked against the prose|"
                         r"removed before the roleplay is stored|never seen by a competitor|"
                         r"invent the company name, the people, and the figures yourself"),
    # A self-report tail inside the body. split_self_report() removes the real one,
    # so a marker still present means the model emitted a second block or opened one
    # mid-document -- either way a competitor would read it.
    ("stray self-report", r"===\s*(?:END\s+)?SELF-REPORT\s*==="),
)

_PROMPT_LEAK_COMPILED: Tuple[Tuple[str, "re.Pattern[str]"], ...] = tuple(
    (label, re.compile(pattern, re.I | re.M)) for label, pattern in _PROMPT_LEAK_MARKERS
)


def check_prompt_leak(text: str) -> List[str]:
    """Authoring-apparatus text that reached the roleplay ([] = clean). No model call.

    Runs on the BODY (self-report tail already split off). This is not a difficulty
    knob -- it is a correctness check on a surface a competitor reads, and it is a
    BANK acceptance criterion (§6e) rather than a day one, because a leak that
    enters the shelf is served every cycle instead of once.

    Like every list in this module it can only recognise wording it has already
    seen. `check_prompt_leak(...) == []` means "no known apparatus marker is
    present," never "nothing leaked."
    """
    issues: List[str] = []
    for label, pattern in _PROMPT_LEAK_COMPILED:
        hits = {m.group(0).strip() for m in pattern.finditer(text)}
        if hits:
            shown = ", ".join(repr(h[:48]) for h in sorted(hits)[:3])
            issues.append(f"prompt-leak ({label}): {shown}")
    return issues


# SECOND PERSON (§6e, found reading the OQ9 chunking arms). A real DECA event
# situation addresses the competitor directly -- "You are Jordan Ellery, Director of
# Guest Loyalty..." -- because the competitor IS the character. An `--chunk 10` agent
# writing ten roleplays in one context drifted wholesale into third-person reportage
# ("Casey Blevins is the Director of Fleet and Inventory..."), and all ten passed every
# other check in this module.
#
# THE TEST IS ZERO OCCURRENCES, NOT "OPENS WITH 'YOU'", and the difference is the
# whole calibration. 396 of 396 corpus situations DO open with "You ", so an opener
# test would look tempting -- but our own clean output does not always (one chunk-1
# roleplay opens "As Director of Human Resources ... at Cascade MedLink, you ..."),
# and a gate that rejects that is rejecting good work to enforce a house style.
# Absence of any second-person reference anywhere in the situation is the categorical
# signal, validated in both directions per §5c:
#
#     396 real DECA corpus situations       0 flagged
#     the 7 committed archive fixtures      0 flagged
#     `--chunk 1` / `--chunk 5` arms        0 of 20 flagged
#     the `--chunk 10` arm                 10 of 10 flagged
#
# BANK-ONLY, and deliberately not folded into check_icdc_shape() -- exactly the
# reasoning check_prompt_leak carries. Voice is not a difficulty knob, and moving the
# day publish bar would invalidate the pass rate `fill_buffer.py --min-pass 22` was
# derived from.
_SECOND_PERSON = re.compile(r"\byou(?:r|rs|rself)?\b", re.I)


def check_participant_voice(situation_slice: str) -> List[str]:
    """Does the situation address the competitor at all ([] = it does). No model call.

    Takes the SITUATION SLICE, not the whole body: the participant instructions and the
    judge characterization are second person in every roleplay ever written, including
    the third-person ones, so running this over the body would never fire.
    """
    if not situation_slice.strip():
        return []
    if _SECOND_PERSON.search(situation_slice):
        return []
    return ["voice: the situation never addresses the participant (no 'you'/'your') -- "
            "a DECA event situation is written in second person (396 of 396 in the corpus)"]


def check_icdc_shape(
    text: str,
    event_cfg: Dict,
    *,
    situation_slice: Optional[str] = None,
    judge_section: Optional[str] = None,
) -> List[str]:
    """Deterministic ICDC-tier issues ([] = passes the countable bar). No model call.

    Measured against real published DECA material, which is the acceptance test
    this replaces the retired ICDC+ bar to satisfy: see the module docstring for
    the 0-of-396 number the old knob set produced and why that was the defect.

    `situation_slice` / `judge_section` let the caller pass the slices
    generate_roleplay already computes; both are derived here if omitted.
    """
    issues: List[str] = []

    if situation_slice is None or judge_section is None:
        jpos = re.search(r"^JUDGE ROLE-PLAY CHARACTERIZATION\s*:?\s*$", text, re.M | re.I)
        sit_label = "CASE STUDY SITUATION" if event_cfg.get("format") == "team" else "EVENT SITUATION"
        spos = re.search(rf"^{sit_label}\s*:?\s*$", text, re.M | re.I)
        if situation_slice is None:
            situation_slice = text[spos.start() : jpos.start() if jpos else len(text)] if spos else ""
        if judge_section is None:
            judge_section = text[jpos.start() :] if jpos else ""

    # F7 -- density. The per-EVENT band, failing in BOTH directions. The direction
    # is carried IN the issue string rather than left to the caller to infer,
    # because the day path's second pass only ever LENGTHENS: see F7_SHORT /
    # f7_too_short above.
    lo, hi = situation_word_band(event_cfg)
    words = situation_word_count(situation_slice)
    if words < lo:
        issues.append(f"F7: situation is {words} words, {F7_SHORT} of {lo} (band {lo}-{hi})")
    elif words > hi:
        issues.append(f"F7: situation is {words} words, {F7_LONG} of {hi} (band {lo}-{hi})")

    # F3 -- NO exhibit. This is the exact inverse of the retired K3, which
    # REQUIRED a labelled data block with >= 4 decision-bearing numbers. Zero of
    # the 396 real DECA roleplays in the corpus carry one, and requiring it is
    # what turned judgment cases into arithmetic problems. `find_exhibit` is kept
    # unchanged and simply read the other way round -- it already knows the
    # difference between a data block and DECA's own all-caps section headers,
    # which cost two rounds of debugging to get right.
    heading, _ = find_exhibit(text)
    if heading is not None:
        issues.append(
            f"F3: the case carries a data exhibit ('{heading[:50]}'); DECA publishes none "
            "(0 of 396 corpus roleplays) -- put any figure the decision needs in the prose"
        )

    # F6 -- judge questions: a RANGE. No analytic-verb test and no counter-argument
    # test; both were rubric register and both are why 396 of 396 real roleplays
    # failed the retired K6.
    questions = judge_questions(judge_section)
    if len(questions) < MIN_JUDGE_QUESTIONS:
        issues.append(
            f"F6: {len(questions)} numbered judge question(s), DECA asks "
            f"{MIN_JUDGE_QUESTIONS}-{MAX_JUDGE_QUESTIONS}"
        )
    elif len(questions) > MAX_JUDGE_QUESTIONS:
        issues.append(
            f"F6: {len(questions)} numbered judge question(s), ceiling is "
            f"{MAX_JUDGE_QUESTIONS} (2 in 302 of 396 corpus roleplays, 3 in 89)"
        )

    # F8 -- blatant resolutions, in the situation only. One real corpus roleplay
    # (RFSM district_2025_1) trips this on the literal phrase "there is only one
    # option", so the list is known to carry a 1-in-396 false-positive rate
    # against DECA's own prose. That is the accepted cost of a phrase list; do not
    # widen it without re-running the corpus check.
    sit_lower = " ".join(situation_slice.lower().split())
    hits = [ph for ph in TELEGRAPH_PHRASES if ph in sit_lower]
    if hits:
        issues.append(f"F8: situation telegraphs the answer: {', '.join(repr(h) for h in hits)}")

    return issues
