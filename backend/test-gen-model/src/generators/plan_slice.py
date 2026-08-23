#!/usr/bin/env python3
"""Emit a slice's CHUNK PLAN -- the per-area work breakdown. Deterministic, no model.

A "slice" is one (cluster, level). A "chunk" is one authoring agent's batch. Finance
chunked by hand in a session handoff every single time, which is how §10-1 ended up
running against a PI list 75 short of the tool's (plan-10 open issue 1). This builds
the same breakdown from `pi_deficit.py`, so a slice plan can be regenerated instead
of transcribed.

THE CHUNKING RULES, all inherited from the finance pilot:
  * an agent's batch stays inside the proven items-per-agent band (build_prompt.py
    AGENT_MIN/MAX -- 75-95 until a bigger one is measured, see agent_cost.py). The
    CEILING is the binding half: a chunk over AGENT_MAX is one build_prompt.py
    refuses to bless, so a big area splits into ceil(n / AGENT_MAX) pieces at
    minimum. Landing UNDER the floor to keep a chunk area-pure is cheap and safe
    (§4.7: §10-6 chunk 4 ran 69 items at 1.59k/item, chunk 8 ran 52 at 2.13k).
  * a chunk NEVER spans an area for no reason: small areas are packed together and
    large ones split, because `build_prompt.group_rows` already refuses to let a
    Write-group straddle two areas (§10-2's only hard gate failures were area drift)
  * UNPROVEN areas are quarantined into their own chunk(s), ordered FIRST, ONE AREA
    PER CHUNK (see PROVEN_AREAS below). An area no closed slice has ever authored has
    no proven exemplars in this pipeline; mixing it with proven areas means the gate's
    first-pass rate and `LONGEST=` compliance cannot be read against the §10-4
    baselines, because a miss cannot be attributed. §10-8 §3 asks for exactly this
    read before the rest of the slice launches in parallel, and the packing rule
    above would otherwise bury the five new hospitality areas inside mixed chunks.
    The packing rule is ALSO why the probe cohort gets its own packer (issue #92):
    `_pack` bags small areas together, so two unproven areas that fit under the
    ceiling landed in ONE probe chunk with ONE set of gate numbers -- separated from
    the old ground, which is what the quarantine was built for, and not from each
    other, which is what "attributed" means once there is more than one. §10-11
    probed risk_management and channel_management that way and could only enter the
    second in PROVEN_AREAS on evidence that was never specific to it.
  * the HARD rows of the whole slice are pooled into ONE batch, authored last, and
    routed C1/C2 off the curated PI pool. Pooling is what keeps a slice to ONE
    referee pair instead of one per chunk (§10-3: that is why H1 cost 349k, not 5x)

    python plan_slice.py pbm District
    python plan_slice.py pbm District --md      # the markdown table for a plan doc
"""
import argparse
import math
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_deficit import build_deficit, _norm_level, slug  # noqa: E402
from build_prompt import AGENT_MIN, AGENT_MAX  # noqa: E402

TARGET = (AGENT_MIN + AGENT_MAX) // 2  # aim mid-band, not at the ceiling

# Areas a CLOSED plan-10 slice has actually authored, so their gate rates can be read
# against the §10-4 baselines. As of 2026-07-31 that is the 12 shared core areas of
# clusters.json plus financial_information_management -- pbm carries zero `extra_areas`
# (which is why §6 put it first, "the order is by how much of the method transfers")
# but FINANCE carries that one, and finance closed across §10-1..§10-4. Everything else
# is unproven and gets quarantined into its own probe chunk by `chunk()`.
#
# ADD AN AREA HERE WHEN THE SLICE THAT FIRST AUTHORED IT CLOSES -- otherwise §10-11
# (entrepreneurship) re-probes the five areas §10-8 will already have proven, and every
# later slice pays for a quarantine it no longer needs. The unproven set is now EMPTY:
# marketing_information_management went in when §10-14 closed, and it was the last one.
PROVEN_AREAS = {
    "business_law", "communication_skills", "customer_relations", "economics",
    "emotional_intelligence", "financial_analysis", "human_resources_management",
    "information_management", "marketing", "operations", "professional_development",
    "strategic_management",
    "financial_information_management",   # finance's only extra area; closed §10-1..§10-4
    # hospitality's 5 extra areas -- probed as §10-8 chunk 1 (65 items, 63/65 first pass,
    # key-longest 22.2%, LONGEST= 95.2%, all inside the §10-4 baselines) and closed with
    # that slice. §10-11 (entrepreneurship) shares four of them and must not re-probe.
    "product_service_management", "selling", "pricing", "promotion", "market_planning",
    # entrepreneurship's 2 remaining unproven areas -- probed TOGETHER as §10-11 chunk 1
    # (29 items, exit 0 first pass, inside the §10-4 baselines). channel_management is
    # entered here on a District probe alone, which is thinner evidence than the rest of
    # this set: §10-14 (marketing) is where it carries real weight, and it owes only 6
    # District questions across 5 PIs. If its gate rates move there, that is the area to
    # suspect first rather than the slice. TOGETHER is the part `chunk()` no longer
    # allows (issue #92) -- a probe chunk is one area now, so the next entry added here
    # will carry its own gate read and this hedge will not need to be written again.
    "risk_management", "channel_management",
    # marketing's only remaining unproven area -- probed ALONE as §10-14 chunk 1 (27 items,
    # issue #92's one-area probe, closed GO) and closed with that slice. This was the last
    # unproven area in plan 10, so the quarantine path in `chunk()` now has nothing left to
    # quarantine; keep it anyway for the next cluster that adds an extra area.
    "marketing_information_management",
}

