#!/usr/bin/env bash
set -Eeuo pipefail

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

tar -xzf /srv/archive/backup.tar.gz -C "$work"
tar -xjf "$work/1996/seal.tar.bz2" -C "$work"
cat "$work/seal.txt"
