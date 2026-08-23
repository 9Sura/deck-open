#!/usr/bin/env python3
"""Build a concept-chunk authoring prompt: the brief + the payload rows, inlined.

Emits ONE self-contained text file that a single Sonnet author agent reads and works from,
so its entire job is `Read` once then `Write` each group. Point the agent at the output with
a short launch message; do not paste the payload into the agent prompt by hand (transcription
of cand_ids / letters / bands is where a slice silently breaks).

WHY THE GROUPS (plan 10-2 §2c, measured 2026-07-28) -- items-per-agent and items-per-Write are
DIFFERENT caps, and CONFLATING THEM IS THE EXPENSIVE MISTAKE:
  * items per agent  75-95    -- what has actually worked. A 120-150 band was proposed on the
                               "~65k fixed overhead per agent" theory; it is CONTESTED, see
                               below, and it is not the default until one chunk measures it.
  * items per Write  ~31     -- the 64k output ceiling is per MESSAGE. Authored items run
                               ~275-293 tok/item, so 93 items in one Write is ~82k: over the
                               ceiling before it starts.

THE AGENT CAP IS NOT MEASURED FROM A FAILURE -- IT IS A BLAST-RADIUS CHOICE, AND THE THEORY
UNDER IT IS IN DOUBT. Nothing has ever died from too many items per AGENT; both deaths on record
were single oversized WRITES, and at 150 items in 5 groups a dead agent costs only the group in
flight (~31 items) since finished groups are already on disk. That part is not contested.
What IS contested is whether a bigger agent is CHEAPER. §2b says yes: ~65k per agent is fixed,
so 8 agents x 65k = 520k of §10-4's 769k slice bought no questions. The rival theory says the
bill is dominated by CONTEXT RE-INGESTION -- every tool call re-sends the brief plus every group
already written -- under which a bigger agent needs MORE Writes and costs MORE.
`agent_cost.py` (lever 1) scored §10-4's three real chunks against both:
    chunk1  measured 187.8k   T_FLAT 101.9k   T_REINGEST 149.7k
    chunk2  measured 161.1k   T_FLAT  96.0k   T_REINGEST 154.3k
    chunk3  measured 158.3k   T_FLAT  92.8k   T_REINGEST 121.6k
All three land nearer T_REINGEST, which does NOT support raising the band. It is retrodiction on
three points and both theories under-predict (the residue is thinking), so it settles nothing --
but it is the only evidence there is. So keep the size that already works until one chunk runs
at ~150 with `agent_cost.py record` filled in; `predict` pre-registers both numbers and they
differ by ~140k on that shape, far too big to miss.
WHATEVER SIZE YOU RUN, hold it to §10-4's quality baselines (check_authored first-pass rate,
key-is-longest ~25-27%, LONGEST= compliance ~97%). If any of the three moves, the size is wrong
and no token saving is worth it.
Run as one agent + one 93-item Write, chunks 1 and 2 BOTH died having written nothing (~30 min
of thinking, 188 and 10 output tokens, zero tool calls after the Read). Re-run at 3 groups of
31 in strict order: 4 tool calls each, 93/93 first-pass gate, no repair, 1.77k tok/item.

The strict-ordering paragraph below is load-bearing -- without it the model plans the whole
batch before emitting anything, which is exactly the failure above. Telling the agent what
happened to its predecessor is part of what fixed it.

GROUP COUNT IS A CAPPED LEVER, AND THAT IS WHY THE PROMPT IS THE FREE ONE (measured on §10-14,
the first slice to score T_REINGEST). `agent_cost.py predict` on chunk 2's real shape:
    95 items, 4 groups, 67,670 chars   T_REINGEST 194.6k  (2.05k/item)
    95 items, 2 groups, 67,670 chars   T_REINGEST 125.1k  <- forbidden: 47.5 items/Write
    95 items, 4 groups, 40,000 chars   T_REINGEST 153.1k  (1.61k/item)
The 2-group column is the cheapest and is UNREACHABLE -- ~31 items per Write is the 64k output
ceiling, so 95 items cannot go below 3 groups no matter what it saves. Do not chase it; two
agents have already died proving that ceiling is real. The prompt-size column has no such cap,
which is the whole reason lever 3 was reopened (see the composition note in main()).
`--pack-groups` is the one group-count saving that is actually available: it removes Writes
whose only reason to exist is an area boundary.

Usage:
  python build_prompt.py <payload.json> --out <prompt.txt> \
      --parts-dir <abs dir where the author writes> --stem chunk3 [--group-size 31]
"""
import argparse
import ast
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BRIEF = os.path.join(HERE, "..", "prompts", "authoring-concept.txt")
# The ONLY brief a payload with hard rows may be authored against -- see the guard in main().
HARD_BRIEF = "authoring-hard-bare.txt"
CHECK_AUTHORED = os.path.join(HERE, "check_authored.py")

# The items-per-AGENT band (see the docstring). Advisory, printed at build time --
# this script builds one prompt and does not decide how the work order was chunked,
# so the only useful thing it can do is tell you the chunk is the wrong size while
# there is still time to re-chunk it. Set to the PROVEN band, not the proposed
# 120-150 one: `agent_cost.py` scored the only three measured chunks against both
# cost theories and they favour the theory under which bigger agents cost MORE.
# Raise these two numbers when, and only when, a 150-item chunk has been measured.
AGENT_MIN, AGENT_MAX = 75, 95
AGENT_OVERHEAD_K = 65  # measured fixed cost of an agent, in thousands of tokens


