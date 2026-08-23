#!/usr/bin/env python3
"""Build the SHARDED input files for a model audit over authored rows. No model.

WHY THIS EXISTS -- issue #127, measured on §10-13
-------------------------------------------------
The deterministic gates (check_authored, check_batch_invariants, check_key_figures,
audit_tells) all have a committed builder. The MODEL audits -- answerability, the
arithmetic pass, the strawman-distractor pass, the survivor hunt -- had none. Their
input file was assembled ad hoc every slice, and in §10-13 it was assembled once and
handed to two agents:

    gate/audit-input.json     192,814 bytes, all 275 rows
    audit-answer-ei           items 103,  prompt_chars 192814,  total  69,598
    audit-answer-opsecon      items 172,  prompt_chars 192814,  total 180,782

They split the ROWS (103 + 172 = 275) and each ingested the WHOLE BATCH -- roughly 48k
tokens of pure duplicate ingestion, and the larger sibling then cost 2.6x the smaller
for 1.7x the rows. Nothing was wrong with either agent: they were handed one file and
told which rows were theirs.

So the fix is here rather than in a prose rule. `--agents` is REQUIRED: this tool cannot
be run without saying how many agents will read the result, and it writes one file per
agent, disjoint, verified. Handing two agents one file is no longer something you can do
by accident -- it is something you would have to build twice on purpose.

TWO PROFILES, because an audit that sees the answer is a different instrument
-----------------------------------------------------------------------------
  blind (default)  row_ref · cand_id · chunk · difficulty · performanceIndicator ·
                   question · options
                   The answerability, strawman and survivor passes. The agent is asked
                   whether the item is answerable / whether a distractor is a throwaway
                   / whether it can beat the row -- all of which it can do trivially if
                   it is shown the key. `answer` and `explanation` are refused on the
                   SERIALIZED BYTES, not merely dropped by the builder.

  full             + cluster · level · instructionalArea · answer · explanation
                   The arithmetic audit only, which checks whether the explanation's
                   figures actually produce the keyed option and therefore cannot run
                   blind.

Both field lists follow §10-13's own files in key order, so a shard's ROWS are diffable
against the ad-hoc originals -- apart from `row_ref`, which leads every row and is
described next. Strip `row_ref` and the `rows` list reproduces the pre-#155 output
byte-for-byte. (The FILE no longer does: #186 wrapped it in a header, described below.)

CHUNK IS PART OF A ROW'S IDENTITY, NOT A LABEL. `cand_id`s COLLIDE across chunks -- a
§10-11 finding, 650 rows carrying 179 distinct ids -- so every row here carries the chunk
it came from, disjointness is checked on the PAIR, and a bare `--ids` token that matches
in more than one chunk is refused rather than resolved.

...AND A MODEL WILL SUMMARISE A SEPARATE FIELD AWAY -- issue #155, measured on §10-14
--------------------------------------------------------------------------------------
Carrying `chunk` alongside `cand_id` made the identity CORRECT and left it RECONSTRUCTED:
the agent had to hand two fields back, and one of them it could get wrong. Blind shard 02
of §10-14's chunks 9/10 held 40 chunk10 rows and 25 chunk9 rows; the agent returned EVERY
finding tagged `chunk9`, including `e0029` and `m0030`, which are chunk10. Both ids also
exist in chunk 9, on a different PI:

    chunk9   ...-e0029 / ...-m0030   Calculate maintained markup after markdowns
    chunk10  ...-e0029 / ...-m0030   Calculate sales commission across tiered rates

Acting on the label would have scoped a repair at two sound questions and left the two
defective ones shipping. `apply_repair --expect` cannot catch this: it takes BARE ids and
is scoped to one chunk's part files, so a finding that is already wrong about which chunk
it means passes it. The guard fires one step too late.

So `row_ref` is the row's PRIMARY identifier: one opaque string, `chunk:cand_id`, leading
every row, which the audit prompts require back VERBATIM. `chunk` and `cand_id` stay --
they are context the auditor reads, and downstream tools take a bare id -- but nothing the
model is asked to return is assembled from two fields any more. The convention already
existed on the INPUT side (`--ids chunk1:...-m0071`); this is the output side.

WHAT THIS DOES NOT DO: make the model copy correctly. It makes a miscopy DETECTABLE --
a returned `row_ref` either appears in the shard's `ids` list or it does not, where a
returned (chunk, cand_id) pair could be wrong and still name a real row.

...AND THE RIGHT *VALUE* SCALES WITH THE BATCH -- issue #156, measured on §10-14
--------------------------------------------------------------------------------------
Requiring `--agents` fixed the duplicate ingestion and left the number itself unstated,
so it gets copied forward from the previous slice. §10-14 carried `--agents 2` from a
263-row batch onto a 130-row one, halving rows-per-agent, and paid the fixed per-agent
overhead twice for half the work:

    chunks 5-8 coherence x2   263 rows   132/agent   223.9k   0.85k/row
    chunks 9+10 coherence x2  130 rows    65/agent   168.9k   1.30k/row
    chunks 5-8 blind x2       263 rows   132/agent   223.8k   0.85k/row
    chunks 9+10 blind x2      130 rows    65/agent   156.4k   1.20k/row

Same prompts, same instruments, 41-53% more per row at half the shard. At `--agents 1`
per instrument those 130 rows read for roughly 221k instead of 325k -- about 104k, and
most of why that slice-half's `tail / authoring` came in at 1.58x against a 0.41-1.13x
norm (#127's tripwire). So `--agents` is sized by ROWS PER AGENT, and the advisory below
prints when the split falls under `ROWS_PER_AGENT_FLOOR`.

THAT FLOOR IS A FLOOR, NOT A KNEE, AND THE BLIND ARM IS CONFOUNDED. Rows-per-agent has
only ever been sampled at two values, 65 and ~131; nothing has run at 260, so there is no
evidence of an optimum -- only evidence that 65 is too few. The coherence arm is a clean
control (four agents at 131-132 rows all land 0.85-0.87k/row, then 65-row agents at 1.30k);
the blind arm is not, because `audit-c5678-01` and `-02` are the SAME instrument at the
SAME shard size (132 and 131 rows) and cost 0.66k vs 1.05k/row -- a 59% spread tracking
tool calls, 2 against 6. That spread is larger than the effect claimed, and it is the same
shape §4.7 recorded when it retired §4.6 cut A ("shape does not predict cost", 47% at
identical shape). Read this as an agent-overhead floor, exactly as `build_prompt.py`'s
`AGENT_MIN` note is, and do not restate it as a measured optimum.

Note the audit case is not the authoring case that killed cut A: an audit agent WRITES
nothing, so `T_REINGEST`'s "a bigger agent needs more Write groups, and therefore costs
more" has no purchase here. That is why a floor is defensible on this path and a ceiling
is not.

...AND A SHARD IS BIGGER THAN ONE `Read` RETURNS -- issue #186, measured on §10-16
--------------------------------------------------------------------------------------
An agent that reads ONE PAGE of its shard, finds nothing in it, and reports a clean batch
returns something INDISTINGUISHABLE IN SHAPE from one that read every row. There is no
signal, no artifact and no downstream check -- a truncated audit reads as a clean audit.

§10-16 chunk10's AUTHOR reported the cap firing, unprompted, as its reason for exceeding
its tool budget: its prompt file "exceeded the single-Read output cap and was truncated by
the system at line 615, requiring a second Read call with an offset". That file is 793
lines / 67,395 chars, and line 615 lands at 45,035 chars -- which is the only direct
measurement of the cap this repo has. It only recovered because the payload's own group
structure told it something was missing.

AN AUDIT SHARD OFFERS NO SUCH TELL. It is a flat list of independent rows: nothing in row
90 says rows 91-228 exist. And §10-16's shards are multiples of the measured cap --
`audit-c91011-cohere-01.json` at 288,566ch / 4,334 lines, `audit-c91011-blind-01.json` at
166,480ch / 3,194 lines, and three earlier passes at 199,339 / 243,565 / 131,658. Whether
those read to the end is NOT RECOVERABLE from any artifact they left.

It also pulls against #156: the measured advice is a BIGGER shard whenever it clears the
rows-per-agent floor, which pushes every shard further past the cap. Nothing mediated the
two, so they are mediated here -- the shard gets bigger AND it carries its own page-through
requirement.

TWO CHANGES, BOTH CHEAP, AND THE THIRD DELIBERATELY NOT MADE:

  1. THE SHARD CARRIES ITS OWN RECONCILIATION REQUIREMENT. A shard is now an object --
     `{"audit": {...}, "rows": [...]}` -- whose header states `n_rows`, `chars`, `lines`,
     the `read_offsets` that page it, and the sentence requiring the examined-row count
     back. The shard is the ONE artifact every auditor provably reads, so that is where the
     requirement lives. §10-16 wrote the same requirement into a per-slice prompt and it
     worked (both passes returned 228, the blind one volunteering its offsets) -- but prose
     in a per-slice prompt is the exact shape #173 found had let twelve slices run with no
     rubric, and the blind prompt has no committed home to put it in.

  2. THE BUILD WARNS, LOUDLY, WHEN A SHARD EXCEEDS THE CAP. The tool knew the size all
     along and printed it as a bare character count; the caller had to infer the
     consequence. It now names the consequence and prints the offsets.

  3. NOT DONE: a checker for the returned count. Nothing in this repo parses an audit's
     RETURN -- the #154 precedent is that a second class cost nothing downstream precisely
     because nothing reads the output -- and adding a parser is a larger change than the
     hazard warrants. The point is to make the requirement ARRIVE WITH THE DATA instead of
     with the prompt.

WHAT THIS DOES NOT DO: make an agent page through. Nothing here can. It makes the
requirement unmissable and the shard's true extent self-describing, so a return that
reconciles is evidence and a return that does not is a finding.

THE CAP NUMBER IS ONE MEASUREMENT, ON PROSE, AND IS TREATED AS A CEILING ESTIMATE.
`READ_CAP_CHARS` is where §10-16's truncation actually fell. The real limit is almost
certainly counted in TOKENS, and JSON tokenizes worse per character than the prose that
measurement was taken on, so the offsets carry `READ_PAGE_MARGIN` -- a stated guess, not a
measurement. Read it exactly as `ROWS_PER_AGENT_FLOOR` is read: a floor with one sample
behind it, not a knee.

    # every chunk's parts, two agents, blind
    python build_audit_input.py --part D/parts/chunk*-part*.json \\
        --out D/gate --stem audit-answer --agents 2

    # the arithmetic pass over the rows that carry figures, one agent
    python build_audit_input.py --part D/parts/chunk*-part*.json \\
        --out D/gate --stem audit-arith --agents 1 --profile full \\
        --ids chunk1:...-m0071 chunk3:...-m0012

Then hand agent N the file named in the index, and nothing else.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Key order otherwise matches §10-13's hand-built files exactly -- `chunk` trails on the
# full profile and leads on the blind one because that is where they put it. `row_ref`
# is FIRST on both, and deliberately so: it is what the audit returns, and the first key
# of a row is the one an agent reads before it has decided what the row is.
ROW_REF = "row_ref"
BLIND_FIELDS = (ROW_REF, "cand_id", "chunk", "difficulty", "performanceIndicator",
                "question", "options")
FULL_FIELDS = (ROW_REF, "cand_id", "cluster", "level", "instructionalArea",
               "performanceIndicator", "question", "options", "answer",
               "explanation", "difficulty", "chunk")
PROFILES = {"blind": BLIND_FIELDS, "full": FULL_FIELDS}

# Refused on the serialized bytes of a blind shard. Dropping a field in the builder and
# checking that it is gone are two different claims; build_audit_payload.blind_check is
# the model for asserting the second one.
BLIND_FORBIDDEN = ('"answer"', '"explanation"', '"answer_letter"')

# The rows-per-agent FLOOR (see the docstring). Advisory, and deliberately one-sided:
# 65 rows/agent measured 41-53% dearer per row than ~131, and no shard has ever run
# larger than ~132, so there is a number below which the fixed overhead dominates and
# no number above which it is known to stop paying. `AGENT_OVERHEAD_K` is the same
# ~65k fixed agent cost `build_prompt.py` names, restated here rather than imported --
# these two tools size different things (items per AUTHOR, rows per AUDITOR) and a
# shared constant would make a change to one silently move the other.
ROWS_PER_AGENT_FLOOR = 130
AGENT_OVERHEAD_K = 65

# The #186 numbers. ONE measurement, and it is stated as one everywhere it is printed.
#
# `READ_CAP_CHARS` is where §10-16 chunk10's prompt actually truncated: 793 lines / 67,395
# chars, cut at line 615, which is 45,035 chars in. That is the only direct observation of
# the single-Read output cap this repo has, so it is a CEILING ESTIMATE, not a limit anyone
# has bracketed -- the true cap is almost certainly counted in tokens, and the observation
# was taken on English prose at 85 chars/line.
#
# `READ_PAGE_MARGIN` is therefore a STATED GUESS and not a measurement: a JSON shard runs
# ~52 chars/line and is denser in punctuation, so it very likely tokenizes worse per
# character than the prose the cap was measured on. Paging at 80% of the measured cap
# costs one extra Read call on a long shard and buys the margin. For reference, §10-16's
# blind auditor paged a 3,194-line shard at ~799 lines and reconciled; this suggests ~690
# for the same file, i.e. it is conservative against the one success we have.
READ_CAP_CHARS = 45_000
READ_PAGE_MARGIN = 0.8

# The shard's two top-level keys. Named here because the audit prompts, the fixtures and
# verify() all have to agree about them, and a string repeated in four files drifts.
HEADER_KEY = "audit"
ROWS_KEY = "rows"


def _red(s: str) -> str:
    return f"\033[31m{s}\033[0m"


def figure_rate(rows: List[Dict]) -> float:
    """Share of rows carrying a numeral in the stem or an option.

    Printed because it is the one deterministic number that says how much of a shard a
    NUMERIC instrument can even reach, and §10-14 is where that mattered: `check_key_figures`
    covered 0.0% of chunk 2 -- no numerals anywhere -- so its 0.00% was not evidence of
    anything, and the arithmetic half of a blind pass has the same ceiling on that shard.

    It does NOT say a blind pass is worthless on a qualitative shard. Ambiguity, throwaway
    distractors and pickability are all reachable there, and §10-13's blind solver found an
    ambiguity no other instrument saw. It says which HALF of the instrument is live, so a
    scoping decision is made on a number instead of a hunch.
    """
    if not rows:
        return 0.0
    n = 0
    for r in rows:
        text = str(r.get("question", "")) + "".join(
            str(v) for v in (r.get("options") or {}).values())
        if any(ch.isdigit() for ch in text):
            n += 1
    return n / len(rows)


def chunk_of(part: Path) -> str:
    """`chunk1-part2.json` -> `chunk1`. The stem up to the authoring tool's `-part`.

    build_prompt.py --stem chunk1 names every group file `chunk1-partN.json`, so this
    reads the label the slice already assigned rather than inventing a new one.
    """
    stem = part.name.removesuffix(".json")
    return stem.split("-part")[0] if "-part" in stem else stem


def ref(chunk: str, cand_id: str) -> str:
    """The row's primary identifier: `chunk9:mkt-district-pool-cand-e0029`.

    One function, because `--ids` parses this shape (`select`), the index publishes it,
    and the audit prompts require it back — three readers of one convention.
    """
    return f"{chunk}:{cand_id}"


def load_rows(parts: List[Path]) -> List[Dict]:
    """Every authored row, stamped with its chunk and `row_ref`. Refuses a repeated pair."""
    rows: List[Dict] = []
    seen: Dict[Tuple[str, str], Path] = {}
    for p in parts:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            sys.exit(f"  {p} is not a JSON array of authored rows")
        for it in data:
            key = (chunk_of(p), it.get("cand_id"))
            if key[1] is None:
                sys.exit(f"  {p}: a row has no cand_id")
            if ":" in key[1]:
                # `row_ref` splits on the FIRST colon, exactly as `--ids` does, so a
                # colon in the id would make the ref ambiguous rather than merely ugly.
                sys.exit(f"  {p}: cand_id {key[1]!r} contains ':', which is the "
                         f"row_ref separator — rename it in the part file")
            if key in seen:
                sys.exit(f"  {ref(*key)} appears in both {seen[key].name} and "
                         f"{p.name} — a glob matched the same rows twice, or a part "
                         f"file was copied. Fix the --part list; do not audit it twice.")
            seen[key] = p
            rows.append({**it, "chunk": key[0], ROW_REF: ref(*key)})
    return rows


def select(rows: List[Dict], tokens: List[str]) -> List[Dict]:
    """Filter to `--ids`. A token is a `row_ref` (`chunk:cand_id`) or a bare cand_id.

    A bare id that lives in more than one chunk is REFUSED, not resolved. §10-11 found
    650 rows carrying 179 distinct cand_ids; `apply_repair --expect` scoped to the wrong
    chunk silently repairs a different question, and an audit scoped to the wrong chunk
    silently audits one.
    """
    by_pair = {(r["chunk"], r["cand_id"]): r for r in rows}
    by_id: Dict[str, List[Tuple[str, str]]] = {}
    for pair in by_pair:
        by_id.setdefault(pair[1], []).append(pair)

    out, missing, ambiguous = [], [], []
    for t in tokens:
        if ":" in t:
            ch, cid = t.split(":", 1)
            if (ch, cid) in by_pair:
                out.append(by_pair[(ch, cid)])
            else:
                missing.append(t)
            continue
        hits = by_id.get(t, [])
        if not hits:
            missing.append(t)
        elif len(hits) > 1:
            ambiguous.append((t, [c for c, _ in hits]))
        else:
            out.append(by_pair[hits[0]])
    if missing:
        sys.exit(f"  {len(missing)} --ids not found in the parts: {', '.join(missing[:8])}")
    if ambiguous:
        lines = "\n".join(f"      {t} is in {', '.join(chs)}" for t, chs in ambiguous[:8])
        sys.exit(f"  {len(ambiguous)} bare id(s) match more than one chunk — scope them "
                 f"`chunk:cand_id`:\n{lines}")
    return out


def project(row: Dict, fields: Tuple[str, ...]) -> Dict:
    """The row as the audit will see it, in the profile's key order.

    A field the authored row lacks is an authoring defect the gate reports; it is not
    this tool's job to invent one, so it is simply absent here and the audit sees what
    the bank holds.
    """
    return {f: row[f] for f in fields if f in row}


def read_offsets(n_lines: int, n_chars: int) -> List[int]:
    """The 1-based `Read` offsets that page a file of this size, first page included.

    Sized in CHARACTERS, not rows: the cap is a property of the reader, and a shard's rows
    vary in length by a factor of three between a bare-label concept row and a full-profile
    row carrying an explanation. Always at least `[1]`, so the requirement sentence reads
    the same on a shard that fits in one call as on one that needs six -- a header whose
    shape changes with the size is a header a reader learns to skim.
    """
    if n_lines <= 0:
        return [1]
    per_line = max(1.0, n_chars / n_lines)
    per_page = max(1, int(READ_CAP_CHARS * READ_PAGE_MARGIN / per_line))
    return list(range(1, n_lines + 1, per_page)) or [1]


def requirement(n_rows: int, n_chars: int, n_lines: int, offsets: List[int]) -> str:
    """The sentence that travels WITH the data. #186's whole point is that it is here.

    It states the number to reconcile against, because §10-16's per-slice version worked
    and a return that says "228 rows examined" is only evidence if 228 is written down
    somewhere the auditor did not choose. Kept to one paragraph: a header nobody finishes
    reading fails exactly like a shard nobody finishes reading.
    """
    pages = len(offsets)
    calls = ("one Read call" if pages == 1 else
             f"{pages} Read calls, at the `offset` values in `read_offsets`")
    return (
        f"READ THIS ENTIRE FILE BEFORE YOU RETURN ANYTHING. A single Read returns roughly "
        f"{READ_CAP_CHARS:,} characters and then stops WITHOUT SAYING SO; this shard is "
        f"{n_chars:,} characters over {n_lines:,} lines, so it takes {calls}. Then state "
        f"the number of rows you examined. It MUST equal n_rows ({n_rows}). A lower count "
        f"means your read was truncated: page to the end of the file and finish the pass "
        f"before returning. An audit that read one page and found nothing looks exactly "
        f"like an audit that read every row and found nothing, which is why this number "
        f"is required."
    )


def serialize(header: Dict, projected: List[Dict]) -> str:
    """`{"audit": {...}, "rows": [...]}` -- the bytes an agent reads.

    The header describes the file it is inside, so `chars`, `lines` and `read_offsets` are
    self-referential and are solved to a FIXED POINT rather than estimated: writing the
    header changes the line count that the header reports. It converges in one or two
    passes (a header is ~10 lines and the offsets move by at most one page), and it
    RAISES rather than shipping a header that disagrees with its own file -- a stale
    `n_lines` would send an auditor's last Read past the end and read as a short file.
    """
    body = json.dumps(projected, indent=2, ensure_ascii=False)
    for _ in range(8):
        text = json.dumps({HEADER_KEY: header, ROWS_KEY: json.loads(body)},
                          indent=2, ensure_ascii=False) + "\n"
        n_chars, n_lines = len(text), text.count("\n")
        offs = read_offsets(n_lines, n_chars)
        if (header["chars"], header["lines"], header["read_offsets"]) == (n_chars, n_lines, offs):
            return text
        header["chars"], header["lines"], header["read_offsets"] = n_chars, n_lines, offs
        header["requirement"] = requirement(header["n_rows"], n_chars, n_lines, offs)
    raise RuntimeError("the shard header did not converge on its own size — refusing to "
                       "write a header that disagrees with the file it describes")


def build_shard(stem: str, i: int, of: int, profile: str, rows: List[Dict],
                fields: Tuple[str, ...]) -> str:
    """One shard's bytes, header and all."""
    projected = [project(r, fields) for r in rows]
    header = {
        "shard": f"{stem}-{i:02d}.json",
        "of": of,
        "profile": profile,
        "n_rows": len(projected),
        # Filled by the fixed point in serialize(); present here so the key ORDER is the
        # reading order -- what this file is, then how big it is, then what to do about it.
        "chars": 0,
        "lines": 0,
        "read_offsets": [1],
        "requirement": "",
    }
    return serialize(header, projected)


