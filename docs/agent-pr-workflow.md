# Agent PR workflow — OpenClaw

**Authority:** [AGENTS.md](../AGENTS.md). Load only for a Git/quality/agent
coordination task; not in every prompt. The coder devbox uses its stricter
[own AGENTS](../workspaces/coder/AGENTS.md).

## PR ownership and conflict repair

- First list open PRs and compare their file sets. Use the current PR if scope
  matches; do not create parallel edits of a skill, Gateway policy or roadmap.
  If none matches, retain small cleanups until a cohesive tested change exists.
- Workstation: `git fetch origin master`, check `git status --short`,
  `git log --left-right --oneline HEAD...origin/master`. If behind, resolve a
  reviewed `git rebase origin/master` **before** new edits. If history
  rewriting is forbidden, use a reviewed non-force merge. Recheck the exact
  HEAD, conflicts and test fixtures. Never blindly use `--ours` or discard
  concurrent commits.
- API-only: bind every read to exact HEAD; batch source edits in a single
  Git-tree update with an expected-SHA fast-forward. If the branch changed,
  stop and re-read. Do not treat the GitHub API as a substitute for local tests.
- Publish only a logical batch with its tests, notes and runtime criteria.
  Production-stability fixes and completed multi-service migrations are
  legitimate exceptions to batching; coordinate dependent repositories.
  No automatic CI rerun/merge.

## Evidence and scope

| Mode | Can validate | Not validated |
| --- | --- | --- |
| Workstation with authorized tools | `just test`, selected read-only Gateway and FinOps checks | deployment not run, secret values not observed |
| Remote Codex/source only | syntax, unit fixtures, source policies | private Gateway, TrueNAS, network, YubiKey, production metrics |

Use existing `just test`, `just workstation-plan` and applicable
`just devbox-plan` rather than running mutating `*-apply*` recipes
for validation. Do not run `just check` if it includes hardware/network
probes without checking its definition. Preserve secrets, rate budgets
and user approvals.
