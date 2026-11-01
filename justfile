# Intentionally offline until TrueNAS image, dataset and models are attested.
default:
    @just --list

test:
    python3 -m unittest discover -s tests -p 'test_*.py' -v

plan:
    python3 scripts/check-target-contract.py

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
