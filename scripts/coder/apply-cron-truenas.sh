#!/usr/bin/env bash
# Declares the daily fastapi-sample review job of the coder agent on the TrueNAS
# Gateway, without restart. --declaration-key makes a re-run update the same job.
# The Telegram group id stays out of Git:
#   CODER_TELEGRAM_GROUP_ID=-100... [CODER_TELEGRAM_THREAD_ID=N] just truenas-apply-coder-cron
set -euo pipefail
cd "$(dirname "$0")/../.."

name=fastapi-sample-daily-improvement
[[ "${CODER_TELEGRAM_GROUP_ID:-}" =~ ^-100[0-9]{6,}$ ]] || { echo "telegram_group_id=invalid"; exit 2; }
thread=""
if [ -n "${CODER_TELEGRAM_THREAD_ID:-}" ]; then
  [[ "$CODER_TELEGRAM_THREAD_ID" =~ ^[0-9]+$ ]] || { echo "telegram_thread_id=invalid"; exit 2; }
  thread="--thread-id $CODER_TELEGRAM_THREAD_ID"
fi

# The message goes through stdin: it holds quotes and backticks.
ssh -o BatchMode=yes truenas "sudo -n docker exec -i openclaw-gateway sh -c 'node openclaw.mjs cron add \
  --declaration-key $name --name $name --agent coder --session isolated \
  --cron \"17 6 * * *\" --tz Europe/Paris --timeout-seconds 1800 \
  --announce --channel telegram --to $CODER_TELEGRAM_GROUP_ID $thread \
  --message \"\$(cat)\"'" < "policies/cron/$name.message.md"
echo "coder_cron=$name declared (06:17 Europe/Paris)"
