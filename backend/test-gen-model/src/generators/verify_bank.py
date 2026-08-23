"""Verify the question bank after a difficulty re-tag (plan 04 §5, plan 06 §7).

The plan 03 verification pass ran these checks ad-hoc; this is them written down
so the acceptance test is repeatable. No model is called and nothing is written —
this only reads and reports.

Checks:
  1. INVARIANT   — vs a git ref, only `difficulty` may differ, across every bank
                   file. Each other field must be byte-identical. The tightest
                   check available, and what makes a re-tag trivially reviewable.
                   `--allow-fields options,explanation` widens it for plan 07 §3's
                   repair pass, which edits exactly those two by design. THE KEY
                   STAYS FROZEN EVEN THEN: with `options` allowed, `options[answer]`
                   is still compared byte-for-byte, because the one thing §3's
                   invariant exists to catch is an agent "fixing" the length tell
                   by trimming the correct answer. Widening the check must not
                   widen it there.
                   `--allow-fields question,explanation` is plan 07 §3c's (lever B):
                   a stem edit, where `options` stays byte-identical wholesale and
                   the key is therefore frozen a fortiori. Do NOT pass `options` and
                   `question` together — lever A and lever B on one item leave
                   neither invariant proving anything (§3c §0.2).
  2. MANIFEST    — each entry's difficultyCounts, areaCounts, letterDistribution
                   and `count` match a fresh tally of its file, and the index is
                   complete in BOTH directions: every bank file on disk has exactly
                   one entry, so an unindexed pool cannot hide from the frontend
                   and two entries cannot point at one file (issue #94).
                   `areaCounts` drives the Question Bank card copy and
                   `letterDistribution` is the answer-balance signal `audit_tells`
                   watches; neither was verified by anything before.
                   The tier sum is checked against the row count SEPARATELY from
                   `count` — see the note in check_manifest for why folding those
                   two into one assertion silently drops the untiered-row case.
                   This is also what the pools-section fix exists to guarantee; it
                   fails loudly if that fix regresses.
  3. SPREAD      — the success signal. Difficulty triples must STOP being uniform
                   within a section. All identical => the re-tag did not work (tag
                   leaked into the payload and anchored the judgment).
  4. RUBRIC      — plan 06 §2. Sets and pools must be measured on ONE rubric, so
                   their `hard` rates should agree within a few points. A wide gap
                   means one half is still on a different standard. Also prints the
                   bank-wide split — the headline number plan 06 exists to produce.
  5. COLLISIONS  — 0 pool<->set and 0 pool<->pool content-hash collisions. The
                   hash covers stem + options only, so a re-tag cannot change it;
                   a hit here means something wrote more than difficulty.
                   Also 0 duplicate STEMS within a cluster x level (issue #34):
                   the content hash is options-blind's opposite — it happily lets
                   the same stem through twice under reworded distractors, and
                   both copies then sit in one candidate pool where one sitting
                   can draw both. Cross-cluster stem twins are reported only:
                   `loadCandidates` never mixes two cluster x levels, so they are
                   not co-servable.
                   Both hashes key on `build_question_bank.dedup_norm` (issue #64),
                   which folds case, curly quotes, sentence punctuation and
                   hyphen-vs-space before comparing. Exact-string comparison let a
                   twin differing by one apostrophe read as two questions and the
                   check report "0 dupes". The fold stops at typography on purpose
                   — `%`/`$`/digits survive, and nothing fuzzy is used, because
                   `collapse_stem_dupes.py --apply` DELETES what this key calls a
                   twin.
  6. AREAS       — every question's `instructionalArea` is one its own cluster is
                   allowed by clusters.json (`core` + that cluster's
                   `extra_areas`). Issue #117: 27 pbm pool questions carried
                   `Financial-Information Management`, a finance-only area, and
                   were therefore UNREACHABLE — the frontend blueprint is built
                   from the numbered sets, so an area no set carries never gets a
                   slot and `composeTest` can never draw it. Compared as SLUGS so
                   DECA's punctuation (the `area_names` overrides) cannot read as
                   a violation.

Usage:
    python verify_bank.py                 # invariant vs HEAD
    python verify_bank.py --base HEAD~1   # invariant vs another ref
    python verify_bank.py --no-invariant  # skip the git comparison
    python verify_bank.py --allow-fields options,explanation   # after a §3 repair
    python verify_bank.py --allow-fields question,explanation  # after a §3c stem pass
    python verify_bank.py --allow-removed receipt.json          # after a dupe collapse
"""

