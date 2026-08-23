"""Build the payload for the easy/medium pool-authoring fan-out (plan 09 §5).

Sibling to author_hard.py. `author_hard.py` targets `hard` via the C1/C2
mechanisms; this builds the easy or medium payload for the pool-expansion
fan-out: a PI-count-weighted blueprint mirroring
generate_test.allocate_questions + select_pis, with each item assigned an answer
letter, an option-length band, and a key-length rank (rule 10 + rule 12, the two
controls plan 07 §2 proved are the only ones that hold). No route is stamped
(easy/medium are not built by the C1/C2 chained-computation mechanism) and no
model is called here -- the authoring is a Sonnet fan-out reading
src/prompts/authoring.txt.

  easy/medium is NOT a quota (authoring.txt "DO NOT FILL A QUOTA"). The payload
  TARGETS a tier so the fan-out can be sized to plan 09 §2's per-slice mix, but
  the item's committed tag is made by the independent referee (tag_difficulty.py),
  never by the author. A hard-*intent* item that reads medium counts toward medium;
  an easy-intent item the referee calls medium is medium. The payload requests a
  tier; the referee decides what landed.

    python author_pool.py finance district --difficulty easy   --n 61 --out DIR/e.json
    python author_pool.py finance district --difficulty medium --n 29 --seed 506 --out DIR/m.json

The band defaults are tier-appropriate (easy options are short recall terms,
medium options are longer applied phrases) but the KEY LENGTH RANK is the hard
control audit_tells measures; the band is the readability/similarity target.
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

# Same-dir imports: this module lives beside the tools it composes.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_test import (  # noqa: E402
    CLUSTERS,
    allocate_questions,
    humanize_area,
    load_pi_by_area,
    select_pis,
)
from build_question_bank import CLUSTER_PREFIX  # noqa: E402
from author_hard import _balanced, OPTION_KEYS, RANKS  # noqa: E402

VALID_LEVELS = {"District", "Association", "ICDC"}
TIERS = ("easy", "medium")

# Tier-appropriate default bands. easy = short recall terms/definitions; medium =
# applied phrases. A per-item band is permitted by rule 12; a constant per-tier one
# is what keeps the fan-out reproducible. The RANK, not the band, is what audit_tells
# measures -- the band only keeps the four options in one length register.
DEFAULT_BANDS = {"easy": (15, 55), "medium": (35, 85)}
# One seed per (slice, tier) keeps PI draws from colliding across the three tiers of
# the same slice. author_hard defaults to 505 for hard; easy/medium offset from it.
DEFAULT_SEEDS = {"easy": 505, "medium": 506}


def build_payload(cluster: str, level: str, difficulty: str, n: int,
                  seed: int, band) -> List[Dict]:
    if cluster not in CLUSTERS:
        raise SystemExit(f"unknown cluster '{cluster}'; one of {sorted(CLUSTERS)}")
    if difficulty not in TIERS:
        raise SystemExit(f"--difficulty must be one of {sorted(TIERS)} (hard -> author_hard.py)")
    if n <= 0:
        raise SystemExit("--n must be positive")

    pi_by_area = load_pi_by_area(CLUSTERS[cluster])
    if not pi_by_area:
        raise SystemExit(f"no PIs loaded for cluster '{cluster}'")

    # Seeded PI selection -- generate_test's own allocator, exactly as author_hard.
    # The level does not change PI selection; it changes the calibration the AUTHOR
    # applies (authoring.txt LEVEL CALIBRATION), carried on the payload.
    random.seed(seed)
    counts = allocate_questions(pi_by_area, n)
    picks = select_pis(pi_by_area, counts)  # [{area, pi}], already shuffled

    # Letters and ranks on independent seed streams so they do not correlate with
    # each other or with area/PI order (rule 10, rule 12(b)).
    letters = _balanced(OPTION_KEYS, len(picks), seed + 11)
    ranks = _balanced(RANKS, len(picks), seed + 12)

    prefix = CLUSTER_PREFIX.get(cluster, cluster[:3])
    lvl = level.lower()
    payload: List[Dict] = []
    for i, (pick, letter, rank) in enumerate(zip(picks, letters, ranks), start=1):
        payload.append({
            # A CANDIDATE id, not a bank id: build_question_bank --pool renumbers
            # on assembly. Unique within this payload only, so a returned part can
            # be matched back to its assignment.
            "cand_id": f"{prefix}-{lvl}-pool-cand-{difficulty[:1]}{i:04d}",
            "cluster": cluster,
            "level": level,
            "instructionalArea": humanize_area(pick["area"]),
            "performanceIndicator": pick["pi"],
            "answer_letter": letter,
            "option_length_band": list(band),
            "key_length_rank": rank,
            "difficulty": difficulty,
        })
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build the easy/medium pool-authoring fan-out payload (plan 09).")
    ap.add_argument("cluster")
    ap.add_argument("level")
    ap.add_argument("--difficulty", choices=list(TIERS), required=True)
    ap.add_argument("--n", type=int, required=True, help="candidates to request")
    ap.add_argument("--seed", type=int, default=None,
                    help="default 505 (easy) / 506 (medium)")
    ap.add_argument("--band", default=None,
                    help="option-length band 'MIN-MAX' (default per tier)")
    ap.add_argument("--out", required=True, help="write the payload JSON here")
    args = ap.parse_args()

    level = args.level.capitalize() if args.level.lower() != "icdc" else "ICDC"
    if level not in VALID_LEVELS:
        raise SystemExit(f"level must be one of {sorted(VALID_LEVELS)}; got '{args.level}'")

    seed = args.seed if args.seed is not None else DEFAULT_SEEDS[args.difficulty]
    if args.band is None:
        lo, hi = DEFAULT_BANDS[args.difficulty]
    else:
        try:
            lo, hi = (int(x) for x in args.band.split("-"))
        except ValueError:
            raise SystemExit(f"--band must be 'MIN-MAX'; got '{args.band}'")
    if lo >= hi:
        raise SystemExit(f"--band MIN must be < MAX; got {lo}-{hi}")

    payload = build_payload(args.cluster, level, args.difficulty, args.n, seed, (lo, hi))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    areas = Counter(p["instructionalArea"] for p in payload)
    letters = Counter(p["answer_letter"] for p in payload)
    ranks = Counter(p["key_length_rank"] for p in payload)
    print(f"wrote {len(payload)} {args.cluster}/{level} {args.difficulty} candidates -> {out}")
    print(f"  band {lo}-{hi} · seed {seed}")
    print(f"  letters {dict(sorted(letters.items()))} · ranks {dict(sorted(ranks.items()))}")
    print(f"  areas covered ({len(areas)}):")
    for area, c in areas.most_common():
        print(f"    {c:>3}  {area}")


if __name__ == "__main__":
    main()
