"""Measure the dimensions §3's gates do NOT constrain (plan 07 §13).

  1. magnitude  — "pick the conspicuously longest option, else abstain".
                  audit_tells measures ORDER; this measures CONSPICUOUSNESS.
                  It scored 100% on the committed bank at every threshold >30ch.
  2. rule 4     — the key/distractor absolute-qualifier gap, per distractor.
  3. mirror     — key-is-shortest, which the rank control should hold at chance.

Before = the file at a git ref; after = the working tree. Usage:
    python measure_unconstrained.py <ref> <bank-file-path>...
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]  # repo root, derived — was hardcoded to the
                                     # pre-rename "GNS DECA APP" path and silently dead
ABS = re.compile(r"\b(only|never|always|regardless|strictly|immediately)\b", re.I)
OPTS = ["A", "B", "C", "D"]


def at_ref(ref: str, path: Path):
    rel = path.relative_to(REPO)
    out = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=REPO,
                         capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"cannot read {rel} at {ref}: {out.stderr.strip()}")
    return json.loads(out.stdout)


def questions(blob):
    return blob["questions"] if isinstance(blob, dict) else blob


def magnitude(qs, thresh):
    """Fires only when one option is >thresh chars longer than every other.
    Returns (hits, fires) — the student's score when the strategy commits."""
    hits = fires = 0
    for q in qs:
        o = q.get("options") or {}
        if set(o) != set(OPTS):
            continue
        lens = sorted(((len(str(o[k]).strip()), k) for k in OPTS), reverse=True)
        if lens[0][0] - lens[1][0] > thresh:          # a conspicuous outlier
            fires += 1
            if lens[0][1] == str(q.get("answer", "")).strip().upper():
                hits += 1
    return hits, fires


def rule4(qs):
    """Absolute-qualifier rate in keys vs distractors, per option."""
    kh = kn = dh = dn = 0
    for q in qs:
        o = q.get("options") or {}
        ans = str(q.get("answer", "")).strip().upper()
        for k in OPTS:
            if k not in o:
                continue
            hit = bool(ABS.search(str(o[k])))
            if k == ans:
                kn += 1
                kh += hit
            else:
                dn += 1
                dh += hit
    return (100 * kh / kn if kn else 0), (100 * dh / dn if dn else 0)


def mirror(qs):
    short = n = 0
    for q in qs:
        o = q.get("options") or {}
        ans = str(q.get("answer", "")).strip().upper()
        if set(o) != set(OPTS) or ans not in o:
            continue
        n += 1
        lens = {k: len(str(o[k]).strip()) for k in OPTS}
        if lens[ans] == min(lens.values()):
            short += 1
    return 100 * short / n if n else 0


def main():
    ref, paths = sys.argv[1], [Path(p).resolve() for p in sys.argv[2:]]
    before, after = [], []
    for p in paths:
        before += questions(at_ref(ref, p))
        after += questions(json.loads(p.read_text()))

    print(f"  n = {len(before)} questions, before@{ref} vs working tree\n")

    print("  MAGNITUDE — 'pick the conspicuously longest, else abstain'")
    print(f"    {'threshold':<14}{'before':>18}{'after':>18}")
    for t in (20, 30, 40, 60):
        bh, bf = magnitude(before, t)
        ah, af = magnitude(after, t)
        b = f"{bh}/{bf} = {100*bh/bf:.0f}%" if bf else "never fires"
        a = f"{ah}/{af} = {100*ah/af:.0f}%" if af else "never fires"
        print(f"    >{t}ch{'':<9}{b:>18}{a:>18}")

    bk, bd = rule4(before)
    ak, ad = rule4(after)
    print("\n  RULE 4 — absolute qualifiers, per option")
    print(f"    {'':<14}{'keys':>10}{'distractors':>14}{'gap':>10}")
    print(f"    {'before':<14}{bk:>9.1f}%{bd:>13.1f}%{bd-bk:>+9.1f}pp")
    print(f"    {'after':<14}{ak:>9.1f}%{ad:>13.1f}%{ad-ak:>+9.1f}pp")

    print(f"\n  MIRROR — key is shortest (keep <=30%)")
    print(f"    before {mirror(before):.1f}%   after {mirror(after):.1f}%")


if __name__ == "__main__":
    main()
