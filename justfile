# Intentionally offline until TrueNAS image, dataset and models are attested.
default:
    @just --list

test:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
    node --test scripts/heartbeat/*.test.mjs scripts/finops/*.test.mjs
    node --test tests/vercelUsageBudget.test.mjs

# TrueNAS heartbeat and morning briefing <- this checkout: collectors, scratch, config and cron job, no restart.
truenas-apply-heartbeat:
    scripts/heartbeat/apply-truenas.sh

plan:
    python3 scripts/check-target-contract.py

# Coder devbox and agent contract (offline, read-only): docs/coder-agent.md.
devbox-plan:
    python3 scripts/check-devbox-contract.py

# Pin the devbox base images by digest (registry API, then local tools); `--via truenas` resolves there.
devbox-pin *args:
    python3 scripts/coder/pin-devbox-images.py {{args}}

# Production path, one command: read-only preflight, or `--apply` with NABLA_RUNTIME_CHANGE_APPROVED=yes.
truenas-deploy-coder *args:
    scripts/coder/deploy-truenas.sh {{ args }}

# Runtime egress proof of the devbox (read-only): direct route blocked, allowlist only.
devbox-egress-check:
    scripts/coder/check-devbox-egress.sh

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

# Manual and read-only: Vercel CLI must be authenticated on this workstation.
# NEVER run this from the OpenClaw heartbeat or public Next.js functions.
vercel-finops:
    node scripts/finops/check-vercel-team.mjs --live --strict

# Offline analysis of a private export (file is never committed).
vercel-finops-file file:
    node scripts/finops/check-vercel-team.mjs --input "{{file}}" --strict

# Manual, read-only FinOps diagnostics. Never run automatically by OpenClaw.
vercel-finops-test:
    node --test tests/vercelUsageBudget.test.mjs scripts/finops/check-vercel-team.test.mjs scripts/heartbeat/vercelFinops.test.mjs

# Manual end-to-end CPU sample: authenticated workstation -> sanitized NAS report.
# The hourly heartbeat itself never invokes Vercel or copies credentials.
vercel-finops-refresh:
    bash scripts/heartbeat/collect-publish-vercel-finops.sh

# Publish an already-sanitized private report from the workstation.
truenas-publish-vercel-finops file:
    bash scripts/heartbeat/publish-vercel-finops.sh "{{file}}"
