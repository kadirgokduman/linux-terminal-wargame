#!/usr/bin/env bash
set -Eeuo pipefail

capture=/srv/pcap/capture.pcap

seal="$(tcpdump -r "$capture" -A 2>/dev/null \
  | sed -n 's/.*X-Archive-Seal: *//p' \
  | tr -d '\r' | head -n1)"

# tcpdump yoksa/başarısızsa: yük düz metin olduğu için strings yeterli.
if [[ -z "$seal" ]]; then
  seal="$(strings "$capture" | sed -n 's/.*X-Archive-Seal: *//p' | head -n1)"
fi

[[ -n "$seal" ]] || { echo "mühür bulunamadı" >&2; exit 1; }
printf '%s\n' "$seal"
