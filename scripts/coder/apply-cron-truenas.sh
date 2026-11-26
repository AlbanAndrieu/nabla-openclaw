#!/usr/bin/env bash
# Declares one scheduled job of the coder agent on the TrueNAS Gateway, without
# restart. --declaration-key makes a re-run update the same job.
#   just truenas-apply-coder-cron [fastapi-sample-daily-improvement|<repo>-roadmap-pass|nabla-compose-infra-referee|all]
# The Telegram group id stays out of Git: CODER_TELEGRAM_GROUP_ID=-100..., or by
# default the group that apply-truenas.sh routed to coder in the Gateway config.
set -euo pipefail
self=$(realpath "$0")
cd "$(dirname "$self")/../.."

name=${1:-fastapi-sample-daily-improvement}
session=isolated
# Every job starts before 00:00: TrueNAS IO stalls 40-60 % from the 01:00
# night window (nabla-compose, Mon-Sat) and the Sunday 00:00 scrub, and the
# 60 s cron setup watchdog of OpenClaw then times out. Waves one hour apart
# (= pass timeout), two jobs each: at most two sandboxes on the 2-CPU devbox.
case $name in
  # Persistent session (not isolated), primed before the passes: they ask it, by
  # sessions_send, whether a failing probe comes from fastapi-sample or nabla-compose.
  nabla-compose-infra-referee) schedule="0 21 * * *" timeout=900 session=session:nabla-compose-infra ;;
  nabla-compose-roadmap-pass) schedule="30 21 * * *" timeout=3600 ;;
  nabla-yubikey-roadmap-pass) schedule="30 21 * * *" timeout=3600 ;;
  # Ends (30 min max) before fastapi-sample-roadmap-pass, in the next wave.
  fastapi-sample-daily-improvement) schedule="30 22 * * *" timeout=1800 ;;
  nabla-site-alban-roadmap-pass) schedule="30 22 * * *" timeout=3600 ;;
  fastapi-sample-roadmap-pass) schedule="30 23 * * *" timeout=3600 ;;
  nabla-site-bababou-roadmap-pass) schedule="30 23 * * *" timeout=3600 ;;
  all)
    for job in nabla-compose-infra-referee fastapi-sample-daily-improvement nabla-compose-roadmap-pass fastapi-sample-roadmap-pass \
               nabla-site-alban-roadmap-pass nabla-site-bababou-roadmap-pass nabla-yubikey-roadmap-pass; do
      "$self" "$job"
    done
    exit 0 ;;
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
  --declaration-key $name --name $name --agent coder --session $session \
  --cron \"$schedule\" --tz Europe/Paris --timeout-seconds $timeout \
  --announce --channel telegram --to $group $thread \
  --message \"\$(cat)\"'" < <(if [[ $name == *-roadmap-pass ]]; then
    sed "s/<repo>/${name%-roadmap-pass}/g" policies/cron/roadmap-pass.message.md
  else
    cat "policies/cron/$name.message.md"
  fi)
echo "coder_cron=$name declared ($schedule Europe/Paris, ${timeout}s max, $session)"
