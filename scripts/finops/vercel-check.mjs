#!/usr/bin/env node
/** Explicit bounded Vercel CLI collector; never accesses the network by default. */
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { pathToFileURL } from "node:url";
import { analyzeUsage } from "./vercel-usage-budget.mjs";

const MAX_BYTES = 2_000_000;
export const DEFAULT_SCOPE = "albanandrieus-projects";
const allowed = new Set(["--input", "--live", "--strict", "--output"]);

function dates(now = new Date()) {
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Los_Angeles", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(now);
  const end = new Date(`${today}T00:00:00Z`);
  end.setUTCDate(end.getUTCDate() - 1);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - 29);
  return [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)];
}

export function parseArgs(args) {
  const opts = { live: false, strict: false, input: null, output: null };
  const seen = new Set();
  for (let i = 0; i < args.length; i++) {
    const key = args[i];
    if (!allowed.has(key) || seen.has(key)) throw new Error("invalid-arguments");
    seen.add(key);
    if (key === "--live" || key === "--strict") opts[key.slice(2)] = true;
    else {
      const value = args[++i];
      if (!value || value.startsWith("--")) throw new Error("invalid-arguments");
      opts[key.slice(2)] = value;
    }
  }
  if (opts.live === Boolean(opts.input)) throw new Error("select-live-or-input");
  return opts;
}

export function summarize(document, now = new Date()) {
  const r = analyzeUsage(document);
  return {
    schema: "vercel-finops-summary-v1", observedAt: now.toISOString(),
    scope: DEFAULT_SCOPE, status: r.status, reason: r.reason,
    cpuHours: r.cpuHours ?? null, percentOfQuota: r.percentOfQuota ?? null,
    periodVerified: r.periodVerified ?? false,
    evidence: r.periodVerified && r.cpuQuantityParsed ? "cpu-quantity" : "insufficient",
  };
}

export function run(argv, deps = {}) {
  let opts;
  try { opts = parseArgs(argv); } catch {
    console.log(JSON.stringify({ schema: "vercel-finops-summary-v1", status: "NOT_MEASURED", reason: "invalid-arguments" }));
    return 2;
  }
  try {
    let raw;
    if (opts.input) raw = (deps.readFile ?? readFileSync)(opts.input, "utf8");
    else {
      const [from, to] = dates(deps.now?.() ?? new Date());
      // The Vercel CLI handles authentication: no credential in argv or logs.
      raw = (deps.exec ?? execFileSync)("vercel",
        ["usage", "--scope", DEFAULT_SCOPE, "--from", from, "--to", to, "--format", "json"],
        { encoding: "utf8", timeout: 20_000, maxBuffer: MAX_BYTES, stdio: ["ignore", "pipe", "pipe"] });
    }
    if (typeof raw !== "string" || Buffer.byteLength(raw) > MAX_BYTES) throw new Error("bad-size");
    const report = summarize(JSON.parse(raw), deps.now?.() ?? new Date());
    if (opts.output) {
      // Persist only the allowlisted compact report; not raw billing data.
      (deps.mkdir ?? mkdirSync)(dirname(opts.output), { recursive: true, mode: 0o700 });
      (deps.write ?? writeFileSync)(opts.output, `${JSON.stringify(report)}\n`, { mode: 0o600, flag: "w" });
    }
    console.log(JSON.stringify(report));
    if (report.evidence === "insufficient") return 2;
    return opts.strict && report.status !== "OK" ? 1 : 0;
  } catch {
    console.log(JSON.stringify({ schema: "vercel-finops-summary-v1", status: "NOT_MEASURED", reason: "source-unavailable" }));
    return 2;
  }
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  process.exitCode = run(process.argv.slice(2));
}
