#!/usr/bin/env bash
# Applies this checkout's heartbeat and morning briefing to the TrueNAS Gateway,
# without restart: collectors into the workspace, monitor scratch, heartbeat
# config, then the morning-briefing cron job (created once, then edited).
set -euo pipefail
cd "$(dirname "$0")/../.."

remote() { ssh -o BatchMode=yes truenas "$@"; }
gateway_cli() { remote "sudo -n docker exec -i openclaw-gateway node openclaw.mjs $*"; }
job_field() { node -e 'const [k, v, f] = process.argv.slice(1); console.log(JSON.parse(require("fs").readFileSync(0)).jobs.find((j) => j[k] === v)?.[f] ?? "")' "$@"; }

workspace=/mnt/cpool/openclaw/state/workspace
remote "sudo -n install -d -o 1000 -g 1000 -m 0700 $workspace/scripts"
for collector in homelab-health morning-briefing; do
  remote "sudo -n install -o 1000 -g 1000 -m 0400 /dev/stdin $workspace/scripts/$collector.mjs" \
    < "scripts/heartbeat/$collector.mjs"
done

jobs=$(gateway_cli cron list --all --json < /dev/null)
gateway_cli cron scratch "$(job_field declarationKey heartbeat:main id <<< "$jobs")" --file - < policies/HEARTBEAT.md

heartbeat=$(node -e 'console.log(JSON.stringify(require("./deploy/truenas/openclaw.json").agents.defaults.heartbeat))')
gateway_cli config set agents.defaults.heartbeat "'$heartbeat'" < /dev/null

# The owner's Telegram chat stays out of Git: reuse the digest's delivery target.
to=$(node -e 'console.log(JSON.parse(require("fs").readFileSync(0)).jobs.find((j) => j.name === "daily-tech-news-digest").delivery.to)' <<< "$jobs")
briefing=$(job_field name morning-briefing id <<< "$jobs")
verb="add --name morning-briefing"
if [ -n "$briefing" ]; then verb="edit $briefing"; fi
flags="--cron \"0 8 * * *\" --tz Europe/Paris --exact --agent main --session isolated \
--model litellm-cron/gpt-4.1-mini --tools exec,process --timeout-seconds 300 --light-context \
--announce --channel telegram --to $to"
remote "sudo -n docker exec -i openclaw-gateway sh -c 'node openclaw.mjs cron $verb $flags --message \"\$(cat)\"'" \
  < policies/cron/morning-briefing.message.md