def _length_assignment(r):
    """(the payload field the gate will score this row's LENGTH on, the token that renders it).

    The length assignment is ONE gated slot in THREE shapes, and both sides pick
    among them by the same precedence -- `check_authored.py` at :497 (rank), then
    :504 (letter), then :533 (the bit), and `_length_spec()` below in that order.
    Only the FIRST shape a row carries is scored, so the others are not owed a
    rendering: every `--free-rank` row carries `longest_letter` AND
    `key_may_be_longest` (build_area.py :414-415) and the gate reads only the
    letter. A per-field guard that did not model this would demand
    `KEY-MAY-BE-LONGEST` on the page for a row nothing will ever score it on.

    `key_may_be_longest` is the one field whose token depends on its VALUE: true
    renders as a permission, false as the opposite instruction.
    """
    if r.get("key_length_rank"):
        return "key_length_rank", "KEY-RANK="
    if r.get("longest_letter"):
        return "longest_letter", "LONGEST="
    if r.get("key_may_be_longest") is not None:
        return ("key_may_be_longest",
                "KEY-MAY-BE-LONGEST" if r["key_may_be_longest"] else "DISTRACTOR>=KEY")
    return None, None


def _length_spec(r):
    """The row's length assignment, as something the author can OBEY.

    Three payload shapes (see `_length_assignment`), and the rank one MUST be
    checked first.

    `key_length_rank` is what a RANKED payload (build_area.py without
    --free-rank -- every hard batch) actually carries, and `check_authored.py`
    HARD-FAILS a row whose key does not land on it. This function used to not
    know the field existed: it fell through to the `key_may_be_longest` branch,
    which is absent on a ranked row, and every row rendered as a blanket
    DISTRACTOR>=KEY. That is not merely silent about the rank -- it is the
    OPPOSITE instruction on a rank-1 row, where the key is meant to be longest.

    MEASURED, twice, before it was diagnosed. §10-8's H1 came back with 13 of 18
    keys at rank 4 against an assigned 5/5/4/4 spread and cost two repair rounds
    (147.2k tokens, more than the 116.6k that authored it); build_repair_prompt
    still carries that batch as evidence of an author "driving every key to rank
    4", when the author was in fact obeying the only length instruction it was
    given. §10-10's H1 then failed 7 of 9 the same way. §10-9's passed 9 of 9 in
    between, which is why it survived this long -- a 9-row batch can land its
    ranks by luck.

    Prefers, in order: the rank (with the per-option targets the payload already
    computes), then `longest_letter` (build_area.longest_letters), then the older
    `key_may_be_longest` bit so pre-existing payloads still render. The letter
    form exists because the bit was a prose comparison the author had to measure
    to obey, and §10-2 chunk 3 missed it on 46 of 46 rows.

    The TOP-GAP cap rides along on whichever shape carries it. It is scored
    (`check_authored.py:552`) and, until issue #76, was rendered nowhere -- the
    same class of defect as the unrendered rank, caught by the same guard once the
    guard was made to agree with the gate.
    """
    field, token = _length_assignment(r)
    if field == "key_length_rank":
        rank = r["key_length_rank"]
        where = {1: "LONGEST", 4: "SHORTEST"}.get(rank, "%d%s longest" % (rank, "nd" if rank == 2 else "rd"))
        spec = "%s%d of 4 (the key is the %s of the four)" % (token, rank, where)
        kt, dts = r.get("key_target_len"), r.get("distractor_target_lens")
        if kt and dts:
            spec += " | key ~%dch, distractors ~%sch" % (kt, "/".join(str(d) for d in dts))
    elif field == "longest_letter":
        spec = "%s%s" % (token, r["longest_letter"])
        tl = r.get("option_target_lens")
        if tl:
            spec += " | AIM " + " ".join("%s~%d" % (k, tl[k]) for k in sorted(tl))
    else:
        spec = token or "DISTRACTOR>=KEY"
    gap = r.get("max_top_gap")
    if gap:
        spec += " | TOP-GAP<=%dch" % gap
    return spec


# Payload fields `check_authored.py` scores PER ROW, each mapped to the token that
# must appear on the rendered row. If a row carries one and the prompt never says
# so, the author is being graded on an instruction it was not given -- which is
# exactly how `key_length_rank` went unrendered for three slices (§10-8, §10-9,
# §10-10; ~215k in repairs before it was diagnosed).
#
# THE MAP IS DERIVED FROM THE GATE, NOT FROM MEMORY. `gate_scored_fields()` below
# reads `check_authored.py` and `assert_map_matches_gate()` fails the build when
# the two disagree in EITHER direction. The hand-written first version (issue #76)
# was wrong both ways at once: it listed `option_target_lens`, which the gate has
# never read, and omitted `key_target_len`, `max_top_gap` and `key_may_be_longest`,
# which it does. A guard advertising coverage it does not have is the failure it
# exists to prevent, and reading the gate is the only way to keep it honest --
# #76's own field list was likewise a field off (it counted
# `distractor_target_lens` as scored; only the author-facing render uses it).
#
# The three LENGTH fields are deliberately absent here: they are one slot in three
# shapes, resolved per row by `_length_assignment()` under the gate's own
# precedence, because a row carrying two of them is scored on only the first.
LENGTH_FIELDS = ("key_length_rank", "longest_letter", "key_may_be_longest")

GATED_FIELDS = {
    "answer_letter": "LETTER=",
    "option_length_band": "BAND ",
    "key_target_len": "key ~",          # inside `| key ~90ch, distractors ~80/70/60`
    "distractor_target_lens": "distractors ~",
    "option_target_lens": "AIM ",
    "max_top_gap": "TOP-GAP<=",
    # Copied-verbatim fields. The gate hard-fails a row whose value was rewritten
    # away from the assignment, so the value itself is what has to be on the page.
    "difficulty": lambda r: r["difficulty"].upper(),
    "performanceIndicator": lambda r: r["performanceIndicator"],
    "instructionalArea": lambda r: r["instructionalArea"],
}

