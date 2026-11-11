#!/usr/bin/env bash
# Upload ONLY an allowlisted sanitized Vercel usage snapshot to the existing
# OpenClaw TrueNAS volume. Does not transfer CLI authentication or raw usage.
set -euo pipefail
umask 077

if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo "Usage: $0 /private/path/vercel-finops-summary.json" >&2
  exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
scratch="$(mktemp)"
trap 'rm -f "$scratch"' EXIT

node --input-type=module - "$root" "$1" > "$scratch" <<'NODE'
import { lstatSync, readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
const [root, filename] = process.argv.slice(2);
const { vercelFinopsAnomalies } = await import(pathToFileURL(resolve(root, "scripts/heartbeat/vercel-finops.mjs")));
try {
  const stat = lstatSync(filename);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 8192 || (stat.mode & 0o077) !== 0) process.exit(2);
  const doc = JSON.parse(readFileSync(filename, "utf8"));
  if (!["OK", "WATCH", "INVESTIGATE", "CRITICAL"].includes(doc.status)) process.exit(2);
  const evidence = vercelFinopsAnomalies(doc);
  if (evidence.some(([key]) => key.startsWith("vercel:evidence:"))) process.exit(2);
  // Strict allowlist: no credentials, billing detail, URLs, secrets or extra keys.
  const clean = {
    team: "albanandrieus-projects", source: "vercel-usage-json",
    observedAt: doc.observedAt, status: doc.status,
    cpuHours: doc.cpuHours, percentOfQuota: doc.percentOfQuota, quotaHours: 4,
    cpuMeasured: true, periodVerified: true, freshnessVerified: true,
  };
  process.stdout.write(JSON.stringify(clean) + "\n");
} catch {
  process.exit(2);
}
NODE

# Successful validation finishes before we contact the NAS. Limit total
# elapsed network time via the systemd oneshot TimeoutStartSec on automation.
remote_cmd='umask 077; dir=/home/node/.openclaw/nabla-heartbeat; mkdir -p "$dir"; chmod 0700 "$dir"; cat > "$dir/vercel-finops.json.tmp"; chmod 0600 "$dir/vercel-finops.json.tmp"; mv -f "$dir/vercel-finops.json.tmp" "$dir/vercel-finops.json"'
ssh -o BatchMode=yes -o ConnectTimeout=6 truenas \
  "sudo -n docker exec -i --user 1000 openclaw-gateway sh -c '${remote_cmd}'" < "$scratch"

echo "VERCEL_FINOPS_SNAPSHOT_PUBLISHED"
