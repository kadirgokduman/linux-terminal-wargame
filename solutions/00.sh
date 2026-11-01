#!/usr/bin/env bash
set -Eeuo pipefail

grep -oE '\b[a-z2-7]{20}\b' ~/welcome.txt | head -n1
