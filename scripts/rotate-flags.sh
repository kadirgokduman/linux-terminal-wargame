#!/usr/bin/env bash
# Tüm mühürleri yeni bir döneme taşır. Eski parolalar geçersiz olur.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

epoch="${1:?kullanım: scripts/rotate-flags.sh 2027Q1}"

if [[ ! "$epoch" =~ ^[A-Za-z0-9._-]{2,32}$ ]]; then
  echo "hata: dönem etiketi 2-32 karakter olmalı (harf, rakam, . _ -)" >&2
  exit 2
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

tmp="$(mktemp)"
awk -v epoch="$epoch" '
  /^WARGAME_EPOCH=/ { print "WARGAME_EPOCH=" epoch; found = 1; next }
  { print }
  END { if (!found) print "WARGAME_EPOCH=" epoch }
' .env > "$tmp"
mv "$tmp" .env

echo "dönem '${epoch}' olarak ayarlandı."
echo "uygulamak için: make restart"
echo "not: oyuncuların elindeki eski parolalar artık geçersiz."
