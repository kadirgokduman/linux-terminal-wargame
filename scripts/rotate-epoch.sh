#!/usr/bin/env bash
# Yeni dönem, yeni sır, temiz konteyner.
#
#   scripts/rotate-epoch.sh                 # varsayılan profil, otomatik dönem etiketi
#   scripts/rotate-epoch.sh 2027Q1          # etiketi sen ver
#   scripts/rotate-epoch.sh --hardened 2027Q1
#
# Yaptıkları sırayla:
#   1. mevcut sırrı zaman damgalı olarak yedekler
#   2. 32 baytlık yeni sır üretir
#   3. .env içindeki WARGAME_EPOCH değerini günceller
#   4. konteyneri ve hacimleri silip yeniden kurar (tüm parolalar ölür)
set -Eeuo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-$(command -v python3 || command -v python)}"
SECRET_FILE="docker/secrets/wargame_secret"

usage() {
  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
}

hardened=0
epoch=""
for arg in "$@"; do
  case "$arg" in
    --hardened) hardened=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "hata: bilinmeyen seçenek $arg" >&2; exit 2 ;;
    *) epoch="$arg" ;;
  esac
done

epoch="${epoch:-$(date -u +%Y%m%dT%H%M)}"
if [[ ! "$epoch" =~ ^[A-Za-z0-9._-]{2,32}$ ]]; then
  echo "hata: dönem etiketi 2-32 karakter olmalı (harf, rakam, . _ -)" >&2
  exit 2
fi

compose=(docker compose)
if [[ $hardened -eq 1 ]]; then
  compose+=(-f deploy/container-compose.yaml)
  echo "profil: sertleştirilmiş"
fi

mkdir -p docker/secrets
if [[ -s "$SECRET_FILE" ]]; then
  backup="${SECRET_FILE}.$(date -u +%Y%m%dT%H%M%S)"
  cp "$SECRET_FILE" "$backup"
  chmod 600 "$backup"
  echo "eski sır yedeklendi: $backup"
fi

head -c 32 /dev/urandom | base64 > "$SECRET_FILE"
chmod 600 "$SECRET_FILE"
echo "yeni sır üretildi: $SECRET_FILE"

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
echo "dönem: $epoch"

echo "konteyner sıfırlanıyor (hacimler dahil)…"
"${compose[@]}" down -v --remove-orphans
"${compose[@]}" up -d --build --wait

echo
echo "tüm eski parolalar geçersiz. yeni giriş:"
WARGAME_EPOCH="$epoch" WARGAME_SECRET_FILE="$PWD/$SECRET_FILE" PYTHONPATH=engine \
  "$PYTHON" -m wargame login 00