# §10-14 discharged channel_management's hedge above on its OWN District evidence: 5/5 on
# `LONGEST=` and 20.0% key-longest, the cleanest of the six areas in its chunk 10. The area
# stays where it is; the caveat no longer applies.


def is_proven(area: str) -> bool:
    return slug(area) in PROVEN_AREAS


def area_rows(wo: Dict) -> List[Dict]:
    """Per-area concept (easy+medium) and hard counts for this slice."""
    by: Dict[str, Dict] = {}
    for r in wo["rows"]:
        a = by.setdefault(r["instructionalArea"],
                          {"area": r["instructionalArea"], "easy": 0, "medium": 0,
                           "hard": 0, "pis": set(), "core": r.get("is_core")})
        a["easy"] += r.get("need_easy", 0)
        a["medium"] += r.get("need_medium", 0)
        a["hard"] += r.get("need_hard", 0)
        if r.get("need_total"):
            a["pis"].add(r["performanceIndicator"])
    for a in by.values():
        a["concept"] = a["easy"] + a["medium"]
        a["pis"] = len(a["pis"])
    return sorted(by.values(), key=lambda a: -a["concept"])


def _split_parts(n: int) -> int:
    """How many agents one area's items become.

    Two constraints, and the CEILING is the one that binds: no part may exceed
    AGENT_MAX, so `ceil(n / AGENT_MAX)` is the floor on part count. Aiming at TARGET
    alone silently emitted over-cap chunks -- `round(110 / 85)` is 1, so hospitality
    /District's 110-item Operations area came out as a single chunk that
    build_prompt.py then flagged as over the band at prompt-build time.
    """
    return max(1, math.ceil(n / AGENT_MAX), round(n / TARGET))


def _pack(areas: List[Dict]) -> List[Dict]:
    """Pack the PROVEN cohort into chunks of ~TARGET concept items.

    Big areas split into near-equal pieces (so no chunk is a 5-item runt); small
    areas accumulate until the batch is full. Both halves keep every chunk inside
    the band and keep area boundaries visible to the author.

    There is deliberately no `probe` flag to pass here: bagging small areas together
    is the whole point on this side and the exact defect on the other (issue #92),
    so the probe cohort has its own packer rather than a parameter on this one.
    """
    chunks: List[Dict] = []
    pending: Dict = {"areas": [], "items": 0, "probe": False}

    def flush():
        nonlocal pending
        if pending["items"]:
            chunks.append(pending)
            pending = {"areas": [], "items": 0, "probe": False}

    for a in areas:
        n = a["concept"]
        if n == 0:
            continue
        if n >= AGENT_MIN:
            flush()
            parts = _split_parts(n)
            base, extra = divmod(n, parts)
            for k in range(parts):
                take = base + (1 if k < extra else 0)
                chunks.append({"areas": [(a["area"], take)], "items": take,
                               "probe": False})
            continue
        if pending["items"] + n > AGENT_MAX:
            flush()
        pending["areas"].append((a["area"], n))
        pending["items"] += n
    flush()
    return chunks


def _pack_probe(areas: List[Dict]) -> List[Dict]:
    """Pack the UNPROVEN cohort: one area per chunk, split only over the ceiling.

    Not `_pack` with a flag (issue #92). A probe exists to be attributed, and the
    decision it feeds is per-area -- PROVEN_AREAS is a set of areas, entered one at a
    time -- so two areas sharing a chunk produce one number for two questions. The
    only splitting left is the ceiling: an unproven area over AGENT_MAX still becomes
    ceil(n / AGENT_MAX) pieces, and those pieces are all the same area, so the read
    is a sum over them rather than an ambiguity.

    The cost is one extra agent per new area, not per new cohort -- ~65k of fixed
    overhead against a PROVEN_AREAS entry that otherwise cannot be defended. Probe
    chunks land under AGENT_MIN and that is sanctioned: §4.7 buys area-purity with
    undersized chunks on the proven side already.
    """
    chunks: List[Dict] = []
    for a in areas:
        n = a["concept"]
        if n == 0:
            continue
        parts = _split_parts(n)
        base, extra = divmod(n, parts)
        for k in range(parts):
            take = base + (1 if k < extra else 0)
            chunks.append({"areas": [(a["area"], take)], "items": take, "probe": True})
    return chunks


