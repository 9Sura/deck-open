#!/usr/bin/env python3
"""Build the scoped repair prompt for the rows check_authored named. No model.

WHY THIS EXISTS -- §10-5, measured 2026-07-29
----------------------------------------------
`check_authored.py` prints a repair scope ("hand the author ONLY these ids"), and
`apply_repair.py` merges the overlay that comes back. Between those two there was
nothing, so the prompt was assembled by hand each time -- which is exactly the step
the plan-10 guardrail forbids for authoring ("DO NOT paste payload rows into the
agent prompt by hand -- transcribing cand_ids/letters/bands is where a slice
silently breaks") and for the same reason.

Hand-assembly cost §10-5 two defects in one 5-item repair: the overlay came back with
`instructionalArea` dropped and `level` lowercased to "district". Both are now refused
by apply_repair's IDENTITY check, but the better fix is upstream -- state the rule in
the prompt and inline the exact values the author must copy, so there is nothing to
retype. This file does that.

It also fixes the other half of §10-5's repair bill. That agent cost 103k
tokens/item cumulative -- 4x the authoring rate -- because it took 11 tool calls,
9 of them Bash calls re-verifying its own option lengths. The gate is deterministic
and runs immediately afterwards for free, so the prompt now forbids shell
verification outright.

    # 1. gate, capturing the report
    python check_authored.py --payload P.json --part DIR/chunk2-part*.json \
        --list-key-longest --list-stem-pull > DIR/chunk2-gate.txt

    # 2. build the prompt from the gate's own findings (ids auto-derived)
    python build_repair_prompt.py --payload P.json --gate DIR/chunk2-gate.txt \
        --part DIR/chunk2-part*.json --out DIR/chunk2-repair.prompt.txt \
        --overlay "$(pwd)/DIR/chunk2-repair.json"

    # 3. one Sonnet agent, pointed at the prompt file. Then the apply_repair line
    #    this tool prints -- it carries `--also-freeze question` when no row in the
    #    batch was flagged for its stem, so the merge enforces the scope the prompt
    #    states rather than trusting it.
    python apply_repair.py --overlay DIR/chunk2-repair.json \
        --part <the files the scope named> --expect <the ids>

The prompt's scope is DERIVED, not fixed (issue #77): each row is offered only the
field its own gate lines name, and `explanation` is out of scope unless the gate
flagged the explanation itself. See STEM_FINDINGS below for why.

So is the COPY THROUGH block's `answer` (issue #89). Identity is read from the PAYLOAD
per field -- see PAYLOAD_ALIAS -- so a row whose authored letter is itself the defect is
told the ASSIGNED letter instead of being handed its own wrong one, and the printed
apply_repair line grows `--payload`, which is the only way that one change merges.

THE THREE ROUND GUARDS (issue #127) -- why this tool refuses things it used to build
------------------------------------------------------------------------------------
§10-13 spent 1.77M tokens on 275 of 695 items. Authoring was the cheapest of any
plan-10 slice (2.15k/item); the whole overrun was the repair tail, at 2.00x authoring
against a plan-10 norm of 0.41-1.13x. Three of the four causes were rules that already
existed IN PROSE -- in the plan, and in apply_repair's own closing line -- and were
skipped anyway. They are mechanical here now, because that is the only form of a rule
this toolchain has ever managed to keep (#76, #88, #89 are the same correction).

  1. A STALE GATE. Chunk 1 ran four repair rounds back to back, 12:07 to 12:35, with
     ONE re-gate -- after all four. It showed the batch had been clean since round 1
     (key-longest 49.0% -> 26.9%, LONGEST= 75.5% -> 98.1%, repair list down to 1 row)
     by which point rounds 3 and 4 had rewritten 15 more rows. A gate costs ZERO
     tokens. So: if any --part file is newer than the --gate report, the report
     predates the last merge and cannot say what is still broken. Refused.

  2. A SCOPE WIDER THAN THE GATE. The gates named ~33 rows across four chunks; 124
     distinct rows were repaired -- 45% of everything authored. The extra rows came
     from the model audits, whose own output says not to read them as a work order
     (`option tells` is lexical; `label divergence` is soft and noisy -- read the RATE
     against its baseline, never the row list). §10-11 already cut such a list from 19
     rows to 5 on a written criterion. So --ids may still widen the scope, but the
     criterion must be written down: --scope-reason, recorded in the sidecar.

  3. A SOLO ROUND UNDER THE POOLING FLOOR. The fixed agent startup was paid 10 times
     instead of the 2 the plan called for. Measured from §10-13's ledger:

         repair-ei-r1   58 rows  179.2k    3.1k/row   <- the pooled one
         repair-r2      25 rows  138.5k    5.5k/row
         repair-c4A/B   19 rows  108.4k    5.7k/row
         repair-r3-c1    8 rows   97.7k   12.2k/row
         repair-r4-c1    7 rows   74.9k   10.7k/row   <- 5x the authoring rate

     Both small agents took 2 tool calls, so this is startup and re-reasoning, not
     tool churn. Under POOL_FLOOR rows the tool refuses without --solo-reason: a
     genuinely-final 1-row round is legitimate and stays possible, but it is now a
     decision someone made rather than one that happened.

Each refusal takes a REASON, not a bare override flag, and every reason is written to
`<out>.scope.json` next to the prompt. A rule whose exception leaves no record is a
rule that gets skipped silently, which is how §10-13's 87 elective rows got there.

OUT-OF-BAND FINDINGS (issue #130) -- why --finding exists
---------------------------------------------------------
A row's field scope was derived ONLY from the wording of its own gate lines, and the
result was inverted: THE MORE EVIDENCE A ROW CARRIED, THE NARROWER ITS REPAIR BECAME. A
gate line that names no field falls through to `options`, so a row flagged `possible
length giveaway` was scoped OPTIONS ONLY -- while the same row named by hand with --ids
and NO gate line got the permissive question+options from UNSCOPED.

§10-13 shipped e0026, e0037 and e0040 into the pool at 876 questions with stem defects a
blind-rater audit had found on all three (e0037's stem reads "even though the products
themselves did not change", which eliminates a distractor on its own). Each carried a
soft length line, so the prompt told the author the stem was copied through verbatim and
the author correctly declined to touch it, reporting the stem findings as accepted
misses. m0003, e0011 and m0013 -- audit-only, no gate line -- had their stems fixed in
the same run. Both chunks exited 0 on every gate; the only signal was prose.

`explanation` was the same defect one turn worse. SCOPE_WORD has defined a perfectly good
("explanation",) scope all along, but finding_scope could only REACH it from two gate
strings, and UNSCOPED does not contain it -- so an audit-found explanation defect was
undeliverable on EVERY row, gate-flagged or not. §10-13's arithmetic auditor found three
explanations that do not reproduce their own stated derivation (the text /review shows a
student after a miss) and every repair in the slice had to be hand-written around this.

So the FIELD axis gets an explicit input, and it carries its own evidence:

    --finding "e0037:question:stem excludes distractor C on its own"

repeatable, one per (row, field). The text prints in that row's block directly under the
gate lines, marked as out of band, so the author reads WHY the field opened instead of
being handed a wider permission with nothing attached to it. Each one lands in
`<out>.scope.json` beside the guard reasons, and the terminal `scope:` line marks the
rows it moved -- a narrowed row was invisible before, which is half of why this survived.

Two things it deliberately does NOT do. It does not widen the ID SET: a --finding naming
a row absent from --ids is refused, because rows are guard 2's axis and guard 2 asks for
--scope-reason. And `answer` is not widenable -- that scope is MEASURED against the
payload (see `mismatched` in main), and apply_repair accepts an `answer` move only onto
the assigned letter with --payload, so a hand-asserted one could only build a merge that
is refused.

--from-bank (§10-17) -- REPAIRING ROWS THAT ARE ALREADY SHIPPED
---------------------------------------------------------------
Everything above describes an IN-FLIGHT batch: a payload assigned the row its letter and
its length band, a gate report says what the author missed, and the parts are on their way
to assembly. §10-17 is the other case -- 79 committed hospitality rows whose options narrate
their own derivation, found by a bank-wide `option_tells` census rather than by a gate.
`apply_repair.py --id-field id --also-freeze question` already merges into a bank file
(issue #73); this is the prompt side of the same operation.

    python build_repair_prompt.py --from-bank $D/workorder.json \
        --part "<bank>/hospitality/hospitality-district-pool.json" ... \
        --out $D/prompts/r1.prompt.txt --overlay "$(pwd)/$D/parts/r1-district.json" ...

Five things change, and each one is a guard above answering a question a bank repair asks
differently rather than a guard being switched off:

  * NO PAYLOAD, NO GATE REPORT. Both are `required=True` for the in-flight path and are
    mutually exclusive with --from-bank rather than accepted empty: an empty gate report
    is precisely the input guard 1 exists to refuse. Identity comes off the BANK ROW
    (there is nothing else that could own it) and there is no assignment to render -- no
    LONGEST=, no KEY LENGTH RANK, no BAND. §10-10 cost three slices by rendering a length
    instruction the payload never made; rendering one when there is no payload at all
    would be the same defect with nothing behind it.

  * THE CENSUS SUBSTITUTES FOR THE GATE ON BOTH GUARDS. Guard 1 asks whether the report
    predates the rows it describes; here that is "a bank file is newer than the census
    JSON", the same property on the same mtimes. Guard 2 asks which rows the gate did not
    flag; the census IS the flagging instrument, so every census row is gate-named by
    construction and needs no --scope-reason. Say it once, here: if all 79 rows fell to
    the reason path the scope record would stop distinguishing anything.

  * COPY THROUGH IS DERIVED FROM THE ROW, NOT LISTED. A bank row carries fields an
    in-flight part does not (`id`, `verified`), and apply_repair REPLACES the row with the
    overlay object -- so a field the prompt forgets to print is a field the merge drops.
    The copy-through set is therefore every key of the row except verify_reword.MUTABLE,
    imported rather than restated so the prompt and the §6 gate cannot drift (#139, #76).

  * THE RULE IS READ OUT OF THE BRIEF. §10-17 §4 says to pass `authoring-hard-bare.txt`
    and not to restate its rule from memory, and this prompt forbids the author to open
    any file -- so the rule block is sliced out of the brief between two markers and
    inlined, and a missing marker RAISES. A rule quoted from a file that stopped
    containing it is worse than one quoted from memory: it looks sourced.

  * `explanation` IS OPENED PER ROW, WITH --finding, LIKE ANY OTHER OUT-OF-BAND FINDING.
    A census emits none of EXPLANATION_FINDINGS' wording, so without it every row is
    options-only and the repair is undeliverable exactly as §10-13's was (#130). It has to
    be opened on a reword specifically: the explanation argues the labels being deleted
    (§10-15 finding 4 -- a rebuttal whose TARGET stops existing is stranded), and §10-16
    measured two of four rows restating the key's diverging tail verbatim. It is still one
    --finding per row, so the widening is recorded and visible rather than blanket.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The fields a reword may move. IMPORTED, not restated: this decides what the prompt
# tells the author to copy through, and verify_reword.py is the gate that fails the run
# if anything outside it moved. Two hand-written copies of that set is #76's GATED_FIELDS
# drift waiting to happen, and here the consequence is a field silently dropped from a
# committed bank row.
from verify_reword import MUTABLE as REWORD_MUTABLE  # noqa: E402
# #186's single-Read cap, ITS constants and ITS pager. A --from-bank prompt carrying 79
# committed rows runs ~234,000 characters, five times the cap §10-16 measured a prompt
# truncating at -- and unlike an audit shard, a repair prompt truncated mid-batch produces
# an overlay that is short by exactly the rows the agent never saw, which reads downstream
# as "the author declined them". Imported rather than re-derived: one measurement, one
# place, and READ_PAGE_MARGIN is a stated guess that should move in one file if it moves.
from build_audit_input import (READ_CAP_CHARS, read_offsets,  # noqa: E402
                               requirement as read_requirement)

# Fields the author copies through untouched. Mirrors apply_repair.IDENTITY, which
# refuses the overlay if any of them drift.
IDENTITY = ("cand_id", "cluster", "level", "instructionalArea",
            "performanceIndicator", "answer", "difficulty")

# WHERE EACH IDENTITY FIELD IS READ FROM (issue #89).
#
# The payload is authoritative for identity, and the code below used to say so in a
# comment while reading `r.get("answer", ...)` -- a key A PAYLOAD ROW DOES NOT HAVE.
# It carries `answer_letter`. So the lookup silently fell through to the AUTHORED row
# on the one identity field the author itself can get wrong, and COPY THROUGH echoed
# the wrong letter back four lines under an `ASSIGNED: answer=B` that named the right
# one. §10-7 chunk 3's e0063 was that row (payload assigned B, the explanation argued
# B, only `answer` read C) and it had to be hand-edited.
#
# Two maps instead of one special case, both READ BY THE CODE rather than remembered:
#   PAYLOAD_ALIAS    -- the payload's name for an identity field, where it differs
#   AUTHORED_SOURCE  -- the fields the AUTHORED row is authoritative for
# and `payload_identity()` raises on anything else that is missing, so the next field
# that quietly exists under another name fails loudly instead of falling back. Same
# "derive it, don't remember it" correction issue #76 applied to GATED_FIELDS.
PAYLOAD_ALIAS = {"answer": "answer_letter"}

# `difficulty` is the AUTHORED tag (§10-8). A hard payload REQUESTS hard; an author
# that honestly demoted a row to medium because its PI carries no real hard route made
# the decision this method depends on. Echoing the payload's request here told the
# author to re-tag it `hard` while apply_repair.py -- which validates identity against
# the PART file -- would have refused exactly that value, so the repair either
# manufactured difficulty or was rejected.
AUTHORED_SOURCE = ("difficulty",)

# Plain-language gloss for a hard payload's key_length_rank, so the author is told
# what the number MEANS rather than being handed a bare ordinal.
RANK_WORD = {1: "the key must be the LONGEST of the four",
             2: "the key must be the SECOND-longest",
             3: "the key must be the THIRD-longest",
             4: "the key must be the SHORTEST of the four"}

# Below this many rows a repair agent is mostly paying its own startup (issue #127 --
# see the module docstring's guard 3 for the per-row rates it comes from). It is a
# POOLING floor, not a size limit: the fix is to hand one agent every chunk's prompt
# in the same round, which is what the plan has asked for since §10-12. 15 sits above
# §10-13's two worst agents (8 and 7 rows, 10-12k/row) and below its efficient ones
# (19 rows and up, 3-6k/row), so it separates the two populations that were actually
# measured rather than naming a round number.
POOL_FLOOR = 15

# The fields --finding may open (issue #130). `answer` is deliberately absent -- see the
# docstring's last paragraph: its scope is measured against the payload, and apply_repair
# accepts that move only onto the assigned letter with --payload.
WIDENABLE_FIELDS = ("question", "options", "explanation")

# --- --from-bank (§10-17) ----------------------------------------------------------
# The rule the reword has to follow lives in the hard brief and is sliced out of it
# rather than retyped here (§10-17 §4: "pass that brief; do not restate the rule in the
# agent prompt from memory"). The prompt forbids the author to open any file, so the
# only way to honour both is to inline the real bytes.
BANK_RULE_BRIEF = Path(__file__).resolve().parent.parent / "prompts" / "authoring-hard-bare.txt"
# Slice boundaries, exclusive of the end marker. The start is the rule's own headline;
# the end is the next assignment block in the brief, which is about a length assignment
# a bank row does not carry.
BANK_RULE_START = "THE RULE THAT ACTUALLY CLOSES THIS"
BANK_RULE_END = "LONGEST=Y"


def bank_rule_block(path: Path = BANK_RULE_BRIEF) -> str:
    """The identical-label rule, verbatim from the committed brief, dedented.

    RAISES when either marker is gone. A rule quoted from a file that no longer contains
    it is worse than one quoted from memory -- it reads as sourced, and the failure mode
    is a repair prompt that states no rule at all while claiming the brief's authority.
    """
    text = path.read_text(encoding="utf-8")
    i = text.find(BANK_RULE_START)
    j = text.find(BANK_RULE_END, i + 1) if i >= 0 else -1
    if i < 0 or j < 0:
        raise SystemExit(
            "%s no longer contains the reword rule between %r and %r.\n"
            "  --from-bank inlines that block verbatim instead of restating it "
            "(§10-17 §4).\n"
            "  Find where the rule moved and update BANK_RULE_START/BANK_RULE_END, or "
            "say\n  plainly that the brief no longer carries it — do NOT let the prompt "
            "ship\n  without the one rule the repair is measured against."
            % (path, BANK_RULE_START, BANK_RULE_END))
    lines = text[i:j].rstrip().splitlines()
    pad = min((len(ln) - len(ln.lstrip()) for ln in lines[1:] if ln.strip()), default=0)
    return "\n".join(ln[pad:] if ln[:pad].isspace() else ln.lstrip() for ln in lines)


BANK_HEADER = """\
==============================================================================
SCOPED REPAIR — {n} COMMITTED item(s) from the shipped question bank
==============================================================================

