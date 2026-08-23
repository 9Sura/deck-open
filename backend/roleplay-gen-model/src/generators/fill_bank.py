#!/usr/bin/env python3
"""Plan 03 §6e -- the bank authoring driver. Fills SHELVES, not days.

D10 split `fill_buffer.py` in two. This is the half that MAKES roleplays and has
no notion of a calendar; `deal_days.py` (§6d, build-order step 13) is the half
that fills days and has no notion of a model. `fill_buffer.py` itself stays as
the proven $0 Ollama day path.

WHAT THE SPLIT BUYS, and it is not cost (§4a). Under a daily batch, quality
control ran AGAINST THE CLOCK: a day had to be written, so a marginal roleplay
either shipped or the batch aborted, and `--min-pass` existed to arbitrate that.
A bank has no clock. A candidate that fails is simply not banked and nothing
downstream notices, so **`--min-pass` does not exist here and must not be
reintroduced** -- D10 deletes the question rather than answering it.

BANK ACCEPTANCE IS STRICTER THAN DAY ACCEPTANCE WAS, deliberately: a banked
roleplay is served for the shelf's whole lifetime, so a defect costs one bad day
per cycle rather than one bad day. A candidate enters the bank only if ALL of:

    validate_roleplay()      == []  structure + verbatim PIs + exemplar originality
    check_icdc_shape()       == []  F3/F6/F7-band/F8-blatant
    check_prompt_leak()      == []  §4f -- and the reason it is new is below
    check_participant_voice()== []  the situation is second person (the OQ9 read)
    company reuse            == {}  §4e, shelf-wide, exact match
    shelf similarity      < thresh  §4e -- LOG-ONLY until calibrated (step 7)

Anything else is DISCARDED AND RE-AUTHORED. Nothing is repaired into the bank
under time pressure, because there is no time pressure.

WHY THE PROMPT-LEAK CHECK HAD TO LAND BEFORE THE FIRST TRANCHE (§4f): the gate
never counted it, and 2 of the 7 committed fixtures echo the authoring prompt's
own "QUALITY BAR" checklist into text a competitor reads. Under a day that is one
bad day; under a shelf it is served every cycle.

THE AUTHOR (§4d). `--author sonnet` (default) does NOT call a model from Python
-- Claude Code subagents are the author, so this runs in two phases, the same
shape `build_prompt.py` uses on the question-bank side:

    1. PLAN   fill_bank.py [--probe|--depth N]        -> prompts/ + work-order.json
    2. AUTHOR (subagents read a prompt, write authored/<slug>.txt)
    3. INGEST fill_bank.py --ingest                   -> gate, then bank or reject

`--author ollama` runs end-to-end in-process via `generate_one()` instead, at
~300-430 s per roleplay, and is the arm to use when you would rather spend
wall-clock than session budget.

NOTHING FANS OUT UNTIL THE PROBE IS READ (§4d, generalising `plan_slice.py`'s
PROVEN_AREAS rule). `--probe` authors ONE event per format family, alone. A gate
miss in a probe is attributable; a gate miss across 28 concurrent events is not.

Usage
  python fill_bank.py --status                      # shelf depth per event, exits
  python fill_bank.py --probe --dry-run             # the work order, zero model calls
  python fill_bank.py --probe                       # write probe prompts
  python fill_bank.py --ingest                      # gate what the subagents wrote
  python fill_bank.py --events HRM --depth 30       # a real shelf extension
  python fill_bank.py --events HRM --depth 30 --chunk 5   # 5 roleplays per agent (OQ9)
  python fill_bank.py --author ollama --events HRM --depth 2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bank  # noqa: E402
import generate_roleplay as g  # noqa: E402
import icdc_gate as gate  # noqa: E402
import parse_roleplay as pr  # noqa: E402
import seed_axes  # noqa: E402

DEFAULT_OUT = pr.DEFAULT_OUT
DEFAULT_WORK_DIR = pr.BASE_DIR / "output" / "bank-work"
BARE_BRIEF = pr.BASE_DIR / "src" / "prompts" / "authoring-bank-bare.txt"

# §4c, settled at build-order step 10 (2026-08-05): 30 per event = 840 roleplays
# and a ~1-month repeat cycle. This is the FLAG DEFAULT, not a committed tranche
# size -- tranche 1's depth is decided at step 12 from the probe's measured cost
# per roleplay, because §4c's token figures are explicitly order-of-magnitude and
# the question-bank precedent is that repair rounds can exceed the authoring
# (§10-8: 147.2k repairing what 116.6k wrote).
# Depth is a SHELF, not a target: extend the thinnest events first afterward, the
# way pi_deficit.py drives the question bank rather than a flat quota.
DEFAULT_DEPTH = 30

# EXPLICITLY UNCALIBRATED, and one step further from calibrated than it looks.
# 0.4 was set against real District PDFs whose shared boilerplate put the baseline
# at 0.05-0.22. 0.5 was then guessed for cross-DAY comparison of our own output.
# THIS is shelf-wide comparison of our own output at FULL LENGTH (bank.py explains
# why the two numbers are not interchangeable), so it is a placeholder inherited
# from a placeholder. Tranche 1 produces the first real distribution; step 7 sets
# p95 + 0.10. Do not treat this number as measured.
DEFAULT_SIMILARITY_THRESHOLD = 0.5

# §4d: one event per format family, plus PFL. HRM series / PBM principles / BLTDM
# team covers the three templates; PFL is the sole `career_cluster: null` event
# and the source of the §3h defect, so it is probed separately rather than
# assumed fixed.
PROBE_EVENTS = ("HRM", "PBM", "BLTDM", "PFL")

# OQ7 arm (a): the District exemplar is withheld from the ICDC prompt because it
# dragged a 14B model toward District complexity (summary 03 measured 0.62 ->
# 0.05 similarity purely from withholding it). Whether that is right for Sonnet is
# UNMEASURED -- showing it may improve format adherence without the cost.
EXEMPLAR_ARMS = ("withheld", "shown")


# ----------------------------
# What the gate cannot check (§4f, §5c) -- printed, never assumed
# ----------------------------
COVERAGE_NOTE = """\
WHAT THIS BAR DOES NOT CHECK -- read before trusting a PASS
  F1 one scenario, one judge             NOT VERIFIED (no referee, D4)
  F4 decidable from the given facts      NOT VERIFIED
  F8 subtle telegraphs                   NOT VERIFIED (blatant phrases only)
  F2 at most 2 parties besides the judge   self-report cross-check RECORDED, NOT GATING
  F5 >=2 options, each with a real cost    self-report cross-check RECORDED, NOT GATING
  prompt leakage                         phrase list -- recognises wording it has SEEN
  shelf similarity                       computed, LOG-ONLY (threshold uncalibrated)

