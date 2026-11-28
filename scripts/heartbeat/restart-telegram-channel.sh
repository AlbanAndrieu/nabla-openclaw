#!/usr/bin/env bash
# Restarts the Telegram channel of the TrueNAS Gateway, never the Gateway, once the
# heartbeat has lost Telegram's session binding adapter. OpenClaw 2026.10.7: a
# Telegram stop that overruns its 5 s budget (host thaw after the night IO stall)
# can leave the restarted account without adapter while polling stays connected;
# every heartbeat then fails with "Session binding owner changed for
# telegram:default" (28/11 from 05:44) and homelab-health.json goes stale.
# Usage: restart-telegram-channel.sh [check|apply]. check is read-only, exit 1 = broken.
set -euo pipefail
mode=${1:-check}

remote() { ssh -o BatchMode=yes truenas "$@"; }
gateway_call() {
  remote "sudo -n docker exec openclaw-gateway node openclaw.mjs gateway call $1 --json --timeout 60000 \
--params '{\"channel\":\"telegram\",\"accountId\":\"default\"}'"
}

# A binding failure logged after the last Telegram start means the live account has no adapter.
last=$(remote "sudo -n docker logs --since 24h openclaw-gateway 2>&1 \
| grep -E 'heartbeat\] failed: Session binding owner changed for telegram|\[telegram\] \[default\] starting provider' \
| tail -n 1" || true)
if [[ "${last}" != *"Session binding owner changed"* ]]; then
  echo "telegram_binding=ok"
  exit 0
fi
echo "telegram_binding=broken since ${last%% *}"
if [[ "${mode}" != apply ]]; then
  exit 1
fi
gateway_call channels.stop
gateway_call channels.start
