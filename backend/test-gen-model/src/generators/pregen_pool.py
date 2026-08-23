"""Background pre-generation of a FRESH question pool (plan 07-8 §3b).

The serving path is bank-first and never blocks on a model (§3a); this job is the
other half — it slowly enriches a *separate* pool of freshly-generated, tell-checked
questions that on-demand live serving can hand out instantly instead of paying the
~15-135s Ollama round-trip. It is deliberately NOT latency-sensitive: run it
overnight / continuously.

Model: **local Ollama only** (the hosted cascade was dropped — every free tier
exhausted its budget in one sitting; see plan §0 UPDATE). Each question goes through
generate_one, which applies length-tell rejection sampling (§5), so what lands in the
pool is already within the tell gate. Nothing here is ever promoted into the committed
bank — these stay `verified: false` in output/fresh-pool/.

Usage:
    source venv/bin/activate
    python backend/test-gen-model/src/generators/pregen_pool.py \
        --cluster marketing --level District --count 40

    # audit the tell on what it wrote:
    python backend/test-gen-model/src/generators/audit_tells.py \
        --path backend/test-gen-model/output/fresh-pool/marketing-district.json

Options:
    --cluster   DECA cluster key (required)
    --level     District | Association | ICDC   (default District)
    --count     how many questions to generate   (default 25)
    --mix       easy,medium,hard integer weights (default 25,50,25 = Balanced)
    --out       output path (default output/fresh-pool/<cluster>-<level>.json)
    --append    merge into an existing pool file instead of overwriting
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

# generate_test / audit_tells are siblings in this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_test as gen  # noqa: E402
from audit_tells import _measure  # noqa: E402

POOL_DIR = gen.OUTPUT_DIR / "fresh-pool"


def _difficulty_sequence(count: int, weights: Dict[str, int]) -> List[str]:
    """A length-`count` list of difficulties matching the weight split.

    Largest-remainder allocation, then interleaved (not blocked) so an interrupted
    run still leaves a representative mix rather than all-easy-then-hard."""
    total = sum(weights.values()) or 1
    exact = {d: count * w / total for d, w in weights.items()}
    alloc = {d: int(v) for d, v in exact.items()}
    leftover = count - sum(alloc.values())
    for d in sorted(exact, key=lambda k: exact[k] - alloc[k], reverse=True)[:leftover]:
        alloc[d] += 1
    # Interleave round-robin across the tiers that still owe questions.
    seq: List[str] = []
    remaining = dict(alloc)
    for d in gen.DIFFICULTY_TIERS:  # seed order easy, medium, hard
        remaining.setdefault(d, 0)
    while len(seq) < count:
        for d in gen.DIFFICULTY_TIERS:
            if remaining[d] > 0:
                seq.append(d)
                remaining[d] -= 1
                if len(seq) >= count:
                    break
    return seq


def pregenerate(
    cluster: str, level: str, count: int, weights: Dict[str, int]
) -> List[Dict]:
    """Generate `count` fresh questions for a cluster×level, spread by difficulty.

    Areas are left to generate_one's PI-weighted pick (area=None); we accumulate
    served performance indicators into exclude_pis so the pool doesn't repeat a PI
    until the cluster's supply is exhausted."""
    if cluster not in gen.CLUSTERS:
        raise SystemExit(f"unknown cluster '{cluster}' (choose from {list(gen.CLUSTERS)})")
    if level not in gen.DIFFICULTY_LEVELS:
        raise SystemExit(f"level must be one of {gen.DIFFICULTY_LEVELS}")

    seq = _difficulty_sequence(count, weights)
    print(
        f"[pregen] {cluster} · {level} · {count} questions "
        f"(mix {weights}) on backend={gen.LLM_BACKEND} model={gen.active_model_name()}"
    )
    print(f"[pregen] reject_retries={gen.TEST_REJECT_RETRIES} "
          f"keep_longest={gen.TEST_REJECT_KEEP_LONGEST}\n")

    out: List[Dict] = []
    excluded: List[str] = []
    longest = 0
    t0 = time.time()
    for i, difficulty in enumerate(seq, start=1):
        t = time.time()
        try:
            q = gen.generate_one(
                cluster, level, difficulty, exclude_pis=tuple(excluded)
            )
        except Exception as e:  # keep going; one bad draw shouldn't sink the run
            print(f"  [{i}/{count}] {difficulty:6} FAILED: {e}")
            continue
        m = _measure(q)
        is_longest = bool(m and m["among_longest"])
        longest += 1 if is_longest else 0
        out.append(q)
        excluded.append(q["performanceIndicator"])
        rate = longest / len(out)
        print(
            f"  [{i}/{count}] {difficulty:6} {time.time() - t:5.1f}s  ans={q['answer']}  "
            f"longest={'Y' if is_longest else 'n'}  running key-is-longest={rate:.0%}"
        )

    dt = time.time() - t0
    kept = len(out)
    print(
        f"\n[pregen] kept {kept}/{count} in {dt:.0f}s "
        f"({dt / max(kept, 1):.1f}s/q); key-is-longest "
        f"{(longest / kept if kept else 0):.1%} (gate ≤35%)"
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Pre-generate a fresh question pool.")
    ap.add_argument("--cluster", required=True)
    ap.add_argument("--level", default="District")
    ap.add_argument("--count", type=int, default=25)
    ap.add_argument("--mix", default="25,50,25",
                    help="easy,medium,hard integer weights (default 25,50,25)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--append", action="store_true",
                    help="merge into the existing pool file (de-duped by id)")
    args = ap.parse_args()

    try:
        e, m, h = (int(x) for x in args.mix.split(","))
    except ValueError:
        raise SystemExit("--mix must be three integers, e.g. 25,50,25")
    weights = {"easy": e, "medium": m, "hard": h}

    out_path = (
        Path(args.out)
        if args.out
        else POOL_DIR / f"{args.cluster}-{args.level.lower()}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fresh = pregenerate(args.cluster, args.level, args.count, weights)

    existing: List[Dict] = []
    if args.append and out_path.is_file():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
    by_id = {q["id"]: q for q in existing}
    for q in fresh:
        by_id[q["id"]] = q
    merged = list(by_id.values())

    out_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"[pregen] wrote {len(merged)} question(s) → {out_path}")
    print("[pregen] these are verified:false and NEVER enter the committed bank.")


if __name__ == "__main__":
    main()