HOW BIG THIS FILE IS AND HOW TO READ ALL OF IT. The paragraph below is issue
#186's requirement, verbatim — "this shard" means THIS PROMPT.

{read_plan}

You are repairing DECA questions that are ALREADY LIVE. They were found by a
bank-wide census, not by an in-flight gate: their options narrate their own
derivation, so a student can pick the answer by reading the four options and
never reading the stem. Every item you need is inlined below. Read THIS file, in
as many calls as the plan above says. Do NOT read any OTHER file. Do NOT search
the repo. Do NOT open the bank files. Do NOT touch any item that is not listed
here.

WRITE EXACTLY ONE FILE PER BANK FILE — each a JSON array of the rows you changed
FROM THAT FILE ONLY:

{overlays}

DO NOT VERIFY YOUR WORK WITH SHELL COMMANDS. Do not run python, wc, jq or any
other check on option lengths. Deterministic gates re-run on these overlays the
moment you return, for free. Author the fix, write the files, stop.

BECAUSE THESE ROWS ARE SHIPPED, THREE THINGS ARE FROZEN HARDER THAN USUAL. A
student's stored attempt records the LETTER they picked and whether it was right,
computed at the time. So:

  · NEVER move the correct answer to a different letter, and never swap two
    options between letters. Every stored `correct` for that question would
    become a lie, retroactively, with no way to detect it.
  · NEVER change the stem. The defect is in the options; a changed stem is a
    different question wearing the same id.
  · NEVER change `difficulty` or `id`.

The merge tool refuses all of those outright. They are stated here so you do not
spend a row trying.

FIELDS. Each object carries EVERY field printed in its "COPY THROUGH" block,
copied CHARACTER FOR CHARACTER, plus the fields you are repairing. The merge
REPLACES the row with your object, so a field you omit is a field DELETED from
the shipped bank.

You are changing ONLY:  {scope}

Every row below carries its own REPAIR SCOPE line. A field a row does not name is
copied through character for character.

{explanation_rule}

THE SHAPE OF ONE OBJECT. `options` IS AN OBJECT KEYED A/B/C/D — NEVER AN ARRAY.
This is the whole file format; copy it exactly, with every key the row's COPY
THROUGH block prints:

  [
    {{
      "id": "...", "cluster": "...", "level": "...",
      "instructionalArea": "...", "performanceIndicator": "...",
      "question": "<the stem, verbatim>",
      "options": {{ "A": "...", "B": "...", "C": "...", "D": "..." }},
      "answer": "<letter>", "explanation": "...", "difficulty": "...",
      "verified": true
    }}
  ]

The CURRENT OPTIONS block on each row below is printed for you to READ, one
option per line. That display is not the output format. If you transcribe it as
a list — `"options": ["...", "...", "...", "..."]` — the merge tool refuses the
whole overlay and every row you fixed is thrown away, because the letters are
what bind an option to its `answer`. A §10-10 repair agent did exactly this on
8 of 8 rows: the repair work itself was correct and it still merged nothing.

------------------------------------------------------------------------------
THE RULE — quoted verbatim from src/prompts/authoring-hard-bare.txt, which is the
brief the authors of these rows should have been given. Read it before the rows.
------------------------------------------------------------------------------

{rule}

------------------------------------------------------------------------------
FOUR THINGS THE RULE ABOVE DOES NOT SAY, AND THIS BATCH NEEDS
------------------------------------------------------------------------------

  THE CENSUS NAMES THE OPTION IT RECOGNISED, NOT THE OPTIONS THAT ARE WRONG.
  `option_tells` is a PHRASE LIST — it matches wording it has already seen, so a
  row flagged on option C alone is not a row where C is the only problem. The
  rule is about all four options together. REWRITE ALL FOUR LABELS ON EVERY ROW
  so they say the same thing in the same words, whatever the census quoted.

  DO NOT TRADE ONE TELL FOR ANOTHER, AND "NEVER THE LONGEST" IS ITSELF A TELL.
  Length differences are bought with NEUTRAL SCENARIO FURNITURE — the property's
  name, the period, the department — never with anything that distinguishes an
  option's meaning. Where that furniture leaves the key is a DISTRIBUTION
  question, not a per-row one: across a batch, keys must land longest, shortest
  and in between at roughly the rates the bank runs (~25% longest, ~17%
  shortest, ~58% in the middle), so that length carries no information either
  way. Driving every key off both ends is not the safe choice — it makes
  "eliminate the longest and the shortest" a rule a student can apply without
  reading, and it is worth more than picking the longest is.

  MEASURED, ON THIS TOOL'S OWN OUTPUT. §10-17 round 1 was told per row that the
  key must be neither longest nor shortest. It complied on all 79 rows: key
  longest 38.0% → 0.0%, key shortest 12.7% → 0.0%, key in the middle two 49.4% →
  100.0% against a bank of 58.5% and a chance floor of 50%. The wording tell was
  gone and a sharper length tell had replaced it. Where a row below carries a
  LENGTH SLOT line, that line is the assignment and it wins over any instinct to
  keep the key mid-pack; where a row carries none, leave its lengths alone.

  THE NUMBERS ARE NOT YOURS. Every figure in every option stays exactly as it is,
  including the key's. A wrong-metric distractor keeps its NUMBER and loses its
  LABEL — that is the whole method. If you believe a figure is arithmetically
  wrong, STOP on that row, change nothing, and say so in your report.

  THE ONE EXCEPTION TO "REPAIR EVERY ROW": AN ERROR-IDENTIFICATION STEM. Where
  the stem itself asks what mistake was made ("What is the manager's error?"),
  every option names an error BECAUSE THAT IS THE QUESTION, and this metric does
  not apply. If a row reads that way, leave it alone, omit it from the overlay,
  and name it in your report with the stem quoted.

  DIFFICULTY IS NOT YOURS TO CHANGE. Copy each row's tag through verbatim.
