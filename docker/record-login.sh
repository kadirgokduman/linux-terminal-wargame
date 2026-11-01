#!/bin/sh
# pam_exec ile her SSH oturumunda root olarak çalışır.
# Skor tablosu için tek gerçek kaynak: başarılı giriş.
set -eu

[ "${PAM_TYPE:-}" = "open_session" ] || exit 0
case "${PAM_USER:-}" in
  player*) ;;
  *) exit 0 ;;
esac

LEVEL_ID="${PAM_USER#player}"
mkdir -p /var/log/wargame
printf '%s\t%s\t%s\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "$LEVEL_ID" \
  "${PAM_RHOST:-local}" \
  "${PAM_TTY:-?}" \
  >> /var/log/wargame/progress.log

exit 0
