"""Measure the bank's stem-blind tells: LENGTH (plan 05 §2) and WORDING (issue #188).

Sibling to `verify_bank.py`: deterministic, no model, reads and reports only.

The defect: the correct option is the longest one ~60% of the time in the pools
and ~70% in the sets, against a 25% baseline. A student can score ~70% on a set
without reading a stem. This module is both the measurement and the acceptance
test for plan 05 (§7: bank-wide `key is longest` <= ~35%).

Metrics:
  KEY IS LONGEST  — the headline and the gate. Share of questions where no
                    distractor is longer than the key. Chance is 25%.

                    This counts a TIE for longest as a hit, which is plan 05 §0's
                    definition: it reproduces that table's 60% pools / 70% sets
                    (strictly-longest gives 52%/67%; ties are 7.2% of pools and
                    3.0% of sets). Kept deliberately, because §7's <=35% target is
                    calibrated on this definition and moving the goalposts
                    mid-plan would make the before/after incomparable. `strictly
                    longest` is reported beside it and is the tidier quantity —
                    it is exactly the margin>0 bands below.

  MARGIN BANDS    — key length minus the longest distractor, bucketed:
                    decisive >=20ch / soft 5-19 / noise 1-4 / clean <=0. The
                    decisive band is plan 05 §5a's work list (198 pools + 915
                    sets = 1,113 items). Ties land in `clean`.

  PICK-LONGEST    — what a student actually scores by always picking the longest
                    option, ties broken at random. The number to put in front of
                    a human.

                    Plan 05 §0's table reuses its key-is-longest figure here (60%
                    / 70%), which overstates it: on a two-way tie for longest the
                    strategy wins half the time, not always. This scores a tie at
                    1/n. The honest figures are 55.3% / 68.2% — the conclusion is
                    unchanged (a student passes a set without reading a stem).
  KEY IS SHORTEST — the mirror defect (§7). Optimising the headline invites it;
                    this keeps it visible from the start rather than after.
  LETTER BALANCE  — answer-letter distribution. Currently fine (21-29%); tracked
                    so a remediation pass cannot quietly break it.

THE WORDING SECTION (issue #188) — REPORT ONLY, NEVER A GATE
------------------------------------------------------------
Length is not the only stem-blind tell. Three option CONSTRUCTIONS carry
systematic information about where the key is, and until #188 nothing measured
any of them over the corpus: three plan-10 slices each re-derived the regexes by
hand, measured its own batch, correctly declined to repair it, and each recorded
that the corpus number deserved its own home. This is that home.

  PASSIVE / ABSOLUTE — the key almost never lands on them (0.13x / 0.33x chance).
                    Free elimination: cross both off without reading the stem.
  TRAILING CLAUSE — an option ending in a comma plus three or more words. Runs
                    the OTHER way, at 1.33x. A correct answer is naturally the
                    one that needs a qualifying clause, because it is the one
                    that has to be precisely true.
  STEM-BLIND SCORE — the headline, and the sibling of PICK-LONGEST: what a
                    student scores combining the three without reading a single
                    question. 29.9% against 25.0% guessing on the bank as
                    measured, which is ~5 questions on a 100-question exam.

Four rules, all of them already paid for elsewhere in this repo:

* THE MARKER LISTS ARE FINDING AIDS, NOT SCORES, and this file must never gain a
  `--max-rate` for them. A lexical instrument for this class has been refuted
  three times in adjacent settings (#131's inverted stem pull, §10-14's lexical
  wrong-key detector at a 44.3% fire rate, the §10-16 chunks 5-8 shingle
  detector), and the self-confessing-derivation marker measured 50% precision on
  n=4. Read the RATE to describe the corpus; never hand the rows to a repair
  round.
* THESE ARE NOT AUTHORING MISTAKES. A situational-judgement item SHOULD offer
  "do nothing" — inaction is a real choice a competitor must learn to reject —
  and an overreach distractor is the standard way to test a tool's limits. The
  fix is never to ban the construction; it is that the near-free elimination
  should not be the ONLY obviously-weak option on the row.
* THE DIRECTION DEPENDS ON THE CLAUSE, NOT ON HAVING ONE. `trailing_relative`
  (a comma then which/that/so/because/since) runs at 0.82x — the OPPOSITE way —
  and is printed beside `trailing_clause` for exactly that reason. Anything keyed
  on "options with trailing clauses" would be repairing two populations that
  behave differently, which is #174's split all over again.
* IT IS NOT #185. Measured on the committed bank: of #185's 110 `spread == 1`
  label rows whose lone divergent option is the key, only 18 (16.4%) carry a
  trailing clause on the key — and on label rows as a population the trailing
  clause measures 24.9%, z = -0.1, i.e. DEAD AT CHANCE. The whole of this
  signal lives in the 8,291 non-label options (34.4%, z = +19.7). The two
  issues are disjoint findings and acting on one does not touch the other.
  (Not computed here: it needs `check_authored.label_divergence`, and a bank
  report should not drag the gate module in for one cross-reference.)

Usage:
    python audit_tells.py                       # bank-wide + per-section report
    python audit_tells.py --per-file            # add the per-file table
    python audit_tells.py --max-rate 0.35       # gate: non-zero exit above this
    python audit_tells.py --flag work.json      # emit ids worst-margin-first
    python audit_tells.py --flag work.json --min-margin 20   # decisive band only
    python audit_tells.py --path probe.json     # audit a probe/sample instead
    python audit_tells.py --no-wording          # length only, the pre-#188 report

--flag is an OUTPUT path, --path an INPUT one. They read alike and do not
behave alike; --flag onto a bank file destroys it, so _guard_flag_target
refuses that write.
"""

