#!/bin/sh
# Starts the coder devbox: checks the read-only SSH material mounted from the
# dataset, prepares the persistent home, then runs sshd in the foreground.
# Never prints key material or the GitHub token.
set -eu
umask 077

material=/etc/openclaw-devbox
for file in ssh_host_ed25519_key authorized_keys; do
  if [ ! -s "$material/$file" ]; then
    echo "devbox_ssh_material=missing file=$file" >&2
    exit 78
  fi
done
if [ ! -s /run/secrets/github_token ]; then
  echo "devbox_github_token=missing (read-only clone still works)" >&2
fi

home=/home/coder
mkdir -p "$home/sandboxes" "$home/.cache" "$home/.config"
chmod 0700 "$home" "$home/sandboxes"
# TMPDIR of the sessions (sshd_config): tests run helpers from pytest tmp_path, and /tmp is noexec.
rm -rf "$home/.tmp"
mkdir -m 0700 "$home/.tmp"

# Commit identity is not secret; credentials come from /etc/gitconfig helpers.
if [ -n "${DEVBOX_GIT_NAME:-}" ] && [ -n "${DEVBOX_GIT_EMAIL:-}" ]; then
  git config --global user.name "$DEVBOX_GIT_NAME"
  git config --global user.email "$DEVBOX_GIT_EMAIL"
fi

echo "devbox_sshd=starting port=2222"
exec /usr/sbin/sshd -D -e -f /etc/ssh/sshd_config
