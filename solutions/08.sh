#!/usr/bin/env bash
# Süreç @reboot ile başlar; environ dosyası görünene kadar bekle.
set -Eeuo pipefail

pid=""
for _ in $(seq 1 20); do
  pid="$(pgrep -u "$(id -un)" -f 'sleep infinity' | head -n1 || true)"
  [[ -n "$pid" ]] && break
  sleep 1
done

[[ -n "$pid" ]] || { echo "süreç bulunamadı" >&2; exit 1; }
tr '\0' '\n' < "/proc/${pid}/environ" | sed -n 's/^ARCHIVE_SEAL=//p'
