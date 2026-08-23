#!/usr/bin/env python3
"""Merge a repair OVERLAY into the part files it fixes. Deterministic, no model.

WHY THIS EXISTS -- plan 10-2 §2d, measured 2026-07-28
-----------------------------------------------------
The in-context repair was projected at ~25k and came in at **239.3k** -- worse than
the ~90-100k fresh agent it was written to avoid. §2d named the mechanism exactly:

    "a 41-item repair still has to re-emit all three part files in full (82 items,
     ~24k of output) because a part file is a JSON array that cannot be patched in
     place, and the repair reasoning is per-item on top of that. The author also
     took 13 tool calls, not 3 -- it re-read its own parts to copy untouched items
     through. The dominant cost of a repair is re-emitting the parts, and that does
     not care whether the agent is fresh or resumed."

A JSON array cannot be patched in place BY THE AUTHOR. It can be patched by 40 lines
of Python. So the author writes only the items it actually fixed, to one overlay
file, and this merges them: no re-reading, no copying untouched items through, no
re-emitting a whole chunk to change 6 rows. A 41-item repair emits 41 items instead
of 82, in 1 tool call instead of 13.

Run `check_authored.py --list-stem-pull` / `--list-key-longest` first: both print the
repair scope (which files hold the flagged ids), which is what the author is handed.

WHAT IT REFUSES, AND WHY EACH REFUSAL IS LOAD-BEARING
------------------------------------------------------
  * an overlay id that is in no part file      -- a hallucinated or mistyped cand_id
                                                  would otherwise vanish silently
  * an overlay id appearing twice              -- which version wins is not a choice
                                                  this script gets to make
  * an id NOT in --expect, when --expect given -- the author repaired something it
                                                  was not asked to touch; that is a
                                                  scope breach, and §10-3's
                                                  `--vs-repair-scope` exists because
                                                  a silent scope drift shipped once
  * a merged item that fails check_question    -- a repair that breaks the assembler's
                                                  own gate must not reach the pool
  * an IDENTITY field that drifted from the     -- §10-5: a repair overlay came back
    original row                                   with level "district" instead of
                                                   "District". check_question accepted
                                                   it (the field was present and a
                                                   string), apply_repair wrote it, and
                                                   the defect surfaced two steps later
                                                   as assemble_slice's opaque "new parts
                                                   contain items for another slice:
                                                   {'pbm/district': 5}". The same
                                                   overlay had also dropped
                                                   instructionalArea entirely. A repair
                                                   edits WORDING -- question, options,
                                                   explanation. Everything that says
                                                   WHICH ROW THIS IS is copied through
                                                   from the original, and any deviation
                                                   is drift, not a fix.

It never renumbers, never reorders, and never touches an item the overlay does not
name: parts keep their original order so `assemble_slice.py` sees exactly what it
saw before, minus the defect. Ids are assigned at assembly BY IDENTITY (§10-4), and
nothing here disturbs that.

ALL-OR-NOTHING (§10-7). Every part is validated BEFORE any part is written. The merge
used to write each file inside the validation loop, so a failure on the third file
left the first two already on disk -- §10-7 chunk 3 hit exactly that and had to be
recovered with a hand-filtered overlay. Plan-10 §4.6 described this guard as "aborts
before any write"; that is now true of the mechanism and not just of the data.

THE `answer` EXCEPTION (§10-7). `answer` is an identity field, but it is the ONE
identity field the authored row can itself get wrong: check_authored hard-fails
`answer 'C' != assigned letter 'B'`, and if the repair must copy `answer` verbatim
from the row that holds the wrong letter, that defect is literally unfixable by this
tool. §10-7 chunk 3's e0063 was a pure clerical slip -- the payload assigned B, the
author's own explanation argued B, only the `answer` field read C -- and it had to be
edited by hand. So: pass `--payload`, and an `answer` change is accepted ONLY when it
moves to that row's assigned `answer_letter`. Any other change is still drift.
Without `--payload` the old rule stands and `answer` is frozen.

Usage:
    python apply_repair.py --overlay DIR/chunk3-repair.json \
        --part DIR/chunk3-part2.json DIR/chunk3-part3.json
    python apply_repair.py --overlay O.json --part P.json --expect c0012 c0044 --dry-run
    python apply_repair.py --overlay O.json --part P.json --payload DIR/payload/chunk3.json
    python apply_repair.py --overlay O.json --id-field id --also-freeze question \
        --part frontend/public/question-bank/hospitality/hospitality-icdc-pool.json
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_question_bank import check_question  # noqa: E402

# check_authored.py stamps this on every item it loads so a repair list can name the
# file that holds each row. It is a report-side annotation and must never be written
# back into a part -- an authored item's fields are the item.
TRANSIENT = ("_part",)

# The fields that say WHICH ROW THIS IS. A repair may rewrite the stem, the options and
# the explanation; it may never change any of these. They are compared against the row
# being replaced, so a dropped field and a subtly-wrong value are the same failure.
# `difficulty` is here too: a tier change is a REFEREE decision (check_authored
# --post-referee), never something a length/stem repair gets to do on the side.
IDENTITY = ("cluster", "level", "instructionalArea", "performanceIndicator",
            "answer", "difficulty")

# WHAT `--id-field id` IS FOR (issue #73). Everything above describes an IN-FLIGHT
# batch: parts keyed by `cand_id`, on their way to assembly. A committed bank file
# is the same shape one step later -- the rows carry `id` instead, assigned at
# assembly by identity (§10-4) -- and a repair of a SHIPPED item is otherwise
# exactly this operation, down to the refusal set. §10-17 is a whole plan of them.
#
# It is safe for the same reason the in-flight merge is: the overlay names rows,
# never positions, and IDENTITY is compared against the row being replaced. On a
# committed row the progress log adds one rule this tool already enforces without
# knowing why -- an `Attempt` stores the LETTER the student picked and the
# correctness computed at answer time, so rewording an option under a letter is
# invisible to it while moving the key between letters retroactively falsifies
# every stored `correct`. That is `answer` in IDENTITY, and on a bank merge it must
# stay frozen: --payload has no meaning here (there is no payload), so pass
# `--also-freeze question` when the repair is scoped to options and the stem is not
# supposed to move either.

# WHY `explanation` IS REPORTED BUT NOT FROZEN (issue #77, from a §10-10 finding).
# `explanation` is the one repairable field with no floor under it. IDENTITY does not
# hold it (a repair legitimately edits wording), and check_authored only asks whether
# it is longer than 60 characters -- so an overlay may replace a four-sentence
# explanation carrying a rationale for each distractor with one sentence, and every
# tool downstream calls that a clean repair. Both §10-10 repair agents did exactly that
# on rows flagged purely for option LENGTH, and what it costs is a student: /review
# shows this text after a miss, so a deleted per-distractor rationale is a wrong answer
# with no reason attached to it.
#
# build_repair_prompt.py now scopes the prompt itself, which is the real fix; this is
# the check on the other side of the agent. It REPORTS and does not refuse, because a
# repair that edits an option the explanation quotes has to fix the quote, and nothing
# here can separate that from a rewrite. `--also-freeze explanation` is the refusal,
# for a repair scoped to something the explanation cannot be quoting.
#
# Both numbers are crude on purpose and must be read as a DELTA on one row, never as a
# score: how much of the original wording survives, and how many distractors the text
# still addresses. "Addresses" is a `(B)`-style marker or two content words shared with
# that option -- 58% of the committed bank addresses all three that way, so the
# absolute value says little while a 3 -> 1 drop on a repaired row says a lot.
STOPWORDS = frozenset("""
    the a an and or of to in for with that this from is are was were be been on at by
    as it its their his her they them not but which who whom when where how what more
    most less least than then so such into over under after before each other another
    all any some
