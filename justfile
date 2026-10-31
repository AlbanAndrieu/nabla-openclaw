# Intentionally offline until TrueNAS image, dataset and models are attested.
default:
    @just --list

test:
    python3 -m unittest discover -s tests -p 'test_*.py' -v

plan:
    python3 scripts/check-target-contract.py

# Workstation Gateway <- this repository (read-only: hashes and states only).
workstation-plan: _workstation-host
    @echo "config_source=nabla-openclaw@$(git rev-parse --short=12 HEAD) uncommitted_config_paths=$(git status --porcelain -- policies deploy/workstation scripts/workstation | wc -l)"
    -python3 scripts/workstation/check-openclaw-runtime-alignment.py
    -python3 scripts/workstation/openclaw-heartbeat-gitops.py --check
    -python3 scripts/workstation/openclaw-heartbeat-gitops.py --briefing-check
    -python3 scripts/workstation/reconcile-openclaw-digest-cron.py --plan

# Strict: non-zero unless the live Gateway matches this repository.
workstation-check: _workstation-host
    #!/usr/bin/env bash
    set -euo pipefail
    python3 scripts/workstation/check-openclaw-runtime-alignment.py
    for flag in --check --briefing-check; do
      out="$(python3 scripts/workstation/openclaw-heartbeat-gitops.py "$flag")"
      echo "$out"
      [[ "$out" == matching* ]]
    done
    python3 scripts/workstation/reconcile-openclaw-digest-cron.py --check

# Explicit: private 0600 backup, atomic replace, no Gateway restart.
workstation-apply-heartbeat: _workstation-host _committed-config
    python3 scripts/workstation/openclaw-heartbeat-gitops.py --apply
    python3 scripts/workstation/openclaw-heartbeat-gitops.py --briefing-apply

# Explicit: existing digest job only; pass runtime_message_sha256 from workstation-plan.
workstation-apply-digest expected_sha: _workstation-host _committed-config
    python3 scripts/workstation/reconcile-openclaw-digest-cron.py --apply --expected-message-sha {{expected_sha}}

_workstation-host:
    @test "$(python3 scripts/workstation/openclaw-host-context.py --kind)" = workstation || { echo 'STOP: not the OpenClaw Workstation (host_context != workstation)' >&2; exit 2; }

_committed-config:
    @test -z "$(git status --porcelain -- policies deploy/workstation scripts/workstation)" || { echo 'STOP: uncommitted config; commit and review before applying to the live Gateway' >&2; exit 2; }
