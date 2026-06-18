#!/usr/bin/env bash
set -Eeuo pipefail

cat <<'BANNER'

+---------------------------------------------------------------+
| Foundry IQ Live Knowledge Sources                             |
| local no-secret scan                                          |
+---------------------------------------------------------------+
BANNER

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "Run this script from inside the git repository." >&2
  exit 2
fi

cd "$(git rev-parse --show-toplevel)"

FILE_LIST="$(mktemp "${TMPDIR:-/tmp}/liveks-secret-files.XXXXXX")"
git ls-files --cached --others --exclude-standard |
  grep -Ev '(^|/)(node_modules|\.next|dist|build|coverage|deployments|\.deployment|scratch)(/|$)' |
  grep -Ev '\.(png|jpg|jpeg|gif|ico|pdf|pptx|docx|xlsx)$' |
  grep -Ev '^scripts/no-secret-scan\.sh$' > "$FILE_LIST"

if [[ ! -s "$FILE_LIST" ]]; then
  rm -f "$FILE_LIST"
  echo "No files to scan."
  exit 0
fi

patterns=(
  '6d93cc9b-abb8-4dab-9406-892843d0de0b'
  '72f988bf-86f1-41af-91ab-2d7cd011db47'
  'MngEnvMCAP'
  'srch-foundry-iq-demo-ext'
  'aoai-foundry-iq-demo-ext'
  'FABRIC_USER_SEARCH_TOKEN=[A-Za-z0-9._-]{20,}'
  'AZURE_OPENAI_API_KEY=[A-Za-z0-9._-]{20,}'
  'SEARCH_API_KEY=[A-Za-z0-9._-]{20,}'
  'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}'
)

failed=false

for pattern in "${patterns[@]}"; do
  if xargs grep -nEI "$pattern" < "$FILE_LIST" >/tmp/liveks-secret-scan-hit.txt 2>/dev/null; then
    echo
    echo "Potential secret or tenant-specific value matched pattern:"
    echo "  $pattern"
    sed -n '1,20p' /tmp/liveks-secret-scan-hit.txt
    failed=true
  fi
done

rm -f /tmp/liveks-secret-scan-hit.txt "$FILE_LIST"

if [[ "$failed" == "true" ]]; then
  echo
  echo "No-secret scan: FAIL"
  echo "Replace real tenant values with placeholders or move local values to ignored env/report files."
  exit 1
fi

echo
echo "No-secret scan: PASS"
