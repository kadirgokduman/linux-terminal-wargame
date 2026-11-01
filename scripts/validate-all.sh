#!/usr/bin/env bash
# Tüm seviyeleri sırayla çözer. Çözüm betiği olmayan seviyeler atlanır.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

pass=0
fail=0
skip=0
failed=()

for dir in levels/*/; do
  level="$(basename "$dir")"
  id="${level%%-*}"
  output="$(bash scripts/validate-level.sh "$id" 2>&1)" && status=0 || status=$?
  if [[ $status -ne 0 ]]; then
    fail=$((fail + 1))
    failed+=("$id")
    printf '%s\n' "$output" | tail -n 20
  elif grep -q '^SKIP' <<<"$output"; then
    skip=$((skip + 1))
    printf '%s\n' "$output" | head -n 1
  else
    pass=$((pass + 1))
    printf 'PASS seviye %s\n' "$id"
  fi
done

echo
echo "sonuç: ${pass} geçti, ${fail} başarısız, ${skip} atlandı"

if [[ $fail -gt 0 ]]; then
  echo "başarısız seviyeler: ${failed[*]}" >&2
  exit 1
fi
