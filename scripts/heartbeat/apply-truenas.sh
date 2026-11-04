#!/usr/bin/env bash
# Applies this checkout's heartbeat to the TrueNAS Gateway, without restart:
# collector into the workspace, monitor scratch, then the heartbeat config.
set -euo pipefail
cd "$(dirname "$0")/../.."

remote() { ssh -o BatchMode=yes truenas "$@"; }
gateway_cli() { remote "sudo -n docker exec -i openclaw-gateway node openclaw.mjs $*"; }

workspace=/mnt/cpool/openclaw/state/workspace
remote "sudo -n install -d -o 1000 -g 1000 -m 0700 $workspace/scripts"
remote "sudo -n install -o 1000 -g 1000 -m 0400 /dev/stdin $workspace/scripts/homelab-health.mjs" \
  < scripts/heartbeat/homelab-health.mjs

job=$(gateway_cli cron list --all --json < /dev/null \
  | node -e 'console.log(JSON.parse(require("fs").readFileSync(0)).jobs.find((j) => j.declarationKey === "heartbeat:main").id)')
gateway_cli cron scratch "$job" --file - < policies/HEARTBEAT.md

heartbeat=$(node -e 'console.log(JSON.stringify(require("./deploy/truenas/openclaw.json").agents.defaults.heartbeat))')
gateway_cli config set agents.defaults.heartbeat "'$heartbeat'" < /dev/null
