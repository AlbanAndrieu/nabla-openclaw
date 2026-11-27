#!/bin/sh
# gh wrapper: SSH sessions do not inherit the container environment, so the
# fine-grained token is read from the read-only Compose secret at each call.
set -eu
if [ -s /run/secrets/github_token ]; then
  GH_TOKEN=$(cat /run/secrets/github_token)
  export GH_TOKEN
fi
export GH_PROMPT_DISABLED=1 GH_NO_UPDATE_NOTIFIER=1
# PRs from the devbox stay Draft and only the owner marks them Ready or merges:
# on 27/11 a roadmap pass opened fastapi-sample#460 as Ready despite its skill.
# shortcut: a guardrail against model slips, not a boundary (`gh api` is not
# filtered); the token's own permissions are the boundary.
case "${1:-} ${2:-}" in
  "pr ready" | "pr merge")
    echo "gh $1 $2: refusé sur la devbox, réservé au propriétaire" >&2
    exit 1
    ;;
  "pr create")
    shift 2
    for arg in "$@"; do
      case $arg in -d | --draft) exec /usr/bin/gh pr create "$@" ;; esac
    done
    exec /usr/bin/gh pr create --draft "$@"
    ;;
esac
exec /usr/bin/gh "$@"
