# Agent policy — nabla-openclaw

Read this file once; load only the skill and nearest tests for the current task.
Detailed procedures belong in [the agent PR runbook](docs/agent-pr-workflow.md).

## Ownership and safety

This repository owns the OpenClaw Gateway configuration, agents, heartbeat,
automations and sandbox. `nabla-compose` owns TrueNAS network/storage and
LiteLLM dependencies; `ansible-workstation` owns Ubuntu OS. The root policy
does not loosen [the isolated coder agent contract](workspaces/coder/AGENTS.md).
Never read or publish API tokens, Telegram/Gmail/Slack data, BW_SESSION,
private state, credentials or sessions. No runtime mutation or restart
without a task-specific approved deployment plan and rollback.

## Execution by actual capability

- **Claude Code on verified Workstation:** use local `mise`/`just`, Python/Node,
  scoped tests and read-only Gateway probes **only after** checking host/rights.
  `AGENT_EXECUTION_MODE=workstation` selects a mode, not permission to deploy.
- **Codex/API-only or detached checkout:** default `AGENT_EXECUTION_MODE=offline`;
  review GitHub code, docs, tests and workflows. Run hermetic checks in the
  agent's available checkout, never probe private LAN/Docker/TrueNAS or
  claim Gateway readiness. Mark live and missing quality checks `NOT_RUN`.
- Separate `CODED`, `TESTED`, `DEPLOYED` and `ACCEPTED`; a 401/403,
  timeout or missing host evidence means `UNVERIFIED`, not `DOWN`.

## Existing PR first, synchronize, batch

1. Inventory open PRs, exact base/HEAD and changed paths. **Reuse a compatible
   existing PR**; assign one writer/PR to each shared agent policy/skill/roadmap
   file to prevent conflicting PRs.
2. Update the branch against `master` **before editing**. In an isolated
   worktree rebase and resolve real conflicts, then rerun targeted tests.
   Never discard another agent's changes; use a verified lease for any
   specifically authorized history rewrite, otherwise a reviewed merge.
3. **Do not push isolated micro-fixes.** Accumulate a coherent tested batch
   on the current Draft PR and publish once after the local gate. Exceptions:
   urgent production/security stabilization requiring deployment, or a
   completed migration with coordinated downstream updates.
4. No direct `master` writes, no auto-merge, no unchecked Ready/CI rerun,
   no weakened security gates and no secrets in PR output. Report exact-SHA
   evidence and unresolved runtime gates.

The `workspaces/coder/AGENTS.md` scope still requires explicit per-task
authorization before that agent can commit or push.
