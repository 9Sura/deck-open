#!/usr/bin/env python3
"""The per-agent token ledger -- LEVER 1. Deterministic, no model.

THE PROBLEM THIS EXISTS TO END
-------------------------------
Every plan-10 slice recorded ONE NUMBER PER AGENT ("chunk 1: 187.8k") and nothing
about what that number is made of. Reconstructing chunk 1 of §10-4 -- 94 items, 1
agent, 187.8k, 5 tool calls:

    the prompt it read (38,221 chars)          ~9.5k
    the questions it wrote (94 x ~291 tok)     ~27k
    ------------------------------------------------
    accounted for                              ~36.5k  (19%)
    UNEXPLAINED                                ~151k   (81%)

Every optimisation in this plan -- including §4.6's cut A -- has been reasoned from
that unexplained 81%. Two theories fit the same totals and they DISAGREE about
whether bigger batches are cheaper:

  T_FLAT      "~65k of fixed overhead per agent, flat in batch size" (§2b, from two
              datapoints: a 20-item agent cost 90.2k, a 47-item agent cost 74.4k).
              => fewer, bigger agents. This is what cut A bets on.
  T_REINGEST  "each tool call re-sends the whole conversation, so the brief is paid
              once per TURN and each finished group's JSON is re-sent by every later
              turn." => cost grows with GROUP COUNT, super-linearly. Under this
              theory cut A partly BACKFIRES: 150 items means 5-6 Writes, not 4.

Nobody has measured which is true, because nobody ever wrote down the line items.
This file is the line items. Record one chunk and the question is settled.

RECORD (after each agent returns, from its reported usage):
    python agent_cost.py --ledger output/plan-10/10-5/cost.json record \
        --label chunk1 --kind authoring --items 94 --groups 4 --tool-calls 5 \
        --prompt-chars 38221 --input 141000 --output 27000 \
        --cache-read 96000 --thinking 20000 --effort default

  Only `--label`, `--items` and the totals you actually have are required; every
  field is optional and missing ones are reported as unknown rather than guessed.
  RECORD WHAT THE TOOL REPORTED, NOT WHAT YOU EXPECTED. A ledger that has been
  tidied to agree with a theory measures the theory.

  `--kind` is the one field the REPORT branches on -- the turn budget below is an
  authoring model and only an authoring agent can overrun it (#187). Omit it and
  the label is used to guess; the guess never returns `authoring` for a label it
  does not recognise.

PREDICT (BEFORE the chunk runs -- this is the whole point):
    python agent_cost.py predict --items 150 --groups 5 --prompt-chars 60000

  Prints both theories' numbers for that shape. Pre-registering them is what makes
  the run an experiment instead of an anecdote: after it lands, whichever theory the
  measurement lands nearer is the one that should drive batch sizing.

REPORT:
    python agent_cost.py --ledger output/plan-10/10-5/cost.json report
"""
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

# Measured constants, all from the finance pilot. Used ONLY for prediction and for
# the accounted/unexplained split -- never to fill in a missing measurement.
TOK_PER_ITEM_OUT = 291      # §2b: 743 items / ~216k of authored part files
CHARS_PER_TOK = 4           # the usual rough ratio, good enough for a prompt file
FLAT_OVERHEAD = 65_000      # §2b's "fixed agent overhead"
SYSTEM_TOK = 4_000          # subagent system prompt + task message, order-of-magnitude

# AGENT KIND (issue #187). The turn budget below is an AUTHORING model -- 1 Read, one
# Write per group, a final message -- and the TURN OVERRUN verdict that reads it is only
# ever true of an authoring agent. Three kinds, because the only distinction the report
# makes is author / repair / neither:
#
#   authoring  writes the batch. Its turn budget is a KNOWN number, so an overrun is a
#              real finding (§10-14 chunk3: 161 calls against 5, 35% more per item).
#   repair     applies an overlay. `apply_repair` requires FULL copy-through rows, so
#              repairing one field means first reading every other field of that row
#              verbatim -- the reads are the tool's contract, not waste. See #187.
#   audit      writes nothing (coherence, blind, arithmetic, raters, blind solvers,
#              survivor hunts). Records `groups` 0/1, so its budget is nominal.
KINDS = ("authoring", "repair", "audit")

