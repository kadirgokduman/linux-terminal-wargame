#!/usr/bin/env bash
set -Eeuo pipefail

# Uyarı: find, bulduğu dosyaya rağmen izin hatası gördüğünde 1 döner.
# `set -e` altında bu, komut yerine koymayı sessizce öldürür.
record="$(find / -type f -user player03 -size 4096c -print -quit 2>/dev/null || true)"
[[ -n "$record" ]] || { echo "kayıt bulunamadı" >&2; exit 1; }

grep -om1 -E '[a-z2-7]{20}' "$record"