""".split())


def content_words(text: str) -> set:
    return {w for w in re.findall(r"[a-z][a-z'-]{3,}", (text or "").lower())
            if w not in STOPWORDS}


# An explanation names a distractor in one of two forms, and this counter used to see
# only the first: `(B)` parenthesised, or `Option B` in prose. The prose form is TWICE
# as common in the committed bank (14.1% of explanations vs 7.2%), because it is what
# the brief's rule 11 produces -- "Option B is just the total expenses".
#
# Missing it under-scored 757 committed rows, each a latent FALSE "<-- LOST" on any
# repair that touched them. That warning is not cosmetic: its whole purpose is to tell
# a reviewer an explanation dropped a per-distractor rationale, and the documented
# response is to put the rationale back. Firing it on an explanation that already names
# every distractor invites exactly the §10-10 defect it exists to prevent -- rewriting
# an explanation that was fine.
#
# §10-12 hit this live: a reconciliation row scored 2/3 with an explanation that named
# A, B and D by letter. The word-overlap fallback missed D because `content_words`
# requires >=4 characters and D's distinguishing noun was "fee".
#
# THE THIRD FORM IS `Choice B`, and it was found the same way as the second: by a row
# reading 0/3 that plainly addressed all three (§10-17 round 3, hos-association-pool-0205).
# It is RARE bank-wide -- 22 explanations, 0.1%, against 12.1% for `Option B` and 6.5%
# for `(B)` -- but the rarity is not the reason to add it. The reason is WHERE it fails:
# 16 of those 22 also score under 3/3 on the word-overlap fallback, and a REWORD is what
# makes that certain. `distractors_addressed` falls back to sharing two content words
# with the option, and §10-17's whole method is to strip an option down to a bare shared
# label ("About $150 RevPAR at the hotel"), which leaves nothing for an explanation to
# share. So both arms go blind on exactly the rows a reword produces, and the `<-- LOST`
# warning -- the guard against §10-10's stripped-explanation defect -- stops firing on
# the batch that needs it most. Adding the word can only ever RAISE a score, so no
# committed row's reading gets worse.
_NAMES_OPTION = re.compile(r"(?:\(([ABCD])\)|\b(?:option|choice)\s+([ABCD])\b)", re.I)


def distractors_addressed(item: Dict, explanation: str) -> int:
    """How many of the three distractors the explanation still says something about."""
    opts = item.get("options") or {}
    ans = str(item.get("answer", "")).strip().upper()
    if set(opts) != {"A", "B", "C", "D"} or ans not in opts:
        return -1
    words = content_words(explanation)
    named = {(a or b).upper() for a, b in _NAMES_OPTION.findall(explanation or "")}
    return sum(1 for k in "ABCD" if k != ans
               and (k in named
                    or len(content_words(str(opts[k])) & words) >= 2))


def surviving_wording(old: str, new: str) -> float:
    """Share of the original explanation's content words still present in the new one."""
    o = content_words(old)
    return len(o & content_words(new)) / len(o) if o else 1.0


