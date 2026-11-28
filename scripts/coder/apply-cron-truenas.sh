#!/usr/bin/env bash
# Declares one scheduled job of the coder agent on the TrueNAS Gateway, without
# restart. --declaration-key makes a re-run update the same job.
#   just truenas-apply-coder-cron [fastapi-sample-daily-improvement|<repo>-roadmap-pass|nabla-compose-infra-referee|security-audit-daily|all]
# The Telegram group id stays out of Git: CODER_TELEGRAM_GROUP_ID=-100..., or by
# default the group that apply-truenas.sh routed to coder in the Gateway config.
set -euo pipefail
self=$(realpath "$0")
cd "$(dirname "$self")/../.."

name=${1:-fastapi-sample-daily-improvement}
session=isolated
# No setup from 01:00 to 08:00: TrueNAS IO stalls 40-60 % in the nabla-compose
# night window (01:00-07:30, Mon-Sat) and the 60 s cron setup watchdog of OpenClaw
# then times out. Roadmap passes run every hour from 08:00 to 23:00, 12 min apart,
# 24 min max: at most two sandboxes at once on the 2-CPU devbox.
case $name in
  # Persistent session (not isolated), primed before the passes: they ask it, by
  # sessions_send, whether a failing probe comes from fastapi-sample or nabla-compose.
  security-audit-daily) schedule="0 0 * * *" timeout=1500 ;;
  nabla-compose-infra-referee) schedule="30 0 * * *" timeout=900 session=session:nabla-compose-infra ;;
  # After the referee and the 23:48 pass, before the night window; never with the fastapi-sample pass.
  fastapi-sample-daily-improvement) schedule="45 0 * * *" timeout=1800 ;;
  nabla-compose-roadmap-pass) schedule="0 8-23 * * *" timeout=1440 ;;
  fastapi-sample-roadmap-pass) schedule="12 8-23 * * *" timeout=1440 ;;
  nabla-site-alban-roadmap-pass) schedule="24 8-23 * * *" timeout=1440 ;;
  nabla-site-bababou-roadmap-pass) schedule="36 8-23 * * *" timeout=1440 ;;
  nabla-yubikey-roadmap-pass) schedule="48 8-23 * * *" timeout=1440 ;;
  all)
    for job in security-audit-daily nabla-compose-infra-referee fastapi-sample-daily-improvement nabla-compose-roadmap-pass fastapi-sample-roadmap-pass \
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

# Install only the reviewed runner from this checkout, as the unprivileged coder.
# Atomic replacement in the existing ZFS-backed home; no new mount or egress.
if [[ $name == security-audit-daily ]]; then
  install_cmd=$(cat <<'REMOTE'
sudo -n docker exec -i -u 1001:1001 openclaw-devbox python3 -c '
import os, sys, tempfile
from pathlib import Path
home = Path("/home/coder")
with tempfile.NamedTemporaryFile(dir=home, prefix=".audit-runner-", delete=False) as f:
    f.write(sys.stdin.buffer.read())
    f.flush()
    os.fchmod(f.fileno(), 0o700)
    os.fsync(f.fileno())
os.replace(f.name, home / ".nabla-security-audit-run.py")
'
REMOTE
)
  ssh -o BatchMode=yes truenas "$install_cmd" < scripts/coder/security-audit-run.py
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
