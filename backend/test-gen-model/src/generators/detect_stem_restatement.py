"""Detect stem<->key restatement -- plan 07 §5's lever B detector. 0 agents.

§5's defect: the stem paraphrases the definition the key names, so a student
matches wording and never retrieves the concept. authoring.txt rule 2 bans
restating the PI as the key; this is the subtler sibling -- restating the KEY in
the STEM. §5 specifies the detector as "stem<->key content-word overlap (drop
stopwords, Jaccard over a calibrated threshold)", calibrated against the known-bad
ent-district-pool-0100 and a sample of known-good, and says: if it cannot separate
them, DO NOT PROCEED ON VIBES -- reconsider the lever.

Deterministic, read-only, no model. Nothing here writes to the bank.

WHAT THIS IS ACTUALLY FOR, WHICH IS NOT "FIND THE BAD ITEMS"
------------------------------------------------------------
§5 triggers lever B off a SYMPTOM (`easy` is still 41-54% after lever A) and
assumes a CAUSE (stems restate their keys) that nothing has ever tested. The
inference is unexamined, and there is a named rival: summary 07-slice-gate §9
found fin-icdc-1-0051's option C -- "a risk mainly to the client's phone battery
life" -- which the item's OWN explanation calls "a nonsensical distractor
unrelated to the actual risk". A throwaway distractor makes an item easy with no
stem involvement at all, and that summary explicitly offers those items as the
work list for "lever B OR a future rule-3 pass".

So the decisive output here is ARITHMETIC, not separation: if stem-restatement
touches only a few percent of the bank, lever B CANNOT move `easy` from ~61% to
~40% however well it detects and however well the agents rewrite. That bound
holds even if the detector is mediocre, which is what makes it worth 0 agents.

THREE THINGS IT MUST ANSWER (and one it must not fake)
------------------------------------------------------
  (a) does the lever survive -- can any metric separate known-bad from known-good?
  (b) how big is it -- the flagged count, i.e. the arithmetic bound above
  (c) does it collide with §3 -- lever A freezes what lever B edits and vice
      versa, so A and B must never touch one item in one pass (§5's invariant
      collision). If lever B's population sits OUTSIDE §3's in-scope set, the
      collision does not bind and the two can run in parallel. `--vs-repair-scope`
      computes that intersection mechanically.

n=1 IS THE TRAP, AND §13 NAMES IT: "a detector calibrated on n=1 positive is
overfit, however good the separation looks." That rule was written about the
explanation-similarity detector, which ranked its one known-bad #4 of 167 at a 2%
false-positive rate and was still correctly refused -- because it missed the two
defects that mattered. ent-district-pool-0100 is ONE positive. A threshold tuned
until it fires on that item is not calibration, it is curve-fitting to a single
point, and it will look excellent while measuring nothing.

Hence THE STRATEGY SCORER, which is the metric this file leads with:

    "pick the option sharing the most wording with the stem, else abstain"

scored against 25% chance. It is the direct analogue of audit_tells.py's
pick-longest, and it calibrates against CHANCE rather than against one example --
so it has an interpretable null with no known-bad required at all. It also binds
the quantity a student actually exploits, which is §1.1a's rule: the length work
cost 4 agents to learn that a control must bind the quantity the metric READS.
A student does not compute a Jaccard threshold; they pick the option that sounds
most like the stem.

THE LENGTH CONFOUND -- the reason a raw overlap count is not usable here
------------------------------------------------------------------------
A LONGER option shares more words with the stem by chance alone. The bank's key
is the longest option 63% of the time (audit_tells). So an unnormalized
"max overlap" scorer partly RE-MEASURES THE LENGTH TELL and reports it as a stem
defect -- it would find a huge signal in a bank whose stems are perfect. Every
metric here is therefore length-normalized (Jaccard by union, or coverage by the
option's own token count), never a raw intersection count.

Normalization is an argument, not a proof, so `--arm-check` tests it: plan 07 §4
built two arms of the same 167 finance/ICDC items differing ONLY in `options`,
one pre-length-repair and one post. Same stems, same keys, same answers. A stem
metric MUST NOT move between them. If it does, it is reading length. This is a
real control with n=167, not a hypothesis -- and it is free, because the arms
already exist.

Usage:
    python detect_stem_restatement.py --calibrate
    python detect_stem_restatement.py --per-slice
    python detect_stem_restatement.py --top 25
    python detect_stem_restatement.py --arm-check PRE_DIR POST_DIR
    python detect_stem_restatement.py --vs-repair-scope --threshold 0.5
    python detect_stem_restatement.py --flag OUT.json --threshold 0.5
"""

