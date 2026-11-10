#!/bin/sh
# gh wrapper: SSH sessions do not inherit the container environment, so the
# fine-grained token is read from the read-only Compose secret at each call.
set -eu
if [ -s /run/secrets/github_token ]; then
  GH_TOKEN=$(cat /run/secrets/github_token)
  export GH_TOKEN
fi
export GH_PROMPT_DISABLED=1 GH_NO_UPDATE_NOTIFIER=1
exec /usr/bin/gh "$@"