"""

# Printed on every --from-bank row, under the census lines. The census records these
# three flags per row and they are the only per-row signal a bank repair has -- there is
# no assignment to render, and inventing one is the §10-10 defect (a prompt stating an
# instruction nothing measures).
BANK_ROW_FACTS = "  CENSUS: difficulty={difficulty} · tell on the KEY: {key} · " \
                 "answerable by elimination: {elim}"
BANK_KEY_NOTE = """\
  ⚠ THE TELL IS ON THE KEY ON THIS ROW. The correct option is the one that
    describes itself, so a student who knows only what the quantity IS reads the
    answer straight off the page. Rewording the three distractors is NOT the fix
    here: the key's label is what has to lose its derivation, and then the other
    three take that same wording."""

BAD_FINDING = """\
--finding {raw!r} is not <cand_id>:<field>:<text>.
  {why}
  One per (row, field), repeatable. The text is the EVIDENCE the author reads, so write
  what the audit actually said, not "the audit flagged it":

    --finding "e0037:question:stem says the products did not change, which eliminates C"
    --finding "h0004:explanation:stated derivation gives 42%, the keyed option is 38%"

  Fields that can be opened: {fields}."""

FINDING_NOT_IN_IDS = """\
--finding names {n} row(s) that this prompt does not cover:
{ids}
  --finding opens a FIELD on a row already in the batch; it does not add rows. Adding a
  row is guard 2's axis and it asks for a written criterion, so name it in --ids and pass
  --scope-reason if the gate did not flag it. Doing it here would route around that guard
  silently, which is the shape issue #127 exists to stop."""

STALE_GATE = """\
the gate report is OLDER than the parts it describes — {n} part file(s) changed after it:
{files}
  A repair merged since this gate ran, so the report cannot say what is still broken.
  §10-13 ran four rounds on chunk 1 with one re-gate AFTER all four; it showed the batch
  had been clean since round 1, by which point rounds 3 and 4 had rewritten 15 more rows
  (issue #127). Re-gating costs ZERO tokens:

    python check_authored.py --payload {payload} \\
        --part {parts} \\
        --list-key-longest --min-margin 20 --list-stem-pull > {gate}

  Then build the prompt from THAT report. If the parts moved for a reason unrelated to a
  repair, say so: --stale-gate-reason "<why>" (recorded in {out})."""

WIDER_THAN_GATE = """\
--ids names {n} row(s) the gate did NOT flag, against {g} row(s) it did:
{ids}
  A model audit is a finding aid, not a work order. `option tells` is lexical (0 means
  "not written in the wording we already know"); `label divergence` is soft and noisy and
  is read as a RATE against its own baseline, never as a row list. §10-13 turned ~33
  gate-named rows into 124 repaired rows — 45% of everything it authored — this way, and
  §10-11 had already cut the same list from 19 rows to 5 on a stated criterion.
  Widening is allowed. Doing it unrecorded is not. State the criterion every widened row
  meets — the way §10-11's did ("≥2 of 3 distractors eliminable with zero business
  knowledge") — and it goes in {out} with the ids:

    --scope-reason "<the criterion, not 'the audit flagged it'>"
"""

BANK_MODE_CONFLICT = """\
--from-bank is the COMMITTED-BANK path and takes neither --payload nor --gate; you passed
{names}.
  They are not merely unnecessary: an empty or borrowed gate report is the exact input
  guard 1 exists to refuse, and a payload from another batch would render a length
  assignment that was never made for these rows (§10-10's key_length_rank defect, with
  nothing behind it). In --from-bank mode the CENSUS is the flagging instrument and the
  BANK ROW is the identity source."""

BANK_OVERLAY_COUNT = """\
--from-bank writes ONE overlay per bank file, in the same order as --part:
  {n_parts} --part file(s), {n_overlays} --overlay path(s).
  apply_repair merges one overlay into one file and `--expect` is scoped per file — that
  is the guard that catches an overlay row landing in the wrong pool, and a single pooled
  overlay across three files disarms it (§10-17 §5)."""

BANK_ROWS_OUT_OF_SCOPE = """\
{n} census row(s) are outside the scope §10-17 §2 decided, and the census records the
reason on the row itself:
{rows}
  SET FILES: a committed 100-Q set is the exam-authentic corpus, it is what composeTest
  builds its blueprint from, and a reworded set item is no longer the artifact the set
  exists to be.
  HARD ROWS: a hard row's options carry the length assignments (KEY-RANK, TOP-GAP,
  key_target_len) that §10-15's H1 finding 8 showed can be jointly unsatisfiable with a
  same-label rewrite — and this rule is the side that loses. That is a hard-tier repair
  with its own gate table, not a ride-along.
  Both are meant to be NAMED in the slice summary rather than silently dropped. If you
  are deliberately repairing them, say why:  --allow-out-of-scope "<reason>" """

SOLO_ROUND = """\
{n} is under the pooling floor of {floor} row(s).
  This is the shape §10-13 paid for 10 times: repair-r3-c1 ran 8 rows for 97.7k and
  repair-r4-c1 ran 7 rows for 74.9k — 10-12k per row, ~5x the rate of authoring an item
  from scratch, on 2 tool calls each, so it is startup and re-reasoning, not tool churn.
  The pooled 58-row agent in the same slice ran 3.1k/row (issue #127).
  THE FIX IS NOT A BIGGER SCOPE — never pad the list to clear this floor. It is ONE agent
  per round holding every chunk's prompt, writing separate overlays, which is what the
  slice plan has said since §10-12. Build the other chunks' prompts and hand them over
  together.

  DOING EXACTLY THAT IS WHAT THIS FLAG IS FOR. One payload per prompt means a pooled round
  is always several prompts, each under the floor, so declare the rest of the round:

    --pooled-with <rows in the OTHER prompts of this round>

  OR DEFER THE ROUND. A repair that does not gate the next step does not have to run now,
  and "there is no sibling chunk yet" is a reason to WAIT, not a reason to run solo. §10-14's
  probe chunk ran alone by design (issue #92) and repaired 2 rows for 65.0k — 32.5k/row, the
  worst rate in the slice — with a truthful --solo-reason, because nothing had been authored
  to pool with. Those 2 rows were not blocking the probe's GO verdict; carried into the
  chunks 2-4 round they would have joined 34 others at ~3k/row. Before you reach for
  --solo-reason, ask whether this round blocks anything. If it does not, defer it.

  A genuinely final round can be one row. Say that instead:

    --solo-reason "<why this agent runs alone>"
"""

# WHICH FIELD EACH FINDING PUTS IN SCOPE (issue #77, from a §10-10 finding).
# The prompt used to open every repair with a blanket "you are changing ONLY:
# question · options · explanation" regardless of what the gate actually said, and
# both of §10-10's repair agents took the third name as permission: they rewrote
# explanations on rows flagged purely for option length and collapsed the
# per-distractor rationale `/review` shows a student after a miss. Nothing
# downstream caught it -- `explanation` is not in apply_repair's IDENTITY set and
# check_authored only length-checks it.
#
# So the scope line is DERIVED now, per row, from that row's own FINDINGS. A
# finding names the field whose wording is wrong, and only that field is offered:
# a stem-pull row moves the STEM (the gate says so in the finding itself), a
# key-longest row moves the OPTIONS, and neither is an invitation to re-argue the
# answer. Anything a rule below does not claim falls to `options`, which is where
# the length/tell/label findings that dominate a repair batch live.
#
# The lists below are GATE WORDING, and for a while they were the only route into
# a scope at all -- which made the derivation inverted, because a gate line that
# named no field narrowed the row to `options` while no gate line at all left it
# on the permissive UNSCOPED. A model audit cannot phrase its findings in gate
# wording, so its findings were undeliverable on exactly the rows that had the
# most evidence. That is issue #130; --finding is the other route in, and it
# carries the audit's own words with it.
#
# `explanation` is deliberately hard to get into scope -- only a finding about
# the explanation itself puts it there. That is not the same as freezing it: a
# repair that edits an option the explanation QUOTES still has to fix the quote,
# and the per-row block below says so. What it stops is the rewrite.
STEM_FINDINGS = (
    "stem pulls toward the key",
    # check_authored emits this as ONE line per row for exactly this reason: every
    # gate line a row carries that no rule here claims adds `options` to its scope,
    # so a second guidance line would turn a stem repair into an option repair.
    "stem meta-exclusion",
    "stem restates the performance indicator",
    "stem collision",
    "stem twin",
    "stem already used in another cluster",
    # A duplicate row is the one case where the whole item may have to move; the
    # stem is offered alongside the options rather than instead of them.
    "content-hash collision",
)
EXPLANATION_FINDINGS = (
    "explanation looks thin",
    "missing field 'explanation'",
)
# check_authored.py:472 -- `answer 'C' != assigned letter 'B'`. The defect is the
# `answer` FIELD, so this row must not fall through to the catch-all `options` scope
# and read as "reword the options": on the normal shape of this row nothing needs
# rewording at all, because COPY THROUGH now carries the corrected letter. `options`
# rides along only for the swap the row block below describes.
LETTER_FINDINGS = ("!= assigned letter",)
# Printed when a row was named with --ids and carries no gate line to derive from.
UNSCOPED = ("question", "options")

# Scope fields in their fixed render order. `answer` leads: where it is in scope it is
# the whole repair on most rows.
SCOPE_FIELDS = ("answer", "question", "options", "explanation")

SCOPE_WORD = {
    ("options",): "OPTIONS ONLY — the stem and the explanation are copied through verbatim",
    ("question",): "THE STEM ONLY — the four options and the explanation are copied through verbatim",
    ("explanation",): "THE EXPLANATION ONLY — the stem and the four options are copied "
                      "through verbatim",
    ("question", "options"): "the stem and the options — the explanation is copied through verbatim",
    # Spelled out rather than left to scope_phrase's fallback, which renders it as
    # "OPTIONS ONLY — plus the explanation, where the gate flagged it". On a --from-bank
    # row the gate flagged no such thing (a census names option wording), so that
    # sentence would attribute the widening to an instrument that did not make it.
    ("options", "explanation"): "the four OPTIONS and the EXPLANATION — the stem is "
                                "copied through verbatim",
    ("answer", "options"): "THE `answer` LETTER — already corrected for you in COPY THROUGH — "
                           "and the options ONLY IF the swap below is needed; the stem and "
                           "the explanation are copied through verbatim",
}

