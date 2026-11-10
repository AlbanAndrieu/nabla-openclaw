#!/usr/bin/env bash
# Runtime proof of the coder devbox egress policy (read-only, from the Workstation):
# no direct route out, GitHub and PyPI through the proxy, everything else
# refused by squid itself (CONNECT 403), LAN and IP literals included.
set -euo pipefail

remote() { ssh -o BatchMode=yes truenas "$@"; }
# Prints "<proxy CONNECT code> <HTTP code>"; curl failures still print the codes.
probe() {
  remote "sudo -n docker exec openclaw-devbox curl -sS -o /dev/null -m 15 -w '%{http_connect} %{http_code}' $*" 2>/dev/null || true
}

proxy="-x http://openclaw-devbox-egress:3128"
failures=0
check() {
  local name=$1 expected=$2 got=$3
  if [[ "$got" =~ $expected ]]; then
    echo "egress_${name}=ok"
  else
    echo "egress_${name}=FAIL got='${got}'"
    failures=$((failures + 1))
  fi
}

check direct_route_blocked '^000 000$' "$(probe https://github.com)"
# Any HTTP status from GitHub proves the tunnel opened (unauthenticated API may answer 403).
check github_tunnel '^200 [1-5][0-9][0-9]$' "$(probe "$proxy" https://api.github.com/zen)"
check pypi_tunnel '^200 200$' "$(probe "$proxy" https://pypi.org/simple/uv/)"
check other_domain_refused '^403 000$' "$(probe "$proxy" https://example.com)"
check lan_refused '^403 000$' "$(probe "$proxy" https://172.17.0.24)"
check ip_literal_refused '^403 000$' "$(probe "$proxy" https://140.82.112.3)"
check plain_http_refused '^000 403$' "$(probe "$proxy" http://pypi.org/simple/)"

if [ "$failures" -gt 0 ]; then
  echo "devbox_egress=FAIL failures=${failures}"
  exit 2
fi
echo "devbox_egress=ok"
