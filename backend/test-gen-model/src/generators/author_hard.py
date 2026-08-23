"""Build the payload for the `hard`-authoring fan-out (plan 07 §6, lever C).

Companion to generate_test.py (PI selection) and build_question_bank.py (--pool
assembly + structural gate). The *authoring* -- writing four options and a stem
that earn `hard` under the independent tagger -- is done by Sonnet subagents in
an offline fan-out reading src/prompts/authoring.txt. This script is the
deterministic payload builder: it picks the real PIs for a slice, assigns each
item its answer letter / option-length band / key-length rank (rule 10 + rule 12,
the controls §2 proved are the only ones that hold), and stamps the C1/C2 route.
No model is called here.

THE PAYLOAD BUILDER EXISTS BECAUSE IT DID NOT (plan 07 §1.4). §2.1's authoring
gate assigned band+rank+letter ad-hoc, off the committed tree -- a measurement
nobody can rebuild. repair_options.py --build-payload is the analogue for the
REPAIR direction (assign around a frozen key of known length); this is the same
assignment for the AUTHORING direction (no key yet -- the band sets the length,
the rank sets the order, and the agent writes to both). §6 is the first authoring
fan-out in plan 07, so this path had no committed builder until now.

  easy/medium/hard is NOT a quota here (authoring.txt "DO NOT FILL A QUOTA"):
  every item this payload requests is TARGETED at `hard` via a mechanism (C1
  chained computation, or C2 two near-correct options), and the item's tag is
  then made by the independent referee (tag_difficulty.py), never by the author.
  The payload requests a mechanism; it does not manufacture a distribution.

    python author_hard.py marketing district --n 50 --out DIR/payload.json
    python author_hard.py finance icdc --n 20 --seed 606 --out DIR/p.json

Route:
  Derived PER ROW by `hard_route()` from the curated computational PI pool. There
  is no `--route` override and there must not be one again (issue #175): a route
  is a property of the PI, so the place to change one is
  data/pi-pools/<cluster>-computational.json, where the change persists, is
  reviewable, and reaches every tool that reads it.

PI restriction (plan 09 §3.1):
  The default PI selection is allocate_questions across the WHOLE cluster, which
  for a C1 fan-out spreads hard slots onto non-computational areas (Emotional
  Intelligence, HR, Communication Skills) that cannot carry chained computation --
  a C1 item forced onto them reads as contrived arithmetic, worse than an honest
  medium (authoring.txt ROUTE C1). `--pi-file` overrides that with a curated pool
  of genuinely-computational {area, pi} pairs; n picks are seed-sampled from it
  (with repeats when n exceeds the pool, exactly select_pis' semantics -- one PI
  can carry several distinct C1 items). This is also §3.1's "mine genuine
  quantitative PIs" lever for the conceptual clusters.

    python author_hard.py finance district --n 26 \
        --pi-file data/pi-pools/finance-computational.json --out DIR/hard.json
"""
import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

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
from pi_deficit import slug  # noqa: E402

VALID_LEVELS = {"District", "Association", "ICDC"}
OPTION_KEYS = ("A", "B", "C", "D")
RANKS = (1, 2, 3, 4)

# The band §2.1's gate put at chance (25.0% key-is-longest, 100/100 in band).
# A per-item band is permitted by rule 12; a constant one is what was measured.
DEFAULT_BAND = (60, 90)
DEFAULT_SEED = 505  # plan 05 §4's seed -- reproducible or it is not a method.

