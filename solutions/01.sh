#!/usr/bin/env bash
set -Eeuo pipefail

grep -rhE '^[[:space:]]+[A-Za-z0-9+/]{20,}={0,2}$' ~/ledger \
  | tr -d '[:space:]' \
  | base64 -d
echo