# AIM USED TO LIVE HERE, AND ISSUE #139 ENDED THAT. The comment in
# `assert_map_matches_gate` called it in advance -- "the day AIM stops being
# advisory, the comment saying 'nothing gates these' becomes the new version of
# the bug" -- and #139's `assigned_option_targets()` is that day: it reads
# `option_target_lens` (free-rank rows) and `distractor_target_lens` (ranked
# rows) off every payload row it scores. The guard caught it at the first prompt
# build after the change, which is exactly the job it was given in #76.
#
# THE DIRECTION IS BACKWARDS FROM #76 AND THEY STILL BELONG IN THE MAP. These two
# are read to SUPPRESS a length soft, not to grade the author -- so omitting one
# cannot make a compliant author look non-compliant, which is the harm #76 was
# about. But `assignment_caused_softs` only defers when the author wrote the key
# WITHIN `TARGET_TOLERANCE` OF ITS ASSIGNED TARGET (condition 2), and an author
# never shown the number cannot meet that condition. Drop the render and the row
# keeps a soft its own ladder assignment caused -- the #76 failure mode one step
# removed: not "graded on an instruction it was never given" but "denied a
# deferral it was never given the chance to earn". Same 46 rows, same cause.
#
# Each renders in its own `_length_spec()` branch and the two payload shapes are
# disjoint (measured: free-rank carries `option_target_lens` only, ranked carries
# `distractor_target_lens` + `key_target_len` only), so the per-row `is None`
# skip in `assert_assignments_rendered` resolves the right one without the
# precedence dance `_length_assignment()` needs.
ADVISORY_FIELDS = ()


def _spec_key(node):
    """The literal payload key this AST node reads off a row's `spec`, or None."""
    def is_spec(n):
        return isinstance(n, ast.Name) and n.id == "spec"

    def literal(n):
        return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None

    if isinstance(node, ast.Subscript) and is_spec(node.value):
        return literal(node.slice)                       # spec["key_target_len"]
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get" and is_spec(node.func.value) and node.args):
        return literal(node.args[0])                     # spec.get("key_may_be_longest")
    if (isinstance(node, ast.Compare) and len(node.ops) == 1
            and isinstance(node.ops[0], (ast.In, ast.NotIn))
            and is_spec(node.comparators[0])):
        return literal(node.left)                        # "max_top_gap" in spec
    return None


def gate_scored_fields(path=CHECK_AUTHORED):
    """Every payload key `check_authored.py` reads off a row's `spec`.

    Parsed, not grepped, so a key inside a comment or a message string cannot
    inflate the set. Scoped to `spec` -- the name the gate binds each row's
    payload entry to -- which is the PER-ROW grading path this guard is about.
    The batch summaries further down that file read the same three length fields
    off `p` and add nothing, so the narrower scope loses nothing today; widen it
    here if that stops being true.
    """
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    return {k for node in ast.walk(tree) if (k := _spec_key(node))}


def assert_map_matches_gate():
    """Fail the build when GATED_FIELDS and the gate have drifted apart.

    This is the part issue #76 was missing. The old map was hand-written and
    silently wrong in both directions; nothing would have told anyone. Now a field
    added to `check_authored` breaks every prompt build until it is classified
    here, and a field dropped from the gate stops being advertised as covered.
    """
    scored = gate_scored_fields()
    mapped = set(GATED_FIELDS) | set(LENGTH_FIELDS)
    unmapped, stale = sorted(scored - mapped), sorted(mapped - scored)
    # ADVISORY_FIELDS is a claim about the gate too, and the same drift breaks it:
    # the day AIM stops being advisory, the comment saying "nothing gates these"
    # becomes the new version of the bug.
    promoted = sorted(set(ADVISORY_FIELDS) & scored)
    if unmapped or stale or promoted:
        raise SystemExit(
            "build_prompt: GATED_FIELDS no longer describes check_authored.py.\n"
            + ("  scored by the gate, unmapped here: %s\n" % ", ".join(unmapped) if unmapped else "")
            + ("  mapped here, no longer scored:     %s\n" % ", ".join(stale) if stale else "")
            + ("  called advisory, now scored:       %s\n" % ", ".join(promoted) if promoted else "")
            + "Classify each one -- give it a render + a token, or drop it -- before shipping.")


def assert_assignments_rendered(rows, blocks):
    """Fail loudly if a scored assignment never reaches the page.

    Not a style check. A payload field the gate reads and the prompt omits is an
    unwinnable instruction, and the author's output will look like non-compliance.

    Checked against the RENDERED ROWS, never the whole prompt. The legend explains
    every token it knows about, so searching the full text finds `KEY-RANK=` in the
    prose while every actual row still says something else -- which is precisely the
    bug this guards, and it passed a whole-prompt check when tried that way.
    """
    assert_map_matches_gate()
    missing = set()
    for r in rows:
        for f, want in GATED_FIELDS.items():
            if r.get(f) is None:
                continue
            token = want(r) if callable(want) else want
            if token not in blocks:
                missing.add(f)
        f, token = _length_assignment(r)
        if f and token not in blocks:
            missing.add(f)
    if missing:
        raise SystemExit(
            "build_prompt: these payload fields are scored by check_authored.py but\n"
            "appear nowhere in the rendered prompt: %s\n"
            "The author would be graded on an assignment it was never given.\n"
            "Add a render + legend branch in _length_spec()/compact() before shipping."
            % ", ".join(sorted(missing)))


