#!/usr/bin/env bash
# Declares one scheduled job of the coder agent on the TrueNAS Gateway, without
# restart. --declaration-key makes a re-run update the same job.
#   just truenas-apply-coder-cron [fastapi-sample-daily-improvement|nabla-compose-roadmap-pass]
# The Telegram group id stays out of Git: CODER_TELEGRAM_GROUP_ID=-100..., or by
# default the group that apply-truenas.sh routed to coder in the Gateway config.
set -euo pipefail
cd "$(dirname "$0")/../.."

name=${1:-fastapi-sample-daily-improvement}
case $name in
  fastapi-sample-daily-improvement) schedule="17 6 * * *" timeout=1800 ;;
  # Ends by 06:07, before the fastapi-sample job.
  nabla-compose-roadmap-pass) schedule="7 5 * * *" timeout=3600 ;;
  *) echo "coder_cron=unknown job $name"; exit 2 ;;
esac

group=${CODER_TELEGRAM_GROUP_ID:-$(ssh -o BatchMode=yes truenas \
  "sudo -n docker exec openclaw-gateway node openclaw.mjs config get channels.telegram.groups --json" \
  | node -e 'const g = JSON.parse(require("fs").readFileSync(0));
console.log(Object.keys(g).find((id) => g[id]?.topics?.["*"]?.agentId === "coder") ?? "")')}
[[ "$group" =~ ^-100[0-9]{6,}$ ]] || { echo "telegram_group_id=invalid"; exit 2; }
thread=""
if [ -n "${CODER_TELEGRAM_THREAD_ID:-}" ]; then
  [[ "$CODER_TELEGRAM_THREAD_ID" =~ ^[0-9]+$ ]] || { echo "telegram_thread_id=invalid"; exit 2; }
  thread="--thread-id $CODER_TELEGRAM_THREAD_ID"
fi

# The message goes through stdin: it holds quotes and backticks.
ssh -o BatchMode=yes truenas "sudo -n docker exec -i openclaw-gateway sh -c 'node openclaw.mjs cron add \
  --declaration-key $name --name $name --agent coder --session isolated \
  --cron \"$schedule\" --tz Europe/Paris --timeout-seconds $timeout \
  --announce --channel telegram --to $group $thread \
  --message \"\$(cat)\"'" < "policies/cron/$name.message.md"
echo "coder_cron=$name declared ($schedule Europe/Paris, ${timeout}s max)"