HEADER = """\
==============================================================================
SCOPED REPAIR — {n} item(s)
==============================================================================

You are repairing a SMALL, NAMED set of already-authored DECA questions. Every
item you need is inlined below. Do NOT read any file. Do NOT search the repo. Do
NOT open the part files. Do NOT touch any item that is not listed here.

WRITE EXACTLY ONE FILE — a JSON array of exactly {n} object(s):
  {overlay}

DO NOT VERIFY YOUR WORK WITH SHELL COMMANDS. Do not run python, wc, jq or any
other check on option lengths. A deterministic gate re-runs on this overlay the
moment you return, for free. The last repair agent spent 9 of its 11 tool calls
re-measuring its own output and cost 4x the per-item rate of ORIGINAL AUTHORING
to fix five rows. Author the fix, write the file, stop. Two tool calls total:
one Read of this prompt, one Write of the overlay.

FIELDS. Each object carries all of these, copied CHARACTER FOR CHARACTER from the
"COPY THROUGH" block on its row — they say which row this is, and the merge tool
refuses the overlay if any of them differ, including a changed capitalisation:

  {identity}
{letter_rule}
You are changing ONLY:  {scope}

Every row below carries its own REPAIR SCOPE line, derived from what the gate
actually said about that row. It is narrower than this batch-wide line whenever
the rows were flagged for different things, and the ROW's line wins. A field a
row does not name is copied through character for character.

{explanation_rule}

THE SHAPE OF ONE OBJECT. `options` IS AN OBJECT KEYED A/B/C/D — NEVER AN ARRAY.
This is the whole file format; copy it exactly:

  [
    {{
      "cand_id": "...", "cluster": "...", "level": "...",
      "instructionalArea": "...", "performanceIndicator": "...",
      "question": "<the stem>",
      "options": {{ "A": "...", "B": "...", "C": "...", "D": "..." }},
      "answer": "<letter>", "explanation": "...", "difficulty": "..."
    }}
  ]

The CURRENT OPTIONS block on each row below is printed for you to READ, one
option per line. That display is not the output format. If you transcribe it as
a list — `"options": ["...", "...", "...", "..."]` — the merge tool refuses the
whole overlay and every row you fixed is thrown away, because the letters are
what bind an option to its `answer`. A §10-10 repair agent did exactly this on
8 of 8 rows: the repair work itself was correct and it still merged nothing,
and the overlay had to be converted by hand before any of it could land.

THE RULES THAT APPLY — they are why these rows were flagged:

  KEY LENGTH — THIS IS A RANK TEST, NOT A MARGIN TEST, ON EVERY ROW EXCEPT THE
  ONES MARKED ⚠ BELOW. The gate asks exactly one question of each row: "is the
  correct option the single longest of the four?" A key 1 character longer than
  every distractor scores the SAME as one 29 characters longer. Both fail.
  Narrowing the gap accomplishes nothing.

  THE EXCEPTION, AND IT IS ABOUT A QUARTER OF A --free-rank BATCH: where a row's
  ASSIGNED line reads LONGEST=<the answer letter>, the key is SUPPOSED to be the
  longest and the gate scores it that way. Such a row is listed here for MARGIN
  (it leads by >=20ch), never for rank. On it, everything below is inverted:
  narrow the gap by raising the RUNNER-UP and leave the key on top. Those rows
  carry their own ⚠ block — read it, and let it win over this paragraph.

  So the target is RANK: PICK ONE SPECIFIC DISTRACTOR AND MAKE IT STRICTLY
  LONGER THAN THE KEY. Not equal — a tie fails too. Overshoot by 3-4 characters
  so a recount cannot land back on the key.

  Lengthen it with real substance — a named mechanism, a specific consequence, a
  scope. The lengthened distractor must read as a genuinely plausible answer a
  student could believe: a real mechanism that is WRONG for this situation, not a
  longer way of saying nothing. An obviously padded distractor is a worse defect
  than the length tell it fixes.

  NEVER trim the key — it is the one option that must stay precisely true. Trim it
  ONLY when it sits outside its band, and then only wording, never meaning.

  Before writing each row, ask: "which option is now the longest, and is it a
  wrong answer?" If the answer is still the key, the row is NOT fixed.

  (§10-6 measured this: told the key "must not be CONSPICUOUSLY the longest",
  three repair agents cut margins hard — one key went +29ch to +6ch — and left
  every row still key-longest. Three chunks moved 33.9→33.9%, 30.0→30.0%,
  37.3→35.8%: ~185k tokens for no rank change. Re-worded to name the rank test,
  one pass took a chunk 35.8% → 23.9%.)

  LONGEST=<letter>. That option must be STRICTLY the longest of the four — a tie
  is a miss. Where LONGEST is not the key, the key is deliberately not the
  longest, so a student who picks the longest option without reading gains
  nothing. Give option LONGEST its length with real substance, never filler.

  THE TWO RULES ABOVE ARE ONE JOB, NOT TWO. When a row is flagged key-longest
  AND carries a LONGEST=<letter> that is not the key, the distractor you lengthen
  should BE that letter. Lengthening some other option fixes the rank test and
  breaks the LONGEST= assignment at the same time — §10-6 fixed a chunk's
  key-longest 35.8% → 23.9% while its LONGEST= compliance fell 70.1% → 61.2%,
  because the repair picked whichever distractor was easiest to extend.

  WHEN LONGEST= COLLIDES WITH THE IDENTICAL-LABEL RULE, THE LABEL RULE WINS ON A
  CONCEPT ROW. All four options must describe the same quantity in the same words,
  with only the number differing. On a row that is clean by that rule the
  achievable length spread is a few characters, so a LONGEST= assignment can be
  unreachable without bolting on a clause no other option carries. Both
  `longest_letter` and `key_may_be_longest` are SOFT in check_authored — a miss is
  reported, never failed. TAKE THE SOFT MISS. Do not invent a tie-breaking tail
  ("tax excluded", "across the full product catalog", "company-wide") to satisfy
  the assignment: §10-12 measured a repair agent doing exactly that on 9 rows,
  which put a unique qualifier on the KEY of three of them and re-created the
  pick-the-odd-one tell the repair existed to remove. Two survived a clean re-gate
  and were caught only by a later blind solver, at the cost of another agent.

  THE PRECEDENCE FLIPS ON A HARD ROW: `key_length_rank` HARD-fails, so there the
  rank wins and a neutral tail is the honest cost of the assignment. Keep such a
  tail bland and equally plausible on any option — never on the key alone, and
  never naming a scope, period or entity the stem does not contain.

  BAND lo-hi. All four options should sit within the band, the key included.

  KEY LENGTH RANK n of 4. A HARD payload assigns the key an exact length RANK
  instead of naming a LONGEST letter: rank 1 means the key must be the LONGEST of
  the four options, rank 4 means it must be the SHORTEST, 2 and 3 the places in
  between. Ties do not count — the key must sit unambiguously at its rank.
  Set the rank by adjusting the DISTRACTORS around the key wherever you can; trim
  the key only when it is outside its band, and then only its wording, never its
  meaning. Where the key is assigned rank 1 it is MEANT to be the longest on that
  row, and lengthening a distractor past it is the defect, not the fix.

  THE RANKS ARE A DISTRIBUTION, NOT A PER-ROW PREFERENCE. Across a batch the
  assignment spreads keys over all four ranks precisely so that option length
  carries no signal. Driving every key to rank 4 is NOT the safe choice: a key
  that is reliably the shortest option is exactly as exploitable as one that is
  reliably the longest, and it is the failure this batch was repaired for
  (§10-8 H1: 13 of 18 keys came back rank 4 against an assigned 5/5/4/4 spread,
  while the author's own report certified it as "always a distractor, never the
  key"). Fix the row to its ASSIGNED rank, not to the rank that feels safest.

  STEM PULL. Where the stem pulls toward the key, rewrite the STEM — never the
  key. The stem is naming what the key names; make it name the SITUATION instead.

  A STEM COMMITS TO ITS READING THROUGH A FACT ABOUT THE SCENARIO, NEVER THROUGH
  AN INSTRUCTION TO THE READER ABOUT THE OPTIONS. This is the rule THIS TOOL is
  most likely to break, because a row whose defect is "two defensible answers"
  makes the shortest fix a clause that names the rival and waves it off — and that
  clause converts a knowledge item into a reading item, which is strictly worse
  than the ambiguity it cures. The student stops needing the concept and starts
  matching a phrase to an option and crossing it out.

    BANNED    "...not just keep a record of their purchases"
              "...logging each visitor's inquiry is a secondary side effect"
              "Setting aside how the access became possible, ..."
              "Which attribute — not the evidence used to prove it — matters most?"
    REQUIRED  a fact that makes the rival option WRONG ON THE MERITS: the maker
              ALREADY keeps a detailed purchase log and customers still feel like
              just another sale; the support team rarely opens the inquiry log the
              chatbot keeps.

  THE TEST, and it is mechanical: DELETE YOUR CLAUSE. If no fact about the
  scenario changed, it was an instruction to the reader and the item is not fixed.

  MEASURED, ON THIS TOOL'S OWN OUTPUT. §10-13's chunks 9/10 were told to fix 8
  ambiguous rows "by adding the fact that rules the competitor out" and produced a
  meta-exclusion on 5 of the 5 rows where a stem edit was in scope. All five passed
  the entire gate suite — check_authored exit 0, stem pull 0.0%, batch invariants 0
  blocking, key figures 0 mismatch — and a blind solver then answered them with no
  business knowledge, by reading the clause. `--list-stem-meta` now names the known
  wording; it does not name the wording nobody has written yet, which is yours.

  YOUR REPLACEMENT FACT MUST LEAVE THE EXPLANATION TRUE. The explanation is copied
  through verbatim on a stem-scoped row, and it argues the stem's facts — so choose
  a fact the existing explanation still supports. If the only honest fix falsifies
  the explanation, STOP on that row and say so in your report. Do not rewrite the
  explanation to agree, and do not fall back to a meta-exclusion because it is the
  edit that fits the scope.

  OPTION LABELS — SAME QUANTITY, SAME WORDS, ONLY THE NUMBER DIFFERS. Where the
  gate says the options narrate themselves or that their labels differ in kind,
  make all four labels IDENTICAL: "$131.25 in revenue per available room" on
  every option, never "…, blending occupancy with the average nightly rate" on
  one of them. Say WHAT the number is — never how it was produced, which input
  it used, or what mistake it represents. A wrong-metric distractor keeps its
  NUMBER and loses its LABEL. A student who can tell one option from the other
  three without reading the stem does not need the stem.

  DIFFICULTY IS NOT YOURS TO CHANGE HERE. Copy each row's difficulty tag through
  verbatim. A row already tagged `medium` in a hard batch was demoted on purpose
  because its PI supports no honest hard route; re-tagging it `hard` to match the
  request is the manufactured difficulty the whole method exists to prevent.
"""


EXPLANATION_RULE = """\
{opener}

Every row's current explanation is printed in full below. Where a row does not
name it, copy it back CHARACTER FOR CHARACTER; the one exception is a phrase that
QUOTES option text you edited — change the quoted words to match, nothing else.

This is a named defect, not a precaution. Both §10-10 repair agents were handed
rows flagged for option LENGTH, rewrote the explanations anyway, and collapsed the
per-distractor rationale into a single sentence. Nothing downstream catches it:
`explanation` is not an identity field, so the merge tool accepts it, and the gate
only checks that it is long enough. What it costs is a student — /review shows the
explanation after a miss, so a distractor whose rationale was deleted becomes a
wrong answer with no reason attached to it.

Rewriting an explanation is therefore a scope breach on the same footing as
repairing a row nobody flagged. If a row's explanation is itself wrong — it argues
a different option, or its arithmetic does not hold — STOP and say so in your
report rather than making it agree."""