D4 stands: there is no model referee, and the author being Claude does not make
Claude the judge. A stronger author probably satisfies F1/F4/subtle-F8 more often
and NOTHING HERE MEASURES WHETHER IT DOES. An empty issue list means "nothing
countable is wrong", never "this roleplay is ICDC-hard". No string anywhere may
claim verified difficulty; the ceiling is "harder than the district-level
material DECA publishes"."""


# ----------------------------
# The work order (zero model calls)
# ----------------------------
def resolve_item(
    code: str, seed_id: str, *, exemplar: str, shelf: Sequence[Dict]
) -> Dict:
    """Everything about one candidate that is decided BEFORE a model runs.

    Seeded on `(code, seed_id)` rather than `(code, date)` -- same SHA-256
    construction with the date removed (§6e). Never Python's `hash()`:
    PYTHONHASHSEED randomizes str hashing per process, which `seed_axes.py`
    already paid for once and which would silently break "re-resolving a work
    order reproduces it".

    SEED ID IS NOT BANK ID, and separating them is what makes the OQ7 A/B honest.
    A probe authors the SAME resolved roleplay twice -- same PIs, same axes, same
    everything -- varying ONLY whether the exemplar is shown, because otherwise
    the arms differ in two ways at once and the comparison says nothing. Both arms
    therefore share a seed id. The bank id is assigned at WRITE time from the live
    shelf (`bank.next_id`), which also fixes a quieter bug: an id reserved at plan
    time goes stale the moment anything else banks in between.
    """
    import random  # noqa: PLC0415

    cfg = g.EVENTS[code]
    random.seed(f"{code}:{seed_id}")
    pi_by_area = g.load_pi_by_area(cfg)
    if not pi_by_area:
        raise RuntimeError(f"no performance indicators available for {code}")
    pi_items, declared_area = g.select_event_pis(pi_by_area, cfg)

    fmt = cfg.get("format", "series")
    return {
        "slug": f"{seed_id.lower()}-{exemplar}",
        "code": code,
        "seed_id": seed_id,
        "format": fmt,
        "exemplar": exemplar,
        # The F7 length band, per EVENT: 0.8x-1.4x this event's own measured corpus
        # mean. The author and the gate render the same pair, so the stated number and
        # the enforced number cannot drift apart.
        "band": list(gate.situation_word_band(cfg)),
        "declared_area": declared_area,
        # The FULL selection record, not the bare PI strings this used to flatten to:
        # `area` and `role` are what D5 puts in the artifact, and the flattening threw
        # them away one step before anything downstream could have noticed.
        "pi_items": pi_items,
        "axes": seed_axes.pick_for_bank(code, seed_id, shelf_axes=bank.shelf_axes(shelf)),
    }


def build_work_order(
    out_dir: Path, codes: Sequence[str], depth: int, *, exemplar_arms: Sequence[str]
) -> List[Dict]:
    """Which roleplays are owed, per event, to reach `depth`. Zero model calls."""
    items: List[Dict] = []
    for code in codes:
        shelf = bank.load_shelf(out_dir, code)
        owed = max(0, depth - len(shelf))
        # Simulate the shelf growing as the batch is planned, so the axes spread
        # ACROSS the batch instead of every candidate drawing against the same
        # starting state. Without this a 30-item work order would cluster.
        simulated = list(shelf)
        for n in range(owed):
            seed_id = bank.next_id(out_dir, code, offset=n)
            for arm in exemplar_arms:
                items.append(resolve_item(code, seed_id, exemplar=arm, shelf=simulated))
            simulated.append({"meta": {"generator": {"axes": items[-1]["axes"]}}})
    return items