LEGEND_LONGEST = """  LONGEST=Y         -> option Y must be the LONGEST of the four. Two assignments per row, and
                       you satisfy BOTH the same way: by deciding, before you write, which slot
                       gets which job. Y is usually NOT the same letter as X -- when it is not,
                       the correct option is deliberately not the longest, so a student who
                       picks the longest option without reading gains nothing. When Y and X ARE
                       the same letter, the key being longest is intended on that row.
                       Give option Y its length with real substance -- a named mechanism, a
                       specific consequence, a scope -- never filler, and NEVER by trimming the
                       key (the key is the one option that must stay precisely true). Option Y
                       still has to obey every other rule: in band, clearly wrong if it is a
                       distractor, same category as the question asks (rule 5), no absolutes
                       (rule 4), not a near-synonym of another option (rule 7).
                       You do not need to count characters to do this. Write option Y with one
                       more clause of real content than the others and it will be the longest.

  AIM A~n B~n C~n D~n -> the character length each option should come out NEAR. These are the
                       band and the LONGEST= letter, restated as four numbers so you never have
                       to check a range or compare options: write each option to about its
                       number and BOTH assignments are satisfied by construction.

                       THEY ARE GUIDANCE, NOT A TEST. Nothing fails for missing one by a few
                       characters. What DOES get flagged is an option outside the BAND, and
                       that is the single most-missed rule in this pipeline -- one batch came
                       back with 83 of 93 rows carrying an out-of-band option. Writing to the
                       number is how you avoid it without measuring anything.

                       An option that will not fit its number is telling you something real:
                       under it, the option is under-specified and needs the same concrete
                       detail the others have; well over it, the option is doing too much and
                       the setup belongs in the stem. Never pad to reach a number, and never
                       cut the qualifier that makes an option true in order to hit one."""

LEGEND_RANK = """  KEY-RANK=n of 4   -> WHERE THE KEY SITS when the four options are ordered longest to
                       shortest. Rank 1 means the key must be the LONGEST option on that row;
                       rank 4 means it must be the SHORTEST; 2 and 3 are the places between.
                       The row also prints the character length each option should come out
                       near -- `key ~90ch, distractors ~80/70/60`. Write to those numbers and
                       the rank falls out on its own; you never have to compare four options.

                       THIS IS THE ONE ASSIGNMENT THAT IS DIFFERENT ON EVERY ROW, and it is
                       checked as a strict rank -- a tie counts as a miss, and being close
                       counts as a miss. It is NOT the rule "the key must never be longest".
                       Roughly a third of the rows in a hard batch are assigned rank 1, and on
                       those rows a distractor longer than the key is the defect, not the fix.

                       THE RANKS ARE A DISTRIBUTION, NOT A PREFERENCE. They are spread across
                       the batch precisely so that option length carries no signal about which
                       option is correct. A key that is reliably the SHORTEST is exactly as
                       exploitable as one that is reliably the longest, so driving every key
                       short is not the safe choice -- it is the failure this assignment exists
                       to prevent. Author each row to its OWN rank.

                       SET THE RANK BY SIZING THE DISTRACTORS, not by trimming the key: the key
                       is the one option that has to stay precisely true, and buying a rank by
                       deleting the qualifier that makes it correct is a worse defect than the
                       length tell it fixes. Give a distractor its length with real substance --
                       a named mechanism that is WRONG here, a plausible wrong formula, the
                       commonly confused metric -- never filler and never a bare figure. Every
                       option still has to obey every other rule: in band, clearly wrong if it
                       is a distractor, same category the question asks for (rule 5), no
                       absolutes (rule 4), not a near-synonym of another option (rule 7)."""

LEGEND_TOP_GAP = """

  TOP-GAP<=n ch     -> the LONGEST option may not stand more than n characters clear of the
                       second-longest. Not a rule about the key: it binds whichever option
                       comes out longest, because "pick the conspicuously longest option"
                       is a strategy that works on the row whether the conspicuous option is
                       the key or a distractor. The rank tells the author WHERE the key sits;
                       this tells it how far apart the top two may be.

                       You get this for free by writing to the per-option numbers on the row
                       -- they are derived from the band, the rank AND this cap together, so
                       four options near their targets cannot breach it. It bites when one
                       option runs away from its number."""


def group_rows(rows, size):
    """Split rows into Write-groups of <=size that NEVER span two instructional areas.

    Blind slicing at N straddles area boundaries, and that is the mechanism behind the
    only hard gate failure §10-2 produced (plan 10-2 §2d): the author infers ONE area per
    group FILE and stamps it across the group, so the rows on the far side of the boundary
    come back with the neighbouring area's label. Grouping per area removes the ambiguity
    instead of relying on the gate to catch it afterwards.

    Within an area the groups are near-equal rather than greedy (36 -> 18+18, not 31+5),
    which keeps every Write comfortably under the 64k output ceiling.
    """
    if len(rows) <= size:
        return [list(rows)]  # one Write: no boundary to straddle, and AREA= is on every row
    groups = []
    for area in dict.fromkeys(r["instructionalArea"] for r in rows):
        arows = [r for r in rows if r["instructionalArea"] == area]
        n = math.ceil(len(arows) / size)
        base, extra = divmod(len(arows), n)
        i = 0
        for k in range(n):
            take = base + (1 if k < extra else 0)
            groups.append(arows[i:i + take])
            i += take
    return groups


