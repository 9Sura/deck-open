#!/bin/bash
# gate_slice.sh <slice-dir> [--apply]
#
# Gates a slice ONLY if every batch has a part. Refuses otherwise.
#
# WHY THIS EXISTS: a part file is on disk while its agent is still iterating.
# Gating one mid-write produced (a) a false "between-agent variance" diagnosis
# and a wasted agent, (b) a factually FALSE explanation applied to the bank that
# all four gates passed, and (c) a phantom 10-violation failure -- three times,
# twice AFTER the rule was written down in prose. Plan 07 §1.1: mechanical
# constraints work, prose rules do not. This is that lesson applied to the
# operator instead of the agents.
#
# A part-count match is a PROXY for "every agent notified" -- it is not proof.
# It catches the case that actually bit (a batch with no part yet). Still read
# the notifications.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"  # repo root, derived — was
# hardcoded to the pre-rename "GNS DECA APP" path, which no longer exists
source venv/bin/activate

W="$1"; APPLY="${2:-}"
nb=$(ls "$W/batches/" | wc -l | tr -d ' ')
np=$(ls "$W/parts/" 2>/dev/null | wc -l | tr -d ' ')
if [ "$nb" != "$np" ]; then
  echo "  REFUSING: $np part(s) for $nb batch(es) — agents are still running."
  echo "  Missing:"
  for b in "$W/batches/"*.json; do
    n=$(basename "$b"); [ -f "$W/parts/$n" ] || echo "    $n"
  done
  exit 1
fi

fail=0
for p in "$W/payload/"*.json; do
  f=$(basename "$p" .json)
  parts=$(ls "$W/parts/$f".batch*.json 2>/dev/null || true)
  [ -z "$parts" ] && { echo "  REFUSING: no parts for $f"; exit 1; }
  printf "  %-36s " "$f"
  out=$(python backend/test-gen-model/src/generators/repair_options.py "$f.json" \
        --check --payload "$p" --parts $parts --reject "$W/reject-$f.json" 2>&1)
  echo "$out" | grep -E "OK|FAIL" | sed 's/^ *//' || true
  echo "$out" | grep -q "FAIL" && fail=1 || true
done

[ "$fail" = "1" ] && { echo "  gate failed — not applying"; exit 1; }

if [ "$APPLY" = "--apply" ]; then
  echo
  for p in "$W/payload/"*.json; do
    f=$(basename "$p" .json)
    python backend/test-gen-model/src/generators/repair_options.py "$f.json" \
      --apply --payload "$p" --parts $(ls "$W/parts/$f".batch*.json) 2>&1 | grep applied
  done
  echo
  python backend/test-gen-model/src/generators/verify_bank.py --base 0eaae0c^ \
    --allow-fields options,explanation 2>&1 | tail -2
  # the check that caught the false explanation: bank must equal the FINAL parts
  python3 - "$W" <<'PY'
import json, glob, sys
from pathlib import Path
W = sys.argv[1]
bank = {}
for f in glob.glob('frontend/public/question-bank/*/*.json'):
    if 'manifest' in f: continue
    for q in json.loads(Path(f).read_text()): bank[q['id']] = q
bad = [r['id'] for p in glob.glob(W + '/parts/*.json') for r in json.load(open(p))
       if bank[r['id']]['options'] != r['options']
       or (bank[r['id']].get('explanation') or '') != (r.get('explanation') or '')]
print('  bank-vs-parts: %s' % (bad if bad else '0 mismatches'))
PY
fi
