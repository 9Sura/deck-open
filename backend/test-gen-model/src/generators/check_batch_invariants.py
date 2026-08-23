#!/usr/bin/env python3
"""Deterministic batch invariants — the checks no model needs to run. No model.

WHY THIS EXISTS -- plan 10-12, measured 2026-08-04.

Every other gate in this pipeline reasons about ONE ROW AT A TIME:
`check_authored` scores a row against its payload spec, `audit_tells` measures a
row's option lengths, `check_key_figures` compares a row's key to a row's
explanation, `option_tells` and `label_divergence` read a row's four options.

§10-12 shipped `m0048` past ALL of them. Its stem was a $50,000 surplus-cash
funding decision; two of its four options had been copied verbatim out of
`m0057`, a chemical-leak ethics item, and read "the company should keep shipping
since the leak is currently small and still legal" and "the manager should let
the insurance carrier make this decision". Two of four options were nonsense for
the stem, collapsing the item to a coin flip. Nothing caught it, because
cross-item option contamination is a BETWEEN-row defect and every instrument was
a WITHIN-row instrument. An answerability agent found the lead; this file is the
cheap deterministic version, and it costs zero tokens.

The rule this encodes: whatever you can check with `==` should never be spent on
a model. Model instruments are for semantics; these are for identity.

WHAT IS BLOCKING VS ADVISORY
  BLOCKING (exit 1) -- an identity error, always wrong, never a judgement call:
      cross-row duplicate option, answer letter off its assignment, duplicate
      options within a row, malformed/missing fields.
  ADVISORY (exit 0, printed) -- needs a human read, has a known false-positive
      class: rule 13b figure sharing, decimal odd-one-out, decimal PRECISION
      odd-one-out, the article-before-a-numeral form, near-duplicate stems.

THERE IS NO SUPERSET CHECK, AND THAT IS A MEASURED DECISION
An option-superset check was written twice and cut twice.

  Form 1, naive substring: reports `20% markup based on cost` inside `120% markup
  based on cost`. Not a superset -- `20` is a digit-suffix of `120`. RULE-13
  NORMALISATION MANUFACTURES THIS: once four options share one label and differ
  only in the number, any number that is a digit-suffix of another collides.
  §10-12 hit 5, all false.

  Form 2, containment on the FIGURE-STRIPPED label, skipping rows whose four
  labels are identical: fired on 45 of §10-12's 152 shipped rows (30%), and every
  hit was a TRAILING QUALIFIER -- "per new member acquired" inside "per new
  member acquired this campaign month". Those tails are not sloppiness; on hard
  rows `key_length_rank` HARD-fails and the tail is the only way to satisfy it,
  so the check penalises exactly what another gate requires.

A flag at a 30% rate is one whoever reads the report learns to skip -- the same
calibration `build_question_bank.check_question` documents for the 1.5x length
rule. The real defect it was reaching for (one option strictly broader in MEANING
than another, so both are correct) is semantic, and belongs to the answerability
instrument. Pinned in slice-tools/fixtures_batch_invariants.py.

THE FORMAT TELLS THAT SIT UNDER DECIMAL-ODD (issue #174, measured 2026-08-10)
DECIMAL-ODD only fires on a 1-of-4 or 3-of-4 split in whether an option carries a
decimal AT ALL. Three narrower format tells sit underneath it, each of which lets
a reader rank the options with zero arithmetic, and none of the other instruments
can see any of them -- `label_divergence` strips every figure before comparing
(blind to digit format by construction) and `option_tells` is a phrase list.

All three were named by a blind solver on §10-14's H1 after it had passed every
deterministic gate. Measured against the committed bank (14,854 rows), the answers
were NOT the same for the three, and each is implemented -- or declined -- on its
own number rather than on the shared story:

  1. ARTICLE BEFORE A NUMERAL. `An $80 keystone selling price` against `A $70... /
     A $75... / A $60...`. "An" agrees with the vowel sound of *eighty*, so the
     article alone identifies the key. GATED HERE, as a CONSTRUCTION rule, and
     the distinction matters: the tell RATE is not measurable. Only 13 bank rows
     put an article before a numeral in all four options with one article odd, and
     the key is the odd one on 3 of them -- 23.1%, BELOW the 25% chance floor
     (p=0.67). What justifies the check is not a rate but that the defect is real
     per item (§10-14 `h0014`, solved cold by a blind solver), the form is
     unnecessary in every case, and the rewrite -- `A keystone selling price of
     $80` -- removes it by construction and is checkable. Rate on the bank: 163
     of 14,854 rows carry the form (1.10%), which is 129 of the 1,056 rows whose
     four options are all quantities (12.2%) -- the second figure is the one the
     report quotes, because the first is diluted by 13,000 prose rows and would
     read every real computational batch as an outlier.

  2. PRECISION, NOT PRESENCE, OF A DECIMAL. `8.0` keyed against `9.88 / 8.78 /
     9.13`: all four carry decimals so DECIMAL-ODD stays silent, but one is
     visibly the "clean" one. GATED HERE. This is the one with a real signal --
     65 bank rows have a lone fewest-significant-places option and the key is it
     on 22, 33.85% against a 25% floor (p=0.070). Suggestive, NOT significant;
     the finding is a candidate to read, never a work order. Two blind solvers
     and one difficulty rater named it independently on §10-14.

  3. LONE NON-ROUND CENTS. `$547.20` keyed against `$608.00 / $576.00 / $520.00`.
     DECLINED, ON THE RECORD, and it must not be added later without new evidence:
     34 bank rows, key on 10, 29.41% (p=0.34) -- at chance. And the cents are a
     TRUE CONSEQUENCE of the correct chain (the full chain lands on cents
     precisely because it is chained; every shortcut is round), so the only fix is
     renumbering the stem, which risks a real arithmetic error to chase a
     non-signal. Recorded as a documented limitation of chain-computation items.

WHAT ISSUE #174's HEADLINE NUMBER ACTUALLY MEASURED, because it will be re-derived
otherwise. The issue reported the article tell at 34% key rate over 1,229 in-scope
rows, which reproduces (1,649 / 485 / 167, 34.4%, p<0.0001 on today's bank) -- but
that scope is EVERY indefinite article anywhere in an option, not one before a
numeral. Split it and the signal is not the article at all:

    article sits before a NUMERAL (the named mechanism)     3 of 13   23.1%
    article sits before a WORD (one option worded oddly)   164 of 472 34.7%

The 34% is one option's WORDING diverging from the other three, with the key being
that option -- `label_divergence`'s defect, already instrumented, not a format
tell. NO BROAD ARTICLE CHECK IS BUILT HERE, and building one would re-report
label divergence in a second place under a name that misattributes it.
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Dict, List

OPTION_KEYS = ("A", "B", "C", "D")

# A figure: an optionally $-prefixed, comma-grouped, optionally decimal number.
FIGURE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")
# A decimal figure specifically -- used by the decimal odd-one-out check.
DECIMAL = re.compile(r"\d+\.\d")
# An indefinite article immediately before a numeral: "An $80 keystone price".
# Captures the article so the four options can be compared against each other.
# The currency prefix is inside the lookahead deliberately -- "an $80" is the form
# that leaks, and the article agrees with the DIGIT's sound, not the symbol's.
ARTICLE_NUMERAL = re.compile(r"\b(an?)\s+(?=[$€£]?\s?\d)", re.I)
# The fractional part of a decimal figure, for the precision odd-one-out check.
DECIMAL_PLACES = re.compile(r"\d[\d,]*\.(\d+)")
# A QUANTITY, not merely a digit -- borrowed from check_authored.label_divergence
# for the same reason it exists there: "Option 2 is cheaper" is a digit and a prose
# row is not the shape these format tells live on. Used only as the DENOMINATOR for
# the article rate, never as a filter on what is checked.
QUANTITY = re.compile(r"([$€£]\s?\d|\d[\d,]*\.\d|\d[\d,]*\s*%|\d[\d,]{2,})")


# A MINUS IN FRONT OF A NUMBER IS PART OF THE NUMBER, NOT PUNCTUATION (§10-17 round 4).
# `norm` strips `[^a-z0-9 ]`, so "-$700 in net worth" and "$700 in net worth" normalise
# to the same string and the duplicate-option check calls them the same text. On a
# signed-quantity row the sign IS the answer -- hos-district-pool-0562 asks for a net
# worth that comes out NEGATIVE, and its C/D pair differ by exactly that. The row only
# became visible once §10-17 gave the key the same label as the other three, which is
# the whole point of the reword: before that the two options differed in wording, so the
# collision was hidden behind a defect.
#
# Measured over all 16,283 committed questions: ONE within-row duplicate exists and this
# is it. The change can only ever UN-collide a pair -- it adds a token, never removes one
# -- so no row starts reporting a duplicate it did not have.
NEGATIVE_FIGURE = re.compile(r"-(?=\s?[$€£]?\s?\d)")


def norm(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — keeping a leading minus."""
    return re.sub(r"\s+", " ", re.sub(
        r"[^a-z0-9 ]", "", NEGATIVE_FIGURE.sub("neg ", (text or "").lower()))).strip()