def pack_rows(rows, size):
    """Like group_rows, but BIN-PACKS small areas together instead of giving each its own Write.

    WHY (plan 10-12, measured 2026-08-04). Every group is a Write, and every Write
    re-sends the brief plus every group so far -- the cost driver `agent_cost.py`
    labels T_REINGEST. So a chunk's price tracks its GROUP COUNT, not its item
    count. §10-12 measured the inversion directly:

        chunk9   87 items, 4 groups (4 areas)  ->  239.0k = 2.75k/item
        chunk10  58 items, 7 groups (7 areas)  ->  176.5k = 3.04k/item

    The SMALLER chunk cost more per item, because seven small areas forced seven
    Writes and ~148k of re-sent prefix against chunk9's ~103k. Packing chunk10's
    seven areas into two groups of <=31 removes five Writes and their prefixes.

    WHY THIS IS OPT-IN. `group_rows` splits per area because of a real failure
    (plan 10-2 §2d): the author inferred ONE area per group file and stamped it
    across the rows. That was mitigated afterwards by rendering AREA= on every row
    and by the mixed-area group header, both of which already exist and already
    ship whenever a whole chunk fits in one group. Packing leans on that
    mitigation rather than on the per-area belt, so it stays behind a flag until a
    slice has run it with the ledger filled in. Never split an area across groups
    unless the area alone exceeds `size`.
    """
    if len(rows) <= size:
        return [list(rows)]
    by_area = {a: [r for r in rows if r["instructionalArea"] == a]
               for a in dict.fromkeys(r["instructionalArea"] for r in rows)}
    split_groups, whole_areas = [], []
    # An area too big for one Write keeps the near-equal split and its own groups,
    # exactly as group_rows does. Those groups are never packed into.
    for area, arows in by_area.items():
        if len(arows) > size:
            n = math.ceil(len(arows) / size)
            base, extra = divmod(len(arows), n)
            i = 0
            for k in range(n):
                take = base + (1 if k < extra else 0)
                split_groups.append(arows[i:i + take])
                i += take
        else:
            whole_areas.append(arows)
    # First-fit-decreasing over the areas that fit whole. Deterministic: sort by
    # size then area name, so one payload always packs to the same groups.
    packed = []
    for arows in sorted(whole_areas, key=lambda g: (-len(g), g[0]["instructionalArea"])):
        for grp in packed:
            if len(grp) + len(arows) <= size:
                grp.extend(arows)
                break
        else:
            packed.append(list(arows))
    return split_groups + packed


