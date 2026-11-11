// Read-only, bounded consumption of a locally supplied *sanitized* Vercel
// usage report. This module never runs vercel, fetch, a cron or an agent.
import { lstatSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

const TEAM = "albanandrieus-projects";
const MAX_REPORT_BYTES = 8 * 1024;
const MAX_SNAPSHOT_AGE_MS = 36 * 60 * 60 * 1000;
const LEVELS = Object.freeze({
  WATCH: { threshold: 0.5, severity: "warn" },
  INVESTIGATE: { threshold: 0.75, severity: "warn" },
  CRITICAL: { threshold: 0.9, severity: "crit" },
});

export function vercelReportPath(healthState, env = process.env) {
  return env.VERCEL_FINOPS_REPORT || join(dirname(healthState), "vercel-finops.json");
}

export function readVercelReport(path, io = { lstatSync, readFileSync }) {
  try {
    const metadata = io.lstatSync(path);
    // The report must be private. Reject symlinks, directories and unbounded input.
    if (!metadata.isFile() || metadata.isSymbolicLink() ||
        metadata.size > MAX_REPORT_BYTES || (metadata.mode & 0o077) !== 0) return null;
    return JSON.parse(io.readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

function previousRisk(previous) {
  const seen = previous?.seen ?? {};
  return Object.entries(seen).flatMap(([key]) => {
    const level = /^vercel:cpu:(WATCH|INVESTIGATE|CRITICAL)$/.exec(key)?.[1];
    if (!level) return [];
    return [[key, LEVELS[level].severity,
      `Vercel Fluid Active CPU : dernier seuil ${level} (preuve actuelle indisponible)`]];
  });
}

function unknown(previous, kind) {
  const text = kind === "stale"
    ? "Vercel Fluid Active CPU : instantané périmé (STALE), quota non vérifiable"
    : "Vercel Fluid Active CPU : métriques absentes ou non vérifiées (NOT_MEASURED)";
  return [[`vercel:evidence:${kind}`, "unknown", text], ...previousRisk(previous)];
}

/** Return only curated anomaly tuples: no raw data, URLs, credentials or prompts. */
export function vercelFinopsAnomalies(report, previous = {}, now = Date.now()) {
  if (!report || report.team !== TEAM || report.source !== "vercel-usage-json") {
    return unknown(previous, "missing");
  }
  const observedAt = Date.parse(report.observedAt ?? "");
  if (!Number.isFinite(observedAt) || observedAt > now + 60_000 ||
      now - observedAt > MAX_SNAPSHOT_AGE_MS || report.status === "STALE_USAGE") {
    return unknown(previous, "stale");
  }
  if (report.cpuMeasured !== true || report.periodVerified !== true ||
      report.freshnessVerified !== true || report.quotaHours !== 4 ||
      !Number.isFinite(report.cpuHours) || report.cpuHours < 0 ||
      !Number.isFinite(report.percentOfQuota) || report.percentOfQuota < 0) {
    return unknown(previous, "missing");
  }
  const ratio = report.cpuHours / 4;
  const percent = ratio * 100;
  if (Math.abs(percent - report.percentOfQuota) > 0.51) return unknown(previous, "missing");
  const status = ratio >= 0.9 ? "CRITICAL" : ratio >= 0.75 ? "INVESTIGATE"
    : ratio >= 0.5 ? "WATCH" : "OK";
  if (status !== report.status) return unknown(previous, "missing");
  if (status === "OK") return [];
  return [[`vercel:cpu:${status}`, LEVELS[status].severity,
    `Vercel Fluid Active CPU : ${report.cpuHours.toFixed(2)} h / 4 h (${percent.toFixed(1)} %) — ${status}`]];
}

export function vercelFinopsCheck(previous, path, now = Date.now(), io) {
  return vercelFinopsAnomalies(readVercelReport(path, io), previous, now);
}