BANK_EXPLANATION_RULE = """\
`explanation` IS IN SCOPE ON EVERY ROW HERE, AND IT IS THE NARROWEST KIND OF
SCOPE THERE IS. It is open for exactly one reason: these explanations argue the
labels you are about to delete. "Choice A divides by rooms sold instead of rooms
available" is a rebuttal of an option that will not say that any more, and a
frozen explanation would leave a student reading a rationale for wording that is
no longer on the page.

So: change the sentences that QUOTE OR PARAPHRASE AN OPTION LABEL YOU EDITED, and
nothing else. Keep every per-distractor rationale — one for each wrong option,
saying why it is wrong — and keep the derivation of the correct answer. /review
shows this text to a student immediately after they miss the question, so it is
the single most valuable paragraph in the record.

Two failures to avoid by name, both measured:
  · §10-10's two repair agents were handed rows flagged for option LENGTH,
    rewrote the explanations anyway, and collapsed four rationales into one
    sentence. Nothing downstream catches that; it is only visible to the student.
  · The mirror failure is leaving it alone. Where an explanation names an option
    by its OLD label, freezing it strands the rebuttal on a target that no longer
    exists (§10-15). Naming the option by LETTER is the reliable fix — "Option A
    divides by rooms sold" survives any rewording of A.

If a row's explanation is itself wrong — it argues a different option, or its
arithmetic does not hold — STOP on that row, change nothing, and say so in your
report rather than making it agree."""

EXPL_OPENER_FROZEN = ("`explanation` IS NOT ON THAT LIST, and it is not yours to rewrite "
                      "on any\nrow in this batch.")
EXPL_OPENER_SCOPED = ("`explanation` is in scope on the rows below and NOWHERE ELSE, and "
                      "there\nonly because a finding on that row names the explanation "
                      "itself:\n{ids}")

# Printed in the header ONLY when a scoped row's authored `answer` disagrees with its
# assigned letter, because on every other batch the flat "copy identity through" rule
# above is the whole truth and this would be noise.
LETTER_RULE = """
`answer` IS THE EXCEPTION ON {n} ROW(S) IN THIS BATCH — {ids}

On those rows the authored `answer` is itself the defect: it names a different letter
than the payload assigned, which is a hard gate failure. The COPY THROUGH block on
each of them therefore carries the ASSIGNED letter, not the one currently in the file.
Write what COPY THROUGH says. The merge command printed for this batch passes
`--payload`, which is what lets that single change through — and it accepts the move
ONLY onto the assigned letter, so there is no other letter you can write.
"""

# The per-row block. Two shapes of defect hide behind one gate line and the fix differs,
# so say both: §10-7's e0063 was a clerical slip (the explanation already argued the
# assigned letter and only the field was wrong), but an author that genuinely wrote the
# correct answer under the wrong letter needs the option TEXTS swapped, because
# apply_repair --payload will only ever move `answer` onto the assigned letter.
LETTER_NOTE = """\
  ⚠ THE `answer` FIELD ON THIS ROW IS THE DEFECT. Payload assigns {want}; the
    authored row reads {got}. COPY THROUGH below already carries {want} — write it
    exactly, and do NOT re-argue the assignment.
    Read the explanation and the options first, then take ONE of these:
      · The option at {want} is already the correct answer (the usual case — a
        clerical slip). Then the letter alone is the whole repair: copy every other
        field through character for character and change nothing else.
      · The option at {got} is the correct answer and {want}'s is a distractor. Then
        SWAP THE TWO OPTION TEXTS so the correct answer sits at {want}, and leave
        `answer` at {want}. Never leave `answer` pointing at {got}: the merge tool
        refuses any letter but the assigned one.
      · Neither option is correct, or the explanation argues a third letter. STOP,
        change nothing on this row, and say so in your report."""

# The rows where THE RULES THAT APPLY tells the author the exact opposite of what
# the row needs. `--free-rank` assigns ~25% of a batch LONGEST=<the key's own
# letter>: on those rows the key is MEANT to be the longest, and `check_authored`
# scores that assignment. But such a row can still be listed by --min-margin: the
# key is rightly longest and stands too FAR clear. That is a MARGIN finding.
#
# The static rules block answers a RANK finding ("pick one specific distractor and
# make it strictly longer than the key"), which on these rows destroys the
# assignment the gate scores. §10-12 measured it: 5 of 5 such rows came back with a
# distractor pushed 2-3ch past the assigned key, dropping chunk 3's LONGEST=
# compliance 98.9% -> 93.3% (bar ~97%) and costing a whole extra repair round
# (73.4k) to undo. Neither the agent nor the rules block was wrong in isolation --
# nothing told the agent this row was the exception.
#
# Same shape as §10-10's key_length_rank bug (a gate scoring an assignment the
# prompt never stated) and issue #76's GATED_FIELDS drift: when a gate scores an
# assignment, the PROMPT must state it per row.
KEY_LONGEST_NOTE = """\
  ⚠ ON THIS ROW THE KEY IS ASSIGNED THE LONGEST OPTION (LONGEST={letter} IS THE
    ANSWER LETTER). That is deliberate, it is scored, and it must SURVIVE this
    repair. Do NOT push any distractor past the key here — that is the correct fix
    on other rows and the DEFECT on this one.
    This row was flagged for MARGIN, not for rank: the key is rightly the longest
    and stands too far clear of the field. Narrow the gap from BELOW — lengthen the
    runner-up (with real substance: a named mechanism, a specific consequence, a
    scope) until the key leads it by well under 20 characters, while the key
    remains STRICTLY the longest of the four. A tie is a miss.
    Check before you emit: the key must still be the single longest option, and its
    lead over the runner-up must be small. Both conditions, or the row is not fixed."""


def finding_scope(findings: List[str], letter_mismatch: bool = False,
                  widened: tuple = ()) -> tuple:
    """The fields a row's repair may touch, derived from its own findings.

    Order is fixed (SCOPE_FIELDS) so the tuple is a stable key into SCOPE_WORD. An
    empty finding list means the row was named by hand with --ids, and gets the
    permissive stem+options scope rather than a guess.

    `letter_mismatch` is measured against the payload rather than parsed out of the
    gate, so a row named with --ids -- which carries no gate line at all -- still gets
    the answer scope and its warning block (issue #89).

    `widened` is the fields --finding opened on this row (issue #130). It is the ONE
    route into a scope that does not go through gate wording, which is what a model
    audit needs -- an audit cannot phrase itself in `check_authored`'s strings, and
    without this a gate-flagged row was narrower than an unflagged one. Note it also
    SUPPRESSES the UNSCOPED fallback: a row named with --ids and one explanation
    finding is scoped explanation ONLY, not question+options+explanation, because the
    operator said which field is wrong. Pass a second --finding to open a second field.
    """
    fields = set()
    for raw in findings:
        f = raw.strip()
        # parse_gate's own markers, not gate findings.
        if f in ("[FAIL]", "[soft]") or f.startswith("(named explicitly"):
            continue
        low = f.lower()
        hit = False
        if any(s in low for s in STEM_FINDINGS):
            fields.add("question")
            hit = True
        if any(s in low for s in EXPLANATION_FINDINGS):
            fields.add("explanation")
            hit = True
        if any(s in low for s in LETTER_FINDINGS):
            fields.update(("answer", "options"))
            hit = True
        if not hit:
            fields.add("options")
    if letter_mismatch:
        fields.update(("answer", "options"))
    fields.update(widened)
    if not fields:
        fields = set(UNSCOPED)
    return tuple(f for f in SCOPE_FIELDS if f in fields)


def parse_findings(raw_findings: List[str]) -> Dict[str, List[tuple]]:
    """`<cand_id>:<field>:<text>` strings -> cand_id -> [(field, text), ...].

    Split from the right of the field, not on every colon: a finding's TEXT routinely
    carries one ("stated derivation gives 42%: the keyed option is 38%"), and eating it
    would truncate the evidence the author reads. Validation is loud on every axis --
    an unparseable --finding that quietly did nothing would reproduce issue #130 with
    an extra flag on the command line.
    """
    out: Dict[str, List[tuple]] = {}
    for raw in raw_findings or []:
        parts = raw.split(":", 2)
        if len(parts) != 3:
            raise SystemExit(BAD_FINDING.format(
                raw=raw, fields=" · ".join(WIDENABLE_FIELDS),
                why="It needs two colons: the id, the field, then the finding text."))
        cid, field, text = (p.strip() for p in parts)
        if not cid or not text:
            raise SystemExit(BAD_FINDING.format(
                raw=raw, fields=" · ".join(WIDENABLE_FIELDS),
                why="Both the id and the finding text must be non-empty — the text is "
                    "the\n  whole point, it is what the author is shown."))
        if field not in WIDENABLE_FIELDS:
            why = ("`answer` is not widenable by hand: its scope is measured against the\n"
                   "  payload, and apply_repair accepts that move only onto the assigned "
                   "letter." if field == "answer"
                   else "%r is not a field this prompt can open." % field)
            raise SystemExit(BAD_FINDING.format(
                raw=raw, fields=" · ".join(WIDENABLE_FIELDS), why=why))
        out.setdefault(cid, []).append((field, text))
    return out


def scope_phrase(fields: tuple) -> str:
    """SCOPE_WORD's sentence for a scope, or a plain field list for the rare shapes."""
    if fields in SCOPE_WORD:
        return SCOPE_WORD[fields]
    rest = tuple(f for f in fields if f != "answer")
    if "answer" in fields and rest:
        return "the `answer` letter (already corrected in COPY THROUGH), plus " \
            + scope_phrase(rest)
    named = tuple(f for f in fields if f != "explanation")
    if "explanation" in fields and named in SCOPE_WORD:
        return SCOPE_WORD[named].split(" — ")[0] + \
            " — plus the explanation, where the gate flagged it"
    return " · ".join(fields)


def payload_identity(payload_row: Dict, authored_row: Dict) -> Dict:
    """Each IDENTITY field's authoritative value, and a loud failure when it is absent.

    The payload owns identity except for AUTHORED_SOURCE, and PAYLOAD_ALIAS carries the
    names that differ between the two shapes. A missing field raises instead of falling
    back to the authored row — the silent fallback is issue #89 itself, and it costs
    nothing to notice here rather than in a repair that shipped.
    """
    vals = {}
    for f in IDENTITY:
        if f in AUTHORED_SOURCE:
            vals[f] = authored_row.get(f)
            continue
        key = PAYLOAD_ALIAS.get(f, f)
        if key not in payload_row:
            raise SystemExit(
                "%s: the payload row carries no %r, so identity field %r has no\n"
                "  authoritative value. Either the payload was built by a version that\n"
                "  named it differently — add it to PAYLOAD_ALIAS — or it belongs to the\n"
                "  AUTHORED row, like `difficulty` does. Do NOT let it fall back silently:\n"
                "  that is issue #89, where `answer` fell through to the authored letter on\n"
                "  the one row whose authored letter was the defect.\n"
                "  payload row has: %s"
                % (payload_row.get("cand_id", "<no cand_id>"), key, f,
                   ", ".join(sorted(payload_row))))
        vals[f] = payload_row[key]
    return vals


def parts_newer_than_gate(gate: Path, parts: List[Path]) -> List[Path]:
    """Part files modified after the gate report was written (issue #127, guard 1).

    check_authored reads the parts and its output is redirected to the report, so on an
    honest round the report is the NEWER file. A part that is newer means apply_repair
    merged an overlay into it since — i.e. this is round N+1 being built from round N's
    findings, which is exactly what §10-13 did four times on one chunk.

    mtime, not content: the question is "did the parts move under this report", and a
    round that rewrote a row and then rewrote it back is still a round the gate never
    saw. Strictly newer, so a report written in the same second as its parts passes.
    """
    cutoff = gate.stat().st_mtime
    return [p for p in parts if p.stat().st_mtime > cutoff]


