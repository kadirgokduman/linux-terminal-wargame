#!/usr/bin/env bash
# İki olası kurulum: SUID okuyucu ya da mühür dosyasında ACL.
set -Eeuo pipefail

seal=""
if [[ -x ~/bin/wargame-read ]]; then
  seal="$(~/bin/wargame-read /etc/wargame/pass/03 2>/dev/null || true)"
fi

# Sertleştirilmiş profilde okuyucu ayrıcalık taşımaz; izin dosyadadır.
if [[ -z "$seal" ]]; then
  seal="$(cat /etc/wargame/pass/03 2>/dev/null || true)"
fi

[[ -n "$seal" ]] || { echo "mühür okunamadı" >&2; exit 1; }
printf '%s\n' "$seal"
