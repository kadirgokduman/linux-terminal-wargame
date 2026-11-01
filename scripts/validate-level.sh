#!/usr/bin/env bash
# Bir seviyenin gerçekten çözülebildiğini kanıtlar.
#
# Test, oyuncunun yapacağını yapar: playerNN kullanıcısı olarak oturum açar
# ve solutions/NN.sh betiğini çalıştırır. Betiğin son satırı, bir sonraki
# seviyenin mührü olmalıdır. Ardından sızıntı denetimi koşar.
#
# Kullanım: scripts/validate-level.sh 01
set -Eeuo pipefail
cd "$(dirname "$0")/.."

level="${1:?kullanım: scripts/validate-level.sh 01}"
id="${level%%-*}"
project="wg-validate-${id}"
solution="solutions/${id}.sh"

# Test konteyneri ana sandbox ile aynı host portunu ve aynı alt ağı
# paylaşmasın; oyun açıkken de test koşabilsin.
export WARGAME_PORT=0
export WARGAME_SUBNET=172.29.0.0/16

if [[ ! -f "$solution" ]]; then
  echo "SKIP seviye ${id}: ${solution} yok (çözümler halka açık repoda tutulmaz)"
  exit 0
fi

cleanup() {
  docker compose -p "$project" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== seviye ${id}: sandbox kuruluyor"
docker compose -p "$project" up -d --build --wait

expected="$(docker compose -p "$project" exec -T sandbox python3 -m wargame flag "${id}" --next | tr -d '\r\n')"
if [[ -z "$expected" ]]; then
  echo "FAIL seviye ${id}: beklenen mühür hesaplanamadı" >&2
  exit 1
fi

echo "== seviye ${id}: player${id} olarak çözüm çalıştırılıyor"
actual="$(docker compose -p "$project" exec -T -u "player${id}" sandbox bash -s < "$solution" \
  | tr -d '\r' | awk 'NF { last = $0 } END { print last }')"

if [[ "$actual" != "$expected" ]]; then
  echo "FAIL seviye ${id}: mühür alınamadı" >&2
  echo "  beklenen: ${expected:0:4}… (${#expected} karakter)" >&2
  echo "  alınan  : ${actual:0:4}… (${#actual} karakter)" >&2
  exit 1
fi

echo "== seviye ${id}: sızıntı denetimi"
docker compose -p "$project" exec -T sandbox python3 -m wargame audit

echo "PASS seviye ${id}"