def main() -> None:
    ap = argparse.ArgumentParser(description="Merge a repair overlay into its part files.")
    ap.add_argument("--overlay", required=True,
                    help="JSON array holding ONLY the repaired items (cand_id keyed)")
    ap.add_argument("--part", required=True, nargs="+",
                    help="the part file(s) check_authored's repair scope named")
    ap.add_argument("--expect", nargs="*", default=None,
                    help="the cand_ids the repair was scoped to; any other id in the "
                         "overlay is a scope breach and fails the run")
    ap.add_argument("--payload", default=None,
                    help="the build_area.py payload these parts answer. Supplying it lets a "
                         "repair correct an `answer` that does not match the row's assigned "
                         "answer_letter -- the one identity field the AUTHORED row can itself "
                         "get wrong, and otherwise unfixable by this tool (§10-7)")
    ap.add_argument("--id-field", default="cand_id",
                    help="the field that names a row. `cand_id` (default) for in-flight "
                         "parts; `id` to merge into a COMMITTED bank file, whose rows "
                         "were renumbered into ids at assembly")
    ap.add_argument("--also-freeze", nargs="*", default=(),
                    help="extra fields the overlay may not change, on top of the "
                         "identity set — e.g. `question` when the repair is scoped to "
                         "options and the stem must not move, or `explanation` when the "
                         "repair could not be quoting the options it edited")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change and write nothing")
    args = ap.parse_args()

    id_field = args.id_field
    identity = IDENTITY + tuple(f for f in args.also_freeze if f not in IDENTITY)

    # cand_id -> assigned answer letter; empty unless --payload was given
    assigned: Dict[str, str] = {}
    if args.payload:
        rows = json.loads(Path(args.payload).read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise SystemExit(f"{args.payload}: expected a JSON array of payload rows")
        assigned = {r["cand_id"]: r["answer_letter"] for r in rows
                    if r.get("cand_id") and r.get("answer_letter")}

    overlay = json.loads(Path(args.overlay).read_text(encoding="utf-8"))
    if not isinstance(overlay, list):
        raise SystemExit(f"{args.overlay}: expected a JSON array of repaired questions")

    fixes: Dict[str, Dict] = {}
    for q in overlay:
        cid = q.get(id_field)
        if not cid:
            raise SystemExit(f"an overlay item has no {id_field}")
        if cid in fixes:
            raise SystemExit(f"{cid} appears twice in the overlay — which one wins is "
                             "not this script's call; de-duplicate it")
        fixes[cid] = {k: v for k, v in q.items() if k not in TRANSIENT}

    if args.expect is not None:
        stray = sorted(set(fixes) - set(args.expect))
        if stray:
            raise SystemExit(
                "SCOPE BREACH: the overlay repairs %d item(s) that were not in scope: %s\n"
                "  A repair that edits rows nobody flagged is unreviewed authoring."
                % (len(stray), ", ".join(stray)))

    applied: Dict[str, str] = {}
    unchanged = 0
    relettered: List[str] = []
    healed: List[str] = []
    rewritten: List[str] = []
    # (path, rendered-json, item-count, touched) staged here and written only after EVERY
    # part has validated -- a failure on part 3 must not leave parts 1 and 2 rewritten.
    staged: List[tuple] = []
    for path in args.part:
        p = Path(path)
        items: List[Dict] = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            raise SystemExit(f"{p}: expected a JSON array of questions")
        out, touched = [], 0
        for q in items:
            cid = q.get(id_field)
            if cid in fixes:
                if cid in applied:
                    raise SystemExit(f"{cid} is in both {applied[cid]} and {p} — the "
                                     "parts overlap; fix the parts, not the overlay")
                new = fixes[cid]
                orig = {k: v for k, v in q.items() if k not in TRANSIENT}
                drift = [(f, orig.get(f), new.get(f)) for f in identity
                         if f in orig and new.get(f) != orig.get(f)]
                # `answer` is the one identity field the AUTHORED row can itself get wrong.
                # With --payload, allow it to move -- but ONLY onto the assigned letter.
                if drift and cid in assigned:
                    want = assigned[cid]
                    kept = []
                    for f, o, n in drift:
                        if f == "answer" and n == want and o != want:
                            relettered.append("%s: answer %r -> %r (the assigned letter)"
                                              % (cid, o, n))
                        else:
                            kept.append((f, o, n))
                    drift = kept
                # CASE-ONLY DRIFT IS HEALED, NOT REFUSED (§10-10). An overlay that
                # returns "icdc" where the row says "ICDC" has not made an edit --
                # the strings denote the same thing and no repair could have meant
                # anything by the difference. Refusing it costs a whole agent
                # round-trip to retype a value this tool already holds: §10-10's
                # chunk5 spent 54.0k on exactly that, on 9 rows, for one letter.
                # The ORIGINAL always wins, so this can only ever restore identity,
                # never accept the overlay's version.
                #
                # Deliberately narrow, and it must stay that way. A field the
                # overlay DROPPED still fails (o is not None while n is), and a
                # genuinely different value still fails -- both are the §10-5 defect
                # this guard was built for, where an overlay came back with a real
                # `level` change and a missing instructionalArea. Only a
                # casefold-equal pair is silently corrected.
                if drift:
                    kept = []
                    for f, o, n in drift:
                        if (isinstance(o, str) and isinstance(n, str)
                                and o.casefold() == n.casefold()):
                            new[f] = o
                            healed.append("%s: %s %r -> %r (case only)" % (cid, f, n, o))
                        else:
                            kept.append((f, o, n))
                    drift = kept
                if drift:
                    raise SystemExit(
                        "%s: the overlay changed %d identity field(s) that a repair may "
                        "never touch:\n%s\n"
                        "  A repair edits only the wording its scope names and copies\n"
                        "  everything else through verbatim. Re-emit the overlay with these\n"
                        "  fields taken from the original row.%s" % (
                            cid, len(drift),
                            "\n".join("    %-22s original %r -> overlay %r"
                                      % (f, o, n) for f, o, n in drift),
                            "" if (args.payload or
                                   not any(f == "answer" for f, _, _ in drift)) else
                            "\n  `answer` is the one identity field the AUTHORED row can"
                            "\n  itself get wrong. If the authored letter is the defect, pass"
                            "\n  --payload: the change is then allowed onto this row's"
                            "\n  assigned answer_letter, and only onto that."))
                hard, _ = check_question(new, require_difficulty=True)
                if hard:
                    raise SystemExit(f"{cid}: the repaired item fails the assembler's "
                                     f"gate — {'; '.join(hard)}")
                old_ex, new_ex = orig.get("explanation"), new.get("explanation")
                if isinstance(old_ex, str) and isinstance(new_ex, str) and old_ex != new_ex:
                    before, after = distractors_addressed(orig, old_ex), \
                        distractors_addressed(new, new_ex)
                    rewritten.append(
                        "%s: %dch -> %dch, %.0f%% of the original wording survives%s"
                        % (cid, len(old_ex), len(new_ex),
                           100 * surviving_wording(old_ex, new_ex),
                           "" if before < 0 or after < 0 else
                           ", distractors addressed %d/3 -> %d/3%s"
                           % (before, after, "  <-- LOST" if after < before else "")))
                if new == {k: v for k, v in q.items() if k not in TRANSIENT}:
                    unchanged += 1
                out.append(new)
                applied[cid] = str(p)
                touched += 1
            else:
                out.append({k: v for k, v in q.items() if k not in TRANSIENT})
        staged.append((p, json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                       len(items), touched))

    # Every part validated. Only now does anything reach disk.
    missing = sorted(set(fixes) - set(applied))
    if missing:
        raise SystemExit(
            "%d overlay item(s) match no row in the parts given: %s\n"
            "  Either the %s is wrong or the part holding it was not passed.\n"
            "  Nothing was written." % (len(missing), ", ".join(missing), id_field))

    for p, rendered, n_items, touched in staged:
        if touched and not args.dry_run:
            p.write_text(rendered, encoding="utf-8")
        note = ("  [dry run, not written]" if (touched and args.dry_run)
                else "  (untouched)" if not touched else "")
        print(f"  {p.name}: {n_items} item(s), {touched} repaired{note}")
    for line in relettered:
        print(f"  RELETTERED  {line}")
    for line in healed:
        print(f"  HEALED      {line}")
    for line in rewritten:
        print(f"  EXPLANATION {line}")
    if rewritten:
        print(f"  NOTE: {len(rewritten)} overlay item(s) changed `explanation`. A repair "
              f"may fix a quote of\n        an option it edited; it may not rewrite the "
              f"explanation, and a dropped\n        per-distractor rationale is what "
              f"/review shows a student after a miss.\n        Read the rows above. "
              f"Nothing here is gated — pass `--also-freeze explanation`\n        to "
              f"refuse the change outright when the repair could not be quoting options.")

    if unchanged:
        print(f"  NOTE: {unchanged} overlay item(s) are byte-identical to the original "
              f"— nothing was actually repaired there")
    print(f"  applied {len(applied)} repair(s) across {len(set(applied.values()))} file(s)"
          + ("  [DRY RUN — nothing written]" if args.dry_run else ""))
    # This line existed, in exactly this shape, through all four of §10-13 chunk 1's
    # back-to-back rounds (issue #127). It is no longer only advice: the parts just moved,
    # so build_repair_prompt.py now REFUSES to build the next round from the report that
    # predates this merge. Re-gate, or nothing further can be built.
    if not args.dry_run:
        print("  RE-GATE NOW — check_authored.py on the same parts, before assemble_slice.py\n"
              "        and before any further repair round. It costs zero tokens, and\n"
              "        build_repair_prompt.py refuses a gate report older than these parts.")


if __name__ == "__main__":
    main()
