"""Per-PI depth deficit: the work order that drives plan-10 authoring.

Plan 10 (`plans/10-per-pi-review-depth-plan.md`) fills every (cluster, PI) up to a
tiered floor with a balanced easy/medium/hard spread, so a "Practice this PI" drill
on the mastery heatmap has a fresh, difficulty-balanced pool instead of running dry
after one question. This script is the deterministic driver of that campaign: it
reads the committed bank and emits, per (cluster, PI, level), how many questions of
each tier are still MISSING. No model is called here.

WHY THIS FILE EXISTS. Plan §3 specified `pi_deficit.py` and then §10-1 and §10-2
both ran without it -- the per-(PI, tier) counts were computed by a throwaway script
inlined in the session handoff, so the numbers in those work orders cannot be
rebuilt from the tree that produced them. Every re-run reverse-engineered the rule
from the prose. This is that script, checked in, and it reproduces §10-2's published
association deficit exactly (287 PIs · 301 easy / 381 medium / 46 hard = 728), which
is the regression test in `--verify-10-2`.

    python pi_deficit.py finance ICDC                     # the summary tables
    python pi_deficit.py finance ICDC --out DIR/wo.json    # + the work-order JSON
    python pi_deficit.py finance --all-levels              # whole-cluster picture
    python pi_deficit.py finance ICDC --base HEAD          # against a git ref
    python pi_deficit.py finance ICDC --expect-zero        # the DONE CHECK (exit 1 if work remains)
    python pi_deficit.py --verify-10-2                     # regression-test the rule

THE DONE CHECK. Re-running this after a slice lands is how plan §6 defines "done":
the slice is complete when its deficit reads all-zero. `--expect-zero` turns that
into an exit code so it can gate a script.

THE ADEQUACY RULE (plan §1) -- a per-tier target per PI, not a raw total:

    PI type                          floor   combined E / M / H
    computational, core area          10          4 / 3 / 3
    computational, extra area          6          2 / 2 / 2
    concept, core area                10          5 / 5 / 0
    concept, extra area                6          3 / 3 / 0

  core    -- the instructional area is in clusters.json `core` (on every exam, so
             review traffic concentrates there -> deeper floor).
  comput. -- area is financial_analysis OR the PI already carries >=1 hard item
             anywhere in the cluster (a proxy for "supports a genuine chained calc").
  concept PIs get NO forced hard slot: a manufactured hard concept question is
             demoted at referee anyway, so its budget goes to medium. Honest tagging
             over quota.

The floor is per (cluster, PI) across all THREE levels combined; a single level's
target is `round(combined / 3)` (--split even, the default). That is the rule §10-1
and §10-2 closed under and it is self-consistent as a per-level done check: all
three levels at floor/3 => the combined floor is met. Plan §3 floated a
"thinnest-level-first" proportional split instead; it was never used, and switching
now would make the three finance slices incomparable. `--split` is here so that
choice stays visible rather than buried.

Gap-aware: need = max(0, target_tier - have_tier), per tier, per PI. A PI sitting on
6 easy / 0 medium gets medium authored up to target and no more easy.
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

# Same-dir imports: this module lives beside the tools it composes.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_question_bank import BANK_DIR, VALID_LEVELS  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]
CLUSTERS_PATH = BASE_DIR / "data" / "clusters.json"

TIERS = ("easy", "medium", "hard")

# Plan §1's floor table, keyed (is_computational, is_core) -> combined (E, M, H).
#
# VERSIONED, because the finance cluster was authored under `v1` and the remaining
# four run under `v2`. A single mutable table would silently re-open a deficit
# across all 3,528 committed finance questions the moment the floor moved, and it
# would break `--verify-10-2`, which is a regression test on the RULE against
# §10-2's published numbers -- those numbers are a fact about v1 and stay one.
#
# v2 (2026-07-29, plan §7): concept-core medium 5 -> 4. Chosen over the floor-8
# option (4/4) because the per-level target is round(combined / 3), so 5 -> 4 keeps
# easy at 2 per level and drops medium to 1, while 4/4 would round BOTH down to 1
# and halve what a single-level "Practice this PI" drill can draw. Measured effect
# on the four remaining clusters: 9,925 -> 7,779 items to author (-22%, ~5M tokens).
# Nothing computational or hard moves -- never buy tokens out of the hard tier.
FLOORS = {
    "v1": {                      # finance ran under this; do not edit
        (True, True): (4, 3, 3),
        (True, False): (2, 2, 2),
        (False, True): (5, 5, 0),
        (False, False): (3, 3, 0),
    },
    "v2": {                      # pbm, marketing, entrepreneurship, hospitality
        (True, True): (4, 3, 3),
        (True, False): (2, 2, 2),
        (False, True): (5, 4, 0),
        (False, False): (3, 3, 0),
    },
}
DEFAULT_FLOOR = "v2"
COMBINED_TARGETS = FLOORS[DEFAULT_FLOOR]  # back-compat for anything importing it

# FINANCE IS CLOSED UNDER v1 AND MUST BE READ UNDER v1. Its three levels exit 0 on
# the v1 floor (§10-4); re-reading them under v2 would report a phantom SURPLUS, and
# a future reader could mistake that for "finance over-delivered". It did not -- the
# floor moved after it shipped.
CLOSED_UNDER = {"finance": "v1"}

# HOW A PI IS CALLED `computational`, AND WHY THIS IS VERSIONED TOO (§10-5).
#
# The floor keyed (is_computational, is_core) asks a computational PI for 3 hard and
# a concept PI for 0. So this predicate decides the entire hard tier of a slice, and
# it was WRONG in a way that cost §10-5 two full hard batches (86 items, ~1.3M tokens):
#
#   legacy:  is_comp = area is Financial Analysis  OR  the PI already has >=1 hard
#
# Both clauses over-select. The area clause makes "Describe insurance" computational
# because it files under Financial Analysis; the hard_anywhere clause is circular --
# owning one hard item marks a PI computational, which then demands three more.
# §10-5's H1 inherited 43 PIs flagged computational of which the CURATED per-PI pool
# calls exactly ZERO computational, so `build_area.py` routed all 43 to C2 -- and
# plan 07 §6 had already measured C2 on non-computational cells at ~0% yield
# (marketing/district 0/50). Both §10-5 hard runs held 0/43, twice, as predicted.
#
# `build_area.py` has read the curated per-PI pool all along. The two tools simply
# disagreed, and the deficit tool is the one that decides what gets authored. Read
# the same file it does; fall back to the legacy heuristic only where no curated pool
# exists, so a cluster without one behaves exactly as before.
#
# FINANCE KEEPS THE LEGACY PREDICATE. It closed under v1 (§10-4) against these exact
# numbers and `--verify-10-2` regression-tests the rule on its published association
# deficit. Re-classifying a closed cluster would re-open 3,528 committed questions and
# move a number that is now a historical fact. Same reasoning as CLOSED_UNDER above.
LEGACY_COMPUTATIONAL = {"finance"}
PI_POOL_DIR = BASE_DIR / "data" / "pi-pools"


def load_computational_pis(cluster: str) -> Optional[set]:
    """{(slug(area), pi)} the curated pool calls genuinely computational, or None.

    Same file and same key shape as author_hard.load_computational_pis (the ROUTER's
    copy, which build_area imports). If the two ever drift about that shape the
    deficit will ask for hard the router cannot build, which is the §10-5 defect.
    They differ in exactly one deliberate place: this one returns None for finance
    (LEGACY_COMPUTATIONAL) to keep a CLOSED cluster's deficit numbers historical,
    while the router reads the pool for every cluster because routing carries no
    such constraint.
    """
    if cluster in LEGACY_COMPUTATIONAL:
        return None
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

# §10-2's published association deficit -- the regression test for the whole rule.
# A v1 fact: 287 PIs · 301 easy / 381 medium / 46 hard = 728.
EXPECT_10_2 = {"pis": 287, "easy": 301, "medium": 381, "hard": 46, "total": 728}
# The bank state those numbers were computed against: finance-association-pool at
# 230, before §10-2's first (EI) chunk landed. NOT the slice's additive base
# `492693f` -- that ref already carries the EI chunk and reads 609.
EXPECT_10_2_BASE = "5b8a47f"


def slug(text: str) -> str:
    """'Financial-Information Management' -> 'financial_information_management'."""
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def _norm_level(raw: str) -> str:
    level = raw.capitalize() if raw.lower() != "icdc" else "ICDC"
    if level not in VALID_LEVELS:
        raise SystemExit(f"level must be one of {sorted(VALID_LEVELS)}; got '{raw}'")
    return level


def load_cluster_questions(cluster: str, base: Optional[str] = None) -> List[Dict]:
    """Every committed question for one cluster.

    `base` reads the files at a git ref instead of the working tree -- which is how
    a work order stays reproducible after the slice it drove has already landed.
    """
    folder = BANK_DIR / cluster
    if not folder.is_dir():
        raise SystemExit(f"no bank folder for cluster '{cluster}' at {folder}")
    out: List[Dict] = []
    for path in sorted(folder.glob("*.json")):
        if path.name == "manifest.json":
            continue
        if base:
            rel = path.resolve().relative_to(REPO_ROOT).as_posix()
            proc = subprocess.run(["git", "show", f"{base}:{rel}"],
                                  cwd=REPO_ROOT, capture_output=True, text=True)
            if proc.returncode != 0:
                continue  # the file did not exist at that ref -- not an error
            raw = proc.stdout
        else:
            raw = path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path}: {e}")
        if isinstance(data, list):
            out.extend(q for q in data if isinstance(q, dict))
    return out


def _summarize(rows: List[Dict]) -> Dict:
    """Derive every row-dependent work-order counter in one place."""
    totals = Counter()
    for row in rows:
        for tier in TIERS:
            totals[tier] += row[f"need_{tier}"]
        totals["hard_met_by_medium"] += row.get("hard_met_by_medium", 0)
    return {
        "pis_needing_work": len({row["performanceIndicator"] for row in rows}),
        "need_easy": totals["easy"],
        "need_medium": totals["medium"],
        "need_hard": totals["hard"],
        "need_total": sum(totals[tier] for tier in TIERS),
        "hard_met_by_medium": totals["hard_met_by_medium"],
    }


def build_deficit(cluster: str, level: Optional[str], base: Optional[str] = None,
                  split: str = "even", honest_hard: bool = False,
                  floor: Optional[str] = None) -> Dict:
    """The work order: one row per (PI, level) that still owes questions.

    `floor` names a FLOORS ruleset. Default: the cluster's entry in CLOSED_UNDER if
    it has one (finance closed under v1), else DEFAULT_FLOOR. Passing it explicitly
    is how you ask "what would this cluster owe under the other floor?".

    `honest_hard` resolves a contradiction between the plan's two rules. §5 defines
    the slice as done when this reads all-zero, while §4/§5's honest-hard guardrail
    says an authored hard the referee demotes is back-filled with MEDIUM, never
    re-authored as a fake hard. Both cannot hold: every demotion re-opens a hard slot
    that the guardrail forbids filling, so a literal zero is unreachable on any slice
    where the referee does its job -- exactly the slices that went well.

    With this flag a PI's hard shortfall is treated as satisfied when the PI has
    reached its total depth for that level, i.e. the questions exist and the referee
    put them in medium. Reported separately as `hard_met_by_medium` so the honest
    hard count stays visible instead of being quietly rounded up.
    """
    floor = floor or CLOSED_UNDER.get(cluster, DEFAULT_FLOOR)
    if floor not in FLOORS:
        raise SystemExit(f"unknown floor '{floor}'; have {sorted(FLOORS)}")
    targets = FLOORS[floor]

    core = set(json.loads(CLUSTERS_PATH.read_text(encoding="utf-8"))["core"])
    questions = load_cluster_questions(cluster, base)
    if not questions:
        raise SystemExit(f"no questions found for cluster '{cluster}'")

    # A PI can appear under more than one area name across the bank; the area it
    # carries MOST OFTEN is the one that decides core/extra, so a single stray
    # mis-filed item cannot flip a PI's floor.
    area_votes: Dict[str, Counter] = defaultdict(Counter)
    have: Dict[tuple, Counter] = defaultdict(Counter)
    hard_anywhere: Counter = Counter()
    for q in questions:
        pi = q.get("performanceIndicator")
        area = q.get("instructionalArea")
        diff = q.get("difficulty")
        if not pi or not area:
            continue
        area_votes[pi][area] += 1
        if q.get("level") in VALID_LEVELS and diff in TIERS:
            have[(pi, q["level"])][diff] += 1
        if diff == "hard":
            hard_anywhere[pi] += 1

    levels = [level] if level else sorted(VALID_LEVELS)
    # Curated per-PI pool where one exists (and the cluster is not closed); else the
    # legacy heuristic, unchanged. See LEGACY_COMPUTATIONAL above for why this is
    # versioned rather than simply corrected everywhere.
    computational = load_computational_pis(cluster)
    comp_source = "curated pool" if computational is not None else "legacy heuristic"
    # Counted here, from the SAME predicate the rows are classified by. The report's
    # parenthetical used to recompute the legacy heuristic inline, so on every cluster
    # but finance it described a rule the tool no longer followed (issue #90) -- and
    # that line is the operator's only cross-check on the predicate §10-5 corrected.
    comp_pis: set = set()
    rows: List[Dict] = []
    for pi in sorted(area_votes):
        area = area_votes[pi].most_common(1)[0][0]
        is_core = slug(area) in core
        if computational is not None:
            is_comp = (slug(area), pi) in computational
        else:
            is_comp = slug(area) == "financial_analysis" or hard_anywhere[pi] >= 1
        if is_comp:
            comp_pis.add(pi)
        combined = targets[(is_comp, is_core)]
        for lvl in levels:
            h = have[(pi, lvl)]
            if split == "even":
                target = [round(c / 3) for c in combined]
            else:  # "thinnest" -- plan §3's unused alternative, kept explicit
                target = _thinnest_split(combined, [have[(pi, l)] for l in sorted(VALID_LEVELS)],
                                         sorted(VALID_LEVELS).index(lvl))
            need = [max(0, target[i] - h[t]) for i, t in enumerate(TIERS)]
            hard_met_by_medium = 0
            if honest_hard and need[2] > 0 and need[0] == 0 and need[1] == 0:
                # Only forgive the hard slot when EVERY other tier is already full and
                # the PI's total depth is there. Forgiving it on depth alone would let
                # a PI sitting on 3 easy / 0 medium claim its hard slot was "met by
                # medium" when no medium exists -- that is a quota dodge, not honesty.
                depth = h["easy"] + h["medium"] + h["hard"]
                if depth >= sum(target):
                    hard_met_by_medium = need[2]
                    need[2] = 0
            if sum(need) == 0 and not hard_met_by_medium:
                continue
            if sum(need) == 0:
                # depth is met; keep the row only so the demotion stays visible
                rows.append({
                    "cluster": cluster, "level": lvl,
                    "instructionalArea": area, "performanceIndicator": pi,
                    "is_core": is_core, "is_computational": is_comp,
                    "need_easy": 0, "need_medium": 0, "need_hard": 0,
                    "need_total": 0, "hard_met_by_medium": hard_met_by_medium,
                })
                continue
            rows.append({
                "cluster": cluster, "level": lvl,
                "instructionalArea": area, "performanceIndicator": pi,
                "is_core": is_core, "is_computational": is_comp,
                "floor_combined": list(combined),
                "have_easy": h["easy"], "have_medium": h["medium"], "have_hard": h["hard"],
                "target_easy": target[0], "target_medium": target[1], "target_hard": target[2],
                "need_easy": need[0], "need_medium": need[1], "need_hard": need[2],
                "need_total": sum(need),
                "hard_met_by_medium": hard_met_by_medium,
            })

    return {
        "meta": {
            "cluster": cluster,
            "level": level or "ALL",
            "base": base or "working tree",
            "split": split,
            "floor": floor,
            "floor_table": {f"comp={c},core={k}": list(v) for (c, k), v in targets.items()},
            "rule": "plan 10 §1 tiered floor; per-level target = round(combined/3)",
            "bank_questions_scanned": len(questions),
            "distinct_pis": len(area_votes),
            "computational_pis": len(comp_pis),
            # Two rules are live in this tool (see LEGACY_COMPUTATIONAL); archive which
            # one ran, so a work order says out loud what its hard tier was sized by.
            "computational_source": comp_source,
            **_summarize(rows),
            "honest_hard": honest_hard,
        },
        "rows": rows,
    }


def _thinnest_split(combined, have_per_level, idx: int) -> List[int]:
    """Plan §3's alternative: give the deficit to whichever level is thinnest.

    Not used by any shipped slice (§10-1/§10-2 both ran `even`). Implemented so
    `--split thinnest` is a real option rather than a documented intention.
    """
    out = []
    for t_i, total in enumerate(combined):
        depths = [h[TIERS[t_i]] for h in have_per_level]
        order = sorted(range(len(depths)), key=lambda i: (depths[i], i))
        share = [total // len(depths)] * len(depths)
        for i in range(total % len(depths)):
            share[order[i]] += 1
        out.append(share[idx])
    return out


def print_report(wo: Dict) -> None:
    m, rows = wo["meta"], wo["rows"]
    print(f"\n{m['cluster']}/{m['level']}  ({m['base']}, split={m['split']}, "
          f"floor={m['floor']})")
    src = m.get("computational_source", "legacy heuristic")
    print(f"  bank scanned: {m['bank_questions_scanned']} questions · "
          f"{m['distinct_pis']} distinct PIs ({m['computational_pis']} computational, "
          f"via {src})")

    if m.get("hard_met_by_medium"):
        print(f"  {m['hard_met_by_medium']} hard slot(s) met by medium after referee "
              f"demotion (honest-hard)")
    if not any(r["need_total"] for r in rows):
        print("\n  DEFICIT IS ZERO — every PI is at its tiered floor.\n")
        return

    per_area: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        a = r["instructionalArea"]
        for t in TIERS:
            per_area[a][t] += r[f"need_{t}"]
        per_area[a]["pis"] += 1
        per_area[a]["core"] = int(r["is_core"])

    print(f"\n  {'instructional area':36}{'PIs':>5}{'E':>6}{'M':>6}{'H':>5}{'total':>7}  core?")
    print("  " + "-" * 72)
    for area, c in sorted(per_area.items(), key=lambda kv: -(kv[1]["easy"] + kv[1]["medium"] + kv[1]["hard"])):
        tot = c["easy"] + c["medium"] + c["hard"]
        print(f"  {area:36}{c['pis']:5}{c['easy']:6}{c['medium']:6}{c['hard']:5}{tot:7}"
              f"  {'core' if c['core'] else 'EXTRA'}")
    print("  " + "-" * 72)
    print(f"  {'TOTAL':36}{m['pis_needing_work']:5}{m['need_easy']:6}"
          f"{m['need_medium']:6}{m['need_hard']:5}{m['need_total']:7}")

    hard_areas = sorted({r["instructionalArea"] for r in rows if r["need_hard"]})
    if hard_areas:
        print(f"\n  hard sits in {len(hard_areas)} area(s) — the only ones needing the "
              f"strong/blind-verify path:")
        for a in hard_areas:
            print(f"    {per_area[a]['hard']:>3}  {a}")
    print()


def verify_10_2() -> int:
    """Regression-test the rule against §10-2's published association deficit."""
    print("verifying the §1 rule against the published §10-2 association deficit...")
    # PINNED ON BOTH AXES, and it was silently broken on one of them.
    #
    # floor="v1"  -- the published numbers are a fact about the floor finance ran
    #                under. The test asserts the RULE still reproduces them, so it
    #                must not move when the floor does (FLOORS above).
    # base=EXPECT_10_2_BASE -- it used to read `base="HEAD"`, which made the test
    #                self-invalidating: it asserts the deficit BEFORE the §10-2 slice,
    #                and HEAD has since grown that very slice. It has been failing
    #                since the association pool was committed (`ffc32d1`), reporting
    #                "the rule no longer reproduces §10-2" when what actually changed
    #                was the bank underneath it. A regression test whose input moves
    #                is not a regression test.
    wo = build_deficit("finance", "Association", base=EXPECT_10_2_BASE, split="even",
                       floor="v1")
    m = wo["meta"]
    got = {"pis": m["pis_needing_work"], "easy": m["need_easy"],
           "medium": m["need_medium"], "hard": m["need_hard"], "total": m["need_total"]}
    ok = got == EXPECT_10_2
    for k in ("pis", "easy", "medium", "hard", "total"):
        flag = "ok " if got[k] == EXPECT_10_2[k] else "MISMATCH"
        print(f"  {k:8} expected {EXPECT_10_2[k]:5}  got {got[k]:5}  {flag}")
    print("\n  PASS — the rule reproduces §10-2 exactly.\n" if ok else
          "\n  FAIL — the rule no longer reproduces §10-2.\n")
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Per-PI depth deficit — the plan-10 work order (no model).")
    ap.add_argument("cluster", nargs="?")
    ap.add_argument("level", nargs="?")
    ap.add_argument("--all-levels", action="store_true",
                    help="every level of the cluster instead of one")
    ap.add_argument("--base", default=None,
                    help="git ref to read the bank at (default: working tree)")
    ap.add_argument("--split", choices=["even", "thinnest"], default="even",
                    help="how a combined floor divides across levels (default even — "
                         "the rule §10-1/§10-2 closed under)")
    ap.add_argument("--areas", default=None,
                    help="comma-separated instructional areas to keep")
    ap.add_argument("--out", default=None, help="write the work-order JSON here")
    ap.add_argument("--honest-hard", action="store_true",
                    help="count a referee-demoted hard slot as satisfied once the PI has "
                         "reached its total depth (the §5 done check needs this)")
    ap.add_argument("--expect-zero", action="store_true",
                    help="THE DONE CHECK: exit 1 if any deficit remains")
    ap.add_argument("--verify-10-2", action="store_true",
                    help="regression-test the rule against §10-2's published numbers")
    ap.add_argument("--floor", choices=sorted(FLOORS), default=None,
                    help="floor ruleset (default: v1 for finance, which closed under it; "
                         "v2 for everything else). Pass explicitly to compare.")
    args = ap.parse_args()

    if args.verify_10_2:
        raise SystemExit(verify_10_2())
    if not args.cluster:
        ap.error("cluster is required (or use --verify-10-2)")
    if not args.level and not args.all_levels:
        ap.error("give a level, or --all-levels")

    level = None if args.all_levels else _norm_level(args.level)
    wo = build_deficit(args.cluster, level, base=args.base, split=args.split,
                       honest_hard=args.honest_hard, floor=args.floor)

    if args.areas:
        keep = {slug(a) for a in args.areas.split(",")}
        wo["rows"] = [r for r in wo["rows"] if slug(r["instructionalArea"]) in keep]
        m = wo["meta"]
        m["areas_filter"] = args.areas
        m.update(_summarize(wo["rows"]))

    print_report(wo)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(wo, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  wrote work order -> {out}  ({len(wo['rows'])} rows)\n")

    if args.expect_zero and wo["meta"]["need_total"] > 0:
        print(f"  DONE CHECK FAILED: {wo['meta']['need_total']} questions still owed.\n")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