def compact(rows, show_area=False):
    """One line per row (+ indented AVOID lines) -- ~56 tok/row vs ~124 as raw JSON.

    ``show_area`` puts AREA= on the row itself, as prominent as LETTER=/LONGEST=.
    The row always carried the area in the payload but never on the rendered line,
    so an author with a mixed batch had nothing to copy from but the group header
    -- which is precisely how §10-2 chunks 6/7 stamped one area across a group.
    """
    out = []
    for r in rows:
        lo, hi = r["option_length_band"]
        out.append(
            "%s | %s | %sPI: %s | LETTER=%s | BAND %d-%d | %s"
            % (
                r["cand_id"],
                r["difficulty"].upper(),
                ("AREA=%s | " % r["instructionalArea"]) if show_area else "",
                r["performanceIndicator"],
                r["answer_letter"],
                lo,
                hi,
                _length_spec(r),
            )
        )
        for a in r.get("avoid") or []:
            out.append("    AVOID: %s -> %s" % (a["gist"], a["key"]))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Build a concept-chunk authoring prompt.")
    ap.add_argument("payload", help="build_area.py --out JSON")
    ap.add_argument("--out", required=True, help="prompt text file to write")
    ap.add_argument("--parts-dir", required=True,
                    help="ABSOLUTE dir the author writes its part files into")
    ap.add_argument("--stem", required=True, help="part-file stem, e.g. chunk3")
    ap.add_argument("--pack-groups", action="store_true",
                    help="bin-pack small instructional areas into shared Write-groups instead "
                         "of one group per area. Cuts Writes, and every Write re-sends the "
                         "whole prefix (§10-12: 58 items in 7 groups cost MORE per item than "
                         "87 items in 4). Opt-in until a slice runs it with the ledger filled.")
    ap.add_argument("--group-size", type=int, default=None,
                    help="items per Write (default: 31 concept, 5 hard -- see the 64k note above)")
    ap.add_argument("--brief", default=BRIEF,
                    help="authoring brief to inline (default authoring-concept.txt; a payload "
                         "containing hard rows must pass ../prompts/authoring-hard-bare.txt "
                         "-- the concept brief omits the C1/C2 hard routes and forbids hard rows, "
                         "and the FULL brief (authoring.txt, 28k) causes the stem-telegraph defect "
                         "it warns about: it held 0 of 43 hard items twice where the bare 15k "
                         "brief held 7 of 8 (plan 10-5, 10-6))")
    ap.add_argument("--brief-override", action="store_true",
                    help="author a hard payload against a brief other than %s. DELIBERATE ONLY: "
                         "it re-opens the measured stem-telegraph failure, so the flag has to "
                         "appear in the slice plan's command block where a reader can see it "
                         "(issue #87)" % HARD_BRIEF)
    args = ap.parse_args()

    with open(args.payload, encoding="utf-8") as f:
        rows = json.load(f)
    areas = sorted({r["instructionalArea"] for r in rows})
    tiers = {r["difficulty"] for r in rows}
    has_hard = "hard" in tiers
    cluster = rows[0]["cluster"]
    level = rows[0]["level"]
    with open(args.brief, encoding="utf-8") as f:
        brief = f.read()
    # Name the brief that was ACTUALLY read. This header used to be the hardcoded
    # string "src/prompts/authoring-concept.txt", so a `--brief` run produced a
    # prompt file that misnamed its own brief. That is the §10-5 failure mode in
    # reverse: the full brief held 0 of 43 hard rows twice, the bare one 7 of 8,
    # so a later session auditing a committed h1 prompt would read the wrong brief
    # off the header and re-diagnose a solved problem.
    brief_label = os.path.relpath(args.brief, os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))

    # THE HARD BRIEF IS AN ALLOW-LIST, NOT A DENY-LIST (issue #87).
    #
    # This guard used to name the ONE wrong brief someone had been bitten by
    # (authoring-concept.txt), which meant the brief with the *measured* failure
    # record on this exact payload shape -- the full authoring.txt -- sailed
    # through it, and five slice plans still named that brief on their H1 line.
    # A deny-list is only ever right about the mistakes already made; an
    # allow-list is right about every brief that does not exist yet, which is
    # the property issue #76 established this toolchain should prefer.
    if has_hard and os.path.basename(args.brief) != HARD_BRIEF and not args.brief_override:
        why = {
            "authoring-concept.txt":
                "the concept brief drops the C1/C2 hard routes and tells the author not to "
                "author any hard item",
            "authoring.txt":
                "the FULL brief causes the stem-telegraph defect it warns about -- it held "
                "0 of 43 hard items TWICE (86 items, ~1.3M tokens) where the bare brief held "
                "7 of 8 (plan 10-5, 10-6). The defect is invisible to every gate in this "
                "suite; only the 2-rater reconcile sees it",
        }.get(os.path.basename(args.brief),
              "only the bare hard brief has ever produced hard items that held")
        ap.error("payload contains %d hard row(s) but --brief is %s: %s. Pass --brief %s "
                 "(or --brief-override, deliberately, in the slice plan's command block)."
                 % (sum(1 for r in rows if r["difficulty"] == "hard"),
                    os.path.basename(args.brief), why,
                    os.path.join(HERE, "..", "prompts", HARD_BRIEF)))

    if has_hard and args.brief_override:
        print("WARNING: --brief-override: authoring %d hard row(s) against %s, not %s. "
              "The full brief measured 0 of 43 held, twice (plan 10-5)."
              % (sum(1 for r in rows if r["difficulty"] == "hard"),
                 os.path.basename(args.brief), HARD_BRIEF))

    # THE PER-WRITE CAP IS A REASONING BUDGET, NOT A BYTE BUDGET (plan 10-4).
    #
    # The 64k ceiling is per RESPONSE and it counts thinking, so what fits in one
    # Write depends on how much reasoning each item costs -- not on how much JSON
    # it produces. §10-2 measured concept items at ~31/Write and that still holds.
    # HARD items are several times more expensive to think through (a C2 needs a
    # defensible near-correct pair plus a stem checked for telegraphing), and 19
    # of them in a single terminal Write killed this slice's first H1 author at
    # ~13k of actual JSON -- the batch's accumulated reasoning, not its output,
    # hit the ceiling. Small groups fix it because each Write ends a response and
    # resets the budget.
    default_size = 5 if has_hard else 31
    group_size = args.group_size or default_size
    groups = (pack_rows if args.pack_groups else group_rows)(rows, group_size)
    n_groups = len(groups)
    pdir = args.parts_dir.rstrip("/") + "/"

    steps = "\n".join(
        "  %d. Author group %d's %d items. Write them to %s%s-part%d.json."
        % (i, i, len(g), pdir, args.stem, i)
        for i, g in enumerate(groups, 1)
    )
    blocks = ""
    # Whether ANY group spans areas decides which closing sentence the
    # `instructionalArea` paragraph gets. group_rows() splits on area, so the
    # unpacked path is always False; --pack-groups deliberately mixes, and the
    # paragraph's "Groups never span areas here." is then a false statement
    # sitting 670 lines above a per-group header that says the opposite. The
    # paragraph is the one carrying the REASON (a prior run stamped one area
    # across a mixed file), so an author has every reason to believe it.
    any_mixed = False
    for i, g in enumerate(groups, 1):
        mix = ", ".join("%d %s" % (sum(1 for r in g if r["difficulty"] == t), t)
                        for t in ("easy", "medium", "hard")
                        if any(r["difficulty"] == t for r in g))
        gareas = list(dict.fromkeys(r["instructionalArea"] for r in g))
        mixed = len(gareas) > 1
        any_mixed = any_mixed or mixed
        hdr = ("INSTRUCTIONAL AREAS VARY IN THIS GROUP — copy each row's own AREA= value; "
               "do NOT stamp one area across the file"
               if mixed else
               "INSTRUCTIONAL AREA FOR EVERY ROW IN THIS GROUP: %s" % gareas[0])
        blocks += (
            "\n%s\nGROUP %d — %d ROWS (%s)  ->  WRITE TO %s%s-part%d.json\n%s\n%s\n%s\n"
            % ("-" * 80, i, len(g), mix, pdir, args.stem, i, hdr, "-" * 80,
               compact(g, show_area=mixed))
        )

    # The length assignment comes in two shapes and they need DIFFERENT legends.
    # A ranked payload (every hard batch) was previously rendered with the
    # LONGEST=/DISTRACTOR>=KEY legend, which says nothing about the rank the gate
    # hard-fails on -- see _length_spec(). Pick the legend the rows actually carry.
    has_rank = any(r.get("key_length_rank") for r in rows)
    length_token = "KEY-RANK=<n> of 4" if has_rank else "LONGEST=<letter>"
    length_legend = LEGEND_RANK if has_rank else LEGEND_LONGEST
    gated_length = ("the key at its assigned KEY-RANK (a strict rank -- a tie fails)"
                    if has_rank else "the longest option at the assigned LONGEST letter")
    # The cap is scored on any row that carries it, so the legend follows the ROWS
    # rather than the payload shape -- it rides on the ranked shape today, but
    # `assert_assignments_rendered` would fail a build where it did not.
    if any(r.get("max_top_gap") for r in rows):
        length_token += " | TOP-GAP<=<n>ch"
        length_legend += LEGEND_TOP_GAP
        gated_length += "; the top two options within the TOP-GAP cap"

    area_line = areas[0] if len(areas) == 1 else ", ".join(areas)
    ia_field = ('"%s"' % areas[0]) if len(areas) == 1 else "<the row's area, copied verbatim>"
    ia_para = (
        """`instructionalArea` IS ASSIGNED, NOT INFERRED. Every row below carries its own AREA=
value, and SOME GROUPS HERE SPAN SEVERAL AREAS — each group's header says so. Copy each row's
own value verbatim; never re-derive it from the PI's wording, and never stamp one area across a
file. (A previous run inferred one area per group file and stamped it across rows whose PI
merely *sounded* like a neighbouring area.)"""
        if any_mixed else
        """`instructionalArea` IS ASSIGNED, NOT INFERRED. Every group below states the one area that
applies to all of its rows, and each row carries it too. Copy it verbatim; never re-derive it
from the PI's wording. (A previous run inferred one area per group file and stamped it across
rows whose PI merely *sounded* like a neighbouring area. Groups never span areas here.)"""
    )
    tier_line = ("NO HARD ROWS — do not author any, and do not tag any item \"hard\"."
                 if not has_hard else
                 "THIS PAYLOAD CONTAINS HARD ROWS. Author them against the C1/C2 routes in the "
                 "brief;\ntag `difficulty` from what the item actually is, never to fill the row.")
    diff_field = ("<easy|medium — the row's tier unless the item you actually wrote is the other one>"
                  if not has_hard else
                  "<easy|medium|hard — what the item actually is, not what the row asked for>")

    prompt = f"""{'=' * 80}
YOUR JOB
{'=' * 80}
You are authoring {len(rows)} DECA practice questions for the permanent question bank:
cluster = {cluster}, level = {level}, instructional area = {area_line}.
{tier_line}

LEVEL — these are {level} items. See LEVEL CALIBRATION in the brief and write to that rung
exactly: an item pitched at the wrong level is not a better item, it is a miscalibrated one.

The {len(rows)} rows are split into {n_groups} GROUPS below. Work them STRICTLY IN ORDER,
ONE GROUP AT A TIME:

{steps}

THIS ORDERING IS MANDATORY AND IT IS THE MOST IMPORTANT INSTRUCTION IN THIS FILE.
An earlier run of this exact task was given every row and one output file. It spent THIRTY
MINUTES planning the whole batch before writing anything, produced no file at all, and had to
be killed. Do NOT plan the batch as a whole. Do NOT think about group 2 until group 1 is
written to disk. Each group is a small, self-contained job: author its items in one pass,
write the file, move on.

Each file is a JSON array of that group's rows, IN ORDER. Each object has exactly these fields:

  {{
    "cand_id": "<the row's id, copied verbatim>",
    "cluster": "{cluster}",
    "level": "{level}",
    "instructionalArea": {ia_field},
    "performanceIndicator": "<the row's PI, copied verbatim, character for character>",
    "question": "<the stem>",
    "options": {{ "A": "...", "B": "...", "C": "...", "D": "..." }},
    "answer": "<the row's assigned LETTER>",
    "explanation": "<see EXPLANATION LENGTH in the brief>",
    "difficulty": "{diff_field}"
  }}

{ia_para}

READING A PAYLOAD ROW:
  <cand_id> | <TIER> | PI: <performance indicator> | LETTER=<letter> | BAND <lo>-<hi> | {length_token}
      AVOID: <gist of an existing stem for this PI> -> <that item's answer key>

  LETTER=X          -> "answer" must be X, and the correct option must sit at X (brief rule 10).
  BAND lo-hi        -> ALL FOUR options must be lo..hi characters, key included (brief rule 12).
{length_legend}
  AVOID lines       -> this PI already has these items at this level. Test a genuinely
                       different fact or angle. A paraphrase is duplication.

MECHANICALLY GATED AFTER YOU FINISH (check_authored.py — you do not run it):
  every cand_id present exactly once and spelled exactly as given; performanceIndicator and
  instructionalArea copied verbatim; the answer at the assigned letter; {gated_length}; all four
  options inside the band; four distinct options; no stem collision with the committed bank.

TOOL BUDGET — {n_groups + 1} TOOL CALLS: THIS READ, THEN {n_groups} WRITES. NOTHING ELSE.
This is a BUDGET, not an estimate. Every tool call re-sends this whole file plus every group you
have already written, so a call spent re-checking your work costs more than the work did. The
banned calls are the ones that feel most responsible:
  * NO Bash, NO Grep, NO python — do not check your rows against the payload programmatically.
  * NO re-Read of this file, the payload, or a part file you already wrote.
  * NO draft file followed by a final file. One Write per group, once.
  * NO second pass over finished items, and no self-assessed pass rate or key-longest percentage.
`check_authored.py` runs on your output after you finish, costs zero tokens, and catches every
mechanical defect. An author that spent 161 tool calls validating its own rows this way cost 35%
more per item than the sibling that spent 4 — and it is the one that shipped five items with the
key on a distractor, because it verified everything mechanically checkable and, where the
assignment fought the meaning, kept the assignment.

PROCESS:
  Author each item ONCE, in a single pass through its group.

Your final message: one short paragraph — how many items you wrote per file, and any cand_id
you skipped and why — then the brief's assertion lines, then one line reading
`TOOL CALLS: <n>` (and, if n is above the budget, the one-line reason). Nothing else.
Report the count honestly; an accurate number is the goal, not a low one.

{'=' * 80}
THE BRIEF — {brief_label}
{'=' * 80}
{brief}
{'=' * 80}
THE PAYLOAD — {len(rows)} ROWS IN {n_groups} GROUPS
{'=' * 80}
{blocks}
"""
    assert_assignments_rendered(rows, blocks)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(prompt)
    print("wrote prompt -> %s" % args.out)
    print("  %d rows · %d group(s) of <=%d · areas: %s"
          % (len(rows), n_groups, group_size, ", ".join(areas)))
    print("  ~%d chars (~%dk tok) · author emits %d file(s): %s%s-part{1..%d}.json"
          % (len(prompt), len(prompt) // 4000, n_groups, pdir, args.stem, n_groups))

    # PROMPT COMPOSITION + projected re-ingestion. Printed because the re-sent prefix
    # is invisible otherwise.
    #
    # LEVER 3 ("trim the brief") WAS DECLARED DEAD ON 2026-07-29 AND IS PARTLY REOPENED.
    # READ THE SIZE OF THE CLAIM, NOT JUST ITS DIRECTION.
    #
    # The measurement that killed it was §10-4 chunk1: a 38,221-char prompt, 45% brief /
    # 42% payload / 13% preamble, whose brief was 17,167 chars -- deleting ALL of it saves
    # ~21k of that agent's 187.8k (11%). That was true at 17k. `authoring-concept.txt`
    # then grew to 44,112 chars by §10-14 (2.9x in eleven days, one appended finding at a
    # time) while the median authoring prompt went 41k -> 82k chars, and §10-14 is the
    # first slice to score T_REINGEST -- under which the prefix is paid PER TURN. It is
    # now 30,454 chars; the history that came out of it is in
    # prompts/authoring-concept-provenance.md, and no rule or worked example moved.
    #
    # WHAT THIS DOES NOT DO IS MAKE THE BRIEF THE BIG LEVER. §10-5's billing split (parent
    # plan §4.5) weights cache READS at ~2% of the bill -- so the re-READ prefix is nearly
    # free, and a smaller brief only pays through the cache WRITE line (~47%), because
    # every turn re-caches the grown prefix. A 13.7k-char cut shrinks what each turn
    # re-caches; it does not change how many turns there are. TURNS REMAIN THE LEVER.
    # The reading that survives untouched: trimming EXAMPLES saves nothing (348 of 17,167
    # chars). What was worth taking out was narrative, and it went to a file agents never
    # read rather than to the bin.
    per_turn = len(prompt) // 4
    turns = n_groups + 2
    print("  composition: brief ~%dk · payload ~%dk · re-sent ~%d turn(s) = ~%dk of prefix"
          % (len(brief) // 4000, (len(prompt) - len(brief)) // 4000, turns,
             per_turn * turns // 1000))

    # GATE GROUP 1 THE MOMENT IT LANDS -- the author is still writing group 2, so this
    # costs zero model tokens and can abort a doomed batch before the rest is paid for.
    # §10-14 chunk 2 was authored in full (117.4k, 95 items, 4 groups), found unusable,
    # discarded, and re-authored for another 256.5k. Re-run against its preserved
    # part1 alone (parts/failed-round1/), this gate reads:
    #     requested 95 · returned 24 · passed 20 · FAILED 4 · soft-only 20
    #     key-is-longest 11/20 (55.0%) — slice bar is 35%
    #     LONGEST= honoured on 6/20 (30.0%) · 14 miss(es)
    # against the accepted round's 100.0% and 33.3% on the same 24 rows. The verdict
    # was legible at 24 of 95 items, for nothing. A part file is a complete JSON array, and
    # `--partial` is exactly the "the rest is not authored yet" mode, so this is the
    # gate the slice already runs, pointed at one part.
    if n_groups > 1:
        print("\n  EARLY GATE — run this as soon as %s%s-part1.json appears, while the\n"
              "  author is still writing group 2. Zero model tokens; a doomed batch\n"
              "  dies at 1/%d of its price instead of after the whole thing is paid for:\n"
              "    python %s --payload %s --part %s%s-part1.json --partial "
              "--list-key-longest --list-longest-miss"
              % (pdir, args.stem, n_groups, os.path.relpath(CHECK_AUTHORED),
                 args.payload, pdir, args.stem))

    # Chunk-size advice. Undersized chunks are the single largest avoidable cost in
    # the pipeline and they are invisible at run time -- every one looks fine, and
    # the bill only shows up as agent count at the end of the slice.
    if not has_hard and len(rows) < AGENT_MIN:
        short = AGENT_MIN - len(rows)
        print("  NOTE: %d rows is under the %d-item agent floor. The ~%dk fixed agent "
              "overhead\n        is paid per AGENT, not per item, so merging ~%d more rows "
              "into this chunk\n        is roughly free authoring. Re-chunk unless the areas "
              "genuinely do not fit."
              % (len(rows), AGENT_MIN, AGENT_OVERHEAD_K, short))
    elif not has_hard and len(rows) > AGENT_MAX:
        print("  NOTE: %d rows is over the %d-item agent ceiling — not a hard limit, but the "
              "saving\n        is flat up here while the blast radius of a dead agent keeps "
              "growing. Split it." % (len(rows), AGENT_MAX))


if __name__ == "__main__":
    main()