import argparse
import collections
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parents[2]
from bank_paths import BANK_DIR  # noqa: E402  the ONE bank path (#203)
REPO_ROOT = BASE_DIR.parents[1]

OPTION_KEYS = ("A", "B", "C", "D")
KNOWN_BAD = "ent-district-pool-0100"

# §3's scope is decisive + soft = 2,288 items, which is margin >= 5 per
# audit_tells._band (decisive >= 20, soft >= 5).
#
# NOT repair_options.DEFAULT_MIN_MARGIN, which is 20 -- the DECISIVE BAND ALONE.
# That default builds §3's original 1,113-item scope, the one §3.0 spent 8 agents
# proving MISSES the gate (projects to 47.8%, vs 28.2% for decisive+soft). A §3
# fan-out that runs `--build-payload` without an explicit `--min-margin 5` gets
# the wrong scope silently and lands at ~48%.
REPAIR_MIN_MARGIN = 5
REPAIR_DECISIVE_MARGIN = 20

STOPWORDS = frozenset("""
a an the and or but if then than that this these those there here of in on at to for from
by with without into onto over under about across after before during between among
is are was were be been being am do does did doing done have has had having
it its it's they them their theirs he she his her him hers we us our ours you your yours i me my
which who whom whose what when where why how
not no nor so as such can could should would may might must will shall
each every both all any some most more much many few several other another same
best most likely represents represent represented following example illustrates illustrate
which one two three four first second third also because while whether either neither
company companys business businesses customer customers employee employees manager managers
new use used using make makes made get gets got take takes taken give gives given
""".split())

_WORD = re.compile(r"[a-z0-9]+")


