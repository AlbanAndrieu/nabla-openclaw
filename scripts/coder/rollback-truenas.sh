#!/usr/bin/env bash
# Removes the coder agent from the TrueNAS Gateway (its sessions and local
# workspace are pruned by `agents delete`), then its provider, model grant and
# Telegram group (dry run first), and stops the devbox App. Keeps the datasets,
# keys and pushed branches; no Gateway restart.
#   CODER_TELEGRAM_GROUP_ID=-100... just truenas-rollback-coder
set -euo pipefail
cd "$(dirname "$0")/../.."

remote() { ssh -o BatchMode=yes truenas "$@"; }

patch=$(node -e '
const c = require("./deploy/truenas/openclaw.json");
const patch = {
  agents: { defaults: { modelPolicy: { allow: c.agents.defaults.modelPolicy.allow.filter((m) => !m.startsWith("litellm-coder/")) } } },
  models: { providers: { "litellm-coder": null } },
};
const group = process.env.CODER_TELEGRAM_GROUP_ID;
if (group) {
  if (!/^-100[0-9]{6,}$/.test(group)) { console.error("telegram_group_id=invalid"); process.exit(2); }
  patch.channels = { telegram: { groups: { [group]: null } } };
}
console.log(JSON.stringify(patch));')
# The roster refuses a silent drop: delete the agent explicitly first.
remote "sudo -n docker exec -i openclaw-gateway node openclaw.mjs agents delete coder --force" < /dev/null
for mode in --dry-run ""; do
  remote "sudo -n docker exec -i openclaw-gateway node openclaw.mjs config patch --stdin $mode" <<< "$patch"
done
remote "sudo -n docker stop openclaw-devbox openclaw-devbox-egress" >/dev/null
echo "coder_rollback=config_removed_devbox_stopped (stop the openclaw-devbox App in the UI to keep it stopped)"