# ----------------------------
# Prompt assembly
# ----------------------------
def build_prompt_text(item: Dict, *, brief: Optional[Path]) -> Dict[str, str]:
    """(system, user) for one candidate. `examples` is the OQ7 arm-(b) switch."""
    cfg = g.EVENTS[item["code"]]

    # Loaded for SCORING always; shown to the author only on the `shown` arm.
    # Keeping the two lists separate is not a nicety: conflating them makes
    # scenario_similarity() short-circuit to 0.0 and validate_roleplay() skip the
    # originality check entirely, which silently voided a headline number once.
    import random  # noqa: PLC0415

    random.seed(f"{item['code']}:{item['seed_id']}")
    examples = g._load_examples_quiet(cfg)
    prompt_examples = examples if item["exemplar"] == "shown" else []

    system = g.build_icdc_system_prompt(cfg, brief)
    user = g.build_user_message(
        cfg,
        "ICDC",
        item["declared_area"],
        item["pi_items"],
        prompt_examples,
        seed_axes.as_context(item["axes"], cfg["event_code"]),
        "",
    )
    return {"system": system, "user": user}


# CHUNKING (OQ9). `--chunk N` packs N roleplays into ONE prompt file, so the shared
# system brief -- ~15.7k of the ~18.1k-char single prompt -- is read once per agent
# instead of once per roleplay. Two things are deliberate about the shape:
#
#   * A chunk never spans events or exemplar arms. `build_icdc_system_prompt` is a
#     function of the event config and the brief, so a mixed chunk would have to print
#     a second system brief and the amortisation it exists for would be gone.
#   * ONE FILE PER ROLEPLAY ON DISK, always. `--ingest`, the gate and every score key
#     on `<slug>.txt`; a combined output file would need a splitter, and a splitter
#     that mis-splits does so silently on text nothing else re-reads.
#
# At `--chunk 1` the prompt bytes are IDENTICAL to the pre-chunking builder, so the
# probe's measured 66.2k/roleplay stays a comparable baseline rather than a number
# taken against a prompt that has since moved.
_AGENT_ENVELOPE = """\
You are authoring ONE DECA roleplay for the permanent roleplay bank.

Write the finished roleplay to this exact path, and write nothing else anywhere:

    {out_path}

Output the roleplay as PLAIN TEXT exactly as the brief specifies -- the section
headers, then the self-report tail. No preamble, no commentary, no markdown code
fence around it, no explanation of what you did. A deterministic parser reads that
file; anything that is not the roleplay corrupts it.

Two things worth knowing, because they are measured rather than assumed:

  * Your situation section must land inside a word RANGE of {lo} to {hi} words. The
    range is this event's own authentic length, scaled up; both ends are real, and
    a roleplay that misses it is discarded, not repaired. The previous author on
    this pipeline plateaued at ~290 words and needed a second pass to clear the
    bottom of its range; reach it the first time, and stop before the top.
  * Do not write ANYTHING about these instructions into the roleplay. Section
    labels from this brief, knob names, word counts and floors are all checked for
    and all cause a discard. Two of the seven roleplays in the current archive
    leaked this brief's own checklist into text a student reads.

=== SYSTEM BRIEF ===

{system}

=== ROLEPLAY PARAMETERS ===

{user}
"""


_AGENT_ENVELOPE_CHUNK = """\
You are authoring {n} DECA roleplays for the permanent roleplay bank.

They share ONE system brief, printed once below. Each roleplay then gets its own
parameters block naming its own output path. Write each finished roleplay to the
exact path named in its block, and write nothing else anywhere:

{path_list}

That is {n} files, one roleplay per file. Do not concatenate them, do not write an
index, do not write a report of what you did.

Output each roleplay as PLAIN TEXT exactly as the brief specifies -- the section
headers, then the self-report tail. No preamble, no commentary, no markdown code
fence around it, no explanation of what you did. A deterministic parser reads each
file; anything that is not the roleplay corrupts it.

Two things worth knowing, because they are measured rather than assumed:

  * Each situation section must land inside a word RANGE named in its own block --
    that event's own authentic length, scaled up. Both ends are real, and a roleplay
    that misses it is discarded, not repaired. The previous author on this pipeline
    plateaued at ~290 words and needed a second pass to clear the bottom of its
    range; reach it the first time, and stop before the top, in every one.
  * Do not write ANYTHING about these instructions into any roleplay. Section labels
    from this brief, knob names, word counts and floors are all checked for and all
    cause a discard. Two of the seven roleplays in the current archive leaked this
    brief's own checklist into text a student reads.

THE {n} ROLEPLAYS ARE INDEPENDENT. They share a brief and nothing else -- different
performance indicators, different seed axes, different businesses. Do not carry a
company, a character or a scenario from one into another; the bank rejects a
repeated company name outright.

=== SYSTEM BRIEF (applies to all {n} roleplays) ===

{system}
"""

_CHUNK_ITEM = """
=== ROLEPLAY {i} of {n} -- write to {out_path} ===

Situation word range for this roleplay: {lo} to {hi} words.

{user}
"""


