#!/usr/bin/env bash
# Warms the coder's persistent caches on the TrueNAS devbox, as `coder`: for each repo
# with a mise.toml, the gate tools it pins (mise, ~/.local/share/mise) and its pre-commit
# or prek hook environments (~/.cache/pre-commit, ~/.cache/prek). Passes clone into a
# fresh workspace each time, but these caches live in /home/coder and are shared.
# Read-only for the repos (shallow clone, removed at the end); downloads go through the
# devbox egress proxy (GitHub, PyPI, npm). Usage: warm-devbox-tools.sh [repo...]
set -euo pipefail
repos=("$@")
[ "${#repos[@]}" -gt 0 ] || repos=(nabla-compose fastapi-sample nabla-site-alban nabla-site-bababou)

ssh -o BatchMode=yes truenas "sudo -n docker exec -i -u coder -w /home/coder openclaw-devbox bash -s -- ${repos[*]}" <<'EOF'
set -uo pipefail
# docker exec skips sshd: take the coder session environment (proxy, TMPDIR, git identity)
# from the image's sshd SetEnv line; its values hold no spaces.
for kv in $(sed -n 's/^SetEnv //p' /etc/ssh/sshd_config); do export "$kv"; done
# Interpreters (python, node) stay the image's; mise-config.toml disables them.
gate_tools=" uv just prek pre-commit shellcheck ruff npm hk "
root=$(mktemp -d /home/coder/.cache/devbox-warm.XXXXXX)
trap 'rm -rf "$root"' EXIT
for repo in "$@"; do
  dir="$root/$repo"
  if ! timeout 300 git clone -q --depth 1 "https://github.com/AlbanAndrieu/$repo.git" "$dir"; then
    echo "$repo clone=FAIL"; continue
  fi
  cd "$dir" || continue
  installed=() failed=()
  if [ -f mise.toml ]; then
    for tool in $(mise ls --current --json 2>/dev/null | jq -r 'keys[]'); do
      case "$gate_tools" in *" $tool "*) ;; *) continue ;; esac
      if timeout 600 mise install "$tool" >/dev/null 2>&1; then installed+=("$tool"); else failed+=("$tool"); fi
    done
  fi
  hooks=skipped
  if [ -f .pre-commit-config.yaml ]; then
    runner=pre-commit
    grep -q 'prek run' scripts/agent-quality-gate.sh 2>/dev/null && runner=prek
    hooks=ok
    for config in .pre-commit-config.yaml .pre-commit-pre-push.yaml; do
      [ -f "$config" ] || continue
      timeout 1200 "$runner" install-hooks --config "$config" >"$root/$repo-$config.log" 2>&1 \
        || { hooks="FAIL($config: $(grep -m1 -iE 'error|fail' "$root/$repo-$config.log" | cut -c1-120))"; }
    done
    hooks="$runner:$hooks"
  fi
  echo "$repo mise_installed=${installed[*]:-none} mise_failed=${failed[*]:-none} hooks=$hooks"
  cd /home/coder || exit 1
done
EOF