import argparse
import collections
import glob
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parents[2]
from bank_paths import BANK_DIR  # noqa: E402  the ONE bank path (#203)
REPO_ROOT = BASE_DIR.parents[1]

OPTION_KEYS = ("A", "B", "C", "D")
CHANCE = 0.25

# Plan 05 §7's acceptance test. §9 stops at ~30% rather than chance: forcing 25%
# invites the mirror defect (key conspicuously shortest), and real DECA keys do
# skew slightly longer, so a band beats a point target.
DEFAULT_MAX_RATE = 0.35

# Plan 05 §5a's work list. 20ch over the runner-up is the "decisive" band —
# 13% of pools / 30% of sets, ~1,113 items.
DEFAULT_MIN_MARGIN = 20


def _load(path: Path) -> List[Dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bank_files() -> List[Path]:
    return sorted(p for p in BANK_DIR.glob("*/*.json") if p.name != "manifest.json")


def _resolve_paths(pattern: str) -> List[Path]:
    """Files matching --path: absolute or relative, glob or literal.

    Path().glob() raises on an absolute pattern ("Non-relative patterns are
    unsupported"), which is the natural way to point --path at a probe output
    sitting outside the repo. The stdlib glob module accepts both forms, and
    falls back to the literal path so a non-glob argument still resolves.
    """
    matches = [Path(p) for p in glob.glob(pattern, recursive=True)] or [Path(pattern)]
    return sorted(p for p in matches if p.is_file())


def _label(path: Path) -> str:
    """Bank-relative name for a bank file; the plain path for anything else.

    --path audits probe output (plan 07 §2.1) and live-path samples (§8.1),
    neither of which lives under BANK_DIR — and BANK_DIR is absolute, so a bare
    relative_to() also raises on a relative path to a bank file. Both cases are
    a label problem, not a measurement problem: never let one abort the audit.
    """
    try:
        return str(path.resolve().relative_to(BANK_DIR))
    except ValueError:
        return str(path)


def _section(path: Path) -> str:
    return "pools" if path.name.endswith("-pool.json") else "sets"


def _measure(q: Dict) -> Optional[Dict]:
    """Per-question length facts. None if the question is malformed."""
    opts = q.get("options") or {}
    ans = str(q.get("answer", "")).strip().upper()
    if ans not in OPTION_KEYS or not all(str(opts.get(k, "")).strip() for k in OPTION_KEYS):
        return None

    lengths = {k: len(str(opts[k]).strip()) for k in OPTION_KEYS}
    key_len = lengths[ans]
    others = [lengths[k] for k in OPTION_KEYS if k != ans]

    longest = max(lengths.values())
    n_at_longest = sum(1 for v in lengths.values() if v == longest)

    return {
        "id": q.get("id"),
        "answer": ans,
        "key_len": key_len,
        "runner_up": max(others),
        # Margin vs the longest distractor. >0 means the key is strictly longest.
        "margin": key_len - max(others),
        # Plan 05 §0's "key is longest": no distractor beats it. Ties included.
        "among_longest": key_len >= max(others),
        # Mirror defect: strictly shorter than every distractor.
        "shortest": key_len < min(others),
        "mean_other": sum(others) / len(others),
        # A student who always picks the longest option, breaking ties at random,
        # expects 1/n_at_longest when the key is among the longest. Scoring ties
        # as a full hit would overstate the tell; as a miss, understate it.
        "pick_longest_ev": (1.0 / n_at_longest) if key_len == longest else 0.0,
    }


def _band(margin: int) -> str:
    if margin >= 20:
        return "decisive"
    if margin >= 5:
        return "soft"
    if margin >= 1:
        return "noise"
    return "clean"


class Stats:
    """Accumulates the per-question facts into the reported metrics."""

    def __init__(self) -> None:
        self.n = 0
        self.longest = 0          # key among the longest (ties incl) — plan 05 §0's definition
        self.strictly_longest = 0  # margin > 0 — the tidier quantity, matches the bands
        self.shortest = 0
        self.bands = collections.Counter()
        self.letters = collections.Counter()
        self.pick_longest_ev = 0.0
        self.key_len_total = 0
        self.other_len_total = 0.0

    def add(self, m: Dict) -> None:
        self.n += 1
        if m["among_longest"]:
            self.longest += 1
        if m["margin"] > 0:
            self.strictly_longest += 1
        if m["shortest"]:
            self.shortest += 1
        self.bands[_band(m["margin"])] += 1
        self.letters[m["answer"]] += 1
        self.pick_longest_ev += m["pick_longest_ev"]
        self.key_len_total += m["key_len"]
        self.other_len_total += m["mean_other"]

    @property
    def longest_rate(self) -> float:
        return self.longest / self.n if self.n else 0.0

    @property
    def strictly_longest_rate(self) -> float:
        return self.strictly_longest / self.n if self.n else 0.0

    @property
    def shortest_rate(self) -> float:
        return self.shortest / self.n if self.n else 0.0

    @property
    def pick_longest_score(self) -> float:
        return self.pick_longest_ev / self.n if self.n else 0.0

    def report(self, label: str) -> None:
        if not self.n:
            return
        key_mean = self.key_len_total / self.n
        other_mean = self.other_len_total / self.n
        lift = (100 * (key_mean - other_mean) / other_mean) if other_mean else 0.0
        print(f"\n  {label} ({self.n} questions)")
        print(f"    key is longest      {self.longest_rate:>6.1%}   (chance {CHANCE:.0%}) "
              f"<- the gate; ties incl, per plan 05 §0")
        print(f"    strictly longest    {self.strictly_longest_rate:>6.1%}   "
              f"(= the margin>0 bands)")
        print(f"    pick-longest score  {self.pick_longest_score:>6.1%}   <- what a student "
              f"scores reading no stems")
        print(f"    key is shortest     {self.shortest_rate:>6.1%}   (mirror defect; keep <=30%)")
        print(f"    mean key vs distr.  {key_mean:>6.1f} vs {other_mean:.1f}  ({lift:+.0f}%)")
        bands = "  ".join(
            f"{b} {self.bands.get(b, 0):>4} ({self.bands.get(b, 0) / self.n:>5.1%})"
            for b in ("decisive", "soft", "noise", "clean")
        )
        print(f"    margin bands        {bands}")
        letters = "  ".join(
            f"{k} {self.letters.get(k, 0) / self.n:>5.1%}" for k in OPTION_KEYS
        )
        print(f"    answer letters      {letters}")


# ---------------------------------------------------------------------------
# WORDING TELLS (issue #188). Read the block at the top of this file first.
#
# THE PATTERNS ARE COMMITTED HERE AND NOWHERE ELSE. Three §10-16 groups derived
# them by hand and their absolute rates differ between sessions, so only the
# within-run comparison was ever valid. `slice-tools/method_note_patterns.py`
# imports this registry rather than keeping a second copy, which is the same
# bargain that file struck for its own builtins.
# ---------------------------------------------------------------------------

# An option ending in ", " plus three or more words. Deliberately WIDE: the
# narrow relative-clause form below is a different population running the other
# way, and both are printed so nobody keys a repair on "has a trailing clause".
TRAILING_CLAUSE = re.compile(r",\s+\S+(?:\s+\S+){2,}\s*$")

WORDING_PATTERNS: Dict[str, Tuple[str, "re.Pattern[str]"]] = {
    "passive": (
        "deflection / inaction. The key lands on it at ~0.13x chance — the single "
        "strongest eliminator in the bank, and free without the stem.",
        # LEADING word boundary only, unlike `absolute` below: the inflections are
        # the point here ("pretending", "deferring", "postponed") and an author
        # writes the construction in whatever tense the option needs. Closing the
        # boundary drops ~7% of the rows and measures a narrower thing than the
        # one three slices named.
        re.compile(
            r"\b(?:wait (?:for|until)|wait and see|do nothing|say nothing|"
            r"take no action|ignore (?:the|it|this)|"
            r"avoid the (?:topic|issue|conversation)|pretend|hope (?:it|the|they)|"
            r"(?:ask|let) someone else|defer|leave it (?:to|for)|postpone)",
            re.IGNORECASE),
    ),
    "absolute": (
        "overreach: always / never / guarantees / all customers. ~0.33x chance. "
        "Overlaps `totalizer` in method_note_patterns, which measures the wider "
        "family (throughout/entire/full) at 0.40x; both are kept, neither subsumes "
        "the other.",
        re.compile(
            r"(?:\balways\b|\bnever\b|\bguarantees?\b|\bguaranteed\b|"
            r"\ball customers\b|\bevery customer\b|"
            r"\b(?:eliminates|replaces) the need\b|\bentirely eliminat)",
            re.IGNORECASE),
    ),
    "trailing_clause": (
        "a comma then three or more words. The only one of the three running "
        "ABOVE chance (~1.33x): the key is the option that has to be precisely "
        "true, so it is the one carrying the qualifier.",
        TRAILING_CLAUSE,
    ),
    "trailing_relative": (
        "a comma then which/that/so/because/since. ~0.82x — the OPPOSITE "
        "direction from `trailing_clause`, and printed beside it so the two "
        "populations are never merged (#174's split).",
        re.compile(r",\s+(?:which|that|so|because|since)\b", re.IGNORECASE),
    ),
}

# The three the stem-blind strategy below actually uses. `trailing_relative` is
# measured and printed but NOT played: it is the caution, not a move.
_ELIMINATORS = ("passive", "absolute")


def poisson_binomial_pvalue(probs: List[float], observed: int) -> float:
    """Exact two-sided p-value: the total probability of every outcome no likelier
    than the observed one. O(n^2) DP, which is nothing at these sizes.

    THE TOLERANCE IS RELATIVE, AND IT HAS TO BE. It was an ABSOLUTE `+ 1e-15`,
    which is fine at slice scale and silently wrong at bank scale: the mass of
    the observed outcome falls below the epsilon itself once n reaches the
    thousands, so `m <= target + 1e-15` stops meaning "no likelier than the
    observed one" and starts meaning "in either far tail". Every strongly
    significant bank-arm result then reported the same ~1e-15 floor regardless
    of how extreme it was — #188's four constructions came back 3.2e-15,
    2.3e-15, 5.9e-15, 3.3e-15, which is a suspiciously tidy coincidence and was
    the tell. Measured: n=4287 / observed=3103 reads 9.15e-15 absolute against
    1.73e-130 relative, while an n=40 control is byte-identical either way, so
    no landed slice number moves.
    """
    dist = [1.0]
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for k, mass in enumerate(dist):
            nxt[k] += mass * (1 - p)
            nxt[k + 1] += mass * p
        dist = nxt
    if observed >= len(dist):
        return 1.0
    target = dist[observed]
    return min(1.0, sum(m for m in dist if m <= target * (1 + 1e-9)))


def stem_blind_pick(opts: Dict[str, str]) -> List[str]:
    """The letters a stem-blind reader is left holding, before tie-breaking.

    (1) cross off every passive or absolute option; (2) if exactly one survivor
    carries a trailing clause, take it; otherwise keep all the survivors.

    Eliminating EVERY option is a real outcome on a row of four weak-sounding
    options, and the honest reading of it is that the strategy learned nothing —
    so it falls back to all four rather than to an empty set.
    """
    survivors = [k for k in OPTION_KEYS
                 if not any(WORDING_PATTERNS[n][1].search(str(opts.get(k, "")))
                            for n in _ELIMINATORS)]
    if not survivors:
        survivors = list(OPTION_KEYS)
    clause = [k for k in survivors if TRAILING_CLAUSE.search(str(opts.get(k, "")))]
    return clause if len(clause) == 1 else survivors


class WordingStats:
    """Per-pattern key loading, plus what the combination scores stem-blind.

    The metric is `method_note_patterns.py`'s, stated once there and reused here
    so the two files cannot print different numbers for the same construction:
    a row is TAGGED when at least one of its options matches, and the chance the
    key is among them is the mean of (matching options / 4) over the tagged rows
    — a Poisson-binomial mean, NOT a flat 25%. A pattern tagging three of four
    options is EXPECTED to sit on the key 75% of the time.
    """

    def __init__(self) -> None:
        self.n = 0
        self.tagged: Dict[str, int] = {k: 0 for k in WORDING_PATTERNS}
        self.key: Dict[str, int] = {k: 0 for k in WORDING_PATTERNS}
        self.probs: Dict[str, List[float]] = {k: [] for k in WORDING_PATTERNS}
        self.moved = 0        # rows where the strategy narrowed below four
        self.blind_ev = 0.0   # expected hits, ties broken uniformly

    def add(self, opts: Dict[str, str], answer: str) -> None:
        self.n += 1
        for name, (_, rx) in WORDING_PATTERNS.items():
            marks = [k for k in OPTION_KEYS if rx.search(str(opts.get(k, "")))]
            if not marks:
                continue
            self.tagged[name] += 1
            self.probs[name].append(len(marks) / 4.0)
            if answer in marks:
                self.key[name] += 1
        pick = stem_blind_pick(opts)
        if len(pick) != len(OPTION_KEYS):
            self.moved += 1
        if answer in pick:
            self.blind_ev += 1.0 / len(pick)

    @property
    def blind_score(self) -> float:
        return self.blind_ev / self.n if self.n else 0.0

    def report(self, label: str) -> None:
        if not self.n:
            return
        print(f"\n  WORDING TELLS — {label} ({self.n} questions) · report only, no gate")
        print(f"    {'construction':<20} {'rows':>6} {'share':>7} {'key':>7} "
              f"{'chance':>7} {'lift':>7} {'p':>9}")
        for name in WORDING_PATTERNS:
            tagged = self.tagged[name]
            if not tagged:
                print(f"    {name:<20} {0:>6} {'—':>7} {'—':>7} {'—':>7} {'—':>7} {'—':>9}")
                continue
            chance = sum(self.probs[name]) / tagged
            rate = self.key[name] / tagged
            lift = (rate / chance) if chance else 0.0
            p = poisson_binomial_pvalue(self.probs[name], self.key[name])
            print(f"    {name:<20} {tagged:>6} {tagged / self.n:>6.1%} {rate:>6.1%} "
                  f"{chance:>6.1%} {lift:>6.2f}x {p:>9.2e}")
        lift = self.blind_score / CHANCE if CHANCE else 0.0
        print(f"    stem-blind score    {self.blind_score:>6.1%}   (chance {CHANCE:.0%}, "
              f"{self.blind_score - CHANCE:+.1%}, {lift:.2f}x) on {self.moved / self.n:.1%} "
              f"of rows")
        print(f"    {'':<20} <- what a student scores eliminating passive/absolute and "
              f"taking the lone")
        print(f"    {'':<20}    trailing clause, reading no stems. Sibling of "
              f"pick-longest above.")


def audit(paths: List[Path]) -> Tuple[Stats, Dict[str, Stats], List[Dict],
                                     Dict[str, Stats], Dict[str, Stats],
                                     WordingStats]:
    bank = Stats()
    sections: Dict[str, Stats] = {"pools": Stats(), "sets": Stats()}
    per_file: Dict[str, Stats] = {}
    per_slice: Dict[str, Stats] = {}
    wording = WordingStats()
    flagged: List[Dict] = []
    malformed = 0

    for path in paths:
        section = _section(path)
        fstats = per_file.setdefault(path.name, Stats())
        sstats = per_slice.setdefault(_slice_of(path.name), Stats())
        for q in _load(path):
            m = _measure(q)
            if m is None:
                malformed += 1
                continue
            # Same well-formedness bar as the length metrics, deliberately: a row
            # counted in one section and not the other makes the two sets of
            # denominators silently incomparable.
            wording.add(q.get("options") or {}, m["answer"])
            bank.add(m)
            sections[section].add(m)
            fstats.add(m)
            sstats.add(m)
            if m["margin"] > 0:
                flagged.append({
                    "id": m["id"],
                    "file": _label(path),
                    "section": section,
                    "margin": m["margin"],
                    "key_len": m["key_len"],
                    "runner_up_len": m["runner_up"],
                })

    if malformed:
        print(f"  \033[33mWARN\033[0m {malformed} question(s) skipped as malformed "
              f"(bad answer letter or empty option)")

    flagged.sort(key=lambda f: -f["margin"])
    return bank, sections, flagged, per_file, per_slice, wording


def _guard_flag_target(out: Path) -> None:
    """Refuse to write the work list on top of the bank.

    --flag takes an OUTPUT path while --path takes an INPUT one, and the work
    list it emits is JSON shaped just enough like a question file to look
    plausible in a diff. Pointing it at a bank file silently destroys 100
    questions. Plan 07 §2.2 hands this flag to an agent working beside the
    bank, so the guard is the cheap half of that bargain.
    """
    try:
        out.resolve().relative_to(BANK_DIR)
    except ValueError:
        return
    print(f"\n  \033[31mREFUSING\033[0m --flag would overwrite a bank file: {out}\n"
          f"  --flag writes the work list; it does not filter input. Use --path "
          f"to audit a file,\n  and send --flag output somewhere outside "
          f"{BANK_DIR}.\n")
    sys.exit(2)


def _print_per_file(per_file: Dict[str, Stats]) -> None:
    print("\n  Per file, worst first (key-is-longest · decisive count)")
    rows = sorted(per_file.items(), key=lambda kv: -kv[1].longest_rate)
    for name, s in rows:
        print(f"    {s.longest_rate:>6.1%}  {s.bands.get('decisive', 0):>4} decisive   {name}")


def _slice_of(name: str) -> str:
    """cluster/level from a bank file name: finance-icdc-pool.json -> finance/icdc.

    The frontend NEVER serves a set whole (plan 07 §0.1): composeTest concats a
    cluster x level's two sets + its pool into one 300-question candidate list and
    draws by slot. So the per-FILE rate is not a number a student can experience,
    and this is the unit to size work against. Kept separate from --per-file rather
    than replacing it: per-file is still how a repair batch is scoped.
    """
    stem = name[:-5] if name.endswith(".json") else name
    parts = stem.split("-")
    return f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else stem


def _print_per_slice(slices: Dict[str, Stats]) -> None:
    print("\n  Per cluster x level — the 300-question candidate pool the frontend "
          "actually draws from (§0.1)")
    print(f"    {'slice':28} {'n':>5}  {'longest':>8} {'pick-longest':>13} "
          f"{'decisive':>9} {'soft':>6}")
    for name, s in sorted(slices.items(), key=lambda kv: -kv[1].longest_rate):
        print(f"    {name:28} {s.n:>5}  {s.longest_rate:>7.1%} {s.pick_longest_score:>12.1%} "
              f"{s.bands.get('decisive', 0):>9} {s.bands.get('soft', 0):>6}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Measure the length tell across the bank.")
    ap.add_argument("--max-rate", type=float, default=DEFAULT_MAX_RATE,
                    help=f"fail if bank-wide key-is-longest exceeds this (default "
                         f"{DEFAULT_MAX_RATE})")
    ap.add_argument("--flag", metavar="PATH",
                    help="write flagged ids (worst margin first) to PATH as JSON")
    ap.add_argument("--min-margin", type=int, default=DEFAULT_MIN_MARGIN,
                    help=f"--flag only includes margins >= this (default "
                         f"{DEFAULT_MIN_MARGIN} = the decisive band)")
    ap.add_argument("--per-file", action="store_true", help="print the per-file table")
    ap.add_argument("--per-slice", action="store_true",
                    help="print the per cluster x level table — the unit composeTest "
                         "draws from (§0.1)")
    ap.add_argument("--path", metavar="GLOB",
                    help="audit specific files instead of the whole bank "
                         "(e.g. a probe output)")
    ap.add_argument("--no-wording", action="store_true",
                    help="skip the wording-tell section (#188) — the pre-#188 report")
    args = ap.parse_args()

    if args.path:
        paths = _resolve_paths(args.path)
    else:
        paths = _bank_files()
    if not paths:
        print("no question files found")
        sys.exit(1)

    print(f"\nAuditing stem-blind tells across {len(paths)} file(s)")
    bank, sections, flagged, per_file, per_slice, wording = audit(paths)

    for name in ("pools", "sets"):
        sections[name].report(name)
    bank.report("BANK")

    if not args.no_wording:
        wording.report("BANK")

    if args.per_file:
        _print_per_file(per_file)

    if args.per_slice:
        _print_per_slice(per_slice)

    if args.flag:
        work = [f for f in flagged if f["margin"] >= args.min_margin]
        _guard_flag_target(Path(args.flag))
        Path(args.flag).write_text(json.dumps(work, indent=2), encoding="utf-8")
        by_section = collections.Counter(f["section"] for f in work)
        print(f"\n  Wrote {len(work)} flagged id(s) (margin >= {args.min_margin}) to "
              f"{args.flag}")
        print(f"    {dict(by_section)}")

    print(f"\n{'-' * 68}")
    if bank.longest_rate > args.max_rate:
        print(f"  \033[31mFAIL\033[0m key-is-longest {bank.longest_rate:.1%} exceeds "
              f"{args.max_rate:.0%} — the tell is live (plan 05 §7)\n")
        sys.exit(1)
    print(f"  \033[32mPASS\033[0m key-is-longest {bank.longest_rate:.1%} within "
          f"{args.max_rate:.0%}\n")


if __name__ == "__main__":
    main()
