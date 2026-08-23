#!/usr/bin/env python3
"""Plan 03 §6b -- the buffer driver. Fills N future days of the roleplay archive.

D2 is the keystone: days are generated and committed AHEAD of their publish
date, and the site reveals one day at a time. That makes slowness free (a batch
runs unattended), removes the GPU-in-CI problem entirely, and means a missed run
is a non-event while the buffer has depth.

FAILURE POLICY (§6b), per day and threshold-gated:
  passed >= --min-pass  -> WRITE the day, recording the rest in day.json.missing.
                           A visibly missing event is honest.
  passed <  --min-pass  -> write NOTHING for that day and STOP the batch.
                           Losing a third of 28 means the model or the prompt is
                           broken; continuing would write six more bad days into
                           a PERMANENT archive. The buffer absorbs the
                           interruption -- that is what it is for.

There is no referee to gate on (D4). The deterministic gate plus the self-report
cross-check is the whole bar, and what it cannot count ships unverified by
design -- see icdc_gate.py's docstring. Nothing here may claim verified
difficulty.

Usage
  # zero model calls -- resolve axes + PIs and print the plan
  python fill_buffer.py --days 7 --dry-run

  # the real thing (see the wall-clock note on --days)
  OLLAMA_MODEL=qwen2.5:14b-instruct python fill_buffer.py --days 7

  python fill_buffer.py --status          # buffer depth, zero model calls
  python fill_buffer.py --rebuild-index   # regenerate data/novelty/* from the archive
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_roleplay as g  # noqa: E402
import icdc_gate as gate  # noqa: E402
import novelty  # noqa: E402
import parse_roleplay as pr  # noqa: E402
import seed_axes  # noqa: E402

DEFAULT_OUT = pr.DEFAULT_OUT

# §6b's `--min-pass 24` was an ASSUMPTION, not a measurement: 24 of 28 needs an
# 85.7% per-event pass rate, and summary 03 measured 71% with retry (57% pass@1)
# -- a 7-day batch would abort on day 1 every time, having written nothing.
# This default is re-derived from the post-K3-fix slice; see summaries/04 for the
# measured rate it comes from. Raise it once a real batch gives a 28-event rate,
# which is a far less noisy instrument than a 7-event slice.
DEFAULT_MIN_PASS = 22

# EXPLICITLY UNCALIBRATED (§5d). Do NOT reuse 0.4: that was calibrated against
# real District PDFs, whose shared boilerplate set a 0.05-0.22 baseline. Cross-day
# is our output vs. our output with an IDENTICAL system prompt every time, so the
# boilerplate is MORE uniform and the baseline sits HIGHER. Ship 0.5 as a
# placeholder, LOG WITHOUT REJECTING for the first two batches (hence
# --enforce-similarity defaulting off), then set p95 + 0.10.
DEFAULT_SIMILARITY_THRESHOLD = 0.5


# ----------------------------
# Archive inspection (no model calls)
# ----------------------------
def existing_days(out_dir: Path) -> List[Dict]:
    """Every day already on disk, oldest first."""
    days: List[Dict] = []
    for day_file in sorted(out_dir.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/day.json")):
        try:
            day = json.loads(day_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if day.get("date"):
            days.append(day)
    return sorted(days, key=lambda d: d["date"])


def buffer_depth(out_dir: Path, today: date) -> Dict:
    """Days stamped today or later -- the runway the buffer actually has."""
    days = existing_days(out_dir)
    future = [d for d in days if d["date"] >= today.isoformat()]
    return {
        "days_on_disk": len(days),
        "depth": len(future),
        "latest": days[-1]["date"] if days else None,
        "next_unfilled": (
            date.fromisoformat(days[-1]["date"]) + timedelta(days=1) if days else today
        ),
        "roleplays": sum(len(d.get("events", [])) for d in days),
    }


def day_dir(out_dir: Path, day: date) -> Path:
    return out_dir / day.strftime("%Y/%m/%d")


# The criteria the DAY path runs (plan 04 §5). SHORTER than fill_bank's
# BANK_GATE_CHECKS by design -- prompt leak, participant voice and the shelf-wide
# company rule are BANK acceptance criteria and deliberately do not run here, which
# is exactly why this list cannot be a constant inside parse_roleplay.
DAY_GATE_CHECKS: Tuple[str, ...] = (
    "structure",
    "verbatim_pis",
    "skills_verbatim",
    "declared_area_echo",
    "exemplar_originality",
    "pi_quota",
    "axis_membership",
    "icdc_shape",
    "cross_day_novelty",     # similarity + 90-day company reuse; LOGGED unless enforced
    "self_report",           # F2/F5 cross-check -- RECORDED, not gating
)


# ----------------------------
# One event
# ----------------------------
def fill_event(
    code: str,
    day: date,
    *,
    tier: str,
    threshold: float,
    enforce_similarity: bool,
    quiet: bool,
) -> Dict:
    """Generate and score one event-day. Returns the generate_one result + verdict."""
    recent = novelty.recent(code, day)
    result = g.generate_one(code, day, tier=tier, recent=recent, quiet=quiet)

    situation = g._scenario_slice(result["body"], g.situation_header(g.EVENTS[code]))
    reused = novelty.reused_company(code, day, situation)

    extra: List[str] = list(result["structural_issues"])
    # Plan 05 §7 step 3's two deterministic record checks. They run on the DAY path
    # too: both are free, both read the draw this run made rather than the authored
    # prose, and neither can fail unless the selection record itself is wrong. Like
    # the band (D10) they move the day publish bar `--min-pass 22` was derived from,
    # and that derivation is already void -- the batch it came from was cancelled
    # and never run, and the only live consumer of this path is
    # .github/workflows/buffer-check.yml, which calls --status and generates
    # nothing. Anyone reviving daily generation re-measures --min-pass.
    extra += gate.check_pi_quota(
        result["pi_items"], result["declared_area"], g.EVENTS[code]
    )
    extra += seed_axes.check_axis_membership(code, result["axes"])
    if result["cross_day_similarity"] >= threshold:
        extra.append(
            f"cross-day: {result['cross_day_similarity']:.0%} similar to "
            f"{result['cross_day_nearest']} (threshold {threshold:.0%}, "
            f"{'enforced' if enforce_similarity else 'LOGGED ONLY -- uncalibrated'})"
        )
    if reused:
        extra.append(f"cross-day: company name(s) reused within 90 days: {', '.join(reused)}")

    result["extra_issues"] = extra
    result["reused_companies"] = reused
    result["situation"] = situation
    # The gate is the bar. Similarity only joins it once someone has calibrated
    # the threshold against two real batches -- until then it is recorded, and
    # rejecting on a guessed number is precisely the failure §5d warns about.
    result["published"] = bool(
        result["passed"]
        and (not enforce_similarity or result["cross_day_similarity"] < threshold)
        and not (enforce_similarity and reused)
    )
    return result


# ----------------------------
# One day
# ----------------------------
def fill_day(
    day: date,
    codes: Sequence[str],
    *,
    out_dir: Path,
    tier: str,
    min_pass: int,
    threshold: float,
    enforce_similarity: bool,
    force: bool,
    all_codes: Sequence[str],
) -> Optional[Dict]:
    """Generate one day. Returns the written RoleplayDay, or None if it aborted."""
    print(f"\n=== {day.isoformat()} ({len(codes)} event(s)) ===")
    day_path = day_dir(out_dir, day)

    results: List[Dict] = []
    for n, code in enumerate(codes, 1):
        target = day_path / f"{code.lower()}.json"
        if target.is_file() and not force:
            print(f"  [{n}/{len(codes)}] {code:6} skip (on disk; --force to regenerate)")
            continue

        started = time.monotonic()
        try:
            result = fill_event(
                code, day, tier=tier, threshold=threshold,
                enforce_similarity=enforce_similarity, quiet=True,
            )
        except Exception as e:  # noqa: BLE001 -- one bad event must not kill the batch
            print(f"  [{n}/{len(codes)}] {code:6} ERROR {type(e).__name__}: {e}")
            continue

        results.append(result)
        verdict = "PASS" if result["published"] else "FAIL"
        print(
            f"  [{n}/{len(codes)}] {code:6} {verdict}  {time.monotonic() - started:5.0f}s  "
            f"words={result['situation_words']:>4}  ex={result['exemplar_similarity']:.2f}  "
            f"xday={result['cross_day_similarity']:.2f}  p{result['passes']}"
        )
        for issue in result["icdc_issues"] + result["extra_issues"]:
            print(f"          - {issue}")

    passed = [r for r in results if r["published"]]
    print(f"  -> {len(passed)}/{len(results)} passed (threshold: {min_pass} of {len(all_codes)})")

    if len(passed) < min_pass:
        print(
            f"\n  ABORT: {len(passed)} passed, --min-pass is {min_pass}. Writing nothing for "
            f"{day.isoformat()} and stopping the batch (§6b).\n"
            "  Losing this share of the day means the model or the prompt is broken; "
            "continuing would write more bad days into a permanent archive."
        )
        return None

    # Write. parse_roleplay owns the JSON contract -- this module never builds it.
    roleplays = []
    for r in passed:
        roleplay = pr.parse_roleplay(
            r["raw"],
            g.EVENTS[r["event"]],
            date=r["date"],
            pi_items=r["pi_items"],
            declared_area=r["declared_area"],
            tier=tier,
            model=r["model"],
            passes=r["passes"],
            extra_issues=r["extra_issues"],
            checks=DAY_GATE_CHECKS,
        )
        roleplay["meta"]["generator"]["axes"] = r["axes"]
        # The axes DATA this draw resolved against (plan 04 §3.2 step 5).
        roleplay["meta"]["generator"]["axesHash"] = seed_axes.axes_content_hash()
        roleplays.append(roleplay)

    written = pr.write_day(out_dir, day.isoformat(), roleplays, all_codes)

    # Record novelty AFTER the day is written, and per day rather than per batch:
    # §2c requires day N+5 to compare against days generated EARLIER IN THIS SAME
    # BATCH, which are not yet published. The comparison set has to grow during
    # the run, so the ledger is written as each day completes.
    for r in passed:
        novelty.record(
            r["event"],
            novelty.entry_for(
                r["event"], day,
                situation=r["situation"], axes=r["axes"],
                similarity=r["cross_day_similarity"], nearest=r["cross_day_nearest"],
                passed=True,
            ),
        )

    print(f"  wrote {len(written['events'])} roleplay(s), {len(written['missing'])} missing")
    return written


# ----------------------------
# --dry-run
# ----------------------------
def dry_run(days: Sequence[date], codes: Sequence[str], out_dir: Path, force: bool) -> None:
    """Resolve axes + PIs and print the plan. ZERO model calls.

    Days generated earlier in the batch are SIMULATED into the comparison set as
    the loop walks forward. Without that, a dry run shows day 1 correctly and
    then diverges: the real run records each day's axes before the next day
    picks its own (§2c), so day 2 onward would be stepped past values the dry run
    never saw. PI selection is seeded per event-day and is unaffected either way,
    but printing axes the real run will not use makes the whole preview
    untrustworthy at exactly the point someone relies on it.
    """
    import random  # noqa: PLC0415

    print("DRY RUN -- no model calls, nothing written\n")
    simulated: Dict[str, List[Dict]] = {}

    for day in days:
        path = day_dir(out_dir, day)
        print(f"=== {day.isoformat()} ===")
        for code in codes:
            if (path / f"{code.lower()}.json").is_file() and not force:
                print(f"  {code:6} skip (on disk)")
                continue

            # The SAME seeding the real run uses, so this shows the real plan.
            random.seed(f"{code}:{day.isoformat()}")
            cfg = g.EVENTS[code]
            pi_by_area = g.load_pi_by_area(cfg)
            pi_items, declared_area = g.select_event_pis(pi_by_area, cfg)

            recent = [*novelty.recent(code, day), *simulated.get(code, [])]
            axes = seed_axes.pick(code, day, recent=recent)
            simulated.setdefault(code, []).append({"date": day.isoformat(), "axes": axes})

            lo, hi = gate.situation_word_band(cfg)
            print(f"  {code:6} {cfg.get('format', 'series'):10} F7 band {lo}-{hi}  "
                  f"declared: [{declared_area}]")
            print(f"         axes: {axes['industry']} | {axes['company_stage']}")
            print(f"               {axes['business_function']} | {axes['dilemma_archetype']}")
            print(f"               {axes['question_shape']}")
            for it in pi_items:
                print(f"         - ({it['role']:8}) [{it['area']}] {it['pi']}")
        print()


# ----------------------------
# CLI
# ----------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Plan 03 §6b -- fill the roleplay buffer")
    ap.add_argument("--days", type=int, default=7, help="how many future days to fill")
    ap.add_argument("--from", dest="start", help="YYYY-MM-DD; default: first unfilled day")
    ap.add_argument("--events", default="", help="comma-separated codes; default all 28")
    ap.add_argument("--tier", default="icdc")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--referee", default="off",
                    help="off (D4 -- there is no referee); a backend name runs a manual spot-check")
    ap.add_argument("--min-pass", type=int, default=DEFAULT_MIN_PASS,
                    help=f"per-day publish threshold (default {DEFAULT_MIN_PASS})")
    ap.add_argument("--similarity-threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD)
    ap.add_argument("--enforce-similarity", action="store_true",
                    help="reject on cross-day similarity. OFF until the threshold is "
                         "calibrated from two real batches (§5d) -- it is LOGGED by default")
    ap.add_argument("--force", action="store_true", help="regenerate days already on disk")
    ap.add_argument("--dry-run", action="store_true", help="resolve axes + PIs, zero model calls")
    ap.add_argument("--rebuild-index", action="store_true",
                    help="rebuild data/novelty/* from the archive, zero model calls")
    ap.add_argument("--status", action="store_true", help="print buffer depth and exit")
    ap.add_argument("--today", help="YYYY-MM-DD; override 'today' for --status (testing)")
    args = ap.parse_args()

    events = pr.load_events()
    all_codes = pr.event_order(events)
    codes = [c.strip().upper() for c in args.events.split(",") if c.strip()] or all_codes
    unknown = [c for c in codes if c not in events]
    if unknown:
        sys.exit(f"unknown event(s): {', '.join(unknown)}")

    today = date.fromisoformat(args.today) if args.today else date.today()

    if args.status:
        depth = buffer_depth(args.out, today)
        print(f"archive      : {args.out}")
        print(f"days on disk : {depth['days_on_disk']}  ({depth['roleplays']} roleplays)")
        print(f"latest day   : {depth['latest']}")
        print(f"buffer depth : {depth['depth']} day(s) at or after {today.isoformat()}")
        print(f"next unfilled: {depth['next_unfilled'].isoformat()}")
        if depth["depth"] < 3:
            print("\nWARNING: buffer depth is below 3 days -- run a batch (§2d).")
        return

    if args.rebuild_index:
        written = novelty.rebuild(args.out, all_codes)
        total = sum(written.values())
        print(f"rebuilt {len(written)} novelty file(s), {total} entr(y/ies), zero model calls")
        for code in sorted(written):
            print(f"  {code:6} {written[code]}")
        return

    if args.referee != "off":
        print(f"[note] --referee {args.referee}: D4 dropped the model referee. This runs a "
              "MANUAL spot-check only and never gates publication.")

    start = (
        date.fromisoformat(args.start) if args.start
        else buffer_depth(args.out, today)["next_unfilled"]
    )
    days = [start + timedelta(days=i) for i in range(args.days)]

    if args.dry_run:
        dry_run(days, codes, args.out, args.force)
        return

    if args.min_pass > len(codes):
        sys.exit(
            f"--min-pass {args.min_pass} exceeds the {len(codes)} event(s) selected; "
            "every day would abort."
        )

    print(f"model     : {g.OLLAMA_MODEL} (backend: {g.LLM_BACKEND})")
    print(f"days      : {days[0].isoformat()} .. {days[-1].isoformat()}")
    print(f"events    : {len(codes)}")
    print(f"min-pass  : {args.min_pass}")
    print(f"similarity: {args.similarity_threshold} "
          f"({'ENFORCED' if args.enforce_similarity else 'logged only -- uncalibrated'})")

    t0 = time.monotonic()
    written_days: List[Dict] = []
    for day in days:
        result = fill_day(
            day, codes,
            out_dir=args.out, tier=args.tier, min_pass=args.min_pass,
            threshold=args.similarity_threshold,
            enforce_similarity=args.enforce_similarity,
            force=args.force, all_codes=all_codes,
        )
        if result is None:
            break
        written_days.append(result)
        # Re-index after every day, so an interrupted batch still leaves a
        # readable archive rather than one whose index disagrees with its days.
        pr.write_index(args.out, existing_days(args.out))

    elapsed = (time.monotonic() - t0) / 3600
    print(f"\nwrote {len(written_days)} day(s) in {elapsed:.1f} h")
    if len(written_days) < len(days):
        print(f"batch stopped early: {len(days) - len(written_days)} day(s) not attempted")
    depth = buffer_depth(args.out, today)
    print(f"buffer depth now: {depth['depth']} day(s)")


if __name__ == "__main__":
    main()
