#!/usr/bin/env bash
# One-time, idempotent TrueNAS preparation of the coder devbox (docs/coder-agent.md):
# directories, devbox host key, Gateway client key, authorized_keys, known_hosts.
# Never prints private keys or the GitHub token; never overwrites an existing key.
# The dataset cpool/openclaw-devbox and the token file are operator prerequisites.
set -euo pipefail

remote() { ssh -o BatchMode=yes truenas "$@"; }

devbox=/mnt/cpool/openclaw-devbox
credentials=/mnt/cpool/openclaw/state/credentials/devbox
token=/mnt/cpool/secrets/runtime/openclaw-devbox/github_token

remote "sudo -n bash -s" <<EOF
set -euo pipefail
if ! zfs list -H -o name cpool/openclaw-devbox >/dev/null 2>&1; then
  echo "devbox_dataset=missing (create cpool/openclaw-devbox first)"; exit 2
fi
install -d -o 1001 -g 1001 -m 0700 $devbox/home
install -d -o 0 -g 0 -m 0755 $devbox/sshd
install -d -o 1000 -g 1000 -m 0700 $credentials

if [ ! -s $devbox/sshd/ssh_host_ed25519_key ]; then
  ssh-keygen -q -t ed25519 -N '' -C openclaw-devbox -f $devbox/sshd/ssh_host_ed25519_key
  echo "devbox_host_key=created"
else
  echo "devbox_host_key=kept"
fi
chown 1001:1001 $devbox/sshd/ssh_host_ed25519_key $devbox/sshd/ssh_host_ed25519_key.pub
chmod 0400 $devbox/sshd/ssh_host_ed25519_key
chmod 0444 $devbox/sshd/ssh_host_ed25519_key.pub

if [ ! -s $credentials/id_ed25519 ]; then
  ssh-keygen -q -t ed25519 -N '' -C openclaw-gateway-coder -f $credentials/id_ed25519
  echo "gateway_client_key=created"
else
  echo "gateway_client_key=kept"
fi
chown 1000:1000 $credentials/id_ed25519 $credentials/id_ed25519.pub
chmod 0600 $credentials/id_ed25519
chmod 0644 $credentials/id_ed25519.pub

# Commands and PTYs only, even if sshd_config were relaxed later.
printf 'restrict,pty %s\n' "\$(cut -d' ' -f1,2 $credentials/id_ed25519.pub)" > $devbox/sshd/authorized_keys
chown 1001:1001 $devbox/sshd/authorized_keys
chmod 0444 $devbox/sshd/authorized_keys

printf '[openclaw-devbox]:2222 %s\n' "\$(cut -d' ' -f1,2 $devbox/sshd/ssh_host_ed25519_key.pub)" > $credentials/known_hosts
chown 1000:1000 $credentials/known_hosts
chmod 0644 $credentials/known_hosts

echo "devbox_host_fingerprint=\$(ssh-keygen -lf $devbox/sshd/ssh_host_ed25519_key.pub | cut -d' ' -f2)"
if [ -s $token ] && [ "\$(stat -c '%u:%g %a' $token)" = "1001:1001 400" ]; then
  echo "github_token=present_1001_0400"
else
  echo "github_token=missing_or_wrong_mode (expected 1001:1001 0400 at $token)"; exit 2
fi
EOF