import argparse
import collections
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional

# Same-dir import: the dedup key must be ONE definition. This gate names
# `collapse_stem_dupes.py` as the remedy when it fails, and that tool groups on
# `build_question_bank.stem_hash` -- if the two normalized differently, the gate
# could fail on a pair the remedy cannot see (issue #64).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_question_bank import dedup_norm  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
from bank_paths import BANK_DIR, MANIFEST_PATH  # noqa: E402  the ONE bank path (#203)
CLUSTERS_PATH = BASE_DIR / "data" / "clusters.json"
REPO_ROOT = BASE_DIR.parents[1]

TIERS = ("easy", "medium", "hard")
MUTABLE_FIELD = "difficulty"

# The only fields any plan-07 pass may repair. `difficulty` is always mutable and is
# not listed here. Everything absent from this set — `id`, `answer`, `cluster`,
# `level`, `performanceIndicator`, `instructionalArea` — is what the invariant exists
# to protect, and `options[answer]` stays frozen even when `options` is allowed.
#
# `question` is here for plan 07 §3c (lever B): a stem whose concrete facts trigger a
# real doctrine the key ignores is fixed by DE-TRIGGERING THE STEM, never by editing
# the key. That edit moves `question` and the `explanation` that argues it, and nothing
# else. Note the two are NEVER passed together with `options` in one pass: lever A
# (options) and lever B (question) on the same item would leave neither invariant
# proving anything.
REPAIRABLE_FIELDS = frozenset({"options", "explanation", "question"})

# Plan 06 §7 asks that sets and pools be "comparable" once both are on the strict
# rubric, and names the `hard` rate as the measure. The `hard` rate is the wrong
# instrument, for the reason §0 gives itself: "the pools/sets hard gap (9% vs 13%)
# is a rubric artifact, not a real difference" — the two rubrics happen to agree
# there (13% vs 9%), so a hard-gap check PASSES on today's known-broken bank.
#
# Where the rubrics visibly disagree is `easy`: 13% (lenient sets) vs 59% (strict
# pools). That is the rule plan 04 added and plan 03 lacked — "findable by
# elimination or a length tell => easy" — showing up as a 46pp chasm. So `easy` is
# the tripwire and `hard` is reported as information.
#
# Threshold is deliberately loose: the probe expects sets ~64% easy vs pools 59%
# (~5pp) and sets ~2% hard vs pools 9% (~7pp, plausibly a real content difference,
# since the pools were authored to an inline quota and the sets were not). A tight
# bound would fire on the correct answer.
MAX_EASY_GAP_PP = 15.0

ok_count = 0
fail_count = 0


def _ok(msg: str) -> None:
    global ok_count
    ok_count += 1
    print(f"  \033[32mPASS\033[0m {msg}")


def _fail(msg: str) -> None:
    global fail_count
    fail_count += 1
    print(f"  \033[31mFAIL\033[0m {msg}")


