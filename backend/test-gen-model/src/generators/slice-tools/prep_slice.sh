#!/bin/bash
# prep_slice.sh [--gap N] <slice-dir-name> <expected-count> <file1> <file2> <file3>
#
# Builds payloads, ASSERTS the count against the per-slice table, and splits into
# balanced batches. Refuses to proceed on a scope miss -- the bare default
# (margin>=20) silently builds the scope that misses the gate.
#
# TWO SELECTORS:
#   default    --min-margin 5   the work list for an UNREPAIRED file (§3).
#   --gap N    --min-top-gap N --freeze-rank
#              the work list for an ALREADY-REPAIRED file (§3b's finance/ICDC).
#              Margin cannot select these: they are repaired, so the key is often
#              no longer the longest option and the margin is NEGATIVE while the
#              top gap stays large. --freeze-rank rides along because these items
#              already passed the rank gate -- re-rolling the rank would turn a
#              minimal length edit into a full re-repair (§1.2).
#
# SCRATCHPAD IS REQUIRED, and deliberately has no default. It is session-scoped --
# it cannot be derived from the repo the way the `cd` below is, and every default is
# a wrong one. This used to carry a literal from a long-dead session, under the
# pre-rename "GNS DECA APP" directory, and the failure was SILENT rather than loud:
# `mkdir -p` happily creates a ghost tree under /private/tmp, so the batches landed
# in a directory no live agent's scratchpad points at, and the miss only surfaced
# later as gate_slice.sh reporting "no parts". A fallback to $TMPDIR reproduces that
# exact defect one directory over. Refusing costs one export and cannot misdirect.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"  # repo root, derived — was
# hardcoded to the pre-rename "GNS DECA APP" path, which no longer exists

GAP=""
if [ "${1:-}" = "--gap" ]; then GAP="$2"; shift 2; fi

# The SCRATCHPAD checks come BEFORE `source venv/bin/activate`: an operator error
# should be reported as an operator error, not as whatever the venv says first.
if [ -z "${SCRATCHPAD:-}" ]; then
  echo "  REFUSING: SCRATCHPAD is unset, and this script has no default." >&2
  echo "  It is session-scoped -- set it to THIS session's scratchpad, the same one" >&2
  echo "  the authoring agents will write their parts into:" >&2
  echo >&2
  echo "    SCRATCHPAD=/private/tmp/claude-501/<project>/<session-uuid>/scratchpad \\" >&2
  echo "      $0 ${GAP:+--gap $GAP }<slice-dir-name> <expected-count> <file>..." >&2
  exit 1
fi
SP="$SCRATCHPAD"
# The directory must ALREADY exist. `mkdir -p` below would otherwise create a whole
# ghost tree for a stale or mistyped path and carry on -- which is the bug this
# script shipped with. A live session's scratchpad always exists.
if [ ! -d "$SP" ]; then
  echo "  REFUSING: SCRATCHPAD does not exist: $SP" >&2
  echo "  A live session's scratchpad already exists; this looks stale or mistyped." >&2
  exit 1
fi

source venv/bin/activate

NAME="$1"; EXPECT="$2"; shift 2
W="$SP/$NAME"
rm -rf "$W"; mkdir -p "$W/payload" "$W/batches" "$W/parts"

if [ -n "$GAP" ]; then SELECT=(--min-top-gap "$GAP" --freeze-rank)
else SELECT=(--min-margin 5); fi
echo "  selector: ${SELECT[*]}"
echo "  workdir:  $W"

for f in "$@"; do
  python backend/test-gen-model/src/generators/repair_options.py "$f.json" \
    --build-payload "$W/payload/$f.json" "${SELECT[@]}" >/dev/null 2>&1
done

python3 - "$W" "$EXPECT" "${GAP:-0}" "$@" <<'PY'
import json, math, sys, glob, os
W, expect, gap, files = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4:]
tot = 0
for f in files:
    n = len(json.load(open(f"{W}/payload/{f}.json"))); tot += n
assert tot == expect, f"SCOPE MISMATCH: got {tot}, want {expect} -- did the selector apply?"

if gap:
    # The freeze-rank contract, asserted rather than trusted: every emitted rank
    # must be the rank the item ALREADY holds in the bank, and no item may carry a
    # tie at key_length (a tie makes the key "among the longest" and GATE 3 errors
    # on it). If the builder is shuffling instead of freezing, this is what catches
    # it -- before an agent is spent, not after.
    sys.path.insert(0, "backend/test-gen-model/src/generators")
    from repair_options import observed_rank, top_gap
    bank = {}
    for bf in glob.glob("frontend/public/question-bank/*/*.json"):
        if "manifest" in bf: continue
        for q in json.load(open(bf)): bank[q["id"]] = q
    bad = []
    tally = {}
    for f in files:
        for i in json.load(open(f"{W}/payload/{f}.json")):
            q = bank[i["id"]]
            r, tied = observed_rank(q["options"], q["answer"])
            g, _ = top_gap(q["options"])
            tally[r] = tally.get(r, 0) + 1
            if i["key_length_rank"] != r:
                bad.append(f"{i['id']}: rank {i['key_length_rank']} emitted, {r} observed")
            if tied:
                bad.append(f"{i['id']}: {tied} distractor(s) tie the key at exactly key_length")
            if g <= gap:
                bad.append(f"{i['id']}: gap {g} <= {gap}, not a breach")
            if i["key"] != q["options"][q["answer"]]:
                bad.append(f"{i['id']}: payload key != bank key")
    assert not bad, "FREEZE-RANK CONTRACT BROKEN:\n  " + "\n  ".join(bad[:10])
    print(f"  freeze-rank OK: all {tot} ranks are the observed ones, 0 ties; "
          f"tally {dict(sorted(tally.items()))}")
caps = {i["max_top_gap"] for f in files for i in json.load(open(f"{W}/payload/{f}.json"))}
assert caps == {20}, f"cap missing/wrong: {caps}"
made = []
for f in files:
    items = json.load(open(f"{W}/payload/{f}.json"))
    # 60, not 45: measured fixed cost is ~50k tokens/agent vs ~850/item marginal,
    # so the agent count is the expensive term. Largest batch that has run clean
    # to date is 45; 60 is the first step past it.
    n = len(items); nb = max(1, math.ceil(n / 60))
    base, rem, idx = n // nb, n % nb, 0
    for b in range(nb):
        k = base + (1 if b < rem else 0)
        chunk = items[idx:idx + k]; idx += k
        name = f"{f}.batch{b+1:02d}"
        json.dump(chunk, open(f"{W}/batches/{name}.json", "w"), indent=2, ensure_ascii=False)
        made.append((name, len(chunk)))
    assert idx == n
print(f"  {os.path.basename(W)}: {tot} items OK (cap 20 in every item), {len(made)} batches")
for name, n in made:
    print(f"    {name:<44} n={n}")
PY
