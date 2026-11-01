#!/usr/bin/env bash
# checker, blob'u 0x5A ile XOR'layıp strcmp'ye veriyor.
# ltrace karşılaştırmanın argümanlarını basar.
set -Eeuo pipefail

cd ~
seal="$(ltrace -s 200 -e strcmp ./bin/checker tahmin 2>&1 \
  | sed -n 's/.*strcmp("\([^"]*\)".*/\1/p' | head -n1 || true)"

# ltrace yoksa: blob'u doğrudan çöz (anahtar objdump -d'de görünür).
if [[ -z "$seal" ]]; then
  seal="$(python3 -c 'import sys
data = open("/home/player11/lib/blob", "rb").read()
sys.stdout.write(bytes(b ^ 0x5A for b in data).decode().strip())')"
fi

[[ -n "$seal" ]] || { echo "mühür bulunamadı" >&2; exit 1; }
printf '%s\n' "$seal"