# =============================================================================
# WHICH HARD ITEMS GET ROUTE C1 (chained computation) vs C2 (near-correct pair).
# The ONE definition -- build_area.py imports it rather than keeping its own.
# =============================================================================
#
# NOT the same question as pi_deficit's `is_computational`, and conflating the two is
# a live trap. That flag is "area is financial_analysis OR the PI holds >=1 hard item
# historically" -- a deliberately loose proxy whose job is SIZING THE FLOOR (give this
# PI 3 hard slots instead of 0). Routing on it hands C1 to any PI that ever carried a
# conceptual hard: it stamped "Describe methods used to protect intellectual property"
# C1, satisfiable only by contriving arithmetic onto an IP-doctrine question. §10-1
# measured what that produces -- the manufactured "hard" items were exactly the ones
# both referees demoted, while genuine C1 numerics (net worth, GDP, TVM, tax, cash
# flow, landed cost, APR) and genuine doctrine items (agency, torts) held.
#
# The right signal is PI-level: data/pi-pools/<cluster>-computational.json, the
# hand-curated {area, pi} pool plan 09 §3.1 mined for exactly this ("a C1 item forced
# onto a non-computational PI reads as contrived arithmetic, worse than an honest
# medium"). It is authoritative wherever it exists, which is now ALL FIVE CLUSTERS.
#
# THERE USED TO BE A CLUSTER ALLOW-LIST IN FRONT OF IT AND IT WAS THE WHOLE BUG (#175).
# `C1_CLUSTERS = {"finance", "pbm"}` short-circuited to C2 BEFORE the pool was ever
# read, and it was written when only those two clusters HAD a curated file. The other
# three grew one and the guard stayed, so on marketing / entrepreneurship / hospitality
# the "assignment" was a constant that no longer described anything. Measured over every
# plan-10 hard payload: 95 of 95 rows on those three clusters are in their cluster's
# curated pool -- the pool says C1 on all of them -- while the allow-list said C2 on all
# of them, and the authors realised C1 (§10-11 all 19, §10-13 all 19, §10-14 20 of 21).
# The derivation the guard was hiding is the one that agrees with the authors.
#
# C1_AREAS is the FALLBACK for a cluster with no curated file. It is deliberately the
# looser of the two: routing slightly too much to C2 is safe (a C2 hard is honest
# discrimination and the referee judges it on merit), while routing a concept PI to
# C1 manufactures the exact item the referee throws away.
C1_AREAS = {
    "financial_analysis",
    "financial_information_management",
    "economics",
    "operations",
}
PI_POOL_DIR = Path(__file__).resolve().parents[2] / "data" / "pi-pools"


def load_computational_pis(cluster: str) -> Optional[set]:
    """{(slug(area), pi)} the curated pool calls genuinely computational, or None.

    Deliberately NOT pi_deficit.load_computational_pis, which returns None for
    finance (LEGACY_COMPUTATIONAL) so a CLOSED cluster's deficit numbers stay
    historical facts. Routing has no such constraint and finance's pool is its
    best route signal, so this one reads the file for every cluster. Same file,
    same key shape; if the two ever drift about the SHAPE, the deficit asks for
    hard the router cannot build, which is the §10-5 defect.
    """
    path = PI_POOL_DIR / f"{cluster}-computational.json"
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = set()
    for item in raw:
        area = item.get("area") or item.get("instructionalArea")
        pi = item.get("pi") or item.get("performanceIndicator")
        if area and pi:
            out.add((slug(area), pi))
    return out or None


def hard_route(cluster: str, area: str, pi: str, computational: Optional[set] = None) -> str:
    """"C1" or "C2" for one hard row, from the curated pool where it exists.

    `computational` is the cluster's pool, hoisted by callers that route a whole
    batch so the file is read once; pass None and it is loaded here.

    NOTHING RENDERS THIS INTO AN AUTHORING PROMPT, and that is deliberate (#175).
    No gate scores `route`, so printing it on a row line would state an assignment
    nothing measures -- the shape that produced four slices of hand-reconciled
    refusals. The brief describes both routes and the author picks per item. This
    field's real consumers are the payload record and build_hard_verify's stage-2
    blind-solver scoping, and both need it to be TRUE, not obeyed.
    """
    if computational is None:
        computational = load_computational_pis(cluster)
    if computational is not None:
        return "C1" if (slug(area), pi) in computational else "C2"
    return "C1" if slug(area) in C1_AREAS else "C2"


def _balanced(values, n: int, seed: int) -> List:
    """n picks from `values`, balanced as evenly as possible, then shuffled so
    the assignment does not track PI order. Same scheme as
    repair_options._assign_ranks -- the letters and ranks are ASSIGNED, not
    chosen by the author (rule 10, rule 12(b))."""
    out = [values[i % len(values)] for i in range(n)]
    random.Random(seed).shuffle(out)
    return out


