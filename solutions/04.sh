#!/usr/bin/env bash
set -Eeuo pipefail

awk '$2=="actor=custodian" && $3=="status=sealed" {print substr($4, 5)}' \
  ~/logs/1996-transfer.log
