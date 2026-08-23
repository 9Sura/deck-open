#!/usr/bin/env python3
"""Measure a blind auditor's DECLINED method-note patterns against a batch and the committed bank.

WHY THIS EXISTS
---------------
A blind audit pass is asked to name every recurring cross-row construction it noticed and
DECLINED to flag. Those names are the valuable half of the return: a blind agent cannot
compute a baseline, so it cannot tell a batch defect from a corpus convention. The caller can.

The protocol has now run on four groups of §10-15 and it has said BOTH things:

  * chunk 1     — one named pattern ("even though it costs something" concessive on the
                  likely-correct option) ran at 4.9x the bank's occurrence and marked the key
                  70% of the time against ~25% chance. It CAUSED a 4-row repair.
  * chunks 2/3/4 — nine named, three measurable, all three DECLINED. The most-suspected one was
                  a corpus-wide property on 20.5% of the whole bank. Prevented a ~25-row round.
  * chunks 5/6/7 — nine named, six measurable, all six DECLINED. Prevented a ~30-row round.

Three groups re-derived these regexes BY HAND and the bank arm's absolute rates differ between
sessions, so only the within-run arm comparison has ever been valid. This file is the fix: the
patterns and the metric are committed, so a rate measured this slice is comparable to one
measured next slice.

THE METRIC, STATED ONCE
-----------------------
Per pattern, per arm (a "row" is one question with four options and a keyed letter):

  tagged rows  rows where AT LEAST ONE option matches the pattern
  key rate     of the tagged rows, the share where the KEY option matches
  chance       the expected key rate if the key were placed at random: the mean over tagged
               rows of (matching options / 4). This is a Poisson-binomial mean, NOT a flat 25% —
               a pattern that tags three of four options is expected to land on the key 75% of
               the time and must be read against that, not against chance-of-one-option.
  lift         key rate / chance. 1.00x is "this construction says nothing about the key".
  p            exact two-sided Poisson-binomial p-value for the observed key count.

READING IT (the rules three groups have already paid for)
---------------------------------------------------------
* Read the RATE to decide the BATCH; read the ROWS as candidates (#153). A pattern declined as
  a batch pattern can still contain individual rows where the construction does the
  disqualifying work. Both are correct at once.
* A batch can deviate from the CORPUS without being gameable WITHIN ITSELF. Compare the batch's
  lift against ~1.00x to decide whether the batch is gameable; compare the batch's lift against
  the BANK's lift to decide whether it diverges in style. Only the first licenses a repair.
* The auditor's own top-confidence pattern has INVERTED on the last two groups. Expect it.

SETTLED — DO NOT RE-LITIGATE (measured on three independent groups):
  * explanatory-clause (since/because/so that/purpose) marks a DISTRACTOR in both the batch and
    the bank arm.
  * the TOTALIZER (throughout/every/full/entire/verbatim) is a real signal but CORPUS-WIDE.
    Filed as an issue; not a batch defect.
  * `passive` · `absolute` · `trailing_clause` · `trailing_relative` are CORPUS-WIDE too and all
    significant past p=1e-22 (#188). The three §10-16 groups that named them each declined them
    as batch patterns and each was right. Their regexes are NOT defined here — see below.

THE SETTLED NUMBERS USED TO BE QUOTED ABOVE AND THEY WENT STALE, so they are not any more.
`--bank-only` prints today's, over today's bank, in one command. Two of them had drifted far
enough to mislead: `justification` was written up as ~0.22-0.26x and reads 0.66x, and
`totalizer` as ~0.15x on ~19% of rows and reads 0.40x on 17.9%. Neither pattern changed — the
bank grew (14,854 -> 15,564 over §10-15 alone) and the original figures came off scoped arms in
sessions that are now several slices back. This is #153's and #185's stale-baseline shape, and
the answer here is the same as there: a number that only drifts as the bank grows should be
MEASURED at the point of use, not transcribed. The VERDICTS above are the durable half — which
way each construction points, and that it is corpus-wide rather than a batch defect.

WHERE THE #188 PATTERNS LIVE, AND WHY NOT HERE
----------------------------------------------
`passive` / `absolute` / `trailing_clause` / `trailing_relative` are imported from
`generators/audit_tells.py`, which is the committed bank-report tier and now prints them
corpus-wide beside the length tells. They are a property of the CORPUS, so their home is the
corpus report and this file borrows them, not the other way round — the same one-definition
bargain this file already struck for its own builtins. `poisson_binomial_pvalue` moved there
with them for the same reason, and it was carrying a real precision bug at bank scale (an
ABSOLUTE epsilon on a probability that goes far below it, flooring every significant bank-arm
result at ~1e-15). Read that docstring before quoting a p-value from before this landed.

USAGE
-----
  python method_note_patterns.py \
      --part "output/plan-10/10-15/parts/chunk8-part*.json" \
      --part "output/plan-10/10-15/parts/chunk9-part*.json" \
      --bank-cluster marketing --bank-level Association     # bank arm scoped, or omit for all
      --pattern "hedge=\\b(usually|generally|typically)\\b"  # ad-hoc, repeatable
      --only concessive,totalizer                            # subset of the builtins

  python method_note_patterns.py --bank-only                 # the CORPUS report (#188), no batch
  python method_note_patterns.py --bank-only --bank-cluster marketing --only totalizer

--bank-only is the answer to the thing #188 was actually about: for twelve slices `--part` was
REQUIRED, so this instrument could only ever answer "is my batch gameable" and never "is the
corpus". Nobody owned the second question, so three groups asked it by hand, three sessions
apart, with three hand-rebuilt copies of the regexes. It is a separate flag rather than a
quietly-optional `--part` because the ARM COMPARISON is still the point on a slice, and a
missing batch must stay an error there.

Paths are resolved relative to the repo root when they are not absolute.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Callable

# .../backend/test-gen-model/src/generators/slice-tools/ -> five levels up is the repo root.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), *([".."] * 5)))
BANK_DIR = os.path.join(REPO_ROOT, "frontend", "public", "question-bank")

# The generators dir is the committed tier; slice-tools borrows from it and never the
# reverse, exactly as the fixtures_*.py in this directory import check_authored.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from audit_tells import (  # noqa: E402
    WORDING_PATTERNS,
    poisson_binomial_pvalue,
)

# --------------------------------------------------------------------------------------
# The builtin pattern registry.
#
# Each entry is (name, note, matcher). A matcher takes (row, letter) and returns True when
# THAT option carries the construction. Most are option-local regexes; two are structural and
# need the whole row, which is why the signature is not just a string.
# --------------------------------------------------------------------------------------

def _rx(pattern: str) -> Callable[[dict, str], bool]:
    compiled = re.compile(pattern, re.IGNORECASE)
    def match(row: dict, letter: str) -> bool:
        return bool(compiled.search(row["options"].get(letter, "")))
    return match


def _shortest_option(row: dict, letter: str) -> bool:
    """The single shortest option. Ties tag every option sharing the minimum."""
    lens = {k: len(v) for k, v in row["options"].items()}
    return lens.get(letter, -1) == min(lens.values())


_WORD = re.compile(r"[a-z]{4,}")
_STOP = {
    "that", "this", "with", "from", "have", "will", "your", "their", "which", "when", "what",
    "them", "than", "then", "they", "been", "were", "into", "more", "most", "some", "such",
    "each", "also", "only", "over", "same", "other", "would", "could", "should", "about",
    "after", "before", "because", "while", "these", "those", "there", "where",
}


def _stem_words(row: dict) -> set:
    return {w for w in _WORD.findall(row["question"].lower()) if w not in _STOP}


def _stem_overlap_argmax(row: dict, letter: str) -> bool:
    """The option sharing the most content words with the stem. Ties tag all the leaders.

    This is the shape a blind reader describes as "keep the one option that talks about what
    the stem talks about". It has measured BELOW chance twice, plausibly because
    check_authored's stem-pull gate trains authors away from exactly that overlap.
    """
    stem = _stem_words(row)
    if not stem:
        return False
    scores = {k: len(stem & {w for w in _WORD.findall(v.lower()) if w not in _STOP})
              for k, v in row["options"].items()}
    top = max(scores.values())
    if top == 0:
        return False
    return scores.get(letter, -1) == top


def _figure_free_shortest(row: dict, letter: str) -> bool:
    """The shortest option, on rows where no option carries a numeral."""
    if any(re.search(r"\d", v) for v in row["options"].values()):
        return False
    return _shortest_option(row, letter)


BUILTINS: dict[str, tuple[str, Callable[[dict, str], bool]]] = {
    # ---- named by blind auditors on §10-15, all measured, most declined -------------------
    "concessive": (
        "chunk 1's class: 'even though / while it costs / at the cost of' on the option. The ONE "
        "pattern the protocol has ever confirmed — 4.9x bank occurrence, 70% key-marking.",
        _rx(r"\b(even though|even if|while it|although|despite the|at the cost of|"
            r"even when|though it)\b"),
    ),
    "appositive": (
        "chunks 2/3/4's definitional appositive: a gloss on a subset of the options. DECLINED as "
        "corpus-wide — 20.5% of the bank, gloss on the key at 1.66x chance.",
        _rx(r"[a-z]{4,},\s+(?:a|an|the)\s+[a-z]+(?:\s+[a-z]+){0,3}\s+(?:that|which|of|used)\b"),
    ),
    "justification": (
        "since / because on an option. SETTLED at ~0.23x in BOTH arms across three groups: the "
        "corpus convention is that an explanatory clause marks a DISTRACTOR.",
        _rx(r"\b(since|because)\b"),
    ),
    "purpose": (
        "so that / in order to on an option. Same family as `justification`, same verdict.",
        _rx(r"\b(so that|in order to|so as to)\b"),
    ),
    "totalizer": (
        "throughout / every / full / entire / verbatim / all of. REAL but CORPUS-WIDE: ~0.15x "
        "over ~19% of the whole bank. Filed as an issue, declined as a batch pattern.",
        _rx(r"\b(throughout|every|entire|entirely|verbatim|all of the|always|never|"
            r"completely|full)\b"),
    ),
    "conjunctive": (
        "an option joining two acts with 'and'. Declined — 40% of the bank carries it.",
        _rx(r"\b\w+\s+and\s+\w+"),
    ),
    "act_and_report": (
        "the situational-judgment 'do X and tell someone' shape.",
        _rx(r"\b(and (then )?(notify|inform|report|tell|escalate|document|alert)|"
            r"then (notify|inform|report|escalate))\b"),
    ),
    "self_label": (
        "an option editorialising about its own status — the L class made greppable. Read the "
        "ROWS, not the rate: the instrument is the blind pass, this is only its net.",
        _rx(r"\b(the (correct|right|best|proper|appropriate|actually)|"
            r"which is (correct|wrong|incorrect)|a common (mistake|error)|"
            r"the response a|the approach that|from the [a-z]+'s (first|second|third) attempt)\b"),
    ),
    # ---- structural, not lexical ----------------------------------------------------------
    "shortest": (
        "the shortest option of the four. Directly refuted twice (~0.20-0.22x).",
        _shortest_option,
    ),
    "shortest_figure_free": (
        "the shortest option on a row carrying no numerals — shard 01's #5.",
        _figure_free_shortest,
    ),
    "stem_overlap": (
        "the option sharing the most content words with the stem. Has measured BELOW chance on "
        "both groups that ran it; the stem-pull gate points the other way.",
        _stem_overlap_argmax,
    ),
}

# ---- the #188 corpus constructions, borrowed whole from the bank report -------------------
# Registered rather than re-typed. Three §10-16 groups named these and each rebuilt the
# regexes by hand; that is the drift this file exists to end, and the registry is one import
# away in audit_tells.py. A name collision would silently replace a builtin above, so it is
# an error rather than an overwrite.
for _name, (_note, _rx_compiled) in WORDING_PATTERNS.items():
    if _name in BUILTINS:
        raise RuntimeError(
            f"#188 pattern {_name!r} collides with a builtin of the same name; rename one — "
            f"a silent overwrite would make two slices' numbers incomparable under one label")
    BUILTINS[_name] = (
        f"#188, corpus-wide: {_note}",
        (lambda rx: lambda row, letter: bool(rx.search(row["options"].get(letter, ""))))(
            _rx_compiled),
    )


# --------------------------------------------------------------------------------------
# Arms
# --------------------------------------------------------------------------------------

def _resolve(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(REPO_ROOT, path)


def _normalise(raw: dict) -> dict | None:
    """Both arms are dicts carrying question/options/answer; the batch arm has no `id`."""
    opts = raw.get("options")
    if not isinstance(opts, dict) or set(opts) != {"A", "B", "C", "D"}:
        return None
    answer = raw.get("answer")
    if answer not in opts:
        return None
    if not isinstance(raw.get("question"), str):
        return None
    return {
        "ref": raw.get("id") or raw.get("cand_id") or "?",
        "question": raw["question"],
        "options": {k: str(v) for k, v in opts.items()},
        "answer": answer,
        "cluster": raw.get("cluster"),
        "level": raw.get("level"),
        "instructionalArea": raw.get("instructionalArea"),
    }


def load_rows(patterns: list[str]) -> list[dict]:
    rows: list[dict] = []
    for pat in patterns:
        hits = sorted(glob.glob(_resolve(pat)))
        if not hits:
            print(f"  WARNING: no files match {pat}", file=sys.stderr)
        for path in hits:
            if os.path.basename(path) == "manifest.json":
                continue
            with open(path) as fh:
                blob = json.load(fh)
            items = blob if isinstance(blob, list) else blob.get("questions", [])
            for raw in items:
                row = _normalise(raw)
                if row:
                    rows.append(row)
    return rows


def bank_rows(cluster: str | None, level: str | None) -> list[dict]:
    rows = load_rows([os.path.join(BANK_DIR, "*", "*.json")])
    if cluster:
        rows = [r for r in rows if r["cluster"] == cluster]
    if level:
        rows = [r for r in rows if r["level"] == level]
    return rows


# --------------------------------------------------------------------------------------
# The measurement
# --------------------------------------------------------------------------------------

def measure(rows: list[dict], matcher: Callable[[dict, str], bool]) -> dict:
    tagged = 0
    key_tagged = 0
    probs: list[float] = []
    hits: list[str] = []
    for row in rows:
        marks = [L for L in "ABCD" if matcher(row, L)]
        if not marks:
            continue
        tagged += 1
        probs.append(len(marks) / 4.0)
        if row["answer"] in marks:
            key_tagged += 1
            hits.append(row["ref"])
    if not tagged:
        return {"rows": len(rows), "tagged": 0, "key": 0, "key_rate": 0.0,
                "chance": 0.0, "lift": None, "p": 1.0, "hits": []}
    chance = sum(probs) / len(probs)
    key_rate = key_tagged / tagged
    return {
        "rows": len(rows),
        "tagged": tagged,
        "key": key_tagged,
        "key_rate": key_rate,
        "chance": chance,
        "lift": (key_rate / chance) if chance else None,
        "p": poisson_binomial_pvalue(probs, key_tagged),
        "hits": hits,
    }


def _fmt_p(p: float) -> str:
    """Fixed notation while it is readable, scientific once it is not.

    `{:.4f}` printed 0.0000 for everything below 1e-4, which is most of the bank arm and
    was hiding the difference between "just significant" and 1e-198 — the same flattening
    that hid the absolute-epsilon bug in poisson_binomial_pvalue for twelve slices.
    """
    return f"{p:>7.4f}" if p >= 1e-4 else f"{p:>7.1e}"


def _fmt(res: dict) -> str:
    if not res["tagged"]:
        return f"{'0':>6} {'':>7}   {'—':>7} {'—':>7} {'—':>6} {'—':>7}"
    return (f"{res['tagged']:>6} {res['tagged'] / res['rows'] * 100:>6.1f}%  "
            f"{res['key_rate'] * 100:>6.1f}% {res['chance'] * 100:>6.1f}% "
            f"{res['lift']:>5.2f}x {_fmt_p(res['p'])}")


def report_bank_only(bank: list[dict], selected: dict, scope: str) -> int:
    """The corpus report (#188): one arm, and a verdict keyed to 1.00x rather than to a batch.

    Split out rather than folded into the two-arm printer because the READING is different.
    On a slice the question is "does my batch diverge from the corpus"; here there is no
    batch, so the only question left is "does this construction say anything about the key
    at all" — and the answer is a standing corpus property, never a work order. A row list
    would be 4,287 items long and is deliberately not offered.
    """
    print(f"\n  CORPUS report · {scope} · no batch arm")
    print("  chance = mean(matching options / 4) over tagged rows, NOT a flat 25%.")
    print("  lift = key rate / chance. 1.00x means the construction says nothing about the key.\n")
    print(f"  {'pattern':<22}{'tagged':>6} {'share':>7}  {'key':>7} {'chance':>7} "
          f"{'lift':>6} {'p':>7}")
    print("  " + "-" * 72)
    results = {}
    for name, (_, matcher) in selected.items():
        results[name] = measure(bank, matcher)
        print(f"  {name:<22}{_fmt(results[name])}")

    # READ THE LIFT AND THE SHARE, NOT THE FLAG. At corpus scale p<0.05 is nearly free —
    # 15 of 15 builtins clear it on today's bank — so significance sorts nothing. The
    # verdicts are ordered by how far the lift stands from 1.00x, strongest first, and a
    # construction on 0.7% of rows is a different problem from one on 38%.
    print(f"\n  Verdicts, strongest lift first (p<0.05 is nearly free at n={len(bank)}):")
    ranked = sorted(
        ((n, r) for n, r in results.items()
         if r["tagged"] and r["lift"] and r["p"] < 0.05
         and not 0.85 < r["lift"] < 1.15),
        key=lambda kv: -max(kv[1]["lift"], 1 / kv[1]["lift"]))
    for name, res in ranked:
        # Both directions are reportable and they are NOT the same finding: a construction
        # the key avoids is a free ELIMINATION, one the key prefers is a free PICK.
        verdict = "PREFERS" if res["lift"] >= 1.15 else "AVOIDS "
        tail = "" if res["lift"] >= 1.15 else "; free elimination without the stem"
        print(f"  ** {name:<22} key {verdict} it — {res['lift']:>5.2f}x on "
              f"{res['tagged'] / res['rows'] * 100:>5.1f}% of rows "
              f"(p={_fmt_p(res['p']).strip()}){tail}")
    print(f"\n  A corpus rate is not a repair scope. {len(bank)} rows cannot be re-authored, "
          f"and a repair\n  round on a sound row makes the bank worse — see #188 and the "
          f"audit_tells.py docstring.\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--part", action="append", default=[],
                    help="glob of authored part files = the BATCH arm (repeatable)")
    ap.add_argument("--bank-cluster", default=None, help="scope the bank arm to one cluster")
    ap.add_argument("--bank-level", default=None, help="scope the bank arm to one level")
    ap.add_argument("--no-bank", action="store_true",
                    help="skip the bank arm (the arm comparison is the whole point — say why)")
    ap.add_argument("--bank-only", action="store_true",
                    help="the CORPUS report (#188): run the bank arm alone, with no batch")
    ap.add_argument("--pattern", action="append", default=[],
                    help="ad-hoc pattern as name=REGEX, matched per option (repeatable)")
    ap.add_argument("--only", default=None,
                    help="comma-separated subset of the builtin pattern names")
    ap.add_argument("--list-patterns", action="store_true",
                    help="print the builtin registry with its notes and exit")
    ap.add_argument("--show-rows", default=None,
                    help="pattern name whose BATCH key-carrying rows should be listed")
    args = ap.parse_args()

    if args.list_patterns:
        for name, (note, _) in BUILTINS.items():
            print(f"{name:<22} {note}")
        return 0

    if args.bank_only:
        # Both of these would leave nothing to measure, or measure it twice under one
        # heading. Refuse rather than pick one for the caller.
        if args.part:
            ap.error("--bank-only takes no --part (it IS the no-batch mode)")
        if args.no_bank:
            ap.error("--bank-only and --no-bank leave no arm at all")
        if args.show_rows:
            # --show-rows lists BATCH rows by design; on the corpus it would be a 4,287-row
            # dump masquerading as a work order, which is the one thing #188 asks nobody to
            # produce. Refuse rather than silently print the bank's.
            ap.error("--show-rows lists BATCH rows; there is no batch under --bank-only")
    elif not args.part:
        ap.error("--part is required (the batch arm), or --bank-only for the corpus report")

    selected: dict[str, tuple[str, Callable[[dict, str], bool]]] = {}
    if args.only:
        for name in [n.strip() for n in args.only.split(",") if n.strip()]:
            if name not in BUILTINS:
                ap.error(f"unknown builtin pattern {name!r}; --list-patterns to see them")
            selected[name] = BUILTINS[name]
    else:
        selected = dict(BUILTINS)
    for spec in args.pattern:
        if "=" not in spec:
            ap.error(f"--pattern wants name=REGEX, got {spec!r}")
        name, rx = spec.split("=", 1)
        selected[name.strip()] = (f"ad-hoc: {rx}", _rx(rx))

    if args.bank_only:
        bank = bank_rows(args.bank_cluster, args.bank_level)
        if not bank:
            print("no bank rows loaded", file=sys.stderr)
            return 2
        return report_bank_only(
            bank, selected,
            f"{len(bank)} rows ({args.bank_cluster or 'all clusters'}"
            f"/{args.bank_level or 'all levels'})")

    batch = load_rows(args.part)
    if not batch:
        print("no batch rows loaded", file=sys.stderr)
        return 2
    bank = [] if args.no_bank else bank_rows(args.bank_cluster, args.bank_level)

    scope = "bank arm SKIPPED" if args.no_bank else (
        f"bank arm {len(bank)} rows"
        + (f" ({args.bank_cluster or 'all clusters'}"
           f"/{args.bank_level or 'all levels'})" if (args.bank_cluster or args.bank_level) else ""))
    print(f"\n  batch arm {len(batch)} rows · {scope}")
    print("  chance = mean(matching options / 4) over tagged rows, NOT a flat 25%.")
    print("  lift = key rate / chance. 1.00x means the construction says nothing about the key.\n")

    head = (f"  {'pattern':<22}{'BATCH':>16}{'':>23}   {'BANK':>15}{'':>23}")
    print(head)
    print(f"  {'':<22}{'tagged':>6} {'share':>7}  {'key':>7} {'chance':>7} {'lift':>6} {'p':>7}"
          f"   {'tagged':>6} {'share':>7}  {'key':>7} {'chance':>7} {'lift':>6} {'p':>7}")
    print("  " + "-" * 120)

    results = {}
    for name, (_, matcher) in selected.items():
        b = measure(batch, matcher)
        k = measure(bank, matcher) if bank else None
        results[name] = (b, k)
        line = f"  {name:<22}{_fmt(b)}"
        line += f"   {_fmt(k)}" if k else "   (skipped)"
        print(line)

    print()
    for name, (b, k) in results.items():
        if not b["tagged"] or b["lift"] is None:
            continue
        flags = []
        if b["p"] < 0.05 and b["lift"] > 1.15:
            flag = f"BATCH key-loaded {b['lift']:.2f}x (p={_fmt_p(b['p']).strip()})"
            # A batch lift that matches the corpus is a CORPUS property the batch inherited.
            # Repairing rows here cannot move a bank-wide baseline (chunks 2/3/4 finding 3a).
            if k and k["lift"] and 0.7 <= b["lift"] / k["lift"] <= 1.4:
                flag += (f" — but the bank runs {k['lift']:.2f}x on {k['tagged'] / k['rows'] * 100:.1f}% "
                         f"of its rows, so this is CORPUS-WIDE, not a batch defect")
            flags.append(flag)
        if k and k["lift"] and b["lift"] > 1.4 * k["lift"] and b["tagged"] >= 15:
            flags.append(f"diverges from corpus ({b['lift']:.2f}x vs bank {k['lift']:.2f}x) — "
                         f"STYLE divergence, not automatically a defect")
        if flags:
            print(f"  ** {name}: " + "; ".join(flags))
    print("\n  Nothing above is a work order. A rate decides the BATCH; the rows stay candidates.\n")

    if args.show_rows:
        if args.show_rows not in selected:
            print(f"  --show-rows: {args.show_rows!r} not measured", file=sys.stderr)
            return 2
        b, _ = results[args.show_rows]
        print(f"  batch rows where the KEY carries `{args.show_rows}` ({len(b['hits'])}):")
        for ref in b["hits"]:
            print(f"    {ref}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
