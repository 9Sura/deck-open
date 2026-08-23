#!/usr/bin/env python3
"""Build the hard tier's two verification sets, IN ORDER. Deterministic, no model.

THE SEQUENCING IS THE POINT -- raters first, solvers scoped to what they surface.
--------------------------------------------------------------------------------
Plan-10 has run the hard tier as four verification agents fanned out SIMULTANEOUSLY
over every hard item: 2 blind solvers + 2 raters. It costs what four agents cost
(§10-2 141.1k, §10-3 four of its six H1 agents, §10-4 141.1k over 19 items) and the
two instruments answer different questions:

    the 2-RATER RECONCILE  asks "is this item genuinely hard, and is it sound?"
                           -- load-bearing, runs on EVERY item, never cut.
                           Authors self-certify hard at ~100% ([[referee-rater-not-haiku]]),
                           so nothing else stands between a quota and the bank.
    the 2 BLIND SOLVERS    ask "is the authored key actually derivable, and is a
                           second option equally correct?" -- a KEY check. Its yield
                           is concentrated where a key is newly computed or where
                           the raters could not agree on what the item is.

Running them at once means the solvers verify keys nobody has questioned. Running
them in order means the raters name the doubtful items and the solvers go there.
The solvers stay independent of each other and blind to the key either way -- the
sequencing changes WHICH items they see, not what they are told about them.

Parent plan §4.5 already specified this scope ("blind-key verify with 2 solvers,
hard-only, NEW-KEYS-ONLY"); the slices widened it in practice. §10-4 widened to all
19 because the routing produced zero C1 and it would not drop an instrument on a
technicality -- the right call, and `--all` keeps it available.

STAGE 1  python build_hard_verify.py --payload h1.json --part h1-part*.json --out DIR
         -> DIR/referee-set.txt   (every item, keys and explanations shown, THE
                                   COMMITTED RUBRIC ON TOP -- see #173 below)
         -> DIR/referee-ids.json  (the id sidecar reconcile_raters.py reads)
         Run both raters on it, SAVE EACH RETURN AS JSON, then:
             python reconcile_raters.py --ids DIR/referee-ids.json \
                 --rater r1.json r2.json
         Its class 1 is the contested set stage 2 scopes to.

STAGE 2  python build_hard_verify.py --payload h1.json --part h1-part*.json --out DIR \
             --blind --key-out DIR/../verify-key/blind-key.json \
             --contested cand-h0004 cand-h0011
         -> DIR/blind-set.txt     (C1 route items + the contested ids, key hidden)
         -> the key sidecar       (OUTSIDE DIR -- see below)
         Run 2 independent solvers on it, save each return, then:
             python reconcile_solvers.py --key ... --solver s1.json s2.json

WHAT IT REFUSES: an empty solver scope. Zero C1 and zero contested is exactly the
§10-4 situation, and the answer there was to widen deliberately, not to skip the
instrument -- so the script stops and makes you choose `--all` or name ids. A
verification stage must never disappear because a filter happened to match nothing.

The blind set is checked on its emitted BYTES for anything that de-blinds it (the
key marker, the answer letter, the explanation) -- the same discipline as
build_audit_payload.blind_check, for the same reason: a payload a solver can read
the answer off is not a blind solve, it is an expensive echo.

THE SOLVERS' DISAGREEMENT WAS THE DETECTOR, AND NOTHING READ IT -- issue #172
-----------------------------------------------------------------------------
§10-14's `h0016` (Calculate cost per rating point) shipped a stem with TWO honest
readings whose answers were BOTH offered:

    "reaches 40 rating points of the target audience with an average frequency of
     5 exposures, for a total campaign cost of $20,000"

    reading 1  "40 rating points" IS the GRP total  -> 20,000/40  = $500 = option A
    reading 2  40 is reach, GRP = 40 x 5 = 200      -> 20,000/200 = $100 = option B, the key

A student who knows CPP, reads it the first way, computes $500 and finds it offered
is marked wrong. It passed check_authored (4 lists, no soft), check_batch_invariants,
check_key_figures at 100% scope (0.00%), audit_tells, the key-coherence audit at
--profile full (class 1: 0, class 2: 0), the arithmetic audit -- which explicitly
checked cap/threshold rows for rival readings and cleared this one -- and both
difficulty raters, one recording "no readable tell".

Solver 1 answered A. Solver 2 answered B. THAT was the detector, it was free, and
it was noticed by a human reading two prose returns side by side. Nothing in the
tooling or the plan read solver disagreement as a signal at all.

Two things changed here, and they fail in OPPOSITE directions -- neither subsumes
the other, which is why both are present:

  THE KEY SIDECAR (`--key-out`, REQUIRED with --blind) makes the mechanical half
  possible. `reconcile_solvers.py` needs the key the blind set deliberately does
  not carry, and until now no file held it: the answers lived in the part files and
  the comparison was done by eye. Mechanical, free, cannot be forgotten -- but it
  only fires when the solvers happen to SPLIT. Two solvers sharing a misreading
  both answer A, agree, and pass.

  THE STRUCTURED RETURN (the blind-set header, below) makes the other half legible
  from ONE solver: every reading of the stem it considered, and which option each
  one lands on. That is what covers the agreed-misreading case. It is a model
  self-report, which this repo has repeatedly found saturates (authors self-certify
  hard at ~100%), so it is the SECOND instrument here and not the first.

WHY THE SIDECAR MAY NOT LIVE IN --out. A solver agent that lists its working
directory can read a key file sitting next to the blind set, and would then be an
expensive echo -- exactly what blind_check exists to prevent, defeated one
directory listing later. `blind_check` guards the blind set's BYTES and cannot see
a second file, so the separation is enforced by path instead: --key-out resolving
into --out is refused.

STAGE 1 SHIPPED WITH NO RUBRIC FOR TWELVE SLICES -- issue #173
---------------------------------------------------------------
The referee set's head used to be two lines: "N items authored and tagged HARD.
Rate each: HARD, MEDIUM (demote), or DEFECTIVE." Nothing else told the raters what
hard MEANS, and every slice plan's H1 block said only "run 2 Sonnet raters.
Reconcile. Both-medium => demote, honestly." So plan-10's headline quality number
came from two models each supplying its own definition.

§10-14 measured what that costs. 21 rows, two Sonnet raters, same task text:

    rater      HARD   MEDIUM   DEFECTIVE   agreed HARD with the other
    A            18        1           2                            3
    B             3       16           2                            3

Both re-derived all 21 and both found the arithmetic sound -- a rubric
disagreement, not a correctness one. A counted DEPENDENT OPERATIONS; B counted
OPERATIONS A COMPETENT DISTRICT COMPETITOR ACTUALLY PERFORMS. Both defensible. The
published 16 of 21 rests on breaking fifteen ties; rater B's reading is 3 of 21;
and 0/19, 7/25, 7/22, ~10/19 were all produced the same way.

The rubric now lives in `src/prompts/hard-referee.txt` and is written into the
referee set. It is a FILE for difficulty_tagging.txt's stated reason -- THE PROMPT
IS PART OF THE MEASUREMENT, and a distribution produced by a prompt nobody can read
is not reproducible -- and because a per-slice agent prompt gets reworded every
time, which is how twelve slices happened. §10-10 measured a written "second
operation" rule moving agreement 6-of-9 to 8-of-9 on a composition-matched batch.

It cannot prove the raters then share a rubric; prose is not enforceable. That is
`reconcile_raters.py`'s half -- it reports the SPLIT beside the held count, so a
number resting on a wide disagreement can never be quoted as if it rested on a
narrow one. Stage 1 therefore also writes `referee-ids.json`, for the same reason
--key-out exists one stage down: the comparison was always available by eye, and a
free signal nobody is obliged to write down does not get read.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_question_bank import OPTION_KEYS  # noqa: E402
from reconcile_raters import RATER_FIELDS  # noqa: E402
from reconcile_solvers import SOLVER_FIELDS  # noqa: E402

KEY_MARKER = "   <== AUTHORED KEY"
REFEREE_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "hard-referee.txt"

# The blind set's header, which asks for a shape, and reconcile_solvers.py, which
# parses one, are two halves of one contract. #139's rule -- check the two against
# each other, not each against its own reasoning -- so the header is asserted to name
# every field the parser requires, at build time, on the bytes about to be written.
# A field renamed in the parser and not in the prose stops the build here.


def referee_head(n: int, cluster: str, level: str) -> str:
    """The rater instruction: one generated line, then the COMMITTED rubric verbatim.

    The rubric is a file, not a string in here, because #173's defect was that it was
    neither -- it lived in the parent plan and in the AUTHOR's brief, and each slice's
    rater agent got whatever its orchestrator paraphrased that day. difficulty_tagging.txt
    already carries the rule for the other rating path: THE PROMPT IS PART OF THE
    MEASUREMENT, and an irreproducible measurement cannot referee anything.

    Same build-time contract as `blind_head` (#139): the prose is asserted to name every
    field `reconcile_raters.py` parses. Here it also catches the reverse -- a prompt EDITED
    to drop a field the parser still requires stops the build instead of producing returns
    that are refused one stage later.
    """
    if not REFEREE_PROMPT.exists():  # pragma: no cover -- a packaging error, not a path
        raise SystemExit(
            f"the committed referee rubric is missing: {REFEREE_PROMPT}\n"
            "  Stage 1 does not fall back to a bare instruction. That IS the #173 defect —\n"
            "  twelve slices of raters each supplying their own definition of hard, and a\n"
            "  headline number that was a property of the rater rather than of the batch.")
    rubric = REFEREE_PROMPT.read_text(encoding="utf-8")
    head = (f"{n} DECA {cluster}/{level} items authored and tagged HARD. Referee them "
            f"against the rubric below.\n\n" + rubric.rstrip() + "\n")
    missing = [f for f in RATER_FIELDS if f'"{f}"' not in head]
    if missing:  # pragma: no cover -- a build-time contract, not a runtime path
        raise SystemExit(
            "the referee rubric does not name field(s) reconcile_raters.py requires: "
            + ", ".join(missing) + " — the prompt and the parser are one contract (#139)")
    return head


def blind_head(n: int, cluster: str, level: str) -> str:
    """The solver instruction. Asks for a JSON array, one object per item.

    IT ASKS FOR THE READINGS, NOT JUST THE ANSWER (#172). The old header asked
    "whether any SECOND option is also defensibly correct" -- a question about
    OPTIONS, put to a solver that has already committed to one reading of the stem.
    From inside §10-14 `h0016`'s reading 1, option A is uniquely correct and nothing
    else is defensible, so that row answered "no" honestly and passed. The question
    that reaches the defect is about the STEM: how else can this be read, and where
    does each reading land?

    `second_defensible` is KEPT rather than replaced -- it is a different question
    (two options defensible under ONE reading) and it has its own yield.
    """
    head = (
        f"{n} DECA {cluster}/{level} multiple-choice items, keys withheld. Solve each one.\n"
        f"\n"
        f"Return a JSON array, one object per item, IN THE ORDER GIVEN, and nothing else:\n"
        f"\n"
        f"  {{\n"
        f"    \"cand_id\": \"<copied verbatim from the item header>\",\n"
        f"    \"answer\": \"<the single letter you believe is correct>\",\n"
        f"    \"confidence\": \"high\" | \"medium\" | \"low\",\n"
        f"    \"readings\": [ {{\"reading\": \"<how the stem can be read>\",\n"
        f"                   \"answer\": \"<the letter THAT reading lands on, or \\\"none\\\">\"}} ],\n"
        f"    \"second_defensible\": \"<letter, or \\\"none\\\">\",\n"
        f"    \"pickable\": true | false,\n"
        f"    \"pickable_cue\": \"<the concrete cue, or \\\"\\\">\"\n"
        f"  }}\n"
        f"\n"
        f"READINGS IS THE ONE THAT IS NEW, AND IT IS ABOUT THE STEM, NOT THE OPTIONS.\n"
        f"Before you commit to an answer, ask what ELSE the stem's quantities could be\n"
        f"naming. List EVERY reading you actually considered -- one entry is a fine and\n"
        f"common answer -- and for each, the letter it lands on. A reading whose answer\n"
        f"is not among the four options takes \"none\"; that is the healthy case, and\n"
        f"saying so is not a finding against the item.\n"
        f"\n"
        f"Two readings landing on two DIFFERENT offered letters is the defect this asks\n"
        f"about. §10-14's `h0016` read \"reaches 40 rating points ... average frequency of\n"
        f"5 ... total cost $20,000\": taking 40 as the GRP total gives $500, offered at A;\n"
        f"taking 40 as reach gives GRP 200 and $100, offered at B. A student who knows the\n"
        f"formula and reads it the first way is marked wrong. It passed every deterministic\n"
        f"gate, the key-coherence audit, the arithmetic audit and both difficulty raters.\n"
        f"\n"
        f"Do not manufacture readings to appear thorough. A reading counts only if you\n"
        f"would defend it to someone who wrote the item -- it must turn on what a quantity\n"
        f"in the stem NAMES, not on ignoring a sentence or misapplying the formula.\n"
        f"\n"
        f"`second_defensible` is the older, different question: under YOUR reading, is a\n"
        f"second option also defensibly correct? `pickable` is test-wiseness -- could the\n"
        f"item be answered WITHOUT the content (length, self-explaining option, odd-one-out,\n"
        f"stem telegraph)? Name the cue when you say true; an unnamed cue is not actionable\n"
        f"(§10-7: pickability is corroborated by a second instrument or it is not acted on).\n"
        f"\n"
        f"You are one of two INDEPENDENT solvers. Do not hedge toward a consensus you\n"
        f"cannot see -- your disagreement with the other solver is itself an instrument.\n"
        f"Your final message is a return value, not a report to a human.\n")
    missing = [f for f in SOLVER_FIELDS if f'"{f}"' not in head]
    if missing:  # pragma: no cover -- a build-time contract, not a runtime path
        raise SystemExit(
            "the blind header does not name field(s) reconcile_solvers.py requires: "
            + ", ".join(missing) + " — the prompt and the parser are one contract (#139)")
    return head


def render(items: List[Dict], blind: bool) -> str:
    out = []
    for n, q in enumerate(items, 1):
        ans = str(q.get("answer", "")).strip().upper()
        out.append("\n--- ITEM %d (%s) · %s · PI: %s"
                   % (n, q.get("cand_id"), q.get("instructionalArea"),
                      q.get("performanceIndicator")))
        out.append("Q: %s" % q.get("question"))
        for k in OPTION_KEYS:
            mark = KEY_MARKER if (not blind and k == ans) else ""
            out.append("   %s. %s%s" % (k, (q.get("options") or {}).get(k, ""), mark))
        if not blind:
            out.append("EXPLANATION: %s" % q.get("explanation", ""))
    return "\n".join(out) + "\n"


def blind_check(text: str, items: List[Dict]) -> List[str]:
    """Refuse to write a blind set a solver could read the answer off."""
    problems = []
    if "AUTHORED KEY" in text or "<==" in text:
        problems.append("the key marker survived into the blind set")
    for q in items:
        expl = (q.get("explanation") or "").strip()
        if expl and expl[:40] in text:
            problems.append(f"{q.get('cand_id')}: its explanation is in the blind set")
        # The authored letter must not appear as a field anywhere in the payload.
        for pat in (f'"answer": "{q.get("answer")}"', f"answer: {q.get('answer')}"):
            if pat in text:
                problems.append(f"{q.get('cand_id')}: an answer field survived")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the hard tier's verification sets, in order.")
    ap.add_argument("--payload", required=True, help="the hard payload (carries `route`)")
    ap.add_argument("--part", required=True, nargs="+", help="the authored part file(s)")
    ap.add_argument("--out", required=True, help="directory to write the set into")
    ap.add_argument("--blind", action="store_true",
                    help="STAGE 2: emit the scoped blind-solver set instead of the rater set")
    ap.add_argument("--contested", nargs="*", default=[],
                    help="cand_ids the raters split on, held HARD, or called DEFECTIVE")
    ap.add_argument("--all", action="store_true",
                    help="STAGE 2 escape hatch: solve every item (what §10-4 did when the "
                         "routing produced zero C1). Deliberate widening, not a default.")
    # Required with --blind, and required for the same reason build_audit_input's
    # --agents is: the comparison this file makes possible was ALWAYS available by eye,
    # and §10-14 shows what happens to a free signal nobody is obliged to write down.
    # It must land OUTSIDE --out; a solver that lists its own directory would otherwise
    # read the key beside the blind set.
    ap.add_argument("--key-out", metavar="PATH",
                    help="STAGE 2, REQUIRED: where the answer-key sidecar is written, for "
                         "reconcile_solvers.py. Must NOT be inside --out — a solver can "
                         "list that directory (#172)")
    args = ap.parse_args()

    payload = {r["cand_id"]: r for r in json.loads(Path(args.payload).read_text(encoding="utf-8"))}
    items: List[Dict] = []
    for p in args.part:
        items.extend(json.loads(Path(p).read_text(encoding="utf-8")))

    hard = [q for q in items if q.get("difficulty") == "hard"]
    if not hard:
        # Pre-referee this is every authored item; post-referee the demotions have
        # already landed and only the survivors matter. Neither is an error.
        hard = items
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    cluster = hard[0].get("cluster")
    level = hard[0].get("level")

    if not args.blind:
        # A repeated cand_id makes the id sidecar's per-row lookup ambiguous exactly as it
        # does the key sidecar's one stage down, and the raters' returns are keyed on it.
        counts: Dict[str, int] = {}
        for q in hard:
            counts[q["cand_id"]] = counts.get(q["cand_id"], 0) + 1
        dupes = sorted(c for c, k in counts.items() if k > 1)
        if dupes:
            raise SystemExit(
                f"{len(dupes)} cand_id(s) appear more than once in the referee set: "
                + ", ".join(dupes[:6]) + "\n"
                "  A --part glob matched the same rows twice, or a repair file was passed\n"
                "  ALONGSIDE the part it supersedes. reconcile_raters.py keys a rater's\n"
                "  return by cand_id, so a repeat scores one rating against another row.")
        head = referee_head(len(hard), cluster, level)
        path = outdir / "referee-set.txt"
        path.write_text(head + render(hard, blind=False), encoding="utf-8")
        ids_path = outdir / "referee-ids.json"
        # This sidecar may live in --out, unlike stage 2's: the raters SEE the keys and
        # explanations by design, so there is nothing here for a directory listing to leak.
        ids_path.write_text(json.dumps({
            "cluster": cluster, "level": level, "n": len(hard),
            "referee_set": str(path),
            "ids": [q["cand_id"] for q in hard],
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        c1 = [q["cand_id"] for q in hard if payload.get(q["cand_id"], {}).get("route") == "C1"]
        print(f"  wrote {path}  ({len(hard)} items — BOTH raters see all of them)")
        print(f"  wrote {ids_path}  (the id sidecar reconcile_raters.py reads)")
        print(f"  rubric: {REFEREE_PROMPT.name} — COMMITTED, and written into the set."
              " Do not paraphrase it")
        print("    into the agent prompt; that is the #173 defect, and it ran for 12 slices.")
        print("  run the 2 raters, SAVE EACH RETURN AS JSON, then:")
        print(f"      python reconcile_raters.py --ids {ids_path} --rater r1.json r2.json")
        print(f"  stage 2 scope so far: {len(c1)} C1 item(s)"
              + (f" ({', '.join(c1)})" if c1 else " — none"))
        print("  then re-run with --blind --key-out <path outside "
              + str(outdir) + "> --contested <its class-1 ids>")
        return

    scope_ids = {q["cand_id"] for q in hard
                 if payload.get(q["cand_id"], {}).get("route") == "C1"}
    unknown = [c for c in args.contested if c not in {q["cand_id"] for q in hard}]
    if unknown:
        raise SystemExit("--contested names id(s) that are not in this batch: "
                         + ", ".join(unknown))
    scope_ids |= set(args.contested)
    scoped = hard if args.all else [q for q in hard if q["cand_id"] in scope_ids]

    if not scoped:
        raise SystemExit(
            "SOLVER SCOPE IS EMPTY — 0 C1 items and 0 contested ids.\n"
            "  This is the §10-4 case, and the answer there was NOT to skip the solvers: it\n"
            "  widened them to the whole batch, because a C2's failure mode (an\n"
            "  indiscriminable near-correct pair) is exactly what blind-solving tests.\n"
            "  Re-run with --all, or name the ids the raters were unsure about.")

    if not args.key_out:
        raise SystemExit(
            "--key-out is REQUIRED with --blind.\n"
            "  The blind set withholds the key by design, so nothing on disk holds the\n"
            "  answers the solvers are about to be scored against, and the comparison gets\n"
            "  done by eye — which is how §10-14's `h0016` reached the bank with two honest\n"
            "  readings landing on two offered options (#172). Write the sidecar, then run\n"
            "  reconcile_solvers.py over it and the two returns.\n"
            "  It must land OUTSIDE --out: a solver agent that lists its working directory\n"
            "  would read the key next to the set it is meant to solve blind.")

    # A duplicate cand_id would make the sidecar's key map silently lossy — two rows,
    # one entry, and a reconcile that scores one solver's answer against the other row's
    # key. Refused here rather than resolved, exactly as build_audit_input.load_rows does
    # with a repeated (chunk, cand_id) pair. Stage 1 is deliberately untouched.
    seen: Dict[str, int] = {}
    for q in scoped:
        seen[q["cand_id"]] = seen.get(q["cand_id"], 0) + 1
    dupes = sorted(c for c, n in seen.items() if n > 1)
    if dupes:
        raise SystemExit(
            f"{len(dupes)} cand_id(s) appear more than once in the scoped set: "
            + ", ".join(dupes[:6]) + "\n"
            "  A --part glob matched the same rows twice, or a repair file was passed\n"
            "  ALONGSIDE the part it supersedes rather than in place of it. Fix the --part\n"
            "  list: the key sidecar is a map, so a repeated id silently keeps one answer.")

    key_path = Path(args.key_out)
    if outdir.resolve() in [key_path.resolve().parent, *key_path.resolve().parents]:
        raise SystemExit(
            f"--key-out is inside --out ({outdir}).\n"
            "  blind_check guards the blind set's BYTES; it cannot see a second file, so a\n"
            "  solver agent that lists this directory reads the key and the blind solve\n"
            "  becomes an expensive echo. Put the sidecar somewhere the solver is not sent.")

    head = blind_head(len(scoped), cluster, level)
    text = head + render(scoped, blind=True)
    problems = blind_check(text, scoped)
    if problems:
        raise SystemExit("BLINDING FAILED — nothing written:\n  " + "\n  ".join(problems))

    path = outdir / "blind-set.txt"
    path.write_text(text, encoding="utf-8")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps({
        "cluster": cluster, "level": level, "n": len(scoped),
        "blind_set": str(path),
        # Order matters: the solvers are asked to return the items IN THE ORDER GIVEN, so
        # a return that has drifted is detectable by position as well as by id.
        "ids": [q["cand_id"] for q in scoped],
        "key": {q["cand_id"]: str(q.get("answer", "")).strip().upper() for q in scoped},
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    n_c1 = sum(1 for q in scoped if payload.get(q["cand_id"], {}).get("route") == "C1")
    print(f"  wrote {path}  ({len(scoped)} of {len(hard)} items — blinding check PASSED)")
    print(f"  wrote {key_path}  (the key sidecar — OUTSIDE {outdir}, never shown to a solver)")
    print(f"  scope: {n_c1} C1 · {len(set(args.contested))} contested"
          + ("  [--all: whole batch]" if args.all else ""))
    print("  run 2 INDEPENDENT solvers on it — independence is the instrument, and their")
    print("    DISAGREEMENT is the ambiguity detector §10-14 found by eye (#172). Save each")
    print("    return as JSON, then:")
    print(f"      python reconcile_solvers.py --key {key_path} --solver s1.json s2.json")


if __name__ == "__main__":
    main()