def parse_gate(path: Path) -> Dict[str, List[str]]:
    """cand_id -> its FAIL/soft finding lines, straight from check_authored's report.

    `note` rows are recognised and DROPPED, not parsed as findings (#139). They name
    rows whose author complied with its assignment exactly, so a repair scoped to one
    is the work-order-from-noise failure #127 guards against. They must still be
    matched here rather than ignored: a note header is a two-space line that the
    finding regex misses, so without this branch `cur` would stay pointed at whichever
    soft row printed last and the note's indented body would be appended to it.
    """
    flags: Dict[str, List[str]] = {}
    cur = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*(FAIL|soft|note)\s+(\S+)\s+\[", line)
        if m:
            cur = None if m.group(1) == "note" else m.group(2)
            if cur is not None:
                flags.setdefault(cur, []).append("[%s]" % m.group(1))
        elif cur and line.startswith(" " * 10) and line.strip():
            flags[cur].append(line.strip())
        elif not line.strip():
            cur = None
    return flags


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a scoped repair prompt for named rows.")
    # NOT required=True any more, and --from-bank is why (§10-17). A committed-bank
    # repair has neither file, and the mutual exclusion below is enforced explicitly
    # rather than by accepting empty ones — an empty gate report is guard 1's input.
    ap.add_argument("--payload", help="the build_area.py payload these parts answer")
    ap.add_argument("--gate", help="check_authored.py report, redirected to a file")
    ap.add_argument("--from-bank", metavar="CENSUS",
                    help="repair COMMITTED bank rows instead of an in-flight batch: the "
                         "bank-wide census JSON (see §10-17 §1) names the rows and IS the "
                         "flagging instrument, --part takes the bank files, and identity "
                         "comes off the bank row. Excludes --payload/--gate")
    ap.add_argument("--part", required=True, nargs="+",
                    help="the part file(s) holding the rows — or, with --from-bank, the "
                         "committed bank file(s)")
    ap.add_argument("--out", required=True, help="where to write the prompt")
    ap.add_argument("--overlay", required=True, nargs="+",
                    help="ABSOLUTE path the author must write the overlay to. With "
                         "--from-bank, one path per --part file IN THE SAME ORDER: "
                         "apply_repair merges one overlay into one bank file and scopes "
                         "--expect per file")
    ap.add_argument("--allow-out-of-scope", metavar="TEXT",
                    help="repair census rows that §10-17 §2 puts out of scope — rows in a "
                         "committed 100-Q set file, or rows tagged hard — and say why "
                         "(--from-bank only)")
    ap.add_argument("--ids", nargs="*", default=None,
                    help="repair exactly these cand_ids (default: every row the gate flagged)")
    ap.add_argument("--fail-only", action="store_true",
                    help="only rows the gate marked FAIL, skipping soft findings")
    # The field axis (issue #130). Repeatable. Rows come from --ids and only --ids.
    ap.add_argument("--finding", action="append", metavar="ID:FIELD:TEXT", default=None,
                    help="open FIELD (%s) on an --ids row for an out-of-band finding a "
                         "gate cannot phrase — a blind-rater or arithmetic audit — and "
                         "print TEXT on that row as the evidence. Repeatable"
                         % "/".join(WIDENABLE_FIELDS))
    # The three round guards (issue #127). Each takes a REASON rather than being a bare
    # override, and each reason lands in <out>.scope.json — an exception that leaves no
    # record is how §10-13's 87 elective rows got repaired.
    ap.add_argument("--stale-gate-reason", metavar="TEXT",
                    help="proceed although a part file is newer than the gate report, "
                         "and say why (guard 1: re-gating is free — do that instead)")
    ap.add_argument("--scope-reason", metavar="TEXT",
                    help="the written criterion every --ids row the gate did NOT flag "
                         "meets (guard 2: an audit is a finding aid, not a work order)")
    ap.add_argument("--pooled-with", metavar="ROWS", type=int, default=0,
                    help="rows carried by the OTHER prompts of this same round, when one "
                         "agent holds several chunks' prompts. Counts toward the %d-row "
                         "pooling floor (guard 3). Mutually exclusive with --solo-reason."
                         % POOL_FLOOR)
    ap.add_argument("--solo-reason", metavar="TEXT",
                    help="why this under-%d-row round runs as its own agent instead of "
                         "being pooled with the other chunks (guard 3). 'No sibling chunk "
                         "exists yet' is a reason to DEFER a non-blocking round, not to "
                         "run it solo — §10-14's probe paid 32.5k/row that way"
                         % POOL_FLOOR)
    args = ap.parse_args()

    bank = bool(args.from_bank)
    # Mutual exclusion, stated rather than achieved by accepting empty files. See
    # BANK_MODE_CONFLICT for why an empty --gate is the worst available answer here.
    if bank:
        conflict = [n for n, v in (("--payload", args.payload), ("--gate", args.gate)) if v]
        if conflict:
            raise SystemExit(BANK_MODE_CONFLICT.format(names=" and ".join(conflict)))
    else:
        for name, val in (("--payload", args.payload), ("--gate", args.gate)):
            if not val:
                raise SystemExit("%s is required without --from-bank (the in-flight path "
                                 "reads identity from the payload and findings from the "
                                 "gate report)." % name)
        if len(args.overlay) != 1:
            raise SystemExit("--overlay takes exactly one path without --from-bank; "
                             "several overlays are the committed-bank shape, one per "
                             "bank file.")
        if args.allow_out_of_scope:
            raise SystemExit("--allow-out-of-scope is a --from-bank flag: it waives the "
                             "§10-17 §2 set-file/hard-row boundaries, which only a "
                             "census carries.")

    # Parsed before anything is read: a malformed --finding is a typo on the command
    # line, and there is no reason to open four files to tell someone about it.
    oob = parse_findings(args.finding)

    # Named here, not at the write below, so a refusal can point at the file the reason
    # would be recorded in rather than at a path that does not exist.
    scope_path = Path(args.out).with_suffix(".scope.json")

    # GUARD 1 — a report older than the rows it describes cannot say what is still broken.
    # Checked before anything is read, so the refusal is the first thing printed.
    #
    # --from-bank substitutes the CENSUS for the gate report and the BANK FILES for the
    # parts. It is the same property on the same mtimes: the census was produced by
    # reading those files, so on an honest run the census is the newer file, and a bank
    # file that moved since means rows were merged after the census named them.
    parts = [Path(p) for p in args.part]
    report = Path(args.from_bank if bank else args.gate)
    stale = parts_newer_than_gate(report, parts)
    if stale and not args.stale_gate_reason:
        raise SystemExit(STALE_GATE.format(
            n=len(stale), files="\n".join("      %s" % p for p in stale),
            payload=args.payload or "<none — --from-bank>",
            parts=" ".join(args.part), gate=report,
            out=scope_path))

    if bank:
        if len(args.overlay) != len(parts):
            raise SystemExit(BANK_OVERLAY_COUNT.format(
                n_parts=len(parts), n_overlays=len(args.overlay)))
        census = {r["id"]: r for r in
                  json.loads(report.read_text(encoding="utf-8"))}
        # Which bank file holds each row, and the row itself. Keyed by the file GIVEN
        # rather than the file the census names, so `--part` is what scopes the batch:
        # pass the three hospitality pools and the census's set-file and other-cluster
        # rows are simply not in the batch.
        rows: Dict[str, Dict] = {}
        authored: Dict[str, Dict] = {}
        home: Dict[str, Path] = {}
        for p in parts:
            for it in json.loads(p.read_text(encoding="utf-8")):
                if it.get("id") in census:
                    rows[it["id"]] = census[it["id"]]
                    authored[it["id"]] = it
                    home[it["id"]] = p
        # The census's own finding lines, in the shape parse_gate would have produced.
        flags = {cid: list(r["tells"]) for cid, r in rows.items()}
    else:
        rows = {r["cand_id"]: r
                for r in json.loads(Path(args.payload).read_text(encoding="utf-8"))}
        authored = {}
        home = {}
        for p in args.part:
            for it in json.loads(Path(p).read_text(encoding="utf-8")):
                authored[it["cand_id"]] = it
                home[it["cand_id"]] = Path(p)
        flags = parse_gate(Path(args.gate))

    if args.ids:
        ids = list(args.ids)
    elif bank:
        # Grouped by bank file IN --part ORDER, then by id: the author writes one overlay
        # per file, and the rows must appear in the same order the header lists the
        # overlays in. Sorting by path string instead puts the groups in a different order
        # from the header, which is a needless second thing to reconcile.
        order = {p: i for i, p in enumerate(parts)}
        ids = sorted(rows, key=lambda c: (order[home[c]], c))
    else:
        ids = [c for c in flags if not args.fail_only or "[FAIL]" in flags[c]]
        ids.sort(key=lambda c: ("[FAIL]" not in flags[c], c))
    if not ids:
        raise SystemExit("nothing to repair — the %s flagged no rows "
                         "(an empty repair is refused, never silently skipped)"
                         % ("census" if bank else "gate"))

    missing = [c for c in ids if c not in rows or c not in authored]
    if missing:
        raise SystemExit("not found in %s: %s"
                         % ("census+bank files" if bank else "payload+parts",
                            ", ".join(missing)))

    # THE CENSUS'S OWN SCOPE BOUNDARIES (§10-17 §2). It records `in_set` and `difficulty`
    # per row precisely because both are boundaries this plan learned the hard way, and a
    # tool that reads that census and ignores the fields is how they get crossed quietly.
    if bank and not args.allow_out_of_scope:
        out_of_scope = [(c, "in a committed 100-Q SET file" if rows[c].get("in_set")
                         else "tagged hard")
                        for c in ids
                        if rows[c].get("in_set") or rows[c].get("difficulty") == "hard"]
        if out_of_scope:
            raise SystemExit(BANK_ROWS_OUT_OF_SCOPE.format(
                n=len(out_of_scope),
                rows="\n".join("      %-28s %s" % (c, why) for c, why in out_of_scope)))

    # --finding is the FIELD axis and nothing else. A finding on a row this prompt does
    # not cover would otherwise be a silent no-op, and letting it ADD the row would route
    # around guard 2, whose whole job is to make a widened id set carry a criterion.
    stray = [c for c in oob if c not in ids]
    if stray:
        raise SystemExit(FINDING_NOT_IN_IDS.format(
            n=len(stray), ids="\n".join("      %s" % c for c in stray)))

    # GUARD 2 — every id the gate did not flag is a judgement call, and the judgement has
    # to be written down. `--fail-only` narrows and can never widen, so it is exempt by
    # construction rather than by a special case.
    widened = [c for c in ids if c not in flags]
    if widened and not args.scope_reason:
        raise SystemExit(WIDER_THAN_GATE.format(
            n=len(widened), g=len(ids) - len(widened),
            ids="\n".join("      %s" % c for c in widened), out=scope_path))

    # GUARD 3 — the pooling floor. Deliberately last: a small round is only worth
    # arguing about once the scope above it is settled.
    #
    # `--pooled-with` EXISTS BECAUSE THE GUARD USED TO FORBID ITS OWN REMEDY. The message
    # tells you to build every chunk's prompt and hand them to one agent; `--payload` takes
    # ONE payload, so a pooled round is necessarily several prompts, each counting only its
    # own rows. §10-14 hit this at 11 + 15 + 8 = 34 rows across three prompts: every one
    # refused, and the only escape was `--solo-reason`, whose text is "why this agent runs
    # ALONE". Overriding with that would have written a false statement into the scope
    # record — corrupting the one artifact issue #127 created to make 33-vs-124 legible.
    # A guard is allowed to be strict; it is not allowed to make the honest answer
    # unsayable.
    #
    # It cannot be used to wave the guard through a round that is really solo: the claim is
    # a ROW COUNT for the sibling prompts, it lands in the scope record, and the sibling
    # prompts either exist on disk with those rows or they do not.
    if args.pooled_with and args.solo_reason:
        raise SystemExit("build_repair_prompt: --pooled-with and --solo-reason contradict "
                         "each other — a round is pooled or it is solo, not both.")
    if len(ids) + args.pooled_with < POOL_FLOOR and not args.solo_reason:
        raise SystemExit(SOLO_ROUND.format(
            n=("%d row(s) here + %d declared pooled = %d"
               % (len(ids), args.pooled_with, len(ids) + args.pooled_with))
            if args.pooled_with else "%d row(s)" % len(ids), floor=POOL_FLOOR))

    # Whose `answer` disagrees with its assignment. Measured against the payload, not
    # read out of the gate report, so a --ids row with no gate line is covered too.
    # This is the ONE identity field the authored row can itself get wrong (§10-7), and
    # it decides the row's scope, its warning block, and whether the printed merge
    # command carries --payload.
    # Compared on the gate's own normalisation (`.strip().upper()`), so a case-only
    # `"c"` is NOT a mismatch here for the same reason it is not one there — the gate
    # passes it and apply_repair heals it.
    #
    # ALWAYS EMPTY IN --from-bank MODE, and that is the correct answer rather than a gap:
    # a committed row's `answer` has no assignment to disagree with, the bank row IS the
    # record, and moving the key between letters is the one edit §3 calls retroactively
    # destructive. apply_repair freezes it (no --payload exists to pass).
    mismatched = {} if bank else {
        cid: (rows[cid]["answer_letter"],
              str(authored[cid].get("answer", "")).strip().upper())
        for cid in ids
        if str(authored[cid].get("answer", "")).strip().upper()
        != rows[cid]["answer_letter"]}

    # Per-row scope first: the batch-wide line in the header is the union of these,
    # and both the follow-up apply_repair command and the explanation rule are
    # decided by what is (and is not) in it.
    scopes = {cid: finding_scope(flags.get(cid, []), cid in mismatched,
                                 tuple(f for f, _ in oob.get(cid, [])))
              for cid in ids}
    # The rows --finding actually MOVED, as opposed to the rows it was passed for. A
    # finding naming `options` on a row already scoped options is legitimate (the author
    # still gets to read it) and is not a widening, so it is not reported as one.
    moved = {cid: tuple(f for f in scopes[cid]
                        if f not in finding_scope(flags.get(cid, []), cid in mismatched))
             for cid in oob}
    moved = {c: f for c, f in moved.items() if f}
    union = tuple(f for f in SCOPE_FIELDS if any(f in s for s in scopes.values()))
    expl_ids = [c for c in ids if "explanation" in scopes[c]]
    opener = (EXPL_OPENER_SCOPED.format(ids="\n".join("  " + c for c in expl_ids))
              if expl_ids else EXPL_OPENER_FROZEN)

    # file -> the overlay it is merged from, and the ids that belong in it. Only
    # meaningful in --from-bank mode; `home` is populated either way so the printed
    # apply_repair line can name the right part.
    overlay_of = {p: args.overlay[i] for i, p in enumerate(parts)} if bank else {}
    ids_by_file: Dict[Path, List[str]] = {}
    for cid in ids:
        ids_by_file.setdefault(home[cid], []).append(cid)

    # Replaced by the read plan at the fixed point below. A literal token rather than a
    # format field because the header is rendered once and re-measured several times.
    READ_PLAN_SLOT = "<<<READ-PLAN>>>"
    if bank:
        out = [BANK_HEADER.format(
            read_plan=READ_PLAN_SLOT,
            n=len(ids),
            overlays="\n".join(
                "  %-4d row(s) from %s\n       -> %s" % (len(ids_by_file.get(p, [])),
                                                         p.name, overlay_of[p])
                for p in parts),
            scope=scope_phrase(union),
            rule=bank_rule_block(),
            explanation_rule=(BANK_EXPLANATION_RULE if expl_ids
                              else EXPLANATION_RULE.format(opener=EXPL_OPENER_FROZEN)))]
    else:
        out = [HEADER.format(n=len(ids), overlay=args.overlay[0],
                             identity=" · ".join(IDENTITY),
                             letter_rule=(LETTER_RULE.format(n=len(mismatched),
                                                             ids=" · ".join(mismatched))
                                          if mismatched else ""),
                             scope=scope_phrase(union),
                             explanation_rule=EXPLANATION_RULE.format(opener=opener))]
    last_file = None
    for cid in ids:
        r, it = rows[cid], authored[cid]
        opts = it["options"]
        mx = max(len(v) for v in opts.values())
        if bank and home[cid] != last_file:
            last_file = home[cid]
            out.append("\n" + "=" * 78)
            out.append("ROWS FROM %s — %d of them, and they go in ONE overlay:"
                       % (last_file.name, len(ids_by_file[last_file])))
            out.append("  %s" % overlay_of[last_file])
            out.append("=" * 78)
        out.append("\n" + "-" * 78)
        out.append("%s   [%s]" % (cid, r["difficulty"]))
        out.append("  %s SAID:" % ("CENSUS" if bank else "GATE"))
        # A census row with an EMPTY tell list is legitimate and means something specific:
        # the row's whole finding is on a field a census cannot speak about, delivered by
        # --finding below. Say that, rather than printing an empty section -- and note it
        # is NOT the same as `cid not in flags`, which is a row nothing flagged at all and
        # is guard 2's business. finding_scope reads the raw list, so an empty one leaves
        # `options` out of scope, which is exactly right here.
        out.extend("      %s" % f for f in
                   flags.get(cid) or ["(no option finding on this row — the whole finding "
                                      "is the audit line below)" if bank and cid in flags
                                      else "(named explicitly, no gate line)"])
        # The audit's own words, verbatim, ABOVE the scope line they widened (issue
        # #130). Printed as evidence rather than as an instruction: a blind rater and an
        # arithmetic auditor are finding aids, and §10-11 already cut such a list from 19
        # rows to 5, so the author is told who said it and left to judge the row.
        if cid in oob:
            out.append("  AN AUDIT ALSO SAID — a finding no gate can phrase, which is why")
            out.append("  the scope below is wider than the gate lines alone would give:")
            for field, text in oob[cid]:
                out.append("      [%s] %s" % (field, text))
        out.append("  REPAIR SCOPE: %s." % scope_phrase(scopes[cid]))
        # NO `ASSIGNED:` LINE ON A BANK ROW, deliberately. There is no payload, so there
        # is no LONGEST=, no KEY LENGTH RANK and no BAND to state -- and §10-10's most
        # expensive tooling bug was a prompt rendering a length instruction that did not
        # match the assignment the gate scored. Rendering one with NOTHING behind it is
        # that defect with the evidence removed. What the census does know goes here
        # instead, and every field of it is measured.
        if bank:
            out.append(BANK_ROW_FACTS.format(
                difficulty=r.get("difficulty"),
                key="YES" if r.get("key_tells") else "no",
                elim="YES" if r.get("eliminable") else "no"))
            if r.get("key_tells"):
                out.append(BANK_KEY_NOTE)
        elif "longest_letter" in r:
            lo, hi = r["option_length_band"]
            out.append("  ASSIGNED:  answer=%s   LONGEST=%s   BAND %d-%d"
                       % (r["answer_letter"], r["longest_letter"], lo, hi))
            # The key is assigned the longest slot on this row, so the blanket
            # "make a distractor longer than the key" rule below is the wrong
            # instruction here -- say so ON THE ROW (see KEY_LONGEST_NOTE).
            if r["longest_letter"] == r["answer_letter"]:
                out.append(KEY_LONGEST_NOTE.format(letter=r["longest_letter"]))
        else:
            rk = r["key_length_rank"]
            lo, hi = r["option_length_band"]
            out.append("  ASSIGNED:  answer=%s   KEY LENGTH RANK %d of 4 (%s)   BAND %d-%d%s"
                       % (r["answer_letter"], rk, RANK_WORD[rk], lo, hi,
                          "   key target ~%dch" % r["key_target_len"]
                          if r.get("key_target_len") else ""))
        if cid in mismatched:
            want, got = mismatched[cid]
            # A row with no `answer` at all lands here too (the gate hard-fails it as a
            # missing field); say so rather than rendering an empty letter.
            out.append(LETTER_NOTE.format(want=want, got=got or "NOTHING — the field is absent"))
        if bank:
            # DERIVED FROM THE ROW, NOT LISTED. apply_repair REPLACES the bank row with
            # the overlay object, so a field this block does not print is a field deleted
            # from the shipped bank -- `verified` was the live one. REWORD_MUTABLE is
            # imported from verify_reword, the §6 gate, so the set of fields the prompt
            # freezes and the set it checks cannot drift (#139, #76).
            out.append("  COPY THROUGH — verbatim, EVERY key below, exactly these strings:")
            for f, v in it.items():
                if f not in REWORD_MUTABLE:
                    out.append('      "%s": %s' % (f, json.dumps(v, ensure_ascii=False)))
        else:
            out.append("  COPY THROUGH — verbatim, these exact strings:")
            # PAYLOAD-authoritative, per field, with `difficulty` carved out and `answer`
            # read off `answer_letter` — see PAYLOAD_ALIAS / AUTHORED_SOURCE (issue #89).
            vals = payload_identity(r, it)
            for f in IDENTITY:
                out.append('      "%s": %s' % (f, json.dumps(vals[f])))
        # On a bank row the stem is already in COPY THROUGH above (it is frozen), so this
        # is a second rendering for READABILITY -- the author has to see the question the
        # four options are answering.
        out.append("\n  CURRENT STEM%s:\n      %s"
                   % (" (FROZEN — copy it through)" if bank else "", it["question"]))
        out.append("\n  CURRENT OPTIONS:")
        # The KEY marker follows the ASSIGNED letter, not the authored one: on a
        # mismatched row the authored letter is the defect, and marking it KEY would
        # point the repair at the wrong option. A bank row has no assignment: its own
        # `answer` IS the record, and it is frozen.
        key_letter = str(it.get("answer", "")).strip().upper() if bank else r["answer_letter"]
        for k in "ABCD":
            tags = ("  <-- KEY%s" % ("" if bank else " (the ASSIGNED letter)")
                    if k == key_letter else "") + \
                   ("  <-- the authored `answer` points HERE — that is the defect"
                    if cid in mismatched and k == mismatched[cid][1] else "") + \
                   ("  <-- currently LONGEST" if len(opts[k]) == mx else "")
            out.append("      %s. (%3dch)%s\n         %s" % (k, len(opts[k]), tags, opts[k]))
        # THE EXPLANATION MUST BE SHOWN (§10-11 finding 2). The header tells the agent
        # to keep `explanation` present and to edit it only where it quotes option text
        # -- but this tool used to inline the stem and options and NOT the explanation,
        # while also forbidding the agent to open any file. So the only way to satisfy
        # "keep it present" was to write a new one blind. Handed a row whose key was
        # arithmetically wrong, the chunk-8 repair agent did exactly that: it invented
        # an explanation ARGUING FOR THE WRONG ANSWER, invented per-distractor
        # rationales to match, and reported that the original had been "carried
        # through". A repair prompt that hides the field it asks you to preserve
        # manufactures that failure. Show it, and say plainly that rewriting is not
        # the job.
        if "explanation" in scopes[cid]:
            head = ("\n  CURRENT EXPLANATION — IN SCOPE on this row, because a finding\n"
                    "  above names the explanation itself. Fix what it named and nothing\n"
                    "  else; every per-distractor rationale already here must survive:")
        else:
            head = ("\n  CURRENT EXPLANATION — OUT OF SCOPE on this row. Carry it through\n"
                    "  UNCHANGED unless it quotes option text you edited, in which case\n"
                    "  change ONLY the quoted words. Do NOT rewrite it, re-derive it, or\n"
                    "  re-argue the answer, and do not drop a per-distractor rationale.\n"
                    "  If it contradicts the key, STOP and say so in your report rather\n"
                    "  than making it agree:")
        out.append("%s\n      %s" % (head, json.dumps(it.get("explanation", ""))))

    out.append("\n" + "-" * 78)
    if bank:
        out.append("\nWrite the overlays now. %d file(s); a row must go in the overlay for "
                   "the\nbank file it came from, and no id may appear in two overlays:\n"
                   % len(parts))
        for p in parts:
            here = ids_by_file.get(p, [])
            out.append("  %s\n    %d object(s): %s\n"
                       % (overlay_of[p], len(here), "\n" + "\n".join(
                           "      %s" % c for c in here) if here else "(none)"))
        out.append("\nThen report: the rows you changed, any row you left alone and why "
                   "(an\nerror-identification stem, an explanation you believe is wrong, a "
                   "figure you\nbelieve does not compute), and any construction you noticed "
                   "and DECLINED to\nrepair across the batch — that last one is worth as "
                   "much as the repairs.\n")
    else:
        out.append("\nWrite the overlay now — %d object(s), these ids and no others:\n  %s\n"
                   % (len(ids), "\n  ".join(ids)))

    text = "\n".join(out) + "\n"
    offsets: List[int] = [1]
    if bank:
        # THE READ PLAN IS SELF-REFERENTIAL, so it is solved to a FIXED POINT (#186's
        # rule: the header describes the file it is inside, to the byte). Inserting the
        # plan lengthens the file, which can add a page, which lengthens the plan. Two
        # or three passes settle it; the loop is bounded so a pathological oscillation
        # fails loudly rather than hanging.
        for _ in range(8):
            n_chars, n_lines = len(text), text.count("\n")
            offsets = read_offsets(n_lines, n_chars)
            plan = read_requirement(len(ids), n_chars, n_lines, offsets)
            if len(offsets) > 1:
                plan += ("\n\n  Read offsets: %s\n  Every row you do not read is a row "
                         "your overlay silently omits — and a short overlay reads "
                         "downstream\n  as an author that DECLINED those rows, which is "
                         "not a signal anything can\n  tell apart from the truth. State "
                         "the number of rows you repaired and the\n  number you "
                         "deliberately left alone; they must add to %d."
                         % (", ".join(str(o) for o in offsets), len(ids)))
            new = "\n".join(out).replace(READ_PLAN_SLOT, plan) + "\n"
            if new == text:
                break
            text = new
        else:
            raise SystemExit("the read plan did not settle in 8 passes — its own length "
                             "keeps changing the page count. Widen READ_PAGE_MARGIN's "
                             "slack or report this.")
    Path(args.out).write_text(text, encoding="utf-8")

    # THE SCOPE RECORD (issue #127). Written every time, not only when a guard was
    # overridden: the slice's own ledger records what each agent COST and nothing about
    # what it was asked to fix, which is why "the gates named 33 rows and 124 were
    # repaired" had to be reconstructed from overlay files afterwards. This is the
    # cheap, boring half of that — one file per prompt, next to the prompt.
    record = {
        "prompt": args.out,
        "mode": "from-bank" if bank else "in-flight",
        "overlay": args.overlay[0] if not bank else None,
        "overlays": ({str(p): overlay_of[p] for p in parts} if bank else None),
        # In --from-bank mode the CENSUS is the flagging instrument, so it is recorded in
        # the `gate` slot rather than beside it: that is what "gate_flagged" below counts
        # against, and a reader reconstructing the scope needs the file that named the rows.
        "gate": args.from_bank if bank else args.gate,
        "payload": args.payload,
        "parts": list(args.part),
        "rows": {"total": len(ids), "gate_flagged": len(ids) - len(widened),
                 "widened": widened,
                 "by_file": ({p.name: ids_by_file.get(p, []) for p in parts}
                             if bank else None)},
        "ids": ids,
        # #186: what the prompt claims about its own size, so a completed round is
        # auditable afterwards rather than only at build time.
        "prompt_chars": len(text),
        "read_offsets": offsets if bank else None,
        # Both axes of the scope, so the record answers "what was this agent asked to
        # fix" without anyone reconstructing it from overlays afterwards: which FIELDS
        # each row ended up with, and every out-of-band finding that opened one.
        "scopes": {c: list(scopes[c]) for c in ids},
        "out_of_band_findings": {c: [{"field": f, "text": t} for f, t in v]
                                 for c, v in oob.items()},
        "fields_widened": {c: list(f) for c, f in moved.items()},
        "guards": {
            "parts_newer_than_gate": [str(p) for p in stale],
            "stale_gate_reason": args.stale_gate_reason,
            "scope_reason": args.scope_reason,
            "solo_reason": args.solo_reason,
            "pooled_with": args.pooled_with,
            "pool_floor": POOL_FLOOR,
            "allow_out_of_scope": args.allow_out_of_scope,
        },
    }
    scope_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")

    print("  wrote repair prompt -> %s" % args.out)
    if bank:
        print("  %d COMMITTED row(s) across %d bank file(s) · %d with the tell on the KEY "
              "· ~%d chars (~%dk tok)"
              % (len(ids), len(parts), sum(rows[c].get("key_tells") for c in ids),
                 len(text), round(len(text) / 4000)))
        for p in parts:
            print("      %-40s %d row(s)" % (p.name, len(ids_by_file.get(p, []))))
        if len(offsets) > 1:
            print("  OVER THE SINGLE-READ CAP — %d chars is ~%.1fx the ~%s-char cap a "
                  "single Read\n  returns before it stops WITHOUT SAYING SO. The prompt "
                  "states its own size and\n  the %d Read offsets that page it: %s"
                  % (len(text), len(text) / READ_CAP_CHARS, format(READ_CAP_CHARS, ","),
                     len(offsets), ", ".join(str(o) for o in offsets)))
    else:
        print("  %d row(s): %d FAIL, %d soft · ~%d chars (~%dk tok)"
              % (len(ids), sum("[FAIL]" in flags.get(c, []) for c in ids),
                 sum("[FAIL]" not in flags.get(c, []) for c in ids),
                 len(text), round(len(text) / 4000)))
    # Distinct from the `scope:` line below, which reports which FIELDS are in scope.
    print("  ids: %d from the %s%s"
          % (len(ids) - len(widened), "census" if bank else "gate",
             " + %d widened by hand (%s)" % (len(widened), args.scope_reason)
             if widened else ""))
    if args.allow_out_of_scope:
        print("  GUARD OVERRIDDEN — §10-17 §2 scope boundary: %s" % args.allow_out_of_scope)
    for label, why in (("stale gate", args.stale_gate_reason),
                       ("solo round", args.solo_reason)):
        if why:
            print("  GUARD OVERRIDDEN — %s: %s" % (label, why))
    # Not an override: the floor is MET, by a round the tool can now see the whole of.
    if args.pooled_with:
        print("  pooled round: %d row(s) here + %d in this round's other prompt(s) = %d "
              "(floor %d)" % (len(ids), args.pooled_with,
                              len(ids) + args.pooled_with, POOL_FLOOR))
    print("  scope record -> %s" % scope_path)
    by_scope: Dict[tuple, int] = {}
    for s in scopes.values():
        by_scope[s] = by_scope.get(s, 0) + 1
    print("  scope: %s" % " · ".join(
        "%d row(s) %s" % (n, "+".join(s)) for s, n in sorted(by_scope.items())))
    # A NARROWED ROW MUST BE VISIBLE (issue #130). The scope counts above say what the
    # batch got; these two lines say which rows are tighter than the batch and which
    # ones an audit had to open by hand. §10-13's three lost stem repairs were invisible
    # here — every chunk exited 0 and the only signal was the agent's prose.
    # Printed even when the WHOLE batch is narrowed, which reads as a repeat of the
    # scope line above and is not: §10-13's chunk 10 was exactly that shape (3 of 3
    # rows options-only, `scope: 3 row(s) options`, nobody read it as a refusal) and
    # it is the case where an audit finding is least deliverable.
    tight = [c for c in ids if "question" not in scopes[c] and "explanation" not in scopes[c]]
    if tight:
        print("  narrowed: %d of %d row(s) may touch OPTIONS only — a stem or "
              "explanation finding\n            is NOT deliverable on them without "
              "--finding: %s" % (len(tight), len(ids), " ".join(tight)))
    if moved:
        print("  fields opened by --finding: %s"
              % " · ".join("%s +%s" % (c, "+".join(f)) for c, f in moved.items()))
    # The scope the prompt states is the scope the merge should enforce. `question`
    # is freezable outright when no row was flagged for its stem; `explanation` is
    # not offered here, because a row whose options moved may legitimately have to
    # fix a quote of them -- apply_repair reports those changes instead of refusing
    # them (issue #77).
    freeze = "" if "question" in union else " --also-freeze question"
    if bank:
        # ONE COMMAND PER FILE, and --expect scoped to that file's ids. A pooled --expect
        # across three pools disarms the one guard that catches an overlay row landing in
        # the wrong file (§10-17 §5), and --id-field id is what keys the merge on the
        # bank's own id rather than an in-flight cand_id (issue #73).
        for p in parts:
            here = ids_by_file.get(p, [])
            print("  overlay -> %s (%d row(s))" % (overlay_of[p], len(here)))
            print("  then: apply_repair.py --overlay %s --part %s --id-field id%s "
                  "--expect %s" % (overlay_of[p], json.dumps(str(p)), freeze,
                                   " ".join(here)))
        print("        (--id-field id keys the overlay on the bank's own id; %s is what "
              "makes\n         §3's \"the stem never moves\" mechanical rather than "
              "stated. `answer` is\n         frozen with no way to unfreeze it — there is "
              "no payload here.)" % (freeze.strip() or "--also-freeze question"))
        return
    print("  overlay must be written to: %s" % args.overlay[0])
    # `answer` is frozen by apply_repair unless --payload is passed, and the letter is
    # the defect on these rows -- so the command that repairs them has to carry it, or
    # the merge refuses the whole overlay and every other row in it is thrown away
    # (issue #89). Only added when a row actually needs it: --payload widens what the
    # merge will accept, and nothing should widen by default.
    payload_flag = " --payload %s" % args.payload if mismatched else ""
    print("  then: apply_repair.py --overlay %s --part %s%s%s --expect %s"
          % (args.overlay[0], " ".join(args.part), payload_flag, freeze, " ".join(ids)))
    if mismatched:
        print("        (--payload is REQUIRED here: %d row(s) carry an `answer` that "
              "disagrees\n         with the assignment — %s — and apply_repair "
              "accepts that change\n         ONLY onto the assigned letter, and only "
              "with --payload)" % (len(mismatched), ", ".join(
                  "%s %s->%s" % (c, got, want) for c, (want, got) in mismatched.items())))
    if freeze:
        print("        (no row here was flagged for its stem, so the merge can freeze it;"
              "\n         add `explanation` to --also-freeze to refuse ANY explanation"
              " edit,\n         at the cost of the quote-level fix the prompt allows)")


if __name__ == "__main__":
    main()
