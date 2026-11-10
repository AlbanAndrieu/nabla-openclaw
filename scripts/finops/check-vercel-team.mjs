#!/usr/bin/env node
// Opt-in, local-first Vercel team CPU monitor; no remote calls except explicit --live.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname } from "node:path";
import { pathToFileURL } from "node:url";
import { analyzeUsage } from "./vercel-usage-budget.mjs";

export const TEAM = "albanandrieus-projects";
const MAX_BYTES = 2_000_000;
export const HELP = "Usage: node scripts/finops/check-vercel-team.mjs (--input FILE | --live) [--strict] [--output FILE]";

export function evaluate(raw, now = new Date()) {
  try {
    if (Buffer.byteLength(raw) > MAX_BYTES) return { status: "NOT_MEASURED", reason: "export-too-large", cpuHours: null };
    const data = JSON.parse(raw);
    const report = analyzeUsage(data, { asOf: now.toISOString() });
    // Only approved numeric evidence. Never emit raw CLI output, tokens, URLs or charges.
    return {
      status: report.status,
      reason: report.reason,
      team: TEAM,
      observedAt: now.toISOString(),
      cpuHours: report.cpuHours ?? null,
      percentOfQuota: report.percentOfQuota ?? null,
      remainingHours: report.remainingHours ?? null,
      quotaHours: 4,
      periodVerified: report.periodVerified === true,
      freshnessVerified: report.status !== "STALE_USAGE" && report.periodVerified === true,
      cpuMeasured: report.cpuQuantityParsed === true,
      source: "vercel-usage-json",
    };
  } catch {
    return { status: "NOT_MEASURED", reason: "invalid-or-unsupported-json", team: TEAM, cpuHours: null };
  }
}

export function run(argv, options = {}) {
  const at = argv.indexOf("--output");
  const output = at >= 0 ? argv[at + 1] : null;
  if (at >= 0) argv = output && !output.startsWith("--") ? argv.toSpliced(at, 2) : [];
  const strict = argv.includes("--strict");
  const args = argv.filter(a => a !== "--strict");
  if (args.length !== (args[0] === "--input" ? 2 : 1) ||
      !["--input", "--live"].includes(args[0]) ||
      (args[0] === "--input" && (!args[1] || args[1].startsWith("--"))) ||
      argv.filter(a => a === "--strict").length > 1) {
    console.log(JSON.stringify({ status: "NOT_RUN", reason: "explicit-input-or-live-required", team: TEAM }));
    return 2;
  }
  let report;
  if (args[0] === "--input") {
    try {
      const text = (options.read ?? readFileSync)(args[1], "utf8");
      report = evaluate(text, options.now ?? new Date());
    } catch {
      report = { status: "NOT_MEASURED", reason: "export-unreadable", team: TEAM, cpuHours: null };
    }
  } else {
    // Does not start agents or call Vercel on import. Avoid propagating tokens
    // through the CLI arguments or saving raw usage data to logs.
    const output = (options.spawn ?? spawnSync)("vercel", [
      "usage", "--scope", TEAM, "--format", "json",
    ], { encoding: "utf8", timeout: 20_000, maxBuffer: MAX_BYTES, stdio: ["ignore", "pipe", "pipe"] });
    report = output.error || output.status !== 0
      ? { status: "NOT_MEASURED", reason: "vercel-cli-unavailable-or-denied", team: TEAM, cpuHours: null }
      : evaluate(output.stdout, options.now ?? new Date());
  }
  if (output) {
    // Briefing snapshot: only this compact report, never the raw Vercel export.
    (options.mkdir ?? mkdirSync)(dirname(output), { recursive: true, mode: 0o700 });
    (options.write ?? writeFileSync)(output, `${JSON.stringify(report)}\n`, { mode: 0o600 });
  }
  console.log(JSON.stringify(report));
  if (["NOT_RUN", "NOT_MEASURED", "WINDOW_UNVERIFIED", "STALE_USAGE", "INVALID"].includes(report.status)) return 2;
  return strict && report.status !== "OK" ? 1 : 0;
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  process.exitCode = run(process.argv.slice(2));
}