def strip_figures(text: str) -> str:
    """The option's LABEL: what is left once every number is removed.

    This is the unit rule 13 actually talks about -- 'all four options describe
    the same quantity in the same words; only the number differs' is exactly the
    claim that these four strings are equal.
    """
    return norm(FIGURE.sub(" ", text or ""))


def figures(text: str) -> set:
    return {f.lstrip("$").rstrip("%").replace(",", "") for f in FIGURE.findall(text or "")}


def article_before_numeral(text: str):
    """The indefinite article this option puts in front of a number, or None.

    Returns the lowercased article ("a"/"an") so the four options are comparable.
    Only the FIRST occurrence is read: an option that says it twice is already
    flagged by the first, and a second reading would let a trailing "a 12-month
    term" outvote the leading tell.
    """
    m = ARTICLE_NUMERAL.search(str(text or ""))
    return m.group(1).lower() if m else None


def decimal_places(text: str):
    """Significant decimal places in this option's first decimal figure, or None.

    TRAILING ZEROS ARE STRIPPED, which is the whole point: `8.0` and `8` are the
    same precision to a reader, and `8.0` beside `9.88 / 8.78 / 9.13` is exactly
    the §10-14 `h0005` shape -- the "clean" one. Counting raw characters would
    score `8.0` at 1 place and hide it among the two-place options.
    """
    m = DECIMAL_PLACES.search(str(text or ""))
    return len(m.group(1).rstrip("0")) if m else None


