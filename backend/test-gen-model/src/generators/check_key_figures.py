"""The wrong-key smoke detector: does the explanation's arithmetic reach the keyed option?

WHY THIS EXISTS (§10-11 finding 1). `chunk8/m0064` passed `check_authored.py` at exit 0
with the WRONG ANSWER KEYED. The stem gave 2% on the first $30,000 and 5% beyond, on
$80,000 of sales -> $600 + $2,500 = $3,100. The author put $3,100 at option A and keyed
B ($4,000). Nothing in this pipeline computes anything: `check_authored` measures letter
placement, length band, key-length rank, stem overlap and option wording, so a row can
satisfy every instrument in the suite while simply having the wrong answer.

The defect left ONE cheap mechanical trace. The explanation concluded "*for a total of
$3,100*" while the keyed option read "$4,000 in total commission" -- the explanation's
figures and the keyed option's figures had NOTHING IN COMMON. That is a regex-and-compare
over any row carrying numerals. No model, no arithmetic engine, no per-row cost.

WHAT IT IS NOT. This is a SMOKE DETECTOR, NOT AN ARITHMETIC CHECKER. It does not compute
the stem, so it cannot tell a right answer from a wrong one -- it only asks whether the
explanation and the key are talking about the same number. It is NECESSARY, NOT
SUFFICIENT, in the same sense `label_divergence()` is: a wrong key whose figure the
explanation happens to mention (as a distractor derivation, say) is invisible to it, and
0.0% here NEVER means the arithmetic is right. Run the agent audit too.

CALIBRATION (measured against the committed 12,109-row bank, 2026-08-03, not invented):

    matching rule                              bank fires   verdict
    exact figure match                            1.05%     ALL false positives
    ... +/- 0.5% relative, sign-insensitive       0.63%
    ... +/- 1%   relative, sign-insensitive       0.53%     ADOPTED
    ... +/- 5%   relative, sign-insensitive       0.42%     starts hiding real gaps

Exact matching is unusable: every one of its 12 hits was a rounding or sign artifact --
"About $8,998" against a computed $8,998.13, "33%" against 33.3%, "12.5% decrease"
against a computed -12.5%. Hence the tolerance and the sign-insensitivity.

THE 0.53% RESIDUAL IS THE FLOOR, AND IT IS FALSE POSITIVES, NOT DEFECTS. All five
surviving bank rows are prose keys whose numerals are incidental or spelled out in words
("About 0% real growth"; "the full six percent match"; "approximately 8,000 room-nights"
against an explanation that never repeats the figure). READ THE RATE AGAINST 0.53%, and
read the rows before acting -- this instrument names candidates, not verdicts.

COVERAGE -- what it structurally cannot see, printed on every run:
  * rows where the key or the explanation carries no parseable numeral (the bank's
    scope is 951 of 12,109 rows = 7.9%; the rest are prose and invisible here)
  * numbers written as words ("six percent") -- the residual false positives above
  * a wrong key whose figure appears anywhere in the explanation, including as a
    named distractor derivation. This is the big one, and it is exactly the shape a
    good per-distractor explanation has.

    python check_key_figures.py --part DIR/chunk8-part*.json
    python check_key_figures.py --bank                 # the whole committed bank
    python check_key_figures.py --part DIR/*.json --max-rate 0.05   # exit 1 over the bar
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bank_paths import BANK_DIR  # noqa: E402  the ONE bank path (#203)

# The bank's measured false-positive floor at TOLERANCE, over rows in scope.
BANK_BASELINE = 0.53
TOLERANCE = 0.01

# Deliberately permissive: "$1,234.50", "62%", "8,000", "0.75". A leading minus is NOT
# captured -- comparison is sign-insensitive anyway, and "-" is far more often a dash
# or a range separator than a negation in this corpus.
NUM = re.compile(r"\$?\d[\d,]*\.?\d*%?")


def figures(text: str) -> List[float]:
    """Every parseable numeral in `text`, as absolute values."""
    out: List[float] = []
    for m in NUM.finditer(text or ""):
        raw = m.group(0).replace("$", "").replace(",", "").rstrip("%")
        try:
            out.append(abs(float(raw)))
        except ValueError:
            pass
    return out


def agree(a: float, b: float, tol: float = TOLERANCE) -> bool:
    """Same figure within `tol` RELATIVE -- so rounding and sign do not fire."""
    hi = max(abs(a), abs(b))
    if hi == 0:
        return abs(a - b) < 1e-9
    return abs(a - b) / hi <= tol


def check_row(q: Dict, tol: float = TOLERANCE) -> Optional[Tuple[List[float], List[float]]]:
    """(key figures, explanation figures) when they share none; None if in the clear
    or out of scope."""
    opts = q.get("options")
    if not isinstance(opts, dict):
        return None
    key_text = opts.get(str(q.get("answer", "")).strip().upper())
    kn = figures(str(key_text or ""))
    en = figures(str(q.get("explanation") or ""))
    if not kn or not en:
        return None  # out of scope, not clean -- see COVERAGE
    if any(agree(k, e, tol) for k in kn for e in en):
        return None
    return kn, en


def load(paths: List[str]) -> List[Dict]:
    rows: List[Dict] = []
    for pattern in paths:
        matched = sorted(glob.glob(pattern)) or [pattern]
        for p in matched:
            path = Path(p)
            if not path.is_file():
                raise SystemExit(f"not found: {p}")
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                rows.extend(r for r in data if isinstance(r, dict))
    return rows


def load_bank() -> List[Dict]:
    rows: List[Dict] = []
    for path in sorted(BANK_DIR.glob("*/*.json")):
        if path.name == "manifest.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            rows.extend(r for r in data if isinstance(r, dict))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Flag rows whose explanation shares no figure with the keyed option.")
    ap.add_argument("--part", nargs="+", default=None, help="authored part/pool JSON files")
    ap.add_argument("--bank", action="store_true", help="scan the whole committed bank")
    ap.add_argument("--tolerance", type=float, default=TOLERANCE,
                    help=f"relative match tolerance (default {TOLERANCE})")
    ap.add_argument("--max-rate", type=float, default=None,
                    help="exit 1 if the flagged rate over rows IN SCOPE exceeds this "
                         f"percentage (bank floor is {BANK_BASELINE}%%, all false positives)")
    ap.add_argument("--quiet", action="store_true", help="rates only, no row list")
    args = ap.parse_args()

    if not args.part and not args.bank:
        raise SystemExit("pass --part <files> or --bank")
    rows = load_bank() if args.bank else load(args.part)
    if not rows:
        raise SystemExit("no rows loaded")

    scope, flagged = 0, []
    for q in rows:
        res = check_row(q, args.tolerance)
        opts = q.get("options")
        if isinstance(opts, dict):
            key_text = opts.get(str(q.get("answer", "")).strip().upper())
            if figures(str(key_text or "")) and figures(str(q.get("explanation") or "")):
                scope += 1
        if res:
            flagged.append((q, res))

    rate = 100 * len(flagged) / scope if scope else 0.0
    print(f"\n  rows                {len(rows)}")
    print(f"  IN SCOPE            {scope}  ({100 * scope / len(rows):.1f}% — key AND "
          f"explanation both carry a numeral)")
    print(f"  figure mismatch     {len(flagged)}  ({rate:.2f}% of scope)   "
          f"bank floor {BANK_BASELINE}%  tol +/-{args.tolerance:.1%}")

    if flagged and not args.quiet:
        print("\n  CANDIDATES — read them; this names candidates, not verdicts:")
        for q, (kn, en) in flagged:
            qid = q.get("cand_id") or q.get("id") or "?"
            print(f"\n    {qid}  [{q.get('difficulty')}]  {q.get('instructionalArea')}")
            print(f"      KEY {q.get('answer')}: {str(q.get('options', {}).get(q.get('answer')))[:100]}")
            print(f"      key figures {kn}   explanation figures {en}")

    print("\n  CANNOT SEE: rows whose key or explanation has no numeral "
          f"({len(rows) - scope} here); numbers spelled as words; a wrong key whose "
          "figure\n              appears anywhere in the explanation. "
          "0.00% DOES NOT MEAN THE ARITHMETIC IS RIGHT.\n")

    if args.max_rate is not None and rate > args.max_rate:
        print(f"  FAIL: {rate:.2f}% exceeds --max-rate {args.max_rate}%\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
