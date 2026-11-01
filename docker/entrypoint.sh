#!/bin/sh
# wargame sandbox giriş noktası.
#
# Sıra önemli: sshd, kullanıcılar ve mühürler hazır olmadan açılmamalı.
set -eu

WARGAME_EPOCH="${WARGAME_EPOCH:-dev}"
SECRET_FILE="${WARGAME_SECRET_FILE:-/run/secrets/wargame_secret}"
export WARGAME_EPOCH WARGAME_SECRET_FILE="$SECRET_FILE"

log() { printf 'wargame: %s\n' "$*" >&2; }

if [ ! -s "$SECRET_FILE" ]; then
  log "sır bulunamadı: $SECRET_FILE"
  log "yerelde 'make secret' ile üretin; üretimde Docker secret kullanın."
  exit 1
fi

mkdir -p /run/sshd /var/log/wargame /var/spool/wargame
chmod 0755 /run/sshd

log "dönem '$WARGAME_EPOCH' — seviyeler materyalize ediliyor"
python3 -m wargame provision --quiet

# Gerçek zamanlayıcı: cron seviyeleri systemd timer değil, gerçek cron kullanır.
if ! pgrep -x cron >/dev/null 2>&1; then
  /usr/sbin/cron
fi

log "sshd başlıyor (22/tcp)"
exec /usr/sbin/sshd -D -e -f /etc/ssh/sshd_config
