#!/usr/bin/env bash
# Servis @reboot ile başlar; ilk yanıtı birkaç saniye beklemek gerekebilir.
set -Eeuo pipefail

for _ in $(seq 1 20); do
  if body="$(curl -fsS --max-time 2 http://127.0.0.1:8080/seal 2>/dev/null)"; then
    printf '%s\n' "$body"
    exit 0
  fi
  sleep 1
done

echo "127.0.0.1:8080 yanıt vermedi" >&2
exit 1
