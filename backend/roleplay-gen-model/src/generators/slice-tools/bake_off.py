"""Plan 03 §3f -- the experiment that settles the author backend.

Two arms over the 7-event slice that covers all three format templates:

  arm 1 "base"  -- system.txt as-is. Reproduces summary 02's known-good result, so
                   any new number is comparable to a measured 0.22. If this does not
                   reproduce, something environmental changed and nothing else here
                   is trustworthy.
  arm 2 "icdc"  -- the same events with src/prompts/icdc.txt appended. THIS IS
                   THE REAL TEST. §3e removed the paid author and D4 removed the
                   judge, so if qwen2.5:14b cannot hold the tier's rules the answer is
                   to fix the prompt or change the local model.

                   The arm still measures the ICDC tier, but that tier is no longer
                   ICDC+: the knob set is F1-F8, DECA's own format. Numbers from this
                   arm are NOT comparable to any recorded against gateVersion <= 4.

Acceptance (identical instrument to summary 02):
  validate_roleplay() == [] for all 7  AND  max scenario_similarity < 0.4
  arm 2 additionally: check_icdc_shape() == []

Prompts come from the REAL build_user_message, so they are byte-identical to what
production would send. Fixtures are not mocked or re-typed anywhere.

Measurements are pass@1 by default (--retries 0): the honest read on the model,
uncontaminated by the retry loop that production layers on top. Re-run just the
failures with --retries to see what repair buys.

Usage
  OLLAMA_MODEL=qwen2.5:14b-instruct \\
    venv/bin/python backend/roleplay-gen-model/src/generators/slice-tools/bake_off.py \\
      --arm both --level ICDC
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

import generate_roleplay as g  # noqa: E402
import icdc_gate as gate  # noqa: E402

# §3f: 7 events covering all three templates -- series, principles, team.
SLICE: List[str] = ["HRM", "ACT", "SEM", "PBM", "PFL", "BLTDM", "MTDM"]

OUT_ROOT = g.BASE_DIR / "output" / "bake-off"
ICDC_PATH = g.PROMPTS_DIR / "icdc.txt"


def build_system_prompt(arm: str, event_cfg: Dict) -> str:
    """system.txt for the base arm; + the knob spec for the ICDC arm.

    Both the prompt assembly and the two-pass expansion now live in
    generate_roleplay (§6a) rather than here. The harness delegating to them is
    the point: summary 03's two deviations were only real in this file, and a
    deviation that exists only in a slice tool is a deviation production does
    not have. The slice now measures the production path.
    """
    if arm != "icdc":
        return g.read_text(g.SYSTEM_PROMPT_PATH)
    return g.build_icdc_system_prompt(event_cfg)


expand_situation = g.expand_situation


def score(
    raw: str, event_cfg: Dict, pi_items: List[Dict[str, str]], examples: List[str], arm: str,
    declared_area: str = "",
) -> Dict:
    """Everything measurable about one generation. No model call."""
    body, report = gate.split_self_report(raw)

    sit = g._scenario_slice(body, g.situation_header(event_cfg))
    jpos = g._has_header(body, "JUDGE ROLE-PLAY CHARACTERIZATION")
    judge = body[jpos:] if jpos is not None else ""

    structural = g.validate_roleplay(body, event_cfg, pi_items, examples, declared_area)
    similarity = g.scenario_similarity(body, event_cfg, examples)
    heading, numerics = gate.find_exhibit(body)

    result = {
        "structural_issues": structural,
        "scenario_similarity": round(similarity, 4),
        "situation_words": gate.situation_word_count(sit),
        "judge_questions": len(gate.judge_questions(judge)),
        "exhibit_heading": heading,
        "exhibit_numerics": numerics,
        "self_report_present": report is not None,
        "chars": len(body),
    }

    if arm == "icdc":
        result["icdc_issues"] = gate.check_icdc_shape(
            body, event_cfg, situation_slice=sit, judge_section=judge
        )
        result["self_report_issues"] = gate.check_self_report(body, report)
    else:
        result["icdc_issues"] = []
        result["self_report_issues"] = []

    # The shipping bar, per §6b: structural clean AND (for the ICDC arm) the
    # deterministic gate clean AND originality under threshold.
    result["passes"] = not structural and not result["icdc_issues"]
    return result


def run_one(
    event_key: str, arm: str, level: str, *, use_examples: bool, retries: int, seed_tag: str,
    expand: bool = False,
) -> Dict:
    event_cfg = g.EVENTS[event_key]

    # Deterministic per (event, arm, example-mode) so a re-run reproduces the same
    # PI selection and the same sampled example -- §6a's reproducibility rule,
    # applied to the experiment so its numbers are re-checkable.
    random.seed(f"{event_key}:{arm}:{use_examples}:{seed_tag}")

    pi_by_area = g.load_pi_by_area(event_cfg)
    pi_items, declared_area = g.select_event_pis(pi_by_area, event_cfg)

    # ALWAYS load the exemplars for SCORING; `use_examples` only controls whether they
    # go into the PROMPT. Conflating the two makes the no-exemplar arm report a trivial
    # similarity of 0.0 -- scenario_similarity() short-circuits on an empty example list
    # and validate_roleplay() skips the originality check entirely, so the arm that most
    # needs an originality number is the one that silently stops producing one. This
    # mirrors generate_roleplay's own retry loop, which re-validates originality against
    # the real examples even on an attempt where it withheld them.
    examples = g.load_examples(event_cfg)
    prompt_examples = examples if use_examples else []

    system_prompt = build_system_prompt(arm, event_cfg)
    reminder = ""
    attempts: List[Dict] = []
    best: Optional[Dict] = None
    raw = ""

    for attempt in range(retries + 1):
        user_message = g.build_user_message(
            event_cfg, level, declared_area, pi_items,
            [] if (best and best.get("dropped_examples")) else prompt_examples,
            None, reminder,
        )
        started = time.monotonic()
        try:
            raw = g.call_ollama(system_prompt, user_message, stream=False)
        except requests.RequestException as e:
            return {
                "event": event_key, "arm": arm, "level": level, "examples": use_examples,
                "error": str(e), "passes": False,
            }
        elapsed = time.monotonic() - started

        scored = score(raw, event_cfg, pi_items, examples, arm, declared_area)
        stats = dict(g.LAST_STATS)
        expand_seconds = 0.0

        # Second pass, only when the density floor is what's failing. Everything else
        # (F3/F6/F8, structure, PI verbatim) the single pass already handles.
        # Direction matters since plan 05 D10: the band fails both ways and this
        # pass only lengthens. See icdc_gate.f7_too_short.
        if expand and arm == "icdc" and gate.f7_too_short(scored["icdc_issues"]):
            band = gate.situation_word_band(event_cfg)
            t_exp = time.monotonic()
            try:
                pre_body = gate.split_self_report(raw)[0]
                # No exhibit is passed: F3 bans the block, so there is nothing above
                # the situation for the rewrite to stay consistent with.
                spliced = expand_situation(pre_body, event_cfg, band)
            except requests.RequestException as e:
                print(f"        [warn] expansion call failed: {e}")
                spliced = None
            expand_seconds = time.monotonic() - t_exp

            if spliced:
                # Re-attach the self-report tail so the cross-check still has it.
                tail_at = raw.find(gate.SELF_REPORT_START)
                merged = spliced + ("\n\n" + raw[tail_at:] if tail_at != -1 else "")
                rescored = score(merged, event_cfg, pi_items, examples, arm, declared_area)
                rescored["expanded"] = True
                # Full pre-expansion snapshot, not just the word count. Without this
                # there is no way to tell "the exhibit was never written" from "the
                # expansion pass deleted the exhibit while fixing the word floor" --
                # and those two call for opposite fixes.
                rescored["pre_expand"] = {
                    k: scored[k] for k in
                    ("situation_words", "judge_questions", "exhibit_heading",
                     "exhibit_numerics", "icdc_issues", "scenario_similarity")
                }
                rescored["words_before_expand"] = scored["situation_words"]
                raw, scored = merged, rescored
        scored.update(
            attempt=attempt + 1,
            seconds=round(elapsed + expand_seconds, 1),
            gen_seconds=round(elapsed, 1),
            expand_seconds=round(expand_seconds, 1),
            prompt_chars=len(system_prompt) + len(user_message),
            prompt_tokens=stats.get("prompt_eval_count"),
            output_tokens=stats.get("eval_count"),
            # A prompt at/over num_ctx was silently truncated -- the knob spec is at
            # the START of the system message, so it is the first thing lost.
            ctx_truncated=bool(stats.get("prompt_eval_count", 0) >= g.NUM_CTX),
            raw=raw,
        )
        attempts.append({k: v for k, v in scored.items() if k != "raw"})

        if best is None or (scored["passes"] and not best["passes"]):
            best = scored
        if scored["passes"]:
            break

        if attempt < retries:
            not_original = any("not original" in i for i in scored["structural_issues"])
            bits = []
            if not_original:
                best["dropped_examples"] = True
                bits.append(g.ORIGINALITY_REMINDER)
            if any("not original" not in i for i in scored["structural_issues"]):
                bits.append(g.STRICT_REMINDER)
            if scored["icdc_issues"]:
                bits.append(
                    "DIFFICULTY REMINDER: your previous attempt missed these ICDC-tier rules: "
                    + "; ".join(scored["icdc_issues"])
                    + ". Fix every one of them."
                )
            reminder = "\n\n".join(bits)

    assert best is not None
    out = {
        "event": event_key, "arm": arm, "level": level, "examples": use_examples,
        "format": event_cfg["format"], "pi_count": len(pi_items),
        "attempts": attempts,
        **{k: v for k, v in best.items() if k != "raw"},
    }

    # Archive the generation itself (self-report tail already stripped by score()).
    d = OUT_ROOT / arm / ("with-example" if use_examples else "no-example")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{event_key.lower()}.txt").write_text(best["raw"], encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Plan 03 §3f provider bake-off")
    ap.add_argument("--arm", choices=["base", "icdc", "both"], default="both")
    ap.add_argument("--events", default=",".join(SLICE), help="comma-separated event codes")
    ap.add_argument("--level", default="ICDC", choices=g.DIFFICULTY_LEVELS)
    ap.add_argument("--retries", type=int, default=0, help="0 = pass@1, the honest measure")
    ap.add_argument("--no-examples", action="store_true", help="the §3f example A/B: drop the District exemplar")
    ap.add_argument("--both-example-modes", action="store_true", help="run with AND without the exemplar")
    ap.add_argument("--expand", action="store_true",
                    help="two-pass: re-write the situation longer when F7 fails SHORT (ICDC arm only)")
    ap.add_argument("--tag", default="v1", help="seed tag; change it for a fresh draw")
    ap.add_argument("--out", default=str(OUT_ROOT / "results.json"))
    args = ap.parse_args()

    events = [e.strip().upper() for e in args.events.split(",") if e.strip()]
    unknown = [e for e in events if e not in g.EVENTS]
    if unknown:
        sys.exit(f"unknown event(s): {', '.join(unknown)}")

    arms = ["base", "icdc"] if args.arm == "both" else [args.arm]
    if args.both_example_modes:
        example_modes = [True, False]
    else:
        example_modes = [not args.no_examples]

    print(f"model      : {g.OLLAMA_MODEL}")
    print(f"level      : {args.level}")
    print(f"arms       : {', '.join(arms)}")
    print(f"events     : {', '.join(events)}")
    print(f"examples   : {example_modes}")
    print(f"retries    : {args.retries} ({'pass@1' if not args.retries else 'with repair'})")
    print(f"temperature: {g.TEMPERATURE}   num_ctx: {g.NUM_CTX}\n")

    results: List[Dict] = []
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = len(arms) * len(events) * len(example_modes)
    n = 0
    t0 = time.monotonic()

    for arm in arms:
        for use_examples in example_modes:
            for event_key in events:
                n += 1
                tag = f"[{n}/{total}] {arm:5} {event_key:6} ex={int(use_examples)}"
                print(f"{tag} generating...", flush=True)
                r = run_one(
                    event_key, arm, args.level,
                    use_examples=use_examples, retries=args.retries, seed_tag=args.tag,
                    expand=args.expand,
                )
                results.append(r)
                out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

                if "error" in r:
                    print(f"{tag} ERROR: {r['error']}")
                    continue
                verdict = "PASS" if r["passes"] else "FAIL"
                print(
                    f"{tag} {verdict}  {r['seconds']}s  sim={r['scenario_similarity']:.2f}  "
                    f"words={r['situation_words']}  q={r['judge_questions']}  "
                    f"exhibit={r['exhibit_numerics']}n"
                )
                for i in r["structural_issues"] + r["icdc_issues"] + r["self_report_issues"]:
                    print(f"        - {i}")

    print(f"\nwall clock: {(time.monotonic() - t0) / 60:.1f} min")
    print(f"results   : {out_path}")
    summarize(results)


def summarize(results: List[Dict]) -> None:
    print("\n" + "=" * 78)
    for arm in ("base", "icdc"):
        rows = [r for r in results if r.get("arm") == arm and "error" not in r]
        if not rows:
            continue
        # Every row now carries a real similarity number, exemplar-in-prompt or not.
        sims = [r["scenario_similarity"] for r in rows]
        struct_ok = sum(1 for r in rows if not r["structural_issues"])
        gate_ok = sum(1 for r in rows if not r["icdc_issues"])
        print(f"\narm '{arm}'  ({len(rows)} generations)")
        print(f"  structural clean      : {struct_ok}/{len(rows)}")
        if arm == "icdc":
            print(f"  ICDC gate clean       : {gate_ok}/{len(rows)}")
        if sims:
            print(f"  max similarity        : {max(sims):.2f}   (threshold {g.ORIGINALITY_THRESHOLD})")
        print(f"  median situation words: {sorted(r['situation_words'] for r in rows)[len(rows) // 2]}")
        print(f"  median seconds        : {sorted(r['seconds'] for r in rows)[len(rows) // 2]}")
        accept = struct_ok == len(rows) and (arm != "icdc" or gate_ok == len(rows)) and (
            not sims or max(sims) < g.ORIGINALITY_THRESHOLD
        )
        print(f"  §3f ACCEPTANCE        : {'MET' if accept else 'NOT MET'}")


if __name__ == "__main__":
    main()
