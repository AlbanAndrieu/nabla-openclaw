#!/usr/bin/env bash
# Optional workstation-side collection, one sample per scheduled invocation.
# The hourly TrueNAS heartbeat reads the snapshot only; it never calls Vercel.
set -euo pipefail
umask 077
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
scratch="$(mktemp)"
trap 'rm -f "$scratch"' EXIT

# A denied CLI or an unsupported Hobby API returns non-zero: no fabricated
# "OK" record is copied, and the NAS heartbeat will report stale evidence.
node "$root/scripts/finops/check-vercel-team.mjs" --live --output "$scratch" > /dev/null
bash "$root/scripts/heartbeat/publish-vercel-finops.sh" "$scratch"