def stem(w: str) -> str:
    """Crude, symmetric suffix stripper. Both sides get the same treatment.

    Not linguistically right and it does not need to be: it only has to map the
    two sides of a comparison onto the same token. `prioritizes` -> `prioritiz`
    and `prioritize` -> `prioritiz` is the case that matters. It will never make
    `likely` meet `probability`, which is precisely the finding this file exists
    to surface rather than paper over.
    """
    for suf in ("ing", "ed", "es", "ly", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    return w


def tokens(text: str) -> set:
    out = set()
    for m in _WORD.finditer(str(text).lower()):
        w = m.group()
        if len(w) < 3 or w in STOPWORDS:
            continue
        s = stem(w)
        if len(s) >= 3 and s not in STOPWORDS:
            out.add(s)
    return out


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def _coverage(target: set, source: set) -> float:
    """Share of `target`'s content words present in `source`. Asymmetric.

    Length-normalized by the TARGET, so a long stem cannot inflate it.
    """
    return len(target & source) / len(target) if target else 0.0


def _idf(corpus: List[set]) -> Dict[str, float]:
    df = collections.Counter(t for doc in corpus for t in doc)
    n = len(corpus)
    return {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}


def _idf_cosine(a: set, b: set, idf: Dict[str, float]) -> float:
    """Cosine over IDF-weighted sets. Rare shared words count for more.

    A shared `risk assessment` should outweigh a shared `company`. Still lexical:
    it cannot see `likely` <-> `probability`, and no amount of IDF will fix that.
    """
    inter = a & b
    if not inter:
        return 0.0
    num = sum(idf.get(t, 1.0) ** 2 for t in inter)
    na = math.sqrt(sum(idf.get(t, 1.0) ** 2 for t in a))
    nb = math.sqrt(sum(idf.get(t, 1.0) ** 2 for t in b))
    return num / (na * nb) if na and nb else 0.0


def _bank_files() -> List[Path]:
    return sorted(p for p in BANK_DIR.glob("*/*.json") if p.name != "manifest.json")


def _load(paths: List[Path]) -> List[Dict]:
    out = []
    for p in paths:
        for q in json.loads(p.read_text(encoding="utf-8")):
            q["_file"] = p.stem
            out.append(q)
    return out


def measure(questions: List[Dict]) -> List[Dict]:
    """Every metric, per item. Length-normalized throughout (see the docstring)."""
    stems = [tokens(q.get("question", "")) for q in questions]
    opts = [{k: tokens(str((q.get("options") or {}).get(k, ""))) for k in OPTION_KEYS}
            for q in questions]
    idf = _idf(stems + [t for o in opts for t in o.values()])

    rows = []
    for q, s, o in zip(questions, stems, opts):
        ans = str(q.get("answer", "")).strip().upper()
        if ans not in OPTION_KEYS or not s or not o.get(ans):
            continue
        key = o[ans]
        distractors = {k: v for k, v in o.items() if k != ans and v}
        if not distractors:
            continue

        # Per-option, length-normalized similarity to the stem.
        sim = {k: _jaccard(s, v) for k, v in o.items() if v}
        cov = {k: _coverage(v, s) for k, v in o.items() if v}
        idfc = {k: _idf_cosine(s, v, idf) for k, v in o.items() if v}

        best_d = max((sim[k] for k in distractors), default=0.0)
        rows.append({
            "id": q.get("id"), "file": q.get("_file"),
            "cluster": q.get("cluster"), "level": q.get("level"),
            # §5's specified metric.
            "jaccard_stem_key": sim[ans],
            # Share of the KEY's words the stem already contains. The shape of
            # "the stem is the answer" -- normalized by the key, not the stem.
            "coverage_key_by_stem": cov[ans],
            "idf_cosine_stem_key": idfc[ans],
            # The analogue of audit_tells' `margin`: does the stem pull toward the
            # key SPECIFICALLY? A stem shares domain vocabulary with all four
            # options; only differential pull is a defect.
            "differential": sim[ans] - best_d,
            "_sim": sim,
            "_ans": ans,
        })
    return rows


def strategy(rows: List[Dict], metric: str = "_sim") -> Dict:
    """"Pick the option sharing the most wording with the stem, else abstain."

    The null is 25%. Ties abstain rather than guess, exactly as audit_tells'
    pick-longest does, so the rate is over items where the strategy FIRES.
    """
    fired = hit = 0
    for r in rows:
        sim = r[metric]
        best = max(sim.values())
        winners = [k for k, v in sim.items() if v == best]
        if len(winners) != 1 or best == 0.0:
            continue  # abstain: no unique signal to exploit
        fired += 1
        hit += winners[0] == r["_ans"]
    return {"fired": fired, "hit": hit, "n": len(rows),
            "rate": hit / fired if fired else 0.0,
            "fire_rate": fired / len(rows) if rows else 0.0}


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _rank_of(rows: List[Dict], qid: str, metric: str) -> Optional[Tuple[int, float]]:
    ordered = sorted(rows, key=lambda r: -r[metric])
    for i, r in enumerate(ordered, start=1):
        if r["id"] == qid:
            return i, r[metric]
    return None


METRICS = ("jaccard_stem_key", "coverage_key_by_stem", "idf_cosine_stem_key", "differential")


def cmd_calibrate(rows: List[Dict]) -> None:
    print(f"\n  CALIBRATION -- n={len(rows)} items\n")
    print(f"  Where does the ONE known-bad ({KNOWN_BAD}) rank on each metric?")
    print(f"  {'metric':<26} {'rank':>12} {'value':>8} {'pctile':>8}")
    for m in METRICS:
        got = _rank_of(rows, KNOWN_BAD, m)
        if not got:
            print(f"  {m:<26} {'NOT FOUND':>12}")
            continue
        rank, val = got
        print(f"  {m:<26} {f'{rank}/{len(rows)}':>12} {val:>8.3f} "
              f"{_pct(1 - rank / len(rows)):>8}")

    print(f"\n  Distribution of each metric across the bank:")
    print(f"  {'metric':<26} {'mean':>8} {'p50':>8} {'p90':>8} {'p99':>8} {'max':>8}")
    for m in METRICS:
        vals = sorted(r[m] for r in rows)
        n = len(vals)
        def q(p): return vals[min(n - 1, int(p * n))]
        print(f"  {m:<26} {sum(vals)/n:>8.3f} {q(.5):>8.3f} {q(.9):>8.3f} "
              f"{q(.99):>8.3f} {vals[-1]:>8.3f}")

    print(f"\n  THE STRATEGY SCORER -- null is 25.0%")
    s = strategy(rows)
    print(f"    'pick the option sharing the most wording with the stem, else abstain'")
    print(f"    fires on {s['fired']}/{s['n']} items ({_pct(s['fire_rate'])}), "
          f"correct {s['hit']}/{s['fired']} = {_pct(s['rate'])}")
    print()


def cmd_top(rows: List[Dict], n: int, metric: str) -> None:
    print(f"\n  TOP {n} by {metric}\n")
    for i, r in enumerate(sorted(rows, key=lambda r: -r[metric])[:n], start=1):
        mark = "  <-- KNOWN BAD" if r["id"] == KNOWN_BAD else ""
        print(f"  {i:>3}. {r[metric]:.3f}  {r['id']:<26} {r['file']}{mark}")
    print()


def cmd_per_slice(rows: List[Dict]) -> None:
    slices: Dict[str, List[Dict]] = collections.defaultdict(list)
    for r in rows:
        slices[f"{r['cluster']}/{r['level']}"].append(r)
    print(f"\n  PER SLICE -- strategy hit rate (null 25.0%)\n")
    print(f"  {'slice':<32} {'n':>5} {'fires':>7} {'hit rate':>9} "
          f"{'mean jac':>9} {'mean diff':>10}")
    for name in sorted(slices, key=lambda k: -strategy(slices[k])["rate"]):
        rs = slices[name]
        s = strategy(rs)
        print(f"  {name:<32} {len(rs):>5} {_pct(s['fire_rate']):>7} "
              f"{_pct(s['rate']):>9} "
              f"{sum(r['jaccard_stem_key'] for r in rs)/len(rs):>9.3f} "
              f"{sum(r['differential'] for r in rs)/len(rs):>10.3f}")
    print()


def cmd_arm_check(pre_dir: Path, post_dir: Path) -> None:
    """The length confound, tested rather than argued.

    Two arms of the same 167 items differing ONLY in `options` (plan 07 §4's
    --at-ref build). Same stems, same keys. A STEM metric must not move. If it
    moves, it is reading option length, and every bank-wide number this file
    prints is partly the length tell wearing a new name.
    """
    def load(d: Path) -> List[Dict]:
        man = json.loads((d / "payload-manifest.json").read_text(encoding="utf-8"))
        qs = []
        for b in man["batches"]:
            qs.extend(json.loads((d / b["batch"]).read_text(encoding="utf-8")))
        for q in qs:
            q["_file"] = "arm"
        return qs

    pre, post = load(pre_dir), load(post_dir)
    if [q["id"] for q in pre] != [q["id"] for q in post]:
        sys.exit("  arms do not carry the same ids in the same order")
    rpre, rpost = measure(pre), measure(post)

    print(f"\n  ARM CHECK -- same {len(rpre)} items, `options` differs, stems identical")
    print(f"  A stem metric MUST NOT move between these arms.\n")
    print(f"  {'metric':<26} {'pre':>8} {'post':>8} {'delta':>9}")
    for m in METRICS:
        a = sum(r[m] for r in rpre) / len(rpre)
        b = sum(r[m] for r in rpost) / len(rpost)
        flag = "  <-- MOVES: reads length" if abs(b - a) > 0.01 else ""
        print(f"  {m:<26} {a:>8.3f} {b:>8.3f} {b-a:>+9.3f}{flag}")

    spre, spost = strategy(rpre), strategy(rpost)
    print(f"\n  strategy hit rate       {_pct(spre['rate']):>8} {_pct(spost['rate']):>8} "
          f"{100*(spost['rate']-spre['rate']):>+8.1f}pp")
    print(f"  strategy fire rate      {_pct(spre['fire_rate']):>8} "
          f"{_pct(spost['fire_rate']):>8} "
          f"{100*(spost['fire_rate']-spre['fire_rate']):>+8.1f}pp")
    print()


def cmd_vs_repair_scope(rows: List[Dict], threshold: float, metric: str) -> None:
    """(c): does lever B's population collide with §3's remaining work?

    §5's invariant collision: lever A may only touch options/explanation, lever B
    only question/explanation. Run on one item in one pass and NEITHER invariant
    proves anything. But that only binds where the populations OVERLAP.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import repair_options

    if repair_options.DEFAULT_MIN_MARGIN != REPAIR_DECISIVE_MARGIN:
        sys.exit(f"  scope drift: repair_options.DEFAULT_MIN_MARGIN is "
                 f"{repair_options.DEFAULT_MIN_MARGIN}, expected "
                 f"{REPAIR_DECISIVE_MARGIN} (the decisive band). §3's scope is "
                 f"margin >= {REPAIR_MIN_MARGIN} and must be passed explicitly.")

    in_scope = set()
    for p in _bank_files():
        for item in repair_options.build_payload(p, REPAIR_MIN_MARGIN,
                                                 repair_options.DEFAULT_SEED):
            in_scope.add(item["id"])

    flagged = {r["id"] for r in rows if r[metric] >= threshold}
    overlap = flagged & in_scope
    print(f"\n  LEVER B vs LEVER A SCOPE -- {metric} >= {threshold}\n")
    print(f"    lever B flagged            {len(flagged):>6}")
    print(f"    lever A (§3) in scope      {len(in_scope):>6}")
    print(f"    OVERLAP (collision)        {len(overlap):>6}  "
          f"({_pct(len(overlap)/len(flagged)) if flagged else 'n/a'} of lever B)")
    print(f"    lever B OUTSIDE §3         {len(flagged - in_scope):>6}  "
          f"<- runnable in parallel with §3")
    print(f"\n    bank total                 {len(rows):>6}")
    print(f"    lever B as a share of bank {_pct(len(flagged)/len(rows)) if rows else 'n/a':>6}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--per-slice", action="store_true")
    ap.add_argument("--top", type=int, metavar="N")
    ap.add_argument("--arm-check", nargs=2, metavar=("PRE_DIR", "POST_DIR"))
    ap.add_argument("--vs-repair-scope", action="store_true")
    ap.add_argument("--flag", metavar="OUT")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--metric", default="coverage_key_by_stem", choices=METRICS)
    args = ap.parse_args()

    if args.arm_check:
        cmd_arm_check(Path(args.arm_check[0]), Path(args.arm_check[1]))
        return

    rows = measure(_load(_bank_files()))
    if not rows:
        sys.exit("  no measurable questions")

    if args.calibrate:
        cmd_calibrate(rows)
    if args.per_slice:
        cmd_per_slice(rows)
    if args.top:
        cmd_top(rows, args.top, args.metric)
    if args.vs_repair_scope:
        cmd_vs_repair_scope(rows, args.threshold, args.metric)
    if args.flag:
        out = [{k: v for k, v in r.items() if not k.startswith("_")}
               for r in rows if r[args.metric] >= args.threshold]
        Path(args.flag).write_text(
            json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\n  flagged {len(out)} item(s) at {args.metric} >= {args.threshold} "
              f"-> {args.flag}\n")
    if not any([args.calibrate, args.per_slice, args.top, args.vs_repair_scope, args.flag]):
        cmd_calibrate(rows)


if __name__ == "__main__":
    main()
