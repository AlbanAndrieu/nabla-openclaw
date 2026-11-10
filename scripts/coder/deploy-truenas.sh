#!/usr/bin/env bash
# One-command production path of the coder agent on TrueNAS (docs/coder-agent.md).
# Default: read-only preflight. `--apply` with NABLA_RUNTIME_CHANGE_APPROVED=yes:
# dataset, SSH material, image build, devbox App, egress proof, agent config.
# Never restarts the Gateway or LiteLLM and never prints a secret.
#   NABLA_RUNTIME_CHANGE_APPROVED=yes CODER_TELEGRAM_GROUP_ID=-100... just truenas-deploy-coder --apply
set -euo pipefail
cd "$(dirname "$0")/../.."

apply=false
case "${1:-}" in
  --apply) apply=true ;;
  "") ;;
  *) echo "usage: $0 [--apply]"; exit 2 ;;
esac

remote() { ssh -o BatchMode=yes truenas "$@"; }
step() { printf '== %s\n' "$*"; }
fail() { echo "deploy=blocked reason=$*"; exit 2; }
truenas_repo=/mnt/cpool/compose/nabla-compose/apps/openclaw
compose=$truenas_repo/deploy/truenas/devbox/compose.yml

step "1/8 contract"
status=$(python3 scripts/check-devbox-contract.py) || fail contract_invalid
echo "$status"
case "$status" in
  *=ready_to_deploy | *=active) ;;
  *) fail "contract_not_ready: just devbox-pin, then contract.json status ready_to_deploy, merged and pulled" ;;
esac

step "2/8 TrueNAS checkout"
local_head=$(git rev-parse HEAD)
truenas_head=$(remote "git -C $truenas_repo rev-parse HEAD 2>/dev/null || sudo -n git -c safe.directory='*' -C $truenas_repo rev-parse HEAD")
[ "$local_head" = "$truenas_head" ] \
  || fail "checkout_mismatch local=${local_head:0:12} truenas=${truenas_head:0:12} (update the apps/openclaw submodule on TrueNAS)"
echo "truenas_checkout=${truenas_head:0:12}"

step "3/8 prerequisites"
dataset=$(remote "sudo -n zfs list -H -o name cpool/openclaw-devbox 2>/dev/null" || true)
token=$(remote "sudo -n stat -c '%u:%g %a' /mnt/cpool/secrets/runtime/openclaw-devbox/github_token 2>/dev/null" || true)
key_file=$(remote "sudo -n stat -c '%u:%g %a' /mnt/cpool/openclaw/state/credentials/litellm/coder.key 2>/dev/null" || true)
echo "dataset=${dataset:-missing} github_token=${token:-missing} gateway_key_file=${key_file:-missing}"
[ "$token" = "1001:1001 400" ] || fail "github_token: fine-grained PAT expected at 1001:1001 0400"
[ "$key_file" = "1000:1000 600" ] || fail "gateway_key_file: run nabla-compose just openclaw-coder-key-apply"

app_state() {
  remote "sudo -n midclt call app.query '[[\"id\",\"=\",\"openclaw-devbox\"]]'" \
    | python3 -c 'import json, sys; apps = json.load(sys.stdin); print(apps[0]["state"] if apps else "MISSING")'
}
state=$(app_state)
echo "devbox_app=$state"

if ! $apply; then
  [ -n "$dataset" ] || echo "plan=create dataset cpool/openclaw-devbox"
  echo "plan=bootstrap SSH material, build images, $([ "$state" = MISSING ] && echo create || echo redeploy) App, prove egress, apply agent"
  echo "deploy=plan_ok (rerun with --apply and NABLA_RUNTIME_CHANGE_APPROVED=yes)"
  exit 0
fi
[ "${NABLA_RUNTIME_CHANGE_APPROVED:-}" = yes ] || fail "approval_missing (NABLA_RUNTIME_CHANGE_APPROVED=yes)"

if [ -z "$dataset" ]; then
  remote "sudo -n midclt call pool.dataset.create '{\"name\":\"cpool/openclaw-devbox\",\"type\":\"FILESYSTEM\",\"share_type\":\"GENERIC\"}'" >/dev/null
  echo "dataset=created"
fi

step "4/8 SSH material"
scripts/coder/bootstrap-truenas.sh

step "5/8 images"
remote "sudo -n docker compose -f $compose build --pull"

step "6/8 App"
payload=$(python3 -c 'import json, sys; print(json.dumps({"app_name": "openclaw-devbox", "custom_app": True,
  "custom_compose_config_string": "include:\n  - " + sys.argv[1] + "\n"}))' "$compose")
case "$state" in
  MISSING) remote "sudo -n sh -c 'midclt call -j app.create \"\$(cat)\"'" <<< "$payload" >/dev/null; echo "devbox_app=created" ;;
  RUNNING) remote "sudo -n midclt call -j app.redeploy openclaw-devbox" >/dev/null; echo "devbox_app=redeployed" ;;
  *) remote "sudo -n midclt call -j app.start openclaw-devbox" >/dev/null; echo "devbox_app=started" ;;
esac
for _ in $(seq 1 60); do
  health=$(remote "sudo -n docker inspect -f '{{.State.Health.Status}}' openclaw-devbox 2>/dev/null" || true)
  [ "$health" = healthy ] && break
  sleep 5
done
[ "$health" = healthy ] || fail "devbox_unhealthy (${health:-absent}): sudo docker logs openclaw-devbox"
echo "devbox_health=healthy"

step "7/8 egress"
scripts/coder/check-devbox-egress.sh

step "8/8 agent"
scripts/coder/apply-truenas.sh
echo "deploy=done (open a Telegram topic and run the smoke test of docs/coder-agent.md)"