# Inference is for the ledgers already on disk, which predate `--kind`. It is deliberately
# ASYMMETRIC: a non-authoring marker classifies outright, but `authoring` is only ever
# inferred from a strict shape with an allow-listed suffix. Everything else is UNKNOWN and
# says so. Guessing `authoring` wrong re-creates exactly the false verdict #187 is about;
# guessing it missing only costs a line under a header that asks for `--kind`.
_REPAIR_MARKERS = ("repair", "deleak", "balance-fix")
_AUDIT_MARKERS = ("audit", "cohere", "blind", "arith", "rater", "referee", "solver",
                  "survivor", "answerability", "strawman")
_AUTHORING_STEM = re.compile(r"^(?:chunk\d+|h1[ab]?|topup)$")
_AUTHORING_SUFFIX = re.compile(r"^(?:author|reauthor|discarded|attempt\d+|g\d+|r\d+)$")


def infer_kind(label: str) -> Optional[str]:
    """Best-effort kind for a row recorded before `--kind` existed. None = unknown."""
    low = (label or "").lower()
    # Repair first: §10-12's `audit-repair` / `audit-repair-pooled` are repair agents
    # named for the audit that scoped them, and its own note says so ("7 rows across 3
    # chunks in ONE agent"). An audit marker in the label does not make it an audit.
    if any(m in low for m in _REPAIR_MARKERS):
        return "repair"
    if any(m in low for m in _AUDIT_MARKERS):
        return "audit"
    parts = low.split("-")
    if _AUTHORING_STEM.match(parts[0]) and all(_AUTHORING_SUFFIX.match(p) for p in parts[1:]):
        return "authoring"
    return None


def agent_kind(e: Dict) -> Optional[str]:
    """What was recorded, else what the label implies, else None."""
    return e.get("kind") or infer_kind(e.get("label", ""))


def predict(items: int, groups: int, prompt_chars: int) -> Dict:
    """Both theories, same shape. Neither is fitted to anything -- that is the point."""
    p = prompt_chars / CHARS_PER_TOK
    out = items * TOK_PER_ITEM_OUT

    t_flat = FLAT_OVERHEAD + p + out

    # Turns = 1 Read + `groups` Writes + a final message. Every turn re-sends the
    # system prompt and the prompt file; turn i additionally re-sends the output of
    # the i-1 groups already written. That second term is the super-linear one.
    turns = groups + 2
    per_group_out = out / groups if groups else 0
    reingested = sum(i * per_group_out for i in range(1, groups))
    t_reingest = turns * (SYSTEM_TOK + p) + reingested + out

    return {
        "items": items, "groups": groups, "prompt_tok": round(p),
        "authored_output_tok": round(out),
        "T_FLAT": round(t_flat), "T_FLAT_per_item": round(t_flat / items) if items else 0,
        "T_REINGEST": round(t_reingest),
        "T_REINGEST_per_item": round(t_reingest / items) if items else 0,
        "spread": round(abs(t_reingest - t_flat)),
    }


def accounted(e: Dict) -> Optional[Dict]:
    """What we can NAME in one agent's bill, vs what is left over."""
    total = e.get("total")
    if total is None:
        parts = [e.get("input"), e.get("output")]
        if any(p is None for p in parts):
            return None
        total = sum(parts)
    p = (e.get("prompt_chars") or 0) / CHARS_PER_TOK
    out = e.get("output")
    if out is None:
        out = (e.get("items") or 0) * TOK_PER_ITEM_OUT
    known = p + out
    return {"total": total, "prompt_tok": round(p), "output_tok": round(out),
            "accounted": round(known), "unexplained": round(total - known),
            "pct_unexplained": round(100.0 * (total - known) / total, 1) if total else 0.0}


