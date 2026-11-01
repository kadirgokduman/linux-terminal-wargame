#!/usr/bin/env bash
# Cron işi @reboot ile hemen, sonra her dakika koşar. İlk koşuyu bekle.
set -Eeuo pipefail

log=/var/spool/wargame/05/seal.log
for _ in $(seq 1 20); do
  [[ -s "$log" ]] && break
  sleep 1
done

cat "$log"
