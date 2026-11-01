#!/usr/bin/env bash
# Yeni seviye iskeleti: levels/NN-slug/ ve docs/levels/NN.md
set -Eeuo pipefail
cd "$(dirname "$0")/.."

id="${1:?kullanım: scripts/new-level.sh 03 \"Başlık\"}"
title="${2:-Yeni Seviye}"

if [[ ! "$id" =~ ^[0-9]{2}$ ]]; then
  echo "hata: ID iki haneli olmalı (ör. 03)" >&2
  exit 2
fi

slugify() {
  local text="$1"
  if command -v iconv >/dev/null 2>&1; then
    text="$(printf '%s' "$text" | iconv -f utf-8 -t ascii//TRANSLIT 2>/dev/null || printf '%s' "$text")"
  fi
  printf '%s' "$text" | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

slug="$(slugify "$title")"
[[ -n "$slug" ]] || slug="level-${id}"
target="levels/${id}-${slug}"

if [[ -e "$target" ]]; then
  echo "hata: ${target} zaten var" >&2
  exit 2
fi

previous="$(printf '%02d' $((10#$id - 1)))"
shopt -s nullglob
previous_dirs=(levels/"${previous}"-*)
shopt -u nullglob
if [[ "$id" != "00" && ${#previous_dirs[@]} -eq 0 ]]; then
  echo "uyarı: ${previous} numaralı seviye yok; kimlik zinciri kesintisiz olmalı" >&2
fi

mkdir -p "${target}/files"

cat > "${target}/level.yml" <<YAML
id: "${id}"
slug: "${slug}"
title: "${title}"
concept: ["komut"]
requires: $([[ "$id" == "00" ]] && echo "null" || echo "\"${previous}\"")
estimated_minutes: 10

dirs:
  - path: /home/player${id}/work
    owner: player${id}
    mode: "0750"

files:
  - path: /home/player${id}/work/README
    owner: player${id}
    mode: "0640"
    template: files/README

flag:
  owner: player${id}
  mode: "0400"

hints:
  - "Birinci kademe ipucu: soruyu daraltır, cevabı vermez."
  - "İkinci kademe ipucu: doğru komutu işaret eder."

docs: docs/levels/${id}.md
YAML

cat > "${target}/files/README" <<TEXT
SEVİYE ${id} — ${title}

Hedef: mühür $((10#$id + 1))'i elde etmek.
Mührü bu dosyaya gömmek için: {{flag:$((10#$id + 1))}}

Bu dosyayı düzenleyin, sonra 'make check' ile doğrulayın.
TEXT

mkdir -p docs/levels
cat > "docs/levels/${id}.md" <<TEXT
# Seviye ${id} — ${title}

| Alan | Değer |
|---|---|
| Kavram | komut |
| Hedef | Mühür $((10#$id + 1)) |
| Süre | ~10 dakika |

## Amaç

Buraya seviyenin sorusunu yazın. Oyuncuya komutu değil, problemi verin.

## Kavram

Öğretilen tek şeyi açıklayın.

## İpuçları

1. Birinci kademe.
2. İkinci kademe.

## Çözüm

Bu sayfa çözüm içermez.
TEXT

cat > "solutions/${id}.sh" <<SH
#!/usr/bin/env bash
# Seviye ${id} referans çözümü — bu dosya commit edilmez.
# Son satır, bir sonraki seviyenin mührünü yazdırmalıdır.
set -Eeuo pipefail

cat ~/work/README        # TODO: gerçek çözüm adımları
SH
chmod +x "solutions/${id}.sh"

echo "oluşturuldu:"
echo "  ${target}/level.yml"
echo "  ${target}/files/README"
echo "  docs/levels/${id}.md"
echo "  solutions/${id}.sh   (git'e girmez)"
echo
echo "sırada: level.yml'i doldur, 'make check' ve 'make validate LEVEL=${id}' çalıştır."