def chunk_items(items: Sequence[Dict], size: int) -> List[List[Dict]]:
    """Pack the work order into per-agent groups.

    Grouped by `(code, exemplar)` FIRST, because those are exactly the two fields the
    shared system brief is a function of -- a chunk that spans either would have to
    print two briefs and would amortise nothing. Order within a group is preserved,
    so a chunked work order runs the same candidates in the same sequence as an
    unchunked one.
    """
    if size < 1:
        raise ValueError("--chunk must be >= 1")
    groups: Dict[tuple, List[Dict]] = {}
    for item in items:
        groups.setdefault((item["code"], item["exemplar"]), []).append(item)
    return [
        group[i:i + size]
        for group in groups.values()
        for i in range(0, len(group), size)
    ]


def write_prompts(
    items: Sequence[Dict], work_dir: Path, *, brief: Optional[Path], chunk: int = 1
) -> int:
    """Write the prompt files. Returns how many were written (agents to launch)."""
    prompts = work_dir / "prompts"
    authored = work_dir / "authored"
    prompts.mkdir(parents=True, exist_ok=True)
    authored.mkdir(parents=True, exist_ok=True)

    written = 0
    for n, group in enumerate(chunk_items(items, chunk), 1):
        parts = [build_prompt_text(item, brief=brief) for item in group]
        out_paths = [authored / f"{item['slug']}.txt" for item in group]

        if len(group) == 1:
            # Byte-identical to the pre-chunking builder, deliberately: the probe's
            # 66.2k/roleplay is the baseline every chunked arm is measured against,
            # and it stops being one if this branch drifts.
            name = f"{group[0]['slug']}.txt"
            text = _AGENT_ENVELOPE.format(
                out_path=out_paths[0],
                lo=group[0]["band"][0],
                hi=group[0]["band"][1],
                system=parts[0]["system"],
                user=parts[0]["user"],
            )
        else:
            code = group[0]["code"].lower()
            name = f"chunk{n:02d}-{code}-{group[0]['exemplar']}.txt"
            text = _AGENT_ENVELOPE_CHUNK.format(
                n=len(group),
                path_list="\n".join(f"    {p}" for p in out_paths),
                system=parts[0]["system"],
            ) + "".join(
                _CHUNK_ITEM.format(
                    i=i, n=len(group), out_path=p,
                    lo=item["band"][0], hi=item["band"][1], user=part["user"],
                )
                for i, (item, part, p) in enumerate(zip(group, parts, out_paths), 1)
            )

        (prompts / name).write_text(text, encoding="utf-8")
        written += 1
        for item, out_path in zip(group, out_paths):
            item["prompt_file"] = str(prompts / name)
            item["authored_file"] = str(out_path)
            # One work-order entry per ROLEPLAY regardless of packing -- `--ingest`
            # walks candidates, not agents. These two fields are the only record of
            # which agent a candidate was authored by, and the cost measurement
            # (OQ9) is read back through them.
            item["chunk"] = n
            item["chunk_size"] = len(group)

    (work_dir / "work-order.json").write_text(
        json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return written


# The criteria the BANK path runs, in the order score_candidate runs them. Recorded
# into meta.gate.checks; what is NOT here is in icdc_gate.UNVERIFIED.
BANK_GATE_CHECKS: Tuple[str, ...] = (
    "structure",             # validate_roleplay: headers, order, sections
    "verbatim_pis",          # validate_roleplay: every selected PI reproduced
    "skills_verbatim",       # validate_roleplay: plan 04 §2's official block
    "declared_area_echo",    # validate_roleplay: the INSTRUCTIONAL AREA line
    "exemplar_originality",  # validate_roleplay: not a copy of a shown example
    "pi_quota",              # icdc_gate.check_pi_quota (plan 05 §3)
    "axis_membership",       # seed_axes.check_axis_membership (plan 04 §3.2)
    "icdc_shape",            # F3/F6/F7-band/F8-blatant
    "prompt_leak",           # 03-plan §4f
    "participant_voice",     # 03-plan §6e
    "shelf_company_reuse",   # bank.corporate_names, exact match
    "self_report",           # F2/F5 cross-check -- RECORDED, not gating
)


# ----------------------------
# Scoring one candidate (zero model calls)
# ----------------------------
def score_candidate(
    text: str,
    item: Dict,
    *,
    out_dir: Path,
    shelf: Sequence[Dict],
    threshold: float,
    enforce_similarity: bool,
    enforce_self_report: bool,
) -> Dict:
    """Gate one authored roleplay against the BANK bar. Pure Python."""
    cfg = g.EVENTS[item["code"]]
    body, report = gate.split_self_report(text)
    pi_items = item["pi_items"]

    import random  # noqa: PLC0415

    random.seed(f"{item['code']}:{item['seed_id']}")
    examples = g._load_examples_quiet(cfg)

    structural = g.validate_roleplay(body, cfg, pi_items, examples, item["declared_area"])
    icdc_issues = gate.check_icdc_shape(body, cfg)
    leak_issues = gate.check_prompt_leak(body)
    report_issues = gate.check_self_report(body, report)

    # Plan 05 §3's quota, read off the SELECTION RECORD in exactly the shape the
    # banked file carries it (`performanceIndicators` + `instructionalArea`), so the
    # same call audits a whole shelf later. The selector guarantees the quota
    # structurally; what this asserts is that the guarantee reaches the artifact.
    quota_issues = gate.check_pi_quota(pi_items, item["declared_area"], cfg)
    # Plan 04 §3.2 step 4. Blocking now that every event has its own axes -- before
    # step 1b an off-domain output was the pipeline obeying its seed, not an author
    # failure. Pinned by meta.generator.axesHash (step 5) so the verdict stays
    # reproducible across a data edit.
    axis_issues = seed_axes.check_axis_membership(item["code"], item["axes"])

    situation = g._scenario_slice(body, g.situation_header(cfg))
    voice_issues = gate.check_participant_voice(situation)
    sim, nearest = bank.shelf_similarity(situation, shelf)
    reused = bank.reused_companies(situation, shelf)
    # The raw extractor's extra hits: repeated people and job titles. Worth a
    # human's eye across a shelf, never grounds to auto-discard -- see the
    # measured ~33% precision recorded in bank._CORPORATE_DESIGNATORS.
    repeated_loose = {
        n: w for n, w in bank.reused_companies(situation, shelf, strict=False).items()
        if n not in reused
    }

    novelty_issues: List[str] = []
    if reused:
        # Exact match, not a calibrated threshold -- so this one enforces (§4e).
        novelty_issues.append(
            "novelty: company name(s) already in this shelf: "
            + ", ".join(f"{n} ({where})" for n, where in sorted(reused.items()))
        )
    similarity_note: List[str] = []
    if sim >= threshold:
        similarity_note.append(
            f"novelty: {sim:.0%} similar to {nearest} (threshold {threshold:.0%}, "
            + ("ENFORCED" if enforce_similarity else "LOGGED ONLY -- uncalibrated")
            + ")"
        )

    blocking = [
        *structural,
        *quota_issues,
        *axis_issues,
        *icdc_issues,
        *leak_issues,
        *voice_issues,
        *novelty_issues,
        *(similarity_note if enforce_similarity else []),
        *(report_issues if enforce_self_report else []),
    ]

    return {
        **item,
        "raw": text,
        "body": body,
        "structural_issues": structural,
        "quota_issues": quota_issues,
        "axis_issues": axis_issues,
        "icdc_issues": icdc_issues,
        "leak_issues": leak_issues,
        "voice_issues": voice_issues,
        "self_report_issues": report_issues,
        "novelty_issues": novelty_issues,
        "similarity_note": similarity_note,
        "blocking": blocking,
        "accepted": not blocking,
        # Kept so `--no-write` can still grow an in-memory shelf: the shelf-wide half
        # of the bar (similarity, company reuse) is the half that only exists ACROSS
        # candidates, and scoring a batch without it reports 0.00 for every row.
        "situation": situation,
        "situation_words": gate.situation_word_count(situation),
        "exemplar_similarity": round(g.scenario_similarity(body, cfg, examples), 4),
        "shelf_similarity": round(sim, 4),
        "shelf_nearest": nearest,
        "reused_companies": reused,
        "repeated_loose": repeated_loose,
    }


def report_candidate(scored: Dict, n: int, total: int) -> None:
    verdict = "BANK" if scored["accepted"] else "DISCARD"
    print(
        f"  [{n}/{total}] {scored['seed_id']:11} {scored['exemplar']:8} {verdict:7} "
        f"words={scored['situation_words']:>4} (band {scored['band'][0]}-{scored['band'][1]})  "
        f"ex-sim={scored['exemplar_similarity']:.2f}  shelf-sim={scored['shelf_similarity']:.2f}"
    )
    for issue in scored["blocking"]:
        print(f"          x {issue}")
    # Non-blocking findings are printed too, and marked, so "recorded not gating"
    # is visible in the run rather than only in a docstring.
    for issue in scored["self_report_issues"]:
        print(f"          . (recorded, not gating) {issue}")
    if scored.get("repeated_loose"):
        names = ", ".join(f"{n} ({w})" for n, w in sorted(scored["repeated_loose"].items()))
        print(f"          . (recorded, not gating) novelty: repeated name(s), not brand-shaped: {names}")
    for issue in scored["similarity_note"]:
        if issue not in scored["blocking"]:
            print(f"          . (recorded, not gating) {issue}")


# ----------------------------
# Banking an accepted candidate
# ----------------------------
def bank_candidate(scored: Dict, out_dir: Path, *, model: str) -> Path:
    """Assign an id and write. The id comes from the LIVE shelf, not the work order.

    Ids are assigned by identity and never renumbered (§4b), so the only safe
    moment to take one is immediately before the write -- a plan-time reservation
    goes stale if a discard leaves a gap or another run banks in between.
    """
    bank_id = bank.next_id(out_dir, scored["code"])
    roleplay = pr.parse_roleplay(
        scored["raw"],
        g.EVENTS[scored["code"]],
        bank_id=bank_id,
        # The selection record and the declared area: parse_roleplay cannot see either
        # (nothing in the authored text names an instructional area) and refuses to
        # guess, so D5's provenance reaches the artifact from here or not at all.
        pi_items=scored["pi_items"],
        declared_area=scored["declared_area"],
        tier="icdc",
        model=model,
        passes=scored.get("passes", 1),
        # parse_roleplay cannot see the exemplar, the PI list or the shelf, so the
        # driver hands it the verdict it reached on those. Leak issues ride here
        # rather than inside check_icdc_shape on purpose: a prompt leak is not a
        # difficulty knob, and folding it into the shape gate would move the DAY
        # publish bar that fill_buffer.py's pass rate was measured against.
        extra_issues=[
            *scored["structural_issues"],
            *scored["quota_issues"],
            *scored["axis_issues"],
            *scored["leak_issues"],
            *scored["voice_issues"],
            *scored["novelty_issues"],
        ],
        # What actually ran on the BANK path (plan 04 §5). Named per criterion
        # rather than as "validate_roleplay", because a reader wants to know that
        # the skills block was compared verbatim and the domain was not classified.
        checks=BANK_GATE_CHECKS,
    )
    meta = roleplay["meta"]
    meta["generator"]["axes"] = scored["axes"]
    # The axes DATA this draw resolved against (plan 04 §3.2 step 5). Recorded
    # beside the values themselves: the membership check above reads a mutable file,
    # so without this its verdict is not reproducible after a data edit.
    meta["generator"]["axesHash"] = seed_axes.axes_content_hash()
    meta["generator"]["exemplar"] = scored["exemplar"]
    meta["bank"] = {
        # The seed the PIs and axes were drawn from. Kept because it is the only
        # way back from a banked entry to the work order that produced it once the
        # two have diverged (a discard leaves the ids out of step, by design).
        "seedId": scored["seed_id"],
        "shelfSimilarity": scored["shelf_similarity"],
        "shelfNearest": scored["shelf_nearest"],
        "exemplarSimilarity": scored["exemplar_similarity"],
        "gateVersion": gate.GATE_VERSION,
    }
    return bank.write_entry(out_dir, roleplay)


# ----------------------------
# --ingest
# ----------------------------
def ingest(work_dir: Path, out_dir: Path, args) -> None:
    order_path = work_dir / "work-order.json"
    if not order_path.is_file():
        sys.exit(f"no work order at {order_path} -- run the plan phase first")
    items = json.loads(order_path.read_text(encoding="utf-8"))

    print(f"work order : {order_path}  ({len(items)} candidate(s))")
    print(f"bank       : {bank.bank_dir(out_dir)}")
    print(f"similarity : {args.similarity_threshold} "
          f"({'ENFORCED' if args.enforce_similarity else 'logged only -- uncalibrated'})")
    print()

    # The shelf grows DURING ingest, so candidate 2 is compared against candidate
    # 1 if candidate 1 was banked. Without this an all-pairs check silently
    # degrades to "against what was already on disk when the batch started".
    shelves: Dict[str, List[Dict]] = {}
    accepted, discarded, missing = 0, 0, 0

    for n, item in enumerate(items, 1):
        authored = Path(item.get("authored_file") or (work_dir / "authored" / f"{item['slug']}.txt"))
        if not authored.is_file():
            print(f"  [{n}/{len(items)}] {item['seed_id']:11} {item['exemplar']:8} (not authored yet)")
            missing += 1
            continue

        code = item["code"]
        if code not in shelves:
            shelves[code] = bank.load_shelf(out_dir, code)

        scored = score_candidate(
            authored.read_text(encoding="utf-8"), item,
            out_dir=out_dir, shelf=shelves[code],
            threshold=args.similarity_threshold,
            enforce_similarity=args.enforce_similarity,
            enforce_self_report=args.enforce_self_report,
        )
        report_candidate(scored, n, len(items))

        if scored["accepted"] and not args.no_write:
            try:
                path = bank_candidate(scored, out_dir, model=args.model_label)
            except pr.PIProvenanceError as e:
                # An authored PI the selection record does not hold. The verbatim gate
                # above only checks that every SELECTED PI is present, so an extra or
                # reworded sixth bullet reaches here -- and it has no honest area. One
                # candidate is discarded; the batch is not, because aborting mid-ingest
                # leaves the shelf half-written for a defect in a single file.
                print(f"          x DISCARD (unbankable): {e}")
                discarded += 1
                continue
            entry = json.loads(path.read_text(encoding="utf-8"))
            shelves[code].append(entry)
            accepted += 1
        elif scored["accepted"]:
            # `--no-write` used to leave the in-memory shelf untouched, which silently
            # switched OFF the two criteria that only exist across a shelf: every row
            # printed `shelf-sim=0.00` and no company collision could ever be found,
            # on the exact runs (a scored batch nobody is banking yet) where reading
            # those numbers is the point. Only `id`/`situation` are needed downstream.
            shelves[code].append({"id": scored["seed_id"], "situation": scored["situation"]})
            accepted += 1
        else:
            discarded += 1

    print()
    print(f"accepted {accepted} · discarded {discarded} · not authored {missing}")
    if accepted and not args.no_write:
        manifest = bank.write_manifest(out_dir, pr.event_order(pr.load_events()))
        print(f"manifest : {manifest['totals']['roleplays']} roleplay(s) across "
              f"{manifest['totals']['events']} event(s); thinnest shelf {manifest['thinnestShelf']}")
    if discarded:
        print("\nDiscarded candidates are RE-AUTHORED, never repaired into the bank (§6e).")
    print()
    print(COVERAGE_NOTE)


# ----------------------------
# --author ollama (in-process, end to end)
# ----------------------------
def author_ollama(items: Sequence[Dict], out_dir: Path, args) -> None:
    """The $0 arm. ~300-430 s per roleplay; `generate_one` owns the model call."""
    print(f"model : {g.OLLAMA_MODEL} (backend: {g.LLM_BACKEND})")
    shelves: Dict[str, List[Dict]] = {}
    accepted = discarded = 0

    for n, item in enumerate(items, 1):
        code = item["code"]
        shelves.setdefault(code, bank.load_shelf(out_dir, code))
        started = time.monotonic()
        try:
            result = g.generate_one(
                code, date.today(), tier="icdc", quiet=True,
                bank_id=item["seed_id"], axes=item["axes"],
            )
        except Exception as e:  # noqa: BLE001 -- one bad candidate must not kill the batch
            print(f"  [{n}/{len(items)}] {item['seed_id']:11} ERROR {type(e).__name__}: {e}")
            discarded += 1
            continue

        scored = score_candidate(
            result["raw"], item, out_dir=out_dir, shelf=shelves[code],
            threshold=args.similarity_threshold,
            enforce_similarity=args.enforce_similarity,
            enforce_self_report=args.enforce_self_report,
        )
        scored["passes"] = result["passes"]
        report_candidate(scored, n, len(items))
        print(f"          ({time.monotonic() - started:.0f}s, {result['passes']} pass(es))")

        if scored["accepted"] and not args.no_write:
            path = bank_candidate(scored, out_dir, model=result["model"])
            shelves[code].append(json.loads(path.read_text(encoding="utf-8")))
            accepted += 1
        elif scored["accepted"]:
            accepted += 1
        else:
            discarded += 1

    print(f"\naccepted {accepted} · discarded {discarded}")
    if accepted and not args.no_write:
        bank.write_manifest(out_dir, pr.event_order(pr.load_events()))
    print()
    print(COVERAGE_NOTE)


# ----------------------------
# --status / --dry-run
# ----------------------------
def print_status(out_dir: Path, codes: Sequence[str], depth: int) -> None:
    print(f"bank : {bank.bank_dir(out_dir)}")
    shelves = {c: bank.shelf_depth(out_dir, c) for c in codes}
    total = sum(shelves.values())
    thinnest = min(shelves.values()) if shelves else 0

    for code in codes:
        n = shelves[code]
        owed = max(0, depth - n)
        flag = "" if not owed else f"  owes {owed}"
        print(f"  {code:6} {g.EVENTS[code].get('format','series'):10} depth {n:>4}{flag}")

    print(f"\ntotal      : {total} roleplay(s) across {len(codes)} event(s)")
    # §7's revision: shelf depth, not archive depth, is the number that can run
    # out -- a day needs one roleplay from EVERY event, so the runway is the
    # thinnest shelf. Reporting the total alone would read as runway it is not.
    print(f"runway     : {thinnest} day(s) at 28 events/day (the THINNEST shelf, not the total)")
    if thinnest < 14:
        print("\nWARNING: under 14 days of runway. A shelf extension is an authoring "
              "session you have to schedule, not a script you re-run (§7).")


def print_dry_run(items: Sequence[Dict]) -> None:
    print("DRY RUN -- no model calls, nothing written\n")
    by_code: Dict[str, List[Dict]] = {}
    for item in items:
        by_code.setdefault(item["code"], []).append(item)

    for code, group in by_code.items():
        cfg = g.EVENTS[code]
        lo, hi = gate.situation_word_band(cfg)
        print(f"=== {code} ({cfg.get('format','series')}, F7 band {lo}-{hi}, "
              f"{len(group)} candidate(s)) ===")
        for item in group:
            print(f"  {item['seed_id']:11} exemplar={item['exemplar']:8} "
                  f"declared: [{item['declared_area']}]")
            print(f"    axes: {item['axes']['industry']} | {item['axes']['company_stage']}")
            print(f"          {item['axes']['business_function']} | {item['axes']['dilemma_archetype']}")
            print(f"          {item['axes']['question_shape']}")
            for it in item["pi_items"]:
                print(f"      - ({it['role']:8}) [{it['area']}] {it['pi']}")
        print()
    print(f"{len(items)} candidate(s) in the work order")


# ----------------------------
# CLI
# ----------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Plan 03 §6e -- author the roleplay bank")
    ap.add_argument("--events", default="", help="comma-separated codes; default all 28")
    ap.add_argument("--depth", type=int, default=DEFAULT_DEPTH,
                    help=f"author until each shelf reaches N (default {DEFAULT_DEPTH})")
    ap.add_argument("--author", choices=("sonnet", "ollama"), default="sonnet",
                    help="sonnet = subagent authoring via prompt files (default); "
                         "ollama = in-process, the $0 arm")
    ap.add_argument("--chunk", type=int, default=1,
                    help="roleplays per subagent prompt file (default 1 -- one per agent, "
                         "so a gate miss is attributable). A chunk never spans events or "
                         "exemplar arms, and still writes one file per roleplay")
    ap.add_argument("--probe", action="store_true",
                    help="one event per format family (HRM/PBM/BLTDM/PFL), authored alone")
    ap.add_argument("--exemplar", choices=("withheld", "shown", "both"), default="withheld",
                    help="OQ7 arm (b): show the District exemplar to the author, or not. "
                         "'both' authors each candidate twice, one per arm (probe only)")
    ap.add_argument("--brief", choices=("bare", "full"), default="bare",
                    help="bare = authoring-bank-bare.txt (§4d, default); full = system.txt")
    ap.add_argument("--referee", default="off",
                    help="off (D4 -- there is no referee); a backend name is a MANUAL spot-check")
    ap.add_argument("--similarity-threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD)
    ap.add_argument("--enforce-similarity", action="store_true",
                    help="reject on shelf similarity. OFF until calibrated from tranche 1 (§4e)")
    ap.add_argument("--enforce-self-report", action="store_true",
                    help="reject on the F2/F5 self-report cross-check. OFF: §6e's acceptance "
                         "list does not include it, and summary 04 records it as a known gap")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="archive root (bank/ lives under it)")
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    ap.add_argument("--model-label", default="claude-sonnet-5",
                    help="recorded in meta.generator.model for subagent-authored entries")
    ap.add_argument("--ingest", action="store_true", help="gate authored files and bank what passes")
    ap.add_argument("--dry-run", action="store_true", help="print the work order, zero model calls")
    ap.add_argument("--status", action="store_true", help="print shelf depth per event and exit")
    ap.add_argument("--no-write", action="store_true", help="score but never write to the bank")
    args = ap.parse_args()

    events = pr.load_events()
    all_codes = pr.event_order(events)
    if args.probe:
        codes = list(PROBE_EVENTS)
    else:
        codes = [c.strip().upper() for c in args.events.split(",") if c.strip()] or all_codes
    unknown = [c for c in codes if c not in events]
    if unknown:
        sys.exit(f"unknown event(s): {', '.join(unknown)}")

    if args.status:
        print_status(args.out, all_codes if not args.events else codes, args.depth)
        return

    if args.referee != "off":
        print(f"[note] --referee {args.referee}: D4 dropped the model referee. This is a "
              "MANUAL spot-check only and never gates anything.\n")

    if args.ingest:
        ingest(args.work_dir, args.out, args)
        return

    arms = list(EXEMPLAR_ARMS) if args.exemplar == "both" else [args.exemplar]
    if args.exemplar == "both" and not args.probe:
        sys.exit("--exemplar both is a probe instrument (it doubles the work order); "
                 "pick one arm for a real shelf extension")

    # A probe authors ONE per event per arm regardless of --depth: its job is to be
    # read by a human, not to fill a shelf.
    depth = None
    if args.probe:
        items: List[Dict] = []
        for code in codes:
            shelf = bank.load_shelf(args.out, code)
            for arm in arms:
                items.append(
                    resolve_item(code, bank.next_id(args.out, code), exemplar=arm, shelf=shelf)
                )
    else:
        depth = args.depth
        items = build_work_order(args.out, codes, depth, exemplar_arms=arms)

    if not items:
        print(f"nothing owed: every selected shelf is already at depth {depth}")
        return

    if args.dry_run:
        print_dry_run(items)
        return

    if args.author == "ollama":
        author_ollama(items, args.out, args)
        return

    if args.chunk < 1:
        sys.exit("--chunk must be >= 1")
    if args.probe and args.chunk != 1:
        sys.exit("--probe authors each candidate ALONE (§4d); --chunk does not apply to it")

    brief = BARE_BRIEF if args.brief == "bare" else None
    written = write_prompts(items, args.work_dir, brief=brief, chunk=args.chunk)

    print(f"wrote {written} prompt(s) covering {len(items)} roleplay(s) "
          f"to {args.work_dir / 'prompts'}")
    print(f"brief : {'authoring-bank-bare.txt (§4d)' if brief else 'system.txt (full)'}")
    print(f"arms  : {', '.join(arms)}")
    print(f"chunk : {args.chunk} roleplay(s) per agent")
    if args.probe:
        print("\nPROBE -- author each of these ALONE, then READ THE OUTPUT before anything "
              "fans out.\nA gate miss in a probe is attributable; a gate miss across 28 "
              "concurrent events is not.")
    print(f"\nEach agent reads ONE prompt file and writes "
          f"{'ONE roleplay' if args.chunk == 1 else 'one file per roleplay'} to the path(s) "
          f"named\ninside it. Then gate and bank them:\n")
    print(f"  python {Path(__file__).name} --ingest --work-dir {args.work_dir}")
    print()
    print(COVERAGE_NOTE)


if __name__ == "__main__":
    main()
