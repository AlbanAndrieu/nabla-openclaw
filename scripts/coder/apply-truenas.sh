#!/usr/bin/env bash
# Applies the coder agent to the running TrueNAS Gateway, without restart:
# devbox network attach, SSH probe, workspace files, config (dry run first),
# then the optional Telegram forum group, whose id stays out of Git.
#   CODER_TELEGRAM_GROUP_ID=-100... just truenas-apply-coder
set -euo pipefail
cd "$(dirname "$0")/../.."

remote() { ssh -o BatchMode=yes truenas "$@"; }
gateway_sh() { remote "sudo -n docker exec -i openclaw-gateway sh -c '$1'"; }
credentials=/home/node/.openclaw/credentials/devbox

health=$(remote "sudo -n docker inspect -f '{{.State.Health.Status}}' openclaw-devbox" || true)
[ "$health" = "healthy" ] || { echo "devbox_health=${health:-absent}"; exit 2; }
# shellcheck disable=SC2016  # expanded inside the Gateway container, never here
gateway_sh 'test -n "$LITELLM_OPENCLAW_CODER_API_KEY"' \
  || { echo "gateway_coder_key=missing (add it to gateway.env and recreate the App)"; exit 2; }

networks=$(remote "sudo -n docker inspect -f '{{json .NetworkSettings.Networks}}' openclaw-gateway")
if ! grep -q '"openclaw-devbox"' <<< "$networks"; then
  # Declared in deploy/truenas/compose.yml; connect now to avoid a Gateway restart.
  remote "sudo -n docker network connect openclaw-devbox openclaw-gateway"
  echo "gateway_devbox_network=connected"
fi

# Same transport as the sandbox backend: pinned host key, Gateway client key, no agent.
gateway_sh "ssh -F /dev/null -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=5 \
  -i $credentials/id_ed25519 -o UserKnownHostsFile=$credentials/known_hosts -o StrictHostKeyChecking=yes \
  -p 2222 -T coder@openclaw-devbox python3 -V" || { echo "devbox_ssh_probe=failed"; exit 2; }

workspace=/mnt/cpool/openclaw/state/workspace-coder
while IFS= read -r -d '' file; do
  relative=${file#workspaces/coder/}
  remote "sudo -n install -D -o 1000 -g 1000 -m 0400 /dev/stdin $workspace/$relative" < "$file"
done < <(find workspaces/coder -type f -print0)
remote "sudo -n find $workspace -type d -exec chown 1000:1000 {} + -exec chmod 0700 {} +"
echo "coder_workspace=installed"

batch=$(node -e '
const c = require("./deploy/truenas/openclaw.json");
console.log(JSON.stringify([
  { path: "models.providers.litellm-coder", value: c.models.providers["litellm-coder"] },
  { path: "agents.defaults.modelPolicy.allow", value: c.agents.defaults.modelPolicy.allow },
  { path: "agents.defaults.maxConcurrent", value: c.agents.defaults.maxConcurrent },
  { path: "agents.entries.coder", value: c.agents.entries.coder },
]));')
for mode in --dry-run ""; do
  remote "sudo -n docker exec -i openclaw-gateway sh -c 'node openclaw.mjs config set --batch-json \"\$(cat)\" $mode'" <<< "$batch"
done

if [ -n "${CODER_TELEGRAM_GROUP_ID:-}" ]; then
  [[ "$CODER_TELEGRAM_GROUP_ID" =~ ^-100[0-9]{6,}$ ]] || { echo "telegram_group_id=invalid"; exit 2; }
  group='{"requireMention":false,"topics":{"*":{"agentId":"coder"}}}'
  for mode in --dry-run ""; do
    remote "sudo -n docker exec -i openclaw-gateway node openclaw.mjs config set \
      'channels.telegram.groups[\"$CODER_TELEGRAM_GROUP_ID\"]' '$group' --strict-json --merge $mode" < /dev/null
  done
else
  echo "telegram_group=skipped (set CODER_TELEGRAM_GROUP_ID to route a forum group to coder)"
fi

remote "sudo -n docker exec -i openclaw-gateway node openclaw.mjs config validate" < /dev/null
# shellcheck disable=SC2016  # JavaScript template literal
remote "sudo -n docker exec -i openclaw-gateway node openclaw.mjs sandbox explain --agent coder --json" < /dev/null \
  | node -e 'const d = JSON.parse(require("fs").readFileSync(0)); const s = d.sandbox;
console.log(`coder_sandbox=${s.mode}/${s.backend}/${s.scope} elevated=${d.elevated.enabled} tools=${s.tools.allow.join(",")}`);'