def _load_pi_pool(pi_file: str) -> List[Dict[str, str]]:
    """A curated {area, pi} pool (plan 09 §3.1). Accepts either the short keys
    (area/pi) or the bank's field names (instructionalArea/performanceIndicator)."""
    raw = json.loads(Path(pi_file).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise SystemExit(f"--pi-file {pi_file} must be a non-empty JSON array")
    pool: List[Dict[str, str]] = []
    for i, item in enumerate(raw):
        area = item.get("area") or item.get("instructionalArea")
        pi = item.get("pi") or item.get("performanceIndicator")
        if not area or not pi:
            raise SystemExit(f"--pi-file entry {i} needs area+pi (or "
                             f"instructionalArea+performanceIndicator)")
        pool.append({"area": area, "pi": pi})
    return pool


def build_payload(cluster: str, level: str, n: int,
                  seed: int, band, pi_file: str = None) -> List[Dict]:
    if cluster not in CLUSTERS:
        raise SystemExit(f"unknown cluster '{cluster}'; one of {sorted(CLUSTERS)}")
    if n <= 0:
        raise SystemExit("--n must be positive")

    random.seed(seed)
    if pi_file:
        # Curated computational pool: seed-sample n, with repeats when n > pool
        # (select_pis' own over-allocation semantics -- a PI carries several C1s).
        pool = _load_pi_pool(pi_file)
        if n <= len(pool):
            picks = random.sample(pool, n)
        else:
            picks = list(pool) + random.choices(pool, k=n - len(pool))
        random.shuffle(picks)
    else:
        pi_by_area = load_pi_by_area(CLUSTERS[cluster])
        if not pi_by_area:
            raise SystemExit(f"no PIs loaded for cluster '{cluster}'")
        # Seeded PI selection -- generate_test's own allocator, exactly as §2.1's
        # gate and every prior probe (plan 05 §4). The level does not change PI
        # selection; it changes the calibration the AUTHOR applies (authoring.txt
        # LEVEL CALIBRATION), carried on the payload for the agent to read.
        counts = allocate_questions(pi_by_area, n)
        picks = select_pis(pi_by_area, counts)  # [{area, pi}], already shuffled

    # Read the curated pool once for the batch, then route each row on its own PI.
    computational = load_computational_pis(cluster)

    # Letters and ranks assigned on independent seed streams so they do not
    # correlate with each other or with area/PI order.
    letters = _balanced(OPTION_KEYS, len(picks), seed + 1)
    ranks = _balanced(RANKS, len(picks), seed + 2)

    prefix = CLUSTER_PREFIX.get(cluster, cluster[:3])
    lvl = level.lower()
    payload: List[Dict] = []
    for i, (pick, letter, rank) in enumerate(zip(picks, letters, ranks), start=1):
        payload.append({
            # A CANDIDATE id, not a bank id: build_question_bank --pool renumbers
            # on assembly. It only has to be unique within this payload so a
            # returned part can be matched back to its assignment.
            "cand_id": f"{prefix}-{lvl}-pool-cand-{i:04d}",
            "cluster": cluster,
            "level": level,
            "instructionalArea": humanize_area(pick["area"]),
            "performanceIndicator": pick["pi"],
            "answer_letter": letter,
            "option_length_band": list(band),
            "key_length_rank": rank,
            "difficulty": "hard",
            "route": hard_route(cluster, pick["area"], pick["pi"], computational),
        })
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build the hard-authoring fan-out payload (plan 07 §6).")
    ap.add_argument("cluster")
    ap.add_argument("level")
    ap.add_argument("--n", type=int, required=True, help="candidates to request")
    # NO --route. It is derived per row from the curated PI pool; see hard_route().
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--band", default="60-90",
                    help="option-length band 'MIN-MAX' (default 60-90)")
    ap.add_argument("--pi-file", default=None,
                    help="curated {area, pi} JSON pool to sample from (plan 09 §3.1); "
                         "overrides the whole-cluster allocator")
    ap.add_argument("--out", required=True, help="write the payload JSON here")
    args = ap.parse_args()

    level = args.level.capitalize() if args.level.lower() != "icdc" else "ICDC"
    if level not in VALID_LEVELS:
        raise SystemExit(f"level must be one of {sorted(VALID_LEVELS)}; got '{args.level}'")
    try:
        lo, hi = (int(x) for x in args.band.split("-"))
    except ValueError:
        raise SystemExit(f"--band must be 'MIN-MAX'; got '{args.band}'")
    if lo >= hi:
        raise SystemExit(f"--band MIN must be < MAX; got {lo}-{hi}")

    payload = build_payload(args.cluster, level, args.n,
                            args.seed, (lo, hi), pi_file=args.pi_file)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    from collections import Counter
    # The route is per row now, so print the DISTRIBUTION -- a batch that reads
    # all-C2 is a claim about its PIs and should be readable as one.
    routes = Counter(p["route"] for p in payload)
    areas = Counter(p["instructionalArea"] for p in payload)
    letters = Counter(p["answer_letter"] for p in payload)
    ranks = Counter(p["key_length_rank"] for p in payload)
    print(f"wrote {len(payload)} {args.cluster}/{level} candidates -> {out}")
    print(f"  routes {dict(sorted(routes.items()))} · band {lo}-{hi} · seed {args.seed}")
    print(f"  letters {dict(sorted(letters.items()))} · ranks {dict(sorted(ranks.items()))}")
    print(f"  areas covered ({len(areas)}):")
    for area, c in areas.most_common():
        print(f"    {c:>3}  {area}")


if __name__ == "__main__":
    main()