def load_parts(patterns: List[str]) -> List[Dict]:
    rows = []
    for pat in patterns:
        for path in sorted(glob.glob(pat)):
            with open(path, encoding="utf-8") as fh:
                for row in json.load(fh):
                    row["_file"] = os.path.basename(path)
                    rows.append(row)
    return rows


def check(rows: List[Dict], payload: Dict[str, Dict], stem_ratio: float,
          scope_label: str) -> tuple:
    blocking, advisory = [], []

    # --- BLOCKING: field shape ------------------------------------------------
    for r in rows:
        cid = r.get("cand_id", "<no cand_id>")
        opts = r.get("options")
        if not isinstance(opts, dict) or set(opts) != set(OPTION_KEYS):
            blocking.append(f"{cid}: options must be exactly A,B,C,D (got "
                            f"{sorted(opts) if isinstance(opts, dict) else type(opts).__name__})")
            continue
        if r.get("answer") not in OPTION_KEYS:
            blocking.append(f"{cid}: answer {r.get('answer')!r} is not one of A-D")
        for field in ("question", "explanation", "performanceIndicator", "instructionalArea"):
            if not str(r.get(field) or "").strip():
                blocking.append(f"{cid}: empty {field}")
        if r.get("difficulty") not in ("easy", "medium", "hard"):
            blocking.append(f"{cid}: difficulty {r.get('difficulty')!r} is not easy/medium/hard")
        # duplicate options within the row (rule 13a)
        seen = {}
        for k in OPTION_KEYS:
            n = norm(str(opts[k]))
            if not n:
                blocking.append(f"{cid}: option {k} is empty")
            elif n in seen:
                blocking.append(f"{cid}: options {seen[n]} and {k} are the same text")
            else:
                seen[n] = k

    # --- BLOCKING: answer letter vs the payload's assignment -------------------
    # GUARDED, because cand_ids COLLIDE ACROSS CHUNKS. build_area restarts its
    # numbering per payload, so chunk9/e0019 and chunk10/e0019 are different
    # questions. Checking a multi-chunk part set against ONE chunk's payload
    # silently compares every row to the wrong spec: doing exactly that on
    # §10-12's shipped batch produced 25 "letter mismatches", all false. Refuse
    # instead -- the same failure `apply_repair --expect` is scoped to avoid.
    if payload:
        seen_ids = defaultdict(set)
        for r in rows:
            seen_ids[r.get("cand_id")].add(r.get("_file"))
        collided = {cid: f for cid, f in seen_ids.items() if len(f) > 1}
        if collided:
            sample = ", ".join(f"{cid} in {sorted(f)}" for cid, f in list(collided.items())[:3])
            raise SystemExit(
                f"\n  REFUSING the answer-letter check: {len(collided)} cand_id(s) appear in more\n"
                f"  than one part file, so a single --payload cannot say which row each spec\n"
                f"  belongs to. cand_ids restart per payload, so the same id names DIFFERENT\n"
                f"  questions in different chunks.\n"
                f"      e.g. {sample}\n"
                f"  Scope --payload and --part to ONE chunk, or drop --payload to run the\n"
                f"  cross-row and advisory checks over the whole batch.")
        for r in rows:
            spec = payload.get(r.get("cand_id"))
            if spec and spec.get("answer_letter") and r.get("answer") != spec["answer_letter"]:
                blocking.append(f"{r['cand_id']}: answer={r.get('answer')} but the payload "
                                f"assigned {spec['answer_letter']}")

    # --- BLOCKING: the same option text in TWO DIFFERENT rows -----------------
    # This is the m0048 check. Short options collide innocently ("Brainstorming"),
    # so only substantial option text counts.
    by_text = defaultdict(set)
    for r in rows:
        opts = r.get("options")
        if not isinstance(opts, dict):
            continue
        for k in OPTION_KEYS:
            n = norm(str(opts.get(k, "")))
            if len(n) >= 18:
                by_text[n].add((r.get("cand_id"), r.get("_file"), k))
    for text, locs in sorted(by_text.items()):
        rows_hit = {cid for cid, _, _ in locs}
        if len(rows_hit) > 1:
            where = "; ".join(f"{cid} opt {k} ({f})" for cid, f, k in sorted(locs))
            blocking.append(f"CROSS-ROW duplicate option text in {len(rows_hit)} rows — {where}\n"
                            f"      {text[:88]!r}")

    # NO SUPERSET CHECK HERE, DELIBERATELY -- see the module docstring. Both the
    # naive form and the figure-stripped form were built and MEASURED against
    # §10-12's 152 shipped rows; the figure-stripped form fired on 45 of them
    # (30%) and every hit was a trailing qualifier, not a superset. See
    # slice-tools/fixtures_batch_invariants.py, which pins that decision.

    # --- ADVISORY: rule 13b, a key figure also printed in the stem ------------
    for r in rows:
        opts = r.get("options")
        if not isinstance(opts, dict) or r.get("answer") not in OPTION_KEYS:
            continue
        shared = {f for f in figures(str(opts[r["answer"]])) & figures(r.get("question", ""))
                  if len(f.replace(".", "")) >= 2}
        if shared:
            advisory.append(f"13b  {r['cand_id']} key shares {sorted(shared)} with its stem "
                            f"(JUDGE: a policy period or a count is a false positive; a keyed "
                            f"VALUE is not)\n      key {r['answer']}: {opts[r['answer']]!r}")

    # --- ADVISORY: the key is the decimal odd-one-out --------------------------
    # §10-12: a blind solver picked $62.50 out of $40/$50/$60 on sight, and said
    # it would trust the cue. Deterministic, so it is checkable rather than a vibe.
    for r in rows:
        opts = r.get("options")
        if not isinstance(opts, dict) or r.get("answer") not in OPTION_KEYS:
            continue
        has = {k: bool(DECIMAL.search(str(opts[k]))) for k in OPTION_KEYS}
        n_dec = sum(has.values())
        if n_dec in (1, 3):
            minority = [k for k, v in has.items() if v == (n_dec == 1)]
            if minority == [r["answer"]]:
                advisory.append(
                    f"DECIMAL-ODD  {r['cand_id']} key {r['answer']} is the only option "
                    f"{'WITH' if n_dec == 1 else 'WITHOUT'} a decimal — a free pick unless the "
                    f"other three are reformatted to match")

    # --- ADVISORY: the key is the decimal PRECISION odd-one-out ---------------
    # The gap DECIMAL-ODD leaves: when all four options carry a decimal its split
    # is 4-of-4 and neither branch above fires, but one may still be visibly the
    # "clean" number. §10-14 h0005 keyed 8.0 against 9.88 / 8.78 / 9.13; two blind
    # solvers and one difficulty rater named it independently. Complementary to
    # DECIMAL-ODD by construction -- that one needs n_dec in (1, 3), this one
    # requires all four -- so no row is reported twice.
    for r in rows:
        opts = r.get("options")
        if not isinstance(opts, dict) or r.get("answer") not in OPTION_KEYS:
            continue
        places = {k: decimal_places(opts[k]) for k in OPTION_KEYS}
        if any(v is None for v in places.values()):
            continue
        lo = min(places.values())
        cleanest = [k for k in OPTION_KEYS if places[k] == lo]
        if len(cleanest) == 1 and cleanest[0] == r["answer"]:
            advisory.append(
                f"DECIMAL-PRECISION  {r['cand_id']} key {r['answer']} is the only option "
                f"rounder than the rest ({lo} significant decimal place(s) against "
                f"{sorted(v for k, v in places.items() if k != r['answer'])}) — bank baseline "
                f"33.9% of such rows are keyed, against a 25% floor (p=0.07, suggestive not "
                f"significant): READ the row, do not repair to the rate\n"
                f"      key {r['answer']}: {opts[r['answer']]!r}")

    # --- ADVISORY: an indefinite article immediately before a numeral ---------
    # A CONSTRUCTION rule, not a rate (issue #174 -- see the module docstring for
    # why the tell rate is not measurable and the issue's 34% belongs to
    # label_divergence). "An $80 keystone selling price" agrees with the vowel
    # sound of *eighty*; write "A keystone selling price of $80" and the tell
    # cannot exist whatever the numbers later become. Every carrier row is named,
    # because a number changed in a later repair round re-creates the leak in a
    # row nobody re-reads.
    #
    # REPORTED AS A RATE WITH A ROLL-UP, WITH ONLY THE LIVE ROWS ITEMISED, and
    # that shape is measured rather than tidy: the form is an AUTHOR HABIT, so it
    # clusters. §10-14's H1 carries it on 19 of 21 rows against a 12.2% bank rate
    # over four-quantity rows, and itemising all 19 with their options buries the
    # ONE row where the article is actually live (h0014) under 76 option lines --
    # the same "a flag whoever reads the report learns to skip" calibration the
    # module docstring records for the superset check. The roll-up still names
    # every cand_id, so a repair scope can be built from it (#127: a gate that
    # reports a count and no rows sends the next round hunting).
    art_scope, carriers_by_row = 0, []
    for r in rows:
        opts = r.get("options")
        if not isinstance(opts, dict) or r.get("answer") not in OPTION_KEYS:
            continue
        # The DENOMINATOR is four-quantity rows only -- the shape the bank baseline
        # was measured over. Every row is still CHECKED; a prose row simply has no
        # baseline to be read against, and putting 13,000 of them in the divisor
        # would report every real batch as spotless.
        if all(QUANTITY.search(str(opts[k] or "")) for k in OPTION_KEYS):
            art_scope += 1
        arts = {k: article_before_numeral(opts[k]) for k in OPTION_KEYS}
        carriers = [k for k in OPTION_KEYS if arts[k]]
        if not carriers:
            continue
        live = ""
        if len(carriers) == len(OPTION_KEYS):
            counts = Counter(arts[k] for k in OPTION_KEYS)
            if len(counts) == 2 and min(counts.values()) == 1:
                odd = [k for k in OPTION_KEYS if counts[arts[k]] == 1][0]
                if odd == r["answer"]:
                    live = arts[odd]
        carriers_by_row.append((r, carriers, live))
    if carriers_by_row:
        rate = f"{len(carriers_by_row) / art_scope * 100:.1f}%" if art_scope else "n/a"
        advisory.append(
            f"ARTICLE-NUMERAL  {len(carriers_by_row)} row(s) put an indefinite article straight "
            f"before a number, against {art_scope} four-quantity row(s) — {rate}, bank baseline "
            f"12.2%\n"
            f"      a CONSTRUCTION rule, not a rate: rewrite as 'A <noun label> of $80', never "
            f"'An $80 <noun label>', and the tell cannot exist whatever the numbers become\n"
            f"      rows: " + ", ".join(r["cand_id"] for r, _, _ in carriers_by_row))
    for r, carriers, live in carriers_by_row:
        if not live:
            continue
        advisory.append(
            f"ARTICLE-NUMERAL LIVE  {r['cand_id']} all four options carry the form and only the "
            f"key ({r['answer']}) reads {live!r}, so the article alone names it — no arithmetic "
            f"needed\n"
            + "\n".join(f"      {k}: {r['options'][k]!r}" for k in OPTION_KEYS))

    # NO LONE-NON-ROUND-CENTS CHECK HERE, DELIBERATELY -- issue #174's third tell,
    # measured and declined. 34 bank rows, key on 10 (29.41%, p=0.34): at chance.
    # And unlike the two above, the obvious fix is worse than the defect -- the
    # cents are a true consequence of the correct chain, so removing them means
    # renumbering the stem and risking a real arithmetic error. Documented as a
    # limitation of chain-computation items. Pinned as a NEGATIVE assertion in
    # slice-tools/fixtures_format_tells.py.

    # --- ADVISORY: near-duplicate stems across the whole batch ----------------
    stems = [(r.get("cand_id"), r.get("_file"), norm(r.get("question", ""))) for r in rows]
    for i in range(len(stems)):
        for j in range(i + 1, len(stems)):
            a, b = stems[i][2], stems[j][2]
            if not a or not b:
                continue
            if abs(len(a) - len(b)) > max(len(a), len(b)) * 0.35:
                continue
            ratio = SequenceMatcher(None, a, b).ratio()
            if ratio >= stem_ratio:
                advisory.append(f"NEAR-DUP STEM  {ratio:.3f}  {stems[i][0]} ({stems[i][1]}) "
                                f"<-> {stems[j][0]} ({stems[j][1]})")

    return blocking, advisory


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Deterministic batch invariants — the between-row checks no model needs.")
    ap.add_argument("--part", nargs="+", required=True,
                    help="authored part file(s); globs are expanded (quote them)")
    ap.add_argument("--payload", help="optional payload, to check answer letters against assignment")
    ap.add_argument("--stem-ratio", type=float, default=0.82,
                    help="near-duplicate stem threshold (default 0.82)")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on ADVISORY findings too")
    args = ap.parse_args()

    rows = load_parts(args.part)
    if not rows:
        print("  no rows matched --part; check the glob is quoted", file=sys.stderr)
        raise SystemExit(2)

    payload = {}
    if args.payload:
        with open(args.payload, encoding="utf-8") as fh:
            payload = {r["cand_id"]: r for r in json.load(fh)}

    blocking, advisory = check(rows, payload, args.stem_ratio, args.part[0])

    print(f"\n  rows              {len(rows)}")
    print(f"  payload           {'yes — answer letters checked' if payload else 'not supplied'}")
    print(f"  BLOCKING          {len(blocking)}")
    print(f"  advisory          {len(advisory)}")

    if blocking:
        print("\n  BLOCKING — an identity error, not a judgement call:")
        for line in blocking:
            print(f"    {line}")
    if advisory:
        print("\n  ADVISORY — read these, do not action them blind:")
        for line in advisory:
            print(f"    {line}")

    print("\n  CANNOT SEE: whether an option is semantically wrong, whether a distractor is "
          "plausible,\n              or whether the arithmetic is right. Those need the model "
          "instruments.\n              0 BLOCKING does not mean the batch is good.")

    if blocking or (args.strict and advisory):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