def _load(path: Path) -> List[Dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pool_files() -> List[Path]:
    return sorted(BANK_DIR.glob("*/*-pool.json"))


def _set_files() -> List[Path]:
    return sorted(p for p in BANK_DIR.glob("*/*.json") if not p.name.endswith("-pool.json"))


def _bank_files() -> List[Path]:
    """Every question file. The invariant covers pools AND sets (plan 06 §2).

    Checking pools alone would pass vacuously on a sets re-tag — the failure mode
    where the acceptance test does not look at the thing that changed.
    """
    return sorted(_pool_files() + _set_files())


def _content_hash(q: Dict) -> str:
    """Hash stem + options only — the same shape the plan-03 collision audit used.

    Normalized with `dedup_norm`, so a re-shipped question whose only edit is a
    straightened apostrophe still collides (issue #64).
    """
    opts = q.get("options", {})
    payload = (dedup_norm(q.get("question", ""))
               + "||" + "|".join(f"{k}={dedup_norm(v)}" for k, v in sorted(opts.items())))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git_show(rel_path: str, ref: str) -> Optional[List[Dict]]:
    try:
        out = subprocess.run(
            ["git", "show", f"{ref}:{rel_path}"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(out)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def _bank_files_at_ref(ref: str) -> List[str]:
    """The paths `_bank_files()` WOULD have globbed, as of `ref`.

    This exists to be differenced against the working tree, so it must enumerate
    exactly the shape `_bank_files()` covers -- `BANK_DIR/<cluster>/<name>.json`,
    one directory deep, manifest excluded. `ls-tree -r` recurses to any depth, so
    a hit at the bank root or two levels down would be reported GONE forever: the
    on-disk glob can never match it, and the difference would never close.

    `-z` because `--name-only` quotes any path with a non-ASCII byte under the
    default `core.quotePath`; NUL-separated output is emitted raw. The path used
    to contain a space and needed this; it no longer does (#203), and `-z` stays
    because the quoting rule is about the bytes, not about this one path.
    """
    bank_rel = BANK_DIR.relative_to(REPO_ROOT).as_posix()
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--name-only", ref, bank_rel],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        _fail(f"cannot enumerate bank files at {ref}: {proc.stderr.strip()}")
        return []
    depth = len(PurePosixPath(bank_rel).parts)
    out = []
    for rel in proc.stdout.split("\0"):
        if not rel.endswith(".json") or rel.endswith("/manifest.json"):
            continue
        # `<bank>/<cluster>/<name>.json` and nothing deeper or shallower.
        if len(PurePosixPath(rel).parts) != depth + 2:
            continue
        out.append(rel)
    return sorted(out)


# ----------------------------
# 1. Invariant: only `difficulty` may differ
# ----------------------------
def check_invariant(ref: str, allow: frozenset = frozenset(), additive: bool = False,
                    allow_removed: frozenset = frozenset()) -> None:
    mutable = {MUTABLE_FIELD} | set(allow)
    label = "`" + "`, `".join(sorted(mutable)) + "`"
    mode = " (additive: file may GROW; existing ids must stay intact)" if additive else ""
    print(f"\n[1] INVARIANT — only {label} may differ vs {ref}{mode}")
    if "options" in allow:
        print("      `options` is allowed, but `options[answer]` — THE KEY — is still frozen (§3)")
    # A collapse (issue #34) removes rows without renumbering, so the file SHRINKS
    # while every surviving id stays byte-identical. Positional zip cannot express
    # that, so an explicit removal list switches the comparison to pair-by-id — the
    # same machinery `--additive` uses — with exactly these ids allowed to vanish
    # and (unless --additive) nothing allowed to appear. That keeps the removal
    # reviewable: the invariant still proves nothing ELSE moved.
    id_paired = additive or bool(allow_removed)
    if allow_removed:
        print(f"      {len(allow_removed)} id(s) are permitted to VANISH; any other "
              f"disappearance still fails")

    on_disk = {path.relative_to(REPO_ROOT).as_posix() for path in _bank_files()}
    for rel in _bank_files_at_ref(ref):
        if rel not in on_disk:
            _fail(f"{rel}: present at {ref}, GONE from the working tree")

    for path in _bank_files():
        rel = str(path.relative_to(REPO_ROOT))
        before = _git_show(rel, ref)
        if before is None:
            # A file absent at REF is a wholly new file — legal under additive
            # expansion (plan 09), a failure otherwise.
            if additive:
                _ok(f"{path.name}: new file (+{len(_load(path))} added)")
            else:
                _fail(f"{path.name}: cannot read at {ref}")
            continue
        after = _load(path)

        if id_paired:
            # Additive-expansion invariant (plan 09): every pre-existing id must
            # survive byte-identical (difficulty aside); the file may only GROW,
            # never shrink, drift, or re-key an existing item. Pairs by id, not by
            # position, since the assembler renumbers on write (existing ids are
            # re-emitted first and unchanged; new ids append).
            after_by_id = {q.get("id"): q for q in after}
            drifted, mangled, missing, removed = [], [], [], []
            touched = collections.Counter()
            for b in before:
                a = after_by_id.get(b.get("id"))
                if a is None:
                    (removed if b.get("id") in allow_removed else missing).append(b.get("id"))
                    continue
                if {k: v for k, v in b.items() if k not in mutable} != \
                   {k: v for k, v in a.items() if k not in mutable}:
                    drifted.append(b.get("id"))
                    continue
                for f in mutable:
                    if b.get(f) != a.get(f):
                        touched[f] += 1
                if "options" in mutable:
                    ans = str(b.get("answer", "")).strip().upper()
                    if (b.get("options") or {}).get(ans) != (a.get("options") or {}).get(ans):
                        mangled.append(b.get("id"))
            added = len(after) - (len(before) - len(missing) - len(removed))
            if missing:
                _fail(f"{path.name}: {len(missing)} pre-existing id(s) VANISHED — only ids passed "
                      f"to --allow-removed may disappear: {', '.join(str(d) for d in missing[:5])}"
                      + (" ..." if len(missing) > 5 else ""))
            elif added and not additive:
                _fail(f"{path.name}: +{added} question(s) APPEARED — a removal pass may only "
                      f"delete; use --additive if the file is meant to grow")
            elif drifted:
                _fail(f"{path.name}: {len(drifted)} existing question(s) changed beyond {label}: "
                      f"{', '.join(str(d) for d in drifted[:5])}"
                      + (" ..." if len(drifted) > 5 else ""))
            elif mangled:
                _fail(f"{path.name}: {len(mangled)} KEY(S) MODIFIED — options[answer] must be "
                      f"byte-identical (§3): {', '.join(str(d) for d in mangled[:5])}"
                      + (" ..." if len(mangled) > 5 else ""))
            else:
                diff_note = ", ".join(f"{n} {f}" for f, n in sorted(touched.items()))
                _ok(f"{path.name}: {len(before) - len(removed)} existing intact; +{added} added"
                    + (f", -{len(removed)} removed" if removed else "")
                    + (f" ({diff_note})" if diff_note else ""))
            continue

        if len(before) != len(after):
            _fail(f"{path.name}: question count {len(before)} -> {len(after)} "
                  f"(use --additive for pool expansion)")
            continue

        drifted, mangled = [], []
        touched = collections.Counter()
        for b, a in zip(before, after):
            if {k: v for k, v in b.items() if k not in mutable} != \
               {k: v for k, v in a.items() if k not in mutable}:
                drifted.append(b.get("id"))
                continue
            for f in mutable:
                if b.get(f) != a.get(f):
                    touched[f] += 1
            # `answer` is never mutable, so it is already proven identical above —
            # which is what makes it safe to index both sides with it here.
            if "options" in mutable:
                ans = str(b.get("answer", "")).strip().upper()
                if (b.get("options") or {}).get(ans) != (a.get("options") or {}).get(ans):
                    mangled.append(b.get("id"))

        if drifted:
            _fail(f"{path.name}: {len(drifted)} question(s) changed beyond {label}: "
                  f"{', '.join(str(d) for d in drifted[:5])}"
                  + (" ..." if len(drifted) > 5 else ""))
        elif mangled:
            _fail(f"{path.name}: {len(mangled)} KEY(S) MODIFIED — options[answer] must be "
                  f"byte-identical (§3): {', '.join(str(d) for d in mangled[:5])}"
                  + (" ..." if len(mangled) > 5 else ""))
        else:
            summary = ", ".join(f"{n} {f}" for f, n in sorted(touched.items())) or "nothing changed"
            _ok(f"{path.name}: content intact; {summary}")


# ----------------------------
# 2. Manifest agrees with the files
# ----------------------------
def check_manifest() -> None:
    print("\n[2] MANIFEST — every bank file is indexed and all tallies match")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    indexed_paths = collections.Counter()
    for section in ("sets", "pools"):
        for key, entry in manifest.get(section, {}).items():
            path = next(BANK_DIR.glob(f"*/{entry['file']}"), None)
            if path is None:
                _fail(f"{key}: file {entry['file']} not found on disk")
                continue
            indexed_paths[path.resolve()] += 1
            questions = _load(path)
            dc = entry.get("difficultyCounts")
            if not dc:
                _fail(f"{key}: no difficultyCounts in manifest")
                continue
            difficulty_tally = collections.Counter(q.get(MUTABLE_FIELD) for q in questions)
            fresh_difficulty = {t: difficulty_tally.get(t, 0) for t in TIERS}
            fresh_areas = dict(collections.Counter(q.get("instructionalArea") for q in questions))
            fresh_letters = dict(collections.Counter(q.get("answer") for q in questions))
            mismatches = []
            if fresh_difficulty != {t: dc.get(t, 0) for t in TIERS}:
                mismatches.append(f"difficultyCounts {dc} != {fresh_difficulty}")
            if fresh_areas != entry.get("areaCounts"):
                mismatches.append(f"areaCounts {entry.get('areaCounts')} != {fresh_areas}")
            if fresh_letters != entry.get("letterDistribution"):
                mismatches.append(
                    f"letterDistribution {entry.get('letterDistribution')} != {fresh_letters}"
                )
            if len(questions) != entry.get("count"):
                mismatches.append(f"count {entry.get('count')} != {len(questions)}")
            # BOTH halves, not either one. `count` vs `len(rows)` catches a stale
            # manifest; the tier sum vs `len(rows)` catches a row whose difficulty
            # is outside TIERS -- nothing else in this file validates that vocabulary.
            # The two are equivalent ONLY while every row is tiered, which is the
            # thing being asserted, so collapsing them to the row-count check alone
            # lets an untiered row through: both sides of the difficultyCounts
            # comparison are clamped to TIERS, so it drops out of both and reads
            # equal. (Regression caught in review of #94; the pre-#94 gate compared
            # the tier sum to `count` and had the untiered case covered by accident.)
            untiered = len(questions) - sum(fresh_difficulty.values())
            if untiered:
                offenders = sorted({str(q.get(MUTABLE_FIELD)) for q in questions
                                    if q.get(MUTABLE_FIELD) not in TIERS})
                mismatches.append(f"{untiered} row(s) carry a difficulty outside "
                                  f"{list(TIERS)}: {offenders}")
            if mismatches:
                _fail(f"{key}: " + "; ".join(mismatches))
            else:
                _ok(f"{key}: {fresh_difficulty}; {len(fresh_areas)} area(s); "
                    f"letters {fresh_letters}")

    for path in _bank_files():
        entry_count = indexed_paths[path.resolve()]
        if entry_count == 0:
            _fail(f"{path.relative_to(BANK_DIR).as_posix()}: bank file has no manifest entry")
        elif entry_count > 1:
            _fail(f"{path.relative_to(BANK_DIR).as_posix()}: bank file has {entry_count} "
                  "manifest entries; expected exactly one")


# ----------------------------
# 3. Spread — the acceptance test
# ----------------------------
def check_spread() -> None:
    print("\n[3] SPREAD — triples must not be uniform within a section (the success signal)")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    # Plan 06 §6 extends this to the sets: "If a re-measure ever shows every file
    # converging on the same triple, something is filling a quota again — treat it
    # as a defect." Both sections now face the same test; a section that passed on
    # spread before can still be uniform after, and that would be the tell.
    for section in ("sets", "pools"):
        entries = manifest.get(section, {})
        triples = [tuple(e["difficultyCounts"].get(t, 0) for t in TIERS)
                   for e in entries.values() if e.get("difficultyCounts")]
        if not triples:
            continue
        distinct = len(set(triples))
        hard = [t[2] for t in triples]
        easy = [t[0] for t in triples]
        print(f"      {section}: {distinct} distinct of {len(triples)} · "
              f"easy {min(easy)}-{max(easy)} · hard {min(hard)}-{max(hard)}")
        if distinct == 1 and len(triples) > 1:
            _fail(f"{section}: all {len(triples)} identical {triples[0]} — re-tag did NOT take "
                  f"effect (suspect difficulty leaked into the label payload)")
        elif distinct < len(triples) / 2:
            _fail(f"{section}: only {distinct} distinct triples of {len(triples)} — "
                  f"suspiciously clustered")
        else:
            _ok(f"{section}: {distinct} distinct triples of {len(triples)} — content-driven")


# ----------------------------
# 4. Rubric parity + the headline number
# ----------------------------
def check_rubric_parity() -> None:
    """Plan 06 §2/§7: one rubric across the whole bank, and report what it says.

    `difficulty` meant strict in the pools and lenient in the sets, so a bank-wide
    distribution was not a real quantity. Once both halves are judged the same way
    their `hard` rates should converge; a wide gap means they did not.
    """
    print("\n[4] RUBRIC — sets and pools on one standard; bank-wide split")
    rates = {}
    totals = {t: 0 for t in TIERS}
    for section, paths in (("sets", _set_files()), ("pools", _pool_files())):
        tally = collections.Counter()
        for path in paths:
            tally.update(q.get(MUTABLE_FIELD) for q in _load(path))
        n = sum(tally.get(t, 0) for t in TIERS)
        if not n:
            continue
        for t in TIERS:
            totals[t] += tally.get(t, 0)
        pct = {t: 100 * tally.get(t, 0) / n for t in TIERS}
        rates[section] = pct
        print(f"      {section:<6} ({n:>5}): easy {pct['easy']:>4.0f}% · "
              f"medium {pct['medium']:>4.0f}% · hard {pct['hard']:>4.0f}%")

    bank_n = sum(totals.values())
    if bank_n:
        bank = {t: 100 * totals[t] / bank_n for t in TIERS}
        print(f"      {'BANK':<6} ({bank_n:>5}): easy {bank['easy']:>4.0f}% · "
              f"medium {bank['medium']:>4.0f}% · hard {bank['hard']:>4.0f}%   <- the headline")

    if len(rates) == 2:
        hard_gap = abs(rates["sets"]["hard"] - rates["pools"]["hard"])
        easy_gap = abs(rates["sets"]["easy"] - rates["pools"]["easy"])
        print(f"      gap: easy {easy_gap:.0f}pp · hard {hard_gap:.0f}pp (informational)")
        if easy_gap > MAX_EASY_GAP_PP:
            _fail(f"easy rate gap {easy_gap:.0f}pp (sets {rates['sets']['easy']:.0f}% vs pools "
                  f"{rates['pools']['easy']:.0f}%) exceeds {MAX_EASY_GAP_PP:.0f}pp — the two "
                  f"halves are being judged by different rubrics (plan 06 §2)")
        else:
            _ok(f"easy rate gap {easy_gap:.0f}pp — sets and pools on one rubric")


# ----------------------------
# 5. Collisions
# ----------------------------
def check_collisions() -> None:
    print("\n[5] COLLISIONS — 0 pool<->pool and 0 pool<->set duplicate content")
    pool_hashes: Dict[str, List[str]] = collections.defaultdict(list)
    set_hashes: Dict[str, List[str]] = collections.defaultdict(list)
    for path in sorted(BANK_DIR.glob("*/*.json")):
        if path.name == "manifest.json":
            continue
        target = pool_hashes if path.name.endswith("-pool.json") else set_hashes
        for q in _load(path):
            target[_content_hash(q)].append(q.get("id"))

    dupes = {h: ids for h, ids in pool_hashes.items() if len(ids) > 1}
    if dupes:
        _fail(f"pool<->pool: {len(dupes)} collision(s), e.g. {list(dupes.values())[:3]}")
    else:
        _ok(f"pool<->pool: 0 collisions across {len(pool_hashes)} questions")

    cross = set(pool_hashes) & set(set_hashes)
    if cross:
        sample = [(pool_hashes[h][0], set_hashes[h][0]) for h in list(cross)[:3]]
        _fail(f"pool<->set: {len(cross)} collision(s), e.g. {sample}")
    else:
        _ok(f"pool<->set: 0 collisions across {len(set_hashes)} set questions")

    check_stem_collisions()


def _stem_hash(q: Dict) -> str:
    """Hash the stem ALONE — the same key build_question_bank.stem_hash uses.

    Both sides run `dedup_norm` (issue #64). Before that, this compared stems as
    exact strings once whitespace and case were folded, so a twin differing by one
    curly apostrophe — `What is a company's 'brand promise'?` vs `What is a
    company's brand promise?` — read as two distinct stems and the check printed
    "0 stem dupes" on a pair a student reads as one question.
    """
    return hashlib.sha256(dedup_norm(q.get("question", "")).encode()).hexdigest()


def check_stem_collisions() -> None:
    """Issue #34: the same stem twice inside one cluster x level, options reworded.

    The content hash above cannot see this — reworded distractors change it — but a
    student cannot see anything else: both copies sit in the one candidate pool
    `loadCandidates(cluster, level)` builds, so a single 50-question draw can serve
    the same stem twice, badged with whatever difficulty each copy was tagged.

    Cross-cluster twins are printed, not failed. Two cluster x levels are never
    mixed into one candidate pool, and generic PIs are legitimately shared across
    clusters; failing there would demand deleting a PI's only coverage in one
    cluster to fix a duplicate no student can encounter.
    """
    by_slice: Dict[tuple, List[str]] = collections.defaultdict(list)
    by_stem: Dict[str, List[tuple]] = collections.defaultdict(list)
    for path in sorted(BANK_DIR.glob("*/*.json")):
        if path.name == "manifest.json":
            continue
        for q in _load(path):
            h = _stem_hash(q)
            by_slice[(q.get("cluster"), q.get("level"), h)].append(q.get("id"))
            by_stem[h].append((q.get("cluster"), q.get("level"), q.get("id")))

    same = {k: ids for k, ids in by_slice.items() if len(ids) > 1}
    if same:
        sample = "; ".join(" / ".join(ids) for ids in list(same.values())[:3])
        _fail(f"same-slice stem dupes: {len(same)} group(s) — one sitting can serve both "
              f"copies (issue #34), e.g. {sample}. Collapse with collapse_stem_dupes.py")
    else:
        _ok(f"stem dupes: 0 within any cluster×level across {len(by_stem)} distinct stem(s)")

    cross = [v for v in by_stem.values()
             if len({(c, lv) for c, lv, _ in v}) > 1]
    if cross:
        print(f"      {len(cross)} cross-cluster×level stem twin(s) — not co-servable, "
              f"informational:")
        for v in cross[:5]:
            print("        " + " / ".join(f"{i} ({c}/{lv})" for c, lv, i in v))


def _area_slug(area: str) -> str:
    """'Financial-Information Management' -> 'financial_information_management'.

    Same normalization as `pi_deficit.slug`. Areas are compared as slugs, never as
    display names: clusters.json's `area_names` overrides exist precisely because
    DECA punctuates a few of them specially (`Product/Service Management`), and a
    name-level comparison would read that punctuation as a violation.
    """
    return re.sub(r"[^a-z0-9]+", "_", str(area).lower()).strip("_")


def check_area_membership() -> None:
    """Issue #117: a question's area must be one its own CLUSTER is allowed.

    clusters.json is the definition — the shared `core` plus that cluster's
    `extra_areas` — and until now nothing enforced it, so 27 pbm pool questions
    sat under `Financial-Information Management`, which belongs to finance alone.

    This is an unreachability check, not a tidiness one. `levelAreaCounts` in
    frontend/lib/question-bank.ts builds the composition blueprint from the
    numbered SETS (deliberately — they are the exam-shaped artifact), so an area
    no set carries gets no slot from `allocateAreas` and `composeTest` can never
    draw it. Those 27 could not reach a student through /test-generator, a focus
    quiz, or any dashboard task, while still counting toward the /progress
    coverage denominator via the derived pi-inventory.

    It fails rather than reports because the defect AMPLIFIES: `pi_deficit.py`
    votes its PI universe off the bank's own rows and never consults clusters.json,
    so three stray plan-09 rows read as three thin PIs and plan-10's pbm slices
    filled each to the reviewable floor — three mis-tags became twenty-seven.
    """
    print("\n[6] AREAS — every question's instructional area is one its cluster allows")
    config = json.loads(CLUSTERS_PATH.read_text(encoding="utf-8"))
    core = [_area_slug(a) for a in config["core"]]
    allowed = {
        cluster: set(core) | {_area_slug(a) for a in cfg.get("extra_areas", [])}
        for cluster, cfg in config["clusters"].items()
    }

    # (cluster, area) -> sample ids. Grouped, because one mis-tag is never alone.
    offenders: Dict[tuple, List[str]] = collections.defaultdict(list)
    unknown_clusters: Dict[str, List[str]] = collections.defaultdict(list)
    total = 0
    for path in _bank_files():
        for q in _load(path):
            total += 1
            cluster, area = q.get("cluster"), q.get("instructionalArea")
            if cluster not in allowed:
                unknown_clusters[str(cluster)].append(q.get("id"))
            elif _area_slug(area) not in allowed[cluster]:
                offenders[(cluster, area)].append(q.get("id"))

    for cluster, ids in sorted(unknown_clusters.items()):
        _fail(f"cluster '{cluster}' is not in clusters.json — {len(ids)} question(s), "
              f"e.g. {ids[:3]}")

    if offenders:
        for (cluster, area), ids in sorted(offenders.items(), key=lambda kv: -len(kv[1])):
            _fail(f"{cluster}: {len(ids)} question(s) tagged '{area}', which is not in "
                  f"{cluster}'s core + extra_areas — UNREACHABLE from every composed "
                  f"test, e.g. {ids[:3]}")
    else:
        _ok(f"area membership: 0 out-of-cluster areas across {total} questions in "
            f"{len(allowed)} cluster(s)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify the bank after a difficulty re-tag.")
    ap.add_argument("--base", default="HEAD", help="git ref to compare content against")
    ap.add_argument("--no-invariant", action="store_true", help="skip the git comparison")
    ap.add_argument("--additive", action="store_true",
                    help="pool-expansion mode (plan 09): files may GROW; every pre-existing id "
                         "must survive byte-identical (difficulty aside), pairing by id not "
                         "position since the assembler renumbers on write")
    ap.add_argument("--allow-removed", default="",
                    help="ids the invariant may find MISSING — a comma-separated list, or a "
                         "path to the JSON receipt collapse_stem_dupes.py writes. Switches the "
                         "invariant to pair-by-id so a shrinking file is still fully checked; "
                         "any id NOT listed that vanishes is still a failure.")
    ap.add_argument("--allow-fields", default="",
                    help="comma-separated fields the invariant may also differ on, e.g. "
                         "`options,explanation` after a plan 07 §3 repair. `difficulty` is "
                         "always allowed; `options[answer]` is never.")
    args = ap.parse_args()

    allow = frozenset(f.strip() for f in args.allow_fields.split(",") if f.strip())
    unknown = allow - REPAIRABLE_FIELDS
    if unknown:
        sys.exit(f"  --allow-fields: refusing to widen the invariant over {sorted(unknown)}. "
                 f"Only {', '.join('`' + f + '`' for f in sorted(REPAIRABLE_FIELDS))} are "
                 f"repairable (plan 07 §3, §3c); everything else — `id`, `answer`, `cluster`, "
                 f"`level`, `performanceIndicator` — is what the invariant exists to protect.")

    removed_arg = args.allow_removed.strip()
    allow_removed: frozenset = frozenset()
    if removed_arg:
        p = Path(removed_arg)
        if p.exists():
            payload = json.loads(p.read_text(encoding="utf-8"))
            ids = payload.get("removed", payload) if isinstance(payload, dict) else payload
            allow_removed = frozenset(ids)
        else:
            allow_removed = frozenset(i.strip() for i in removed_arg.split(",") if i.strip())

    print(f"\nVerifying bank at {BANK_DIR.relative_to(REPO_ROOT)}")
    if not args.no_invariant:
        check_invariant(args.base, allow, additive=args.additive, allow_removed=allow_removed)
    check_manifest()
    check_spread()
    check_rubric_parity()
    check_collisions()
    check_area_membership()

    print(f"\n{'-' * 60}\n  {ok_count} passed · {fail_count} failed\n")
    sys.exit(1 if fail_count else 0)


if __name__ == "__main__":
    main()