def cmd_report(entries: List[Dict]) -> None:
    if not entries:
        print("  ledger is empty — nothing recorded yet")
        return
    print(f"\n  {'label':<12} {'items':>5} {'grp':>4} {'calls':>5} {'total':>9} "
          f"{'/item':>7} {'unexpl':>8} {'%':>6} {'effort':>8}")
    print("  " + "-" * 76)
    tot_items = tot_tok = 0
    for e in entries:
        a = accounted(e)
        items = e.get("items") or 0
        tot_items += items
        if a:
            tot_tok += a["total"]
        total_s = f"{a['total'] / 1000:.1f}k" if a else "?"
        rate_s = f"{a['total'] / items / 1000:.2f}k" if (a and items) else "?"
        unexp_s = f"{a['unexplained'] / 1000:.1f}k" if a else "?"
        pct_s = f"{a['pct_unexplained']:.0f}%" if a else "?"
        print(f"  {e.get('label', '?'):<12} {items:>5} {str(e.get('groups', '?')):>4} "
              f"{str(e.get('tool_calls', '?')):>5} {total_s:>9} {rate_s:>7} "
              f"{unexp_s:>8} {pct_s:>6} {str(e.get('effort', '?')):>8}")
    print("  " + "-" * 76)
    if tot_items and tot_tok:
        print(f"  {'TOTAL':<12} {tot_items:>5} {'':>4} {'':>5} {tot_tok/1000:>8.1f}k "
              f"{tot_tok/tot_items/1000:>6.2f}k")

    # The cache line is the one that can change what "cost" even means here.
    #
    # A RECORDED ZERO IS NOT A MEASUREMENT (found reading §10-14's ledger, which carries
    # "cache_read": 0 on all 11 agents alongside "input": 0). The Agent tool reports ONE
    # `subagent_tokens` number with no input/output/cache split, so the slice wrote the
    # total into `output` and zeroed the rest as placeholders. Read literally this printed
    # "0k of 1,556k were cache READS (0%)" -- a confident false claim. `input == 0` with a
    # positive total is the signature: no agent has ever genuinely consumed zero input.
    #
    # WHAT THE ANSWER ACTUALLY IS, so nobody re-derives it from these zeros: §10-5 measured
    # the split out of band over chunk1+chunk2 (173 items) and the parent plan §4.5 carries
    # the table -- output 15% of raw / 50% weighted, cache WRITE 56% / 47%, cache READ 29% /
    # 2%, fresh input ~0. So cache reads are large in count and nearly free in price, and
    # the bill is output plus cache WRITES, which are billed at a premium because every turn
    # re-caches the grown prefix. That is T_REINGEST arriving from the billing side, and it
    # is why the lever is TURNS. This ledger cannot show any of it while the fields are
    # placeholder zeros -- which is the whole point of refusing to read them as data.
    def unmeasured(e: Dict) -> bool:
        a = accounted(e)
        return (e.get("cache_read") in (None, 0)
                and (e.get("input") in (None, 0))
                and bool(a) and a["total"] > 0)

    cached = [e for e in entries if not unmeasured(e) and e.get("cache_read") is not None]
    blind = [e for e in entries if unmeasured(e)]
    if cached:
        cr = sum(e["cache_read"] for e in cached)
        tt = sum(accounted(e)["total"] for e in cached if accounted(e))
        print(f"\n  CACHE: {cr/1000:.0f}k of {tt/1000:.0f}k tokens were cache READS "
              f"({100.0*cr/tt:.0f}%), over {len(cached)} of {len(entries)} agent(s).")
        if tt and cr / tt > 0.4:
            print("  Most of this bill is re-sent context being served from cache. Cache reads\n"
                  "  are billed and rate-limited far below fresh input, so the raw token totals\n"
                  "  these slices have been optimised against OVERSTATE the real constraint —\n"
                  "  re-check the per-item target in whatever unit the 5-hour window counts.")
    if blind:
        print(f"\n  CACHE: NOT MEASURED on {len(blind)} of {len(entries)} agent(s) — a recorded"
              f"\n  cache_read of 0 next to input 0 is a placeholder, not a zero, and this tool"
              f"\n  refuses to read it as one. NEVER RECORD A ZERO YOU DID NOT MEASURE; leave the"
              f"\n  field out. The split HAS been measured once, out of band, on §10-5's first two"
              f"\n  chunks (parent plan §4.5): weighted, the bill is output ~50% and cache WRITES"
              f"\n  ~47%, with cache reads ~2%. Cache writes carry a premium because every turn"
              f"\n  re-caches the grown prefix — so the lever is TURNS, and the turn count is the"
              f"\n  one column below that every ledger already fills in.")
    elif not cached:
        print("\n  CACHE: not recorded. Record --cache-read: if it is most of the bill, the\n"
              "  token totals overstate the true cost and the whole target moves.")

    # Which theory does the data support? Only answerable per-agent, and only when
    # the shape was recorded.
    usable = [e for e in entries if e.get("groups") and e.get("items")
              and e.get("prompt_chars") and accounted(e)]
    if usable:
        print(f"\n  {'label':<12} {'measured':>10} {'T_FLAT':>10} {'T_REINGEST':>11}  verdict")
        print("  " + "-" * 62)
        for e in usable:
            a = accounted(e)
            pr = predict(e["items"], e["groups"], e["prompt_chars"])
            d_flat = abs(a["total"] - pr["T_FLAT"])
            d_re = abs(a["total"] - pr["T_REINGEST"])
            verdict = ("T_FLAT" if d_flat < d_re else "T_REINGEST")
            if abs(d_flat - d_re) < 0.1 * a["total"]:
                verdict = "inconclusive"
            print(f"  {e['label']:<12} {a['total']/1000:>9.1f}k {pr['T_FLAT']/1000:>9.1f}k "
                  f"{pr['T_REINGEST']/1000:>10.1f}k  {verdict}")
        print("\n  T_FLAT wins   -> keep cut A: fewer, bigger agents (120-150 items).")
        print("  T_REINGEST wins -> cut A is backwards. Cut TURNS instead: fewer, larger\n"
              "                  Writes and a smaller re-ingested prefix (lever 3).")
    else:
        print("\n  Record --groups and --prompt-chars to discriminate the two cost theories.")

    turn_sections(entries)
    print()


