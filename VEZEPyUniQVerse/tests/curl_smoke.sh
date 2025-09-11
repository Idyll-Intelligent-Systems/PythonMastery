#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE_URL:-http://localhost:8000}"

say() { echo -e "\n==> $*"; }

say "Ping health"
curl -sS "$BASE/health" | jq -r '.'

say "Fetch landing page (/)"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/")
echo "HTTP $code"; test "$code" = "200"

say "Fetch Helm page (/helm)"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/helm")
echo "HTTP $code"; test "$code" = "200"

say "List metrics head"
curl -sS "$BASE/metrics" | head -n 10

say "Check services exist on Helm (simple string match)"
for name in VEZEPyWeb VEZEPySocial VEZEPyGame VEZEPyEmail VEZEPySports VEZEPyCGrow; do
  curl -sS "$BASE/helm" | grep -q "$name" && echo "Found $name" || { echo "Missing $name"; exit 1; }
done

echo -e "\nAll checks passed."