def chunk(areas: List[Dict]) -> List[Dict]:
    """Chunk the slice: unproven areas first, in quarantine, then the proven ones.

    An unproven area is never packed alongside a proven one, AND never alongside
    another unproven one. The probe chunk exists to be READ -- gate first-pass rate,
    key-is-longest, `LONGEST=` -- and neither a mixed chunk nor a two-new-area chunk
    can be read, because a miss cannot be attributed to the new ground.
    """
    unproven = [a for a in areas if not is_proven(a["area"])]
    proven = [a for a in areas if is_proven(a["area"])]
    return _pack_probe(unproven) + _pack(proven)


def main() -> None:
    ap = argparse.ArgumentParser(description="Chunk plan for one (cluster, level) slice.")
    ap.add_argument("cluster")
    ap.add_argument("level")
    ap.add_argument("--base", default=None)
    ap.add_argument("--md", action="store_true", help="markdown tables for a plan doc")
    args = ap.parse_args()

    level = _norm_level(args.level)
    wo = build_deficit(args.cluster, level, base=args.base, split="even")
    areas = area_rows(wo)
    chunks = chunk(areas)
    m = wo["meta"]
    hard = m["need_hard"]
    concept = m["need_easy"] + m["need_medium"]

    # Probe chunks are indexed here, not just collected: the read-before-you-launch
    # step is per CHUNK, so the report has to say which chunk carries which area
    # rather than listing the areas and the chunk numbers separately (issue #92).
    probe_idx = [(i, c) for i, c in enumerate(chunks, 1) if c["probe"]]
    probes = [c for _, c in probe_idx]
    new_areas = sorted({a for c in probes for a, _ in c["areas"]})
    probe_lines = [(i, a, n) for i, c in probe_idx for a, n in c["areas"]]

    if args.md:
        print(f"| # | instructional area(s) | items | |")
        print(f"|---|---|--:|---|")
        for i, c in enumerate(chunks, 1):
            names = " + ".join(f"{a} ({n})" for a, n in c["areas"])
            tag = "**PROBE — run first, gate before the rest**" if c["probe"] else ""
            print(f"| {i} | {names} | **{c['items']}** | {tag} |")
        print(f"| H1 | pooled hard, all areas | **{hard}** | author LAST |")
        print(f"| | **total** | **{concept + hard}** | |")
        if new_areas:
            print()
            print(f"Chunk{'s' if len(probes) > 1 else ''} "
                  f"{', '.join(str(i) for i, _ in probe_idx)} "
                  f"quarantine{'' if len(probes) > 1 else 's'} the "
                  f"{len(new_areas)} area(s) no closed slice has authored, "
                  f"**one area per chunk** — each gets its own gate read:")
            print()
            for i, a, n in probe_lines:
                print(f"- chunk {i} — {a} ({n} items)")
            print()
            print(f"Run {'them' if len(probes) > 1 else 'it'} first and read EACH "
                  f"chunk's gate against §10-4's baselines before launching the rest "
                  f"in parallel. A chunk that misses names the area to suspect; "
                  f"`PROVEN_AREAS` is entered one area at a time, so a shared read "
                  f"could not be defended per area.")
        return

    print(f"\n  {args.cluster}/{level}  (floor {m['floor']})")
    print(f"  deficit: {m['need_easy']} easy · {m['need_medium']} medium · {hard} hard "
          f"= {m['need_total']} across {m['pis_needing_work']} PIs")
    print(f"  plan: {len(chunks)} concept chunk(s) + 1 pooled hard batch "
          f"= {len(chunks) + 1} authoring agent(s)\n")
    for i, c in enumerate(chunks, 1):
        names = " + ".join(f"{a} ({n})" for a, n in c["areas"])
        tag = "  <- PROBE, unproven area" if c["probe"] else ""
        print(f"    chunk {i:<2} {c['items']:>4} items   {names}{tag}")
    print(f"    H1     {hard:>4} items   pooled hard, routed C1/C2 — author LAST")
    print(f"\n  {concept} concept + {hard} hard = {concept + hard} items in "
          f"{len(chunks) + 1} agents")
    if new_areas:
        print(f"\n  {len(new_areas)} UNPROVEN area(s), quarantined ONE PER CHUNK:")
        for i, a, n in probe_lines:
            print(f"    chunk {i:<2} {n:>4} items   {a}")
        print(f"  Run these first and read EACH chunk's first-pass rate / "
              f"key-is-longest / LONGEST=")
        print(f"  against §10-4's baselines BEFORE launching the proven chunks in "
              f"parallel.")
        print(f"  One chunk per area is the point: PROVEN_AREAS is entered one area "
              f"at a time,")
        print(f"  so a miss has to name the area that carried it.")
    over = [c for c in chunks if c["items"] > AGENT_MAX]
    if over:
        print(f"\n  WARNING: {len(over)} chunk(s) over the {AGENT_MAX}-item band ceiling")
    # The invariant this tool exists to hold, asserted on its own output rather than
    # only in a docstring -- #76, #88 and #89 were each a guard that was wrong while
    # the comment above it was right.
    impure = [i for i, c in probe_idx if len(c["areas"]) > 1]
    if impure:
        print(f"\n  WARNING: probe chunk(s) {', '.join(map(str, impure))} span more "
              f"than one unproven area — a miss there cannot be attributed (issue #92)")
    print()


if __name__ == "__main__":
    main()