def shard(rows: List[Dict], agents: int, per_chunk: bool) -> List[List[Dict]]:
    """Split into one list per agent. Contiguous, so a shard stays topically coherent.

    Even split by ROW COUNT, not by character count: an audit's cost tracked rows
    closely in §10-13 once the duplicate ingestion is removed, and a character-balanced
    split would cut chunk boundaries in places nobody can describe to an agent.
    """
    if per_chunk:
        order: List[str] = []
        for r in rows:
            if r["chunk"] not in order:
                order.append(r["chunk"])
        if len(order) != agents:
            sys.exit(f"  --per-chunk gives {len(order)} shard(s) ({', '.join(order)}) "
                     f"but --agents says {agents}. Say how many agents will read this.")
        return [[r for r in rows if r["chunk"] == c] for c in order]

    n, k = len(rows), agents
    if k > n:
        sys.exit(f"  {k} agents for {n} row(s) — some shard would be empty")
    sizes = [n // k + (1 if i < n % k else 0) for i in range(k)]
    out, i = [], 0
    for s in sizes:
        out.append(rows[i:i + s])
        i += s
    return out


def verify(shards: List[List[Dict]], rows: List[Dict], raw: List[str],
           profile: str) -> None:
    """Disjoint, complete, carrying an unambiguous `row_ref`, and — on the blind profile
    — actually blind. Checked on the written bytes, because that is what the agent reads."""
    problems: List[str] = []
    seen: Dict[Tuple[str, str], int] = {}
    for i, sh in enumerate(shards, start=1):
        if not sh:
            problems.append(f"shard {i} is empty")
        for r in sh:
            key = (r["chunk"], r["cand_id"])
            if key in seen:
                problems.append(f"{ref(*key)} is in shard {seen[key]} AND {i} "
                                f"— the whole point of this tool is that it is not")
            seen[key] = i
    expected = {(r["chunk"], r["cand_id"]) for r in rows}
    if set(seen) != expected:
        lost = expected - set(seen)
        problems.append(f"{len(lost)} row(s) reached no shard, e.g. "
                        f"{sorted(lost)[:3]}")

    # #155: the returned identifier is only worth anything if it is present, unique
    # across the WHOLE selection, and actually agrees with the pair it claims to name.
    # A project() that dropped the field, or a duplicate ref, would be silent otherwise
    # — and silent is how the pair-based version failed.
    # #186: the header describes the file it is inside, so it is checked against the file
    # it is inside. A stale `n_rows` is worse than none -- it is a number an auditor
    # reconciles against and passes, while having read a different shard than it thinks.
    for i, text in enumerate(raw, start=1):
        doc = json.loads(text)
        if not isinstance(doc, dict) or ROWS_KEY not in doc or HEADER_KEY not in doc:
            problems.append(f"shard {i} is not a {{{HEADER_KEY}, {ROWS_KEY}}} object — the "
                            f"page-through requirement travels in the header, so a bare "
                            f"array ships without it")
            continue
        head, body = doc[HEADER_KEY], doc[ROWS_KEY]
        if head.get("n_rows") != len(body):
            problems.append(f"shard {i}: header n_rows {head.get('n_rows')} != "
                            f"{len(body)} rows in the file — the reconciliation number "
                            f"is the fix, and a wrong one is worse than none")
        if head.get("chars") != len(text) or head.get("lines") != text.count("\n"):
            problems.append(f"shard {i}: header says {head.get('chars')}ch / "
                            f"{head.get('lines')} lines, file is {len(text)}ch / "
                            f"{text.count(chr(10))} — the offsets are computed from these")
        offs = head.get("read_offsets") or []
        if not offs or offs[0] != 1 or offs != sorted(set(offs)) \
                or any(o > head.get("lines", 0) for o in offs):
            problems.append(f"shard {i}: read_offsets {offs} do not page this file from "
                            f"line 1 to its end")
        if str(head.get("n_rows")) not in str(head.get("requirement", "")):
            problems.append(f"shard {i}: the requirement sentence does not state n_rows — "
                            f"an auditor cannot reconcile against a number it is not given")

    refs: Dict[str, int] = {}
    for i, text in enumerate(raw, start=1):
        doc = json.loads(text)
        for r in (doc[ROWS_KEY] if isinstance(doc, dict) and ROWS_KEY in doc else []):
            got = r.get(ROW_REF)
            if not got:
                problems.append(f"shard {i} has a row with no {ROW_REF} — the audit has "
                                f"nothing unambiguous to return")
                continue
            if got != ref(r.get("chunk", ""), r.get("cand_id", "")):
                problems.append(f"shard {i}: {ROW_REF} {got!r} does not match its own "
                                f"chunk/cand_id — the ref is the identity, not a label")
            if got in refs:
                problems.append(f"{got} appears in shard {refs[got]} AND {i} — a "
                                f"{ROW_REF} that names two rows names neither")
            refs[got] = i

    if profile == "blind":
        for i, text in enumerate(raw, start=1):
            for token in BLIND_FORBIDDEN:
                if token in text:
                    problems.append(f"shard {i} contains {token} — a blind audit must "
                                    f"not see the key")
    if problems:
        print(f"\n  {_red('FAIL')} the shards are not a clean split")
        for p in problems[:10]:
            print(f"    {p}")
        sys.exit(1)


def sizing_note(n_rows: int, agents: int, per_chunk: bool) -> str:
    """The #156 advisory, or "" when the split is already at or above the floor.

    Fires only when a STRICTLY SMALLER agent count would still leave every shard at or
    above `ROWS_PER_AGENT_FLOOR` — i.e. only when the fix is inside measured territory.
    A 200-row batch at 2 agents is 100/agent, under the floor, but the alternative is a
    200-row shard and no shard above ~132 has ever run; advising it would extrapolate,
    so this stays quiet there rather than trading a known shortfall for an unknown one.
    """
    if agents < 2 or n_rows // agents >= ROWS_PER_AGENT_FLOOR:
        return ""
    suggested = max(1, round(n_rows / ROWS_PER_AGENT_FLOOR))
    if suggested >= agents:
        return ""
    per = n_rows // agents
    saved = (agents - suggested) * AGENT_OVERHEAD_K
    note = (f"  NOTE: {agents} agents over {n_rows} rows is {per} rows each, under the "
            f"~{ROWS_PER_AGENT_FLOOR}-row floor.\n        The ~{AGENT_OVERHEAD_K}k agent "
            f"overhead is paid per AGENT, not per row — §10-14 read 65 rows/agent at "
            f"41-53%\n        more per row than ~131 (#156). `--agents {suggested}` reads "
            f"the same rows for roughly\n        {saved}k less. This is a floor, not an "
            f"optimum: nothing has run above ~132 rows/agent.")
    if per_chunk:
        note += ("\n        --per-chunk pins --agents to the chunk count, so the only "
                 "lever here is dropping it —\n        an even split costs the "
                 "per-shard topical coherence --per-chunk exists to buy.")
    return note


def main() -> None:
    ap = argparse.ArgumentParser(description="Shard a model-audit input, one file per agent.")
    ap.add_argument("--part", required=True, nargs="+",
                    help="the authored part file(s) to audit")
    ap.add_argument("--out", required=True, metavar="DIR", help="where the shards land")
    ap.add_argument("--stem", required=True,
                    help="file stem, e.g. audit-answer -> audit-answer-01.json")
    # Required, and that is the fix: §10-13's one file was read by two agents because
    # nothing ever asked how many would read it. The VALUE is the #156 half: size it by
    # rows-per-agent so it changes when the batch does, instead of riding along from the
    # previous slice's command block.
    ap.add_argument("--agents", required=True, type=int,
                    help=f"how many agents will read this — ONE FILE EACH, disjoint. "
                         f"Size it by ROWS PER AGENT, not by a fixed count: aim for at "
                         f"least ~{ROWS_PER_AGENT_FLOOR} rows each, since the ~"
                         f"{AGENT_OVERHEAD_K}k agent overhead is paid per AGENT and 65 "
                         f"rows/agent measured 41-53%% dearer per row than ~131 (#156). "
                         f"So {ROWS_PER_AGENT_FLOOR} rows is 1 agent and "
                         f"{ROWS_PER_AGENT_FLOOR * 2 + 3} is 2 — recompute it for THIS "
                         f"batch rather than carrying the last slice's number")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="blind",
                    help="blind (no answer/explanation; the default) or full (the "
                         "arithmetic audit only)")
    ap.add_argument("--ids", nargs="*", default=None, metavar="ID",
                    help="audit only these rows; a row_ref `chunk:cand_id` (the form a "
                         "previous audit returned), or a bare cand_id where it is "
                         "unambiguous")
    ap.add_argument("--per-chunk", action="store_true",
                    help="one shard per chunk instead of an even split (--agents must "
                         "match the chunk count)")
    args = ap.parse_args()

    if args.agents < 1:
        sys.exit("  --agents must be at least 1")

    rows = load_rows([Path(p) for p in args.part])
    if args.ids:
        rows = select(rows, args.ids)
    if not rows:
        sys.exit("  no rows selected — an empty audit is refused, never silently written")

    fields = PROFILES[args.profile]
    shards = shard(rows, args.agents, args.per_chunk)
    raw = [build_shard(args.stem, i, len(shards), args.profile, sh, fields)
           for i, sh in enumerate(shards, start=1)]
    verify(shards, rows, raw, args.profile)

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    index = {"stem": args.stem, "profile": args.profile, "fields": list(fields),
             "agents": args.agents, "total_rows": len(rows), "shards": []}
    for i, (sh, text) in enumerate(zip(shards, raw), start=1):
        name = f"{args.stem}-{i:02d}.json"
        (outdir / name).write_text(text, encoding="utf-8")
        head = json.loads(text)[HEADER_KEY]
        index["shards"].append({
            "file": name, "n": len(sh), "chars": len(text),
            # #186: recorded so a completed pass is auditable AFTER the fact. §10-16's
            # three earlier passes cannot be checked either way, because the only trace
            # they left of their size was a number printed to a terminal.
            "lines": head["lines"], "reads": len(head["read_offsets"]),
            "read_offsets": head["read_offsets"],
            "figure_rate": round(figure_rate(sh), 4),
            "chunks": sorted({r["chunk"] for r in sh}),
            # Named `ids` since §10-13 and left named that, but these ARE the row_refs:
            # this list is what a returned finding is resolved against, so it must be
            # the same strings the shard carries, not a parallel construction of them.
            "ids": [r[ROW_REF] for r in sh],
        })
    (outdir / f"{args.stem}-index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total = sum(len(t) for t in raw)
    print(f"\n  {len(rows)} row(s) -> {args.agents} shard(s), {args.profile} profile "
          f"({len(fields)} field(s))")
    for s in index["shards"]:
        print(f"    {s['file']}  n={s['n']:>3}  {s['chars']:>7,}ch  "
              f"(~{round(s['chars'] / 4000)}k tok)  {s['lines']:>5,} lines  "
              f"{s['reads']} read(s)  figures {s['figure_rate']:.0%}  "
              f"{', '.join(s['chunks'])}")
    # #186. The size was always printed; the CONSEQUENCE was left for the caller to infer,
    # and nobody did until an authoring agent volunteered that the cap had truncated it.
    over = [s for s in index["shards"] if s["chars"] > READ_CAP_CHARS]
    if over:
        print(f"\n  {_red('OVER THE SINGLE-READ CAP')} — {len(over)} of "
              f"{len(index['shards'])} shard(s) exceed ~{READ_CAP_CHARS:,}ch, the point at "
              f"which\n    §10-16's authoring prompt was truncated BY THE SYSTEM, without "
              f"a message (#186).")
        for s in over:
            offs = ", ".join(str(o) for o in s["read_offsets"])
            print(f"      {s['file']}  needs {s['reads']} Read calls — offsets {offs}")
        print(f"    An audit that reads one page, finds nothing and reports a clean batch "
              f"returns\n    something INDISTINGUISHABLE from one that read every row. Each "
              f"shard's `{HEADER_KEY}`\n    header carries these offsets and REQUIRES the "
              f"examined-row count back; keep that\n    requirement in the prompt you hand "
              f"the agent, and check the count against `n_rows`.")
    overall = figure_rate(rows)
    print(f"  figure rows: {overall:.1%} of the selection carry a numeral — the ceiling on "
          f"every NUMERIC\n    instrument over these shards. Below ~10% the arithmetic half "
          f"of a blind pass has\n    almost nothing to reach (§10-14 chunk 2: 0.0%), and its "
          f"yield is ambiguity /\n    throwaway distractors / pickability only. This does not "
          f"scope the KEY-COHERENCE\n    pass, which is qualitative and runs over every row.")
    print(f"  disjoint + complete: verified on {len(rows)} (chunk, cand_id) pair(s)"
          + ("  · blind: no answer/explanation in any shard" if args.profile == "blind"
             else "  · FULL profile — these shards carry the key"))
    # Printed every run, not just when chunks are mixed: the §10-14 shard that broke
    # WAS mixed, but a single-chunk shard read by an agent that names the wrong chunk
    # from memory fails identically, and the reader cannot tell which case they have.
    print(f"  every row leads with `{ROW_REF}` (`chunk:cand_id`) — require it back "
          f"VERBATIM in the audit\n    prompt, and resolve findings against this index's "
          f"`ids`, never against a chunk label the\n    model restated (#155: an agent "
          f"tagged 40 chunk10 rows `chunk9`, and both ids existed in\n    both chunks)")
    print(f"  every shard is {{`{HEADER_KEY}`, `{ROWS_KEY}`}} — the header states n_rows and "
          f"requires that count\n    back, because a truncated audit and a clean one return "
          f"the same shape (#186)")
    if args.agents > 1:
        # What the unsharded file would have cost, stated in the same units as the
        # ledger, so the saving is a number rather than a claim.
        waste = total * (args.agents - 1)
        print(f"  one shared file would have re-sent {waste:,}ch (~{round(waste / 4000)}k "
              f"tok) as duplicate ingestion — §10-13 paid ~48k of exactly this")
    # ...and the other side of that same trade, printed beside it rather than left to be
    # rediscovered per slice: sharding costs one fixed agent overhead per extra shard,
    # so the saving above is only a saving while each shard is big enough to earn it.
    note = sizing_note(len(rows), args.agents, args.per_chunk)
    if note:
        print(note)
    print(f"  wrote {outdir}/{args.stem}-index.json — hand agent N its OWN file, "
          f"and nothing else\n")


if __name__ == "__main__":
    main()
