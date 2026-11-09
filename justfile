# Intentionally offline until TrueNAS image, dataset and models are attested.
default:
    @just --list

test:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
    node --test scripts/heartbeat/*.test.mjs

# TrueNAS heartbeat and morning briefing <- this checkout: collectors, scratch, config and cron job, no restart.
truenas-apply-heartbeat:
    scripts/heartbeat/apply-truenas.sh

plan:
    python3 scripts/check-target-contract.py

# Coder devbox and agent contract (offline, read-only): docs/coder-agent.md.
devbox-plan:
    python3 scripts/check-devbox-contract.py

# Workstation, registry access required: pin the devbox base images by digest.
devbox-pin:
    python3 scripts/coder/pin-devbox-images.py

# TrueNAS, once: devbox directories, host key, Gateway client key, known_hosts.
truenas-bootstrap-coder:
    scripts/coder/bootstrap-truenas.sh

# TrueNAS coder agent <- this checkout, no restart. Optional: CODER_TELEGRAM_GROUP_ID=-100...
truenas-apply-coder:
    scripts/coder/apply-truenas.sh

# Explicit: delete the coder agent (prunes its sessions), its provider and group; stop the devbox.
truenas-rollback-coder:
    scripts/coder/rollback-truenas.sh

# Workstation Gateway <- this repository (read-only: hashes and states only).
workstation-plan:
    python3 scripts/workstation/openclaw-workstation-gitops.py plan

# Strict: non-zero unless the live Gateway matches this repository.
workstation-check:
    python3 scripts/workstation/openclaw-workstation-gitops.py check

# Explicit, merged config only: private 0600 backup, atomic replace, no restart.
workstation-apply-heartbeat:
    python3 scripts/workstation/openclaw-workstation-gitops.py apply-heartbeat

# Explicit: existing digest job only; pass runtime_message_sha256 from workstation-plan.
workstation-apply-digest $expected_sha:
    python3 scripts/workstation/openclaw-workstation-gitops.py apply-digest --expected-message-sha "$expected_sha"
