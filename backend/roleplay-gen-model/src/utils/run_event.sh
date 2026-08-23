#!/bin/bash
# Usage: run_event.sh <ABBR> <slug> <"Series Name">
# Scrapes a DECA event page, downloads its roleplay PDFs to a temp dir, extracts
# each to a cleaned .txt in data/<ABBR>/, and leaves NO PDFs in the data folder.
#
# Requires: the repo venv with pymupdf installed (see plans/data-seeding-pipeline.md).
set -u
ABBR="$1"; SLUG="$2"; SERIES="$3"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"        # .../roleplay-gen-model/src/utils
MODEL_ROOT="$(cd "$HERE/../.." && pwd)"                      # .../roleplay-gen-model
REPO_ROOT="$(cd "$MODEL_ROOT/../.." && pwd)"                 # repo root
VP="$REPO_ROOT/venv/bin/python3"
DATA="$MODEL_ROOT/data/$ABBR"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DATA"

# DECA event pages paginate the Related Resources list with the query param
# b29253f7_page. 6 pages covers every event to date (max seen: 5).
for p in 1 2 3 4 5 6; do
  curl -sL "https://www.deca.org/compete/$SLUG?b29253f7_page=$p" -o "$TMP/pg_$p.html"
done
# roleplay PDFs only (District/Association/ICDC "..._Event_N"); exclude _Sample
# (those are the new SOLUTION/CAREER-COMPETENCIES format we intentionally skip).
grep -hoE "https://[^\"]+_DECA_${ABBR}_[0-9]{4}_(District|Association|ICDC)_Event[^\"]*\.pdf" "$TMP"/pg_*.html \
  | sort -u | grep -v '_Sample' > "$TMP/urls.txt"

total=$(wc -l < "$TMP/urls.txt" | tr -d ' ')
echo "### $ABBR: found $total roleplay PDFs"
ok=0; skip=0; fail=0
while read -r url; do
  short=$(echo "${url##*/}" | sed -E 's/^[a-f0-9]+_//')
  year=$(echo "$short"  | sed -E 's/.*_([0-9]{4})_.*/\1/')
  level=$(echo "$short" | sed -E 's/.*_[0-9]{4}_(District|Association|ICDC)_Event.*/\1/')
  n=$(echo "$short"     | sed -E 's/.*_Event_?([0-9]+).*/\1/'); [[ "$n" == "$short" ]] && n=1
  lvl_lc=$(echo "$level" | tr '[:upper:]' '[:lower:]')
  outname="${lvl_lc}_${year}_${n}.txt"
  curl -sfL "$url" -o "$TMP/f.pdf" || { echo "  DL-FAIL $short"; fail=$((fail+1)); continue; }
  if "$VP" "$HERE/extract_roleplay.py" "$TMP/f.pdf" "$ABBR" "$SERIES" "$year" "$n" "$level" > "$DATA/$outname" 2>"$TMP/e.txt"; then
    ok=$((ok+1))
  else
    rm -f "$DATA/$outname"; echo "  SKIP $short -> $(cat "$TMP/e.txt")"; skip=$((skip+1))
  fi
done < "$TMP/urls.txt"
echo "### $ABBR done: wrote=$ok skipped=$skip dlfail=$fail | folder has $(ls -1 "$DATA"/*.txt 2>/dev/null | wc -l | tr -d ' ') txt, $(ls -1 "$DATA"/*.pdf 2>/dev/null | wc -l | tr -d ' ') pdf"