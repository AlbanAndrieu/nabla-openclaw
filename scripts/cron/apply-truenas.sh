#!/usr/bin/env bash
# Installs the digest's FreshRSS source sync into the TrueNAS Gateway workspace.
# The read token stays in state/credentials/freshrss-rss-token (0600), never here.
set -euo pipefail
cd "$(dirname "$0")/../.."

ssh -o BatchMode=yes truenas \
  "sudo -n install -o 1000 -g 1000 -m 0400 /dev/stdin /mnt/cpool/openclaw/state/workspace/scripts/freshrss-sources.py" \
  < scripts/cron/freshrss-sources.py
