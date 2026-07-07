#!/usr/bin/env bash
# Fetch real public-domain novellas (Project Gutenberg, via the GITenberg GitHub
# mirror) and strip the Gutenberg header/footer, into ./examples.
#
# The hosted dev environment reaches raw.githubusercontent.com (not gutenberg.org),
# so this uses the GITenberg mirror. Runs anywhere with curl + python3.
#
# Usage:  bash examples/fetch_novellas.sh
#
# Two cleaned texts are already committed (a_christmas_carol.txt, heart_of_darkness.txt);
# this adds more and is how you'd refresh or extend the set.

set -euo pipefail
cd "$(dirname "$0")"

# repo-path-on-GITenberg  ->  local filename   (id is the trailing number)
texts=(
  "A-Christmas-Carol_46/46|a_christmas_carol.txt"
  "Heart-of-Darkness_219/219|heart_of_darkness.txt"
  "The-Time-Machine_35/35|the_time_machine.txt"
  "The-Strange-Case-of-Dr.-Jekyll-and-Mr.-Hyde_43/43|jekyll_and_hyde.txt"
  "Frankenstein_84/84|frankenstein.txt"
)

for entry in "${texts[@]}"; do
  spec="${entry%%|*}"; out="${entry##*|}"
  repo="${spec%/*}"; id="${spec#*/}"
  url="https://raw.githubusercontent.com/GITenberg/${repo}/master/${id}.txt"
  echo "fetching $out"
  curl -fsSL "$url" -o "/tmp/_gut_${id}.txt"
  python3 - "/tmp/_gut_${id}.txt" "$out" <<'PY'
import re, sys, pathlib
raw = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore")
start = re.search(r"\*\*\*\s*START OF TH[EIS].*?\*\*\*", raw, re.S)
end = re.search(r"\*\*\*\s*END OF TH[EIS].*?\*\*\*", raw, re.S)
body = raw[start.end():(end.start() if end else len(raw))].strip() + "\n"
pathlib.Path(sys.argv[2]).write_text(body, encoding="utf-8")
print(f"  {len(body.split())} words -> {sys.argv[2]}")
PY
done

echo "done. Chapter detection recognizes: CHAPTER/PART/BOOK/STAVE/CANTO + lone roman numerals."
echo "Note: texts whose chapters have bare titles (no keyword), e.g. Jekyll & Hyde,"
echo "won't segment — analyzed as one chapter. See SMOKE_TEST_S1.md."