def turn_sections(entries: List[Dict]) -> None:
    """The three turn readings, one per agent kind. See KINDS and issue #187.

    Deliberately NOT gated on `prompt_chars` the way the two-theory table above is: a
    turn budget needs only the shape. §10-16's `repair-r1-c1234` and `repair-c5678-pooled`
    carry no prompt_chars, so the four-point comparison that refutes the old verdict was
    invisible to the tool that printed it.
    """
    shaped = [e for e in entries if e.get("tool_calls") and e.get("groups") is not None
              and e.get("items") and accounted(e)]
    if not shaped:
        return

    def line(e: Dict) -> str:
        a = accounted(e)
        rate = f"{a['total'] / e['items'] / 1000:.2f}k/item"
        return (f"    {e['label']:<20} {e['tool_calls']:>4} calls vs "
                f"{e['groups'] + 2:>2} budgeted "
                f"({e['tool_calls'] / (e['groups'] + 2):>3.0f}x)   {rate}")

    def over_budget(e: Dict) -> bool:
        return e["tool_calls"] >= 2 * (e["groups"] + 2)

    # TURN OVERRUN. Under T_REINGEST the bill tracks turns, and an AUTHORING agent's turn
    # budget is a KNOWN number -- 1 Read + one Write per group + a final message. §10-14's
    # chunk3 took 161 tool calls against a 5-call budget and cost 35% more per item than
    # the 4-call sibling; the ledger recorded the count and nothing read it.
    #
    # Reported at >=2x only, and for `kind == authoring` ONLY. The old version scoped this
    # by proxy -- "a `groups` of 1 on a non-authoring agent makes the budget nominal" --
    # and that proxy fails in both directions (#187). A pooled REPAIR agent records
    # `groups` = the number of repair prompts it was handed, so it was scored exactly like
    # an author; and a 6-call audit against a nominal 3 fired anyway, which is the "4-vs-3
    # line is noise" the proxy was supposed to prevent (§10-13 `audit-answer-opsecon`,
    # §10-14 `audit-c5678-02`). Kind is now read, not guessed from the group count.
    over = [e for e in shaped if agent_kind(e) == "authoring" and over_budget(e)]
    if over:
        print(f"\n  TURN OVERRUN — {len(over)} authoring agent(s) spent at least twice the "
              f"tool calls\n  their group count budgets (1 Read + one Write per group + a "
              f"final message):")
        for e in sorted(over, key=lambda x: -x["tool_calls"] / (x["groups"] + 2)):
            print(line(e))
        print("  Those calls bought nothing the gate does not do for free, and the batch\n"
              "  that spent the most of them is the one that shipped five wrong keys.")

    # REPAIR TURNS. A repair agent runs past an authoring budget BY CONSTRUCTION and it is
    # not a cost finding -- `apply_repair` requires FULL copy-through rows (an absent field
    # reads as "changed to None" and the overlay is refused), so an agent repairing one
    # field must first obtain every other field of that row verbatim. §10-16's ledger
    # measured what that costs and the answer is nothing: 29 rows in 8 calls read 8.06k/row
    # and 41 rows in 69 calls read 8.12k/row -- 8.6x the turns, same rate to within 1%,
    # because those reads are cache hits against a prefix the agent already carries (its
    # T_REINGEST estimate overshot, 389.3k against a measured 333.1k). What the rate tracks
    # on all four points is the DENOMINATOR, rows -> rate:
    #     52 -> 6.21k, 41 -> 8.12k, 29 -> 8.06k, 7 -> 17.27k
    # So the table is printed sorted by rows, not by turns, and it is printed whenever
    # repair rounds exist -- the comparison IS the finding (#187).
    repairs = [e for e in shaped if agent_kind(e) == "repair"]
    if repairs:
        flagged = sum(1 for e in repairs if over_budget(e))
        print(f"\n  REPAIR TURNS — {len(repairs)} repair round(s)"
              + (f", {flagged} past an authoring turn budget." if flagged else ".")
              + "\n  Turns are NOT a cost lever here and this is not an overrun: `apply_repair`"
                "\n  requires FULL copy-through rows, so repairing one field means first reading"
                "\n  every other field of that row verbatim. The rate tracks the ROW COUNT (#187):")
        for e in sorted(repairs, key=lambda x: -x["items"]):
            a = accounted(e)
            print(f"    {e['label']:<20} {e['items']:>4} rows  {e['tool_calls']:>4} calls   "
                  f"{a['total'] / e['items'] / 1000:>6.2f}k/row")
        print("  §10-16 measured 8.6x the turns at the same rate to within 1%. Do not propose\n"
              "  cutting a repair agent's turns to save tokens — it is measured and refuted.\n"
              "  The lever is the SIZE of the round (#127's POOL_FLOOR).")

    # A row whose kind could not be READ or INFERRED is reported as such rather than
    # assumed. Inferring `authoring` wrong is how #187 happened; inferring it missing only
    # costs this line. §10-11's `chunk3-tail`/`chunk4-tail` are the live case -- an agent
    # that audited AND repaired, which is neither.
    unknown = [e for e in shaped if agent_kind(e) is None and over_budget(e)]
    if unknown:
        print(f"\n  KIND NOT RECORDED — {len(unknown)} agent(s) ran past the same budget, but "
              f"their\n  kind is neither recorded nor inferable from the label. The budget is an"
              f"\n  AUTHORING model, so no verdict is offered here. Record `--kind`:")
        for e in sorted(unknown, key=lambda x: -x["tool_calls"] / (x["groups"] + 2)):
            print(line(e))


def main() -> None:
    ap = argparse.ArgumentParser(description="Per-agent token ledger for a plan-10 slice.")
    ap.add_argument("--ledger", default=None, help="the slice's cost.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="add one agent's measured line items")
    r.add_argument("--label", required=True)
    r.add_argument("--items", type=int, required=True)
    r.add_argument("--kind", choices=KINDS, default=None,
                   help="what the agent DID: authoring | repair | audit. The turn budget "
                        "is an AUTHORING model, so only an authoring agent can overrun it "
                        "(#187). Raters and blind solvers record as `audit` — they write "
                        "nothing. Omit it and the label is used to guess, which is "
                        "one-sided: `authoring` is never inferred from an unrecognised "
                        "label.")
    r.add_argument("--groups", type=int, default=None, help="Write-groups the agent used")
    r.add_argument("--tool-calls", type=int, default=None)
    r.add_argument("--prompt-chars", type=int, default=None, help="wc -c of the prompt file")
    r.add_argument("--input", type=int, default=None)
    r.add_argument("--output", type=int, default=None)
    r.add_argument("--cache-read", type=int, default=None)
    r.add_argument("--cache-write", type=int, default=None)
    r.add_argument("--thinking", type=int, default=None)
    r.add_argument("--total", type=int, default=None, help="if only the total is reported")
    r.add_argument("--effort", default="default", help="reasoning effort this agent ran at")
    r.add_argument("--model", default="sonnet")
    r.add_argument("--note", default=None)

    p = sub.add_parser("predict", help="pre-register both theories for a chunk shape")
    p.add_argument("--items", type=int, required=True)
    p.add_argument("--groups", type=int, required=True)
    p.add_argument("--prompt-chars", type=int, required=True)

    sub.add_parser("report", help="reconcile the ledger")
    args = ap.parse_args()

    if args.cmd == "predict":
        pr = predict(args.items, args.groups, args.prompt_chars)
        print(f"\n  {pr['items']} items · {pr['groups']} Write-groups · "
              f"prompt ~{pr['prompt_tok']}tok · authored output ~{pr['authored_output_tok']}tok\n")
        print(f"  T_FLAT      {pr['T_FLAT']/1000:>7.1f}k   "
              f"({pr['T_FLAT_per_item']/1000:.2f}k/item)   fixed ~65k/agent + output")
        print(f"  T_REINGEST  {pr['T_REINGEST']/1000:>7.1f}k   "
              f"({pr['T_REINGEST_per_item']/1000:.2f}k/item)   context re-sent every turn")
        print(f"\n  they differ by {pr['spread']/1000:.0f}k on this shape — big enough to "
              f"tell apart.\n  Record the real number and the argument is over.\n")
        return

    if not args.ledger:
        raise SystemExit("--ledger is required for record/report")
    path = Path(args.ledger)
    entries: List[Dict] = []
    if path.exists():
        entries = json.loads(path.read_text(encoding="utf-8"))

    if args.cmd == "record":
        e = {k: v for k, v in vars(args).items()
             if k not in ("cmd", "ledger") and v is not None}
        if any(x.get("label") == e["label"] for x in entries):
            raise SystemExit(f"'{e['label']}' is already in this ledger — pick a new label "
                             "(a re-run is its own row, e.g. chunk1-rerun)")
        entries.append(e)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
        a = accounted(e)
        print(f"  recorded {e['label']}: {e['items']} items"
              + (f", {a['total']/1000:.1f}k tokens, {a['pct_unexplained']:.0f}% unexplained"
                 if a else " (no totals given)"))
        return

    cmd_report(entries)


if __name__ == "__main__":
    main()
