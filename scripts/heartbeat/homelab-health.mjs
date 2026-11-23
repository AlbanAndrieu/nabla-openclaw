#!/usr/bin/env node
// Homelab health collector for the OpenClaw heartbeat (TrueNAS and Workstation).
// Read-only HTTP probes. Prints NO_REPLY unless an anomaly appeared or cleared;
// the model only relays this text. Ongoing anomalies go to the morning briefing.
import { execFile } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";
import { vercelFinopsCheck, vercelReportPath } from "./vercel-finops.mjs";

const TRUENAS = "172.17.0.24";
export const WORKSTATION = "172.17.0.57";
const PROM = `http://${TRUENAS}:9090`;
const HOSTS = { TrueNAS: 'job="truenas_node"', Workstation: `instance="${WORKSTATION}:9100"` };
const FS = 'fstype!~"tmpfs|devtmpfs|overlay|squashfs|ramfs|nsfs|tracefs|fusectl|autofs|fuse.lxcfs"';
const LITELLM = { TrueNAS: "http://litellm:4000", Workstation: `http://${WORKSTATION}:4000` };
export const STATE = process.env.HOMELAB_HEALTH_STATE
  ?? join(process.env.HOME ?? ".", ".openclaw/nabla-heartbeat/homelab-health.json");
// The coder agent cannot reach the LAN: each of its sessions is seeded from
// this workspace, so the heartbeat leaves it the current anomalies there.
export const CODER_STATUS = process.env.CODER_STATUS_FILE
  ?? join(process.env.HOME ?? ".", ".openclaw/workspace-coder/status/homelab-health.json");
// The coder's own LiteLLM key (file SecretRef): /key/info on it returns only
// its spend and budget. The key is sent to LiteLLM and nowhere else.
export const CODER_KEY = process.env.CODER_LITELLM_KEY_FILE
  ?? join(process.env.HOME ?? ".", ".openclaw/credentials/litellm/coder.key");
// The 09:00 tech digest archives the titles it publishes: no archive means its
// model answered without running the pipeline (invented digests, 20 and 23/11).
export const DIGEST_ARCHIVE = join(process.env.HOME ?? ".", ".openclaw/workspace/archive/tech-news-digest");
let coderBudgetSeen = null;
const ICON = { crit: "🔴", warn: "🟠", unknown: "⚪" };
const RANK = { crit: 0, warn: 1, unknown: 2 };
const MAX_LINES = 40;
// Gateway CLI of the packaged image (`cd /app && node openclaw.mjs`).
export const OPENCLAW_CLI = process.env.OPENCLAW_CLI ?? "/app/openclaw.mjs";
// A coder run recorded "ok" below either bound ran no tool: on 23/11 the
// fastapi-sample job reported PASS in 17-30 s with ~180 output tokens (the
// report alone), while its `pytest --cov` takes ~80 s by itself.
export const HOLLOW_RUN = { minMs: 60_000, minOutputTokens: 400 };

async function getJson(url) {
  const res = await fetch(url, { signal: AbortSignal.timeout(10_000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const query = async (get, expr) =>
  (await get(`${PROM}/api/v1/query?query=${encodeURIComponent(expr)}`)).data.result;
const value = (sample) => Number(sample?.value[1] ?? 0);

export function dockerAnomalies(containers) {
  return containers.flatMap(({ Names, State, Status, Health }) => {
    const name = Names[0].replace(/^\//, "");
    const code = /^Exited \((\d+)\)/.exec(Status)?.[1];
    const reason = State === "restarting" ? "redémarre en boucle"
      : State === "dead" ? "mort"
      : Health?.Status === "unhealthy" || /\(unhealthy\)/.test(Status) ? "unhealthy"
      : State === "exited" && code !== "0" ? `arrêté (code ${code ?? "?"})`
      : null;
    return reason ? [[`docker:${name}`, "warn", `Conteneur TrueNAS ${name} : ${reason}`]] : [];
  });
}

const usd = (n) => (typeof n === "number" && Number.isFinite(n) && n >= 0 ? n : null);

// Spend, cap and reset date only, from a LiteLLM /key/info payload.
export function coderBudgetFrom(payload) {
  const info = payload?.info ?? {};
  const spend = usd(info.spend);
  const max = usd(info.max_budget);
  if (spend === null || max === null || max === 0) return null;
  const reset = Date.parse(info.budget_reset_at ?? "");
  return { spend: Math.round(spend * 100) / 100, max_budget: max, budget_duration: info.budget_duration ?? null,
    budget_reset_at: Number.isFinite(reset) ? new Date(reset).toISOString() : null };
}

export function coderBudgetLine(budget = coderBudgetSeen) {
  if (!budget) return "⚪ Budget LiteLLM du coder : non mesuré";
  const pct = (100 * budget.spend) / budget.max_budget;
  const icon = pct >= 100 ? "🔴" : pct >= 80 ? "🟠" : "✅";
  const reset = budget.budget_reset_at
    ? `, remise à zéro le ${new Date(budget.budget_reset_at).toLocaleDateString("fr-FR", { timeZone: "Europe/Paris" })}` : "";
  return `${icon} Budget LiteLLM du coder : ${budget.spend.toFixed(2)} / ${budget.max_budget} USD (${pct.toFixed(0)} %)${reset}`;
}

// Latest "ok" run of each coder job (`cron runs` entries), flagged when it ran no tool.
// It stays flagged until a later run of the same job does real work.
export function hollowCoderRuns(entries) {
  const latest = new Map();
  for (const run of entries) {
    if (run.status !== "ok" || !run.sessionKey?.startsWith("agent:coder:")) continue;
    if (!(latest.get(run.jobId)?.ts >= run.ts)) latest.set(run.jobId, run);
  }
  return [...latest.values()]
    .filter((run) => run.durationMs < HOLLOW_RUN.minMs || run.usage?.output_tokens < HOLLOW_RUN.minOutputTokens)
    .map((run) => [`coderruns:${run.jobId}`, "warn", `Run coder ${run.jobName ?? run.jobId} « ok » en `
      + `${Number.isFinite(run.durationMs) ? Math.round(run.durationMs / 1000) : "?"} s, `
      + `${run.usage?.output_tokens ?? "?"} tokens de sortie : aucun outil exécuté, compte rendu non fondé`]);
}

// execFile's message is the command line; the cause is the CLI's first stderr line.
const openclawCli = (args) => promisify(execFile)(process.execPath, [OPENCLAW_CLI, ...args],
  { timeout: 25_000, maxBuffer: 4 << 20 }).then(({ stdout }) => stdout, (err) => {
  throw new Error(err.killed ? "délai dépassé" : err.stderr?.trim().split("\n")[0] || "CLI OpenClaw en échec");
});

// Each check returns [key, severity, text]; keys start with the check name so
// an unreachable source keeps its previous anomalies instead of "resolving" them.
export const checks = {
  async alerts(get) {
    const { data } = await get(`${PROM}/api/v1/alerts`);
    return data.alerts
      .filter((a) => a.state === "firing" && a.labels.severity !== "info")
      .map(({ labels }) => {
        const id = Object.entries(labels).filter(([k]) => k !== "severity").sort()
          .map(([k, v]) => `${k}=${v}`).join(",");
        // The job names the exporter or service; the instance is only an IP:port.
        const where = [labels.job ?? labels.instance, labels.mountpoint].filter(Boolean).join(" ");
        return [`alerts:${id}`, labels.severity === "critical" ? "crit" : "warn",
          `Alerte ${labels.alertname}${where ? ` (${where})` : ""}`];
      });
  },
  async targets(get) {
    const [{ data: targets }, { data: alerts }] = await Promise.all([
      get(`${PROM}/api/v1/targets?state=active`), get(`${PROM}/api/v1/alerts`)]);
    const alerted = new Set(alerts.alerts.map((a) => a.labels.instance));
    return targets.activeTargets
      .filter((t) => t.health !== "up" && !alerted.has(t.labels.instance))
      .map((t) => [`targets:${t.labels.job}`, "warn", `Cible Prometheus ${t.labels.job} injoignable`]);
  },
  async hosts(get) {
    const out = [];
    for (const [host, sel] of Object.entries(HOSTS)) {
      const q = (expr) => query(get, expr);
      if (!(await q(`node_memory_MemTotal_bytes{${sel}}`)).length) {
        out.push([`hosts:${host}:metrics`, "unknown", `${host} : CPU, RAM et disque non collectés par Prometheus`]);
        continue;
      }
      const [[cpu], [mem], disks, pools, units] = await Promise.all([
        q(`100 * (1 - avg(rate(node_cpu_seconds_total{${sel},mode="idle"}[15m])))`),
        // MemAvailable leaves out the ZFS ARC the kernel reclaims down to c_min: count it as available,
        // like nabla-compose's TrueNASHostOutOfMemory rule; hosts without ZFS metrics fall back to MemAvailable.
        q(`100 * (1 - (node_memory_MemAvailable_bytes{${sel}} + (clamp_min(node_zfs_arc_size{${sel}} - node_zfs_arc_c_min{${sel}}, 0)`
          + ` or node_memory_MemAvailable_bytes{${sel}} * 0)) / node_memory_MemTotal_bytes{${sel}})`),
        q(`100 * (1 - node_filesystem_avail_bytes{${sel},${FS}} / node_filesystem_size_bytes{${sel},${FS}}) >= 85`),
        q(`node_zfs_zpool_state{${sel},state!="online"} == 1`),
        q(`node_systemd_unit_state{${sel},state="failed"} == 1`),
      ]);
      if (value(cpu) >= 90) out.push([`hosts:${host}:cpu`, "warn", `${host} : CPU ${value(cpu).toFixed(0)} % sur 15 min`]);
      if (value(mem) >= 90) out.push([`hosts:${host}:mem`, value(mem) >= 95 ? "crit" : "warn", `${host} : RAM ${value(mem).toFixed(0)} %`]);
      // Bind mounts repeat a device: report it once, under its shortest mountpoint.
      const byDevice = new Map(disks.toSorted((a, b) => b.metric.mountpoint.length - a.metric.mountpoint.length)
        .map((d) => [d.metric.device, d]));
      for (const d of byDevice.values()) {
        out.push([`hosts:${host}:disk:${d.metric.mountpoint}`, value(d) >= 95 ? "crit" : "warn",
          `${host} : disque ${d.metric.mountpoint} plein à ${value(d).toFixed(0)} %`]);
      }
      for (const p of pools) out.push([`hosts:${host}:zpool:${p.metric.zpool}`, "crit", `${host} : pool ZFS ${p.metric.zpool} ${p.metric.state}`]);
      for (const u of units) out.push([`hosts:${host}:unit:${u.metric.name}`, "warn", `${host} : service systemd ${u.metric.name} en échec`]);
    }
    return out;
  },
  async gatus(get) {
    const endpoints = await get(`http://${TRUENAS}:8085/api/v1/endpoints/statuses?page=1&pageSize=500`);
    return endpoints.filter((e) => e.results?.length && !e.results.at(-1).success)
      .map((e) => [`gatus:${e.key}`, "warn", `Sonde Gatus ${e.group ? `${e.group}/` : ""}${e.name} en échec`]);
  },
  async docker(get) {
    // The read-only proxy publishes no host port since 10/11: reached on the docker-proxy network.
    return dockerAnomalies(await get("http://docker-socket-proxy:2375/containers/json?all=1"));
  },
  async smart(get) {
    const { data } = await get(`http://${TRUENAS}:31054/api/summary`);
    return Object.entries(data.summary).filter(([, s]) => s.device.device_status !== 0)
      .map(([wwn, { device: d }]) => [`smart:${wwn}`, "crit", `Disque ${d.device_name} (${d.model_name}) : SMART en échec (Scrutiny)`]);
  },
  async vercel(_get, prev) {
    // Snapshot updated separately from an authenticated workstation.
    // Each hourly heartbeat only reads a local private 0600 report.
    return vercelFinopsCheck(prev, vercelReportPath(STATE));
  },
  async services(get) {
    const sel = HOSTS.Workstation;
    const [health, [age], [up]] = await Promise.all([
      query(get, `workstation_container_healthy{${sel}}`),
      query(get, `time() - node_textfile_mtime_seconds{${sel},file=~".*/docker-health.prom"}`),
      query(get, `up{${sel}}`),
    ]);
    // An exporter that is down is already reported by the hosts check.
    if (!health.length) {
      return value(up) === 1 ? [["services:Workstation:missing", "unknown", "Workstation : santé de postgres et redis non collectée"]] : [];
    }
    // The timer rewrites the file every minute: older values say nothing.
    if (value(age) > 300) {
      return [["services:Workstation:stale", "unknown", `Workstation : santé de postgres et redis figée depuis ${Math.round(value(age) / 60)} min`]];
    }
    return health.filter((s) => value(s) < 1)
      .map((s) => [`services:Workstation:${s.metric.container}`, "warn", `Workstation : conteneur ${s.metric.container} arrêté ou non sain`]);
  },
  // Restic touches /var/lib/restic/last-success.prom after each successful nightly
  // backup; node_exporter exports its mtime. Zabbix alerts at 26 h too.
  async backup(get) {
    const sel = HOSTS.Workstation;
    const [[age], [up]] = await Promise.all([
      query(get, `time() - node_textfile_mtime_seconds{${sel},file=~".*/last-success.prom"}`),
      query(get, `up{${sel}}`),
    ]);
    if (!age) {
      return value(up) === 1 ? [["backup:Workstation:missing", "unknown", "Workstation : aucune sauvegarde Restic réussie connue"]] : [];
    }
    const hours = value(age) / 3600;
    if (hours <= 26) return [];
    return [["backup:Workstation:stale", hours > 72 ? "crit" : "warn",
      `Workstation : dernière sauvegarde Restic réussie il y a ${Math.round(hours)} h`]];
  },
  async digest(_get, _prev, now = Date.now(), dir = DIGEST_ARCHIVE) {
    if (!existsSync(dir)) return []; // no digest job on this Gateway
    const paris = (t) => new Date(t).toLocaleString("sv-SE", { timeZone: "Europe/Paris" });
    // Before 09:10 the last expected run is yesterday's (12 h back, whatever the DST).
    const day = paris(paris(now).slice(11) >= "09:10" ? now : now - 12 * 3600_000).slice(0, 10);
    if (existsSync(join(dir, `daily-${day}.md`))) return [];
    return [[`digest:${day}`, "warn",
      `Digest tech du ${day} sans archive : pipeline non exécuté, digest livré probablement inventé`]];
  },
  async coderbudget(get, prev, keyFile = CODER_KEY) {
    let key;
    try {
      key = readFileSync(keyFile, "utf8").trim();
    } catch {
      return []; // no coder agent on this Gateway
    }
    const res = await fetch(`${LITELLM.TrueNAS}/key/info`, {
      headers: { Authorization: `Bearer ${key}` }, signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    coderBudgetSeen = coderBudgetFrom(await res.json());
    if (!coderBudgetSeen) throw new Error("réponse /key/info sans budget");
    const pct = (100 * coderBudgetSeen.spend) / coderBudgetSeen.max_budget;
    if (pct < 80) return [];
    return [[`coderbudget:${pct >= 100 ? "exhausted" : "high"}`, pct >= 100 ? "crit" : "warn",
      coderBudgetLine(coderBudgetSeen).replace(/^\S+ /, "")]];
  },
  async litellm(get) {
    const out = [];
    for (const [host, base] of Object.entries(LITELLM)) {
      // Unreachable LiteLLM is the anomaly itself, not a missing source.
      const r = await get(`${base}/health/readiness`).catch((err) => ({ status: err.message }));
      if (r.status !== "healthy" || r.db !== "connected") {
        out.push([`litellm:${host}`, "crit", `LiteLLM ${host} : ${r.status ?? "?"}, base ${r.db ?? "?"}`]);
      }
    }
    return out;
  },
  // Read-only run history (SQLite, so through the CLI). Newest first: the
  // nightly coder runs sit well inside the last 100 "ok" runs.
  async coderruns(_get, _prev, cli = openclawCli, workspace = dirname(dirname(CODER_STATUS))) {
    if (!existsSync(workspace)) return []; // no coder agent on this Gateway
    const page = JSON.parse(await cli(["cron", "runs", "--all", "--status", "ok", "--limit", "100", "--timeout", "20000", "--json"]));
    return hollowCoderRuns(page.entries ?? []);
  },
};

export async function collect(prev, get = getJson) {
  const names = Object.keys(checks);
  const results = await Promise.allSettled(names.map((name) => checks[name](get, prev)));
  return results.flatMap((r, i) => {
    if (r.status === "fulfilled") return r.value;
    const name = names[i];
    const kept = Object.entries(prev.seen ?? {})
      .filter(([key]) => key.startsWith(`${name}:`) && key !== `${name}:unreachable`)
      .map(([key, v]) => [key, v.sev, v.text]);
    return [[`${name}:unreachable`, "unknown", `Source ${name} injoignable (${r.reason?.message ?? r.reason})`], ...kept];
  });
}

export function diff(prev, current, now) {
  const seen = {};
  const fresh = [];
  const ongoing = [];
  for (const [key, sev, text] of current) {
    seen[key] = { sev, text, since: prev.seen?.[key]?.since ?? now };
    (prev.seen?.[key] ? ongoing : fresh).push(seen[key]);
  }
  const gone = Object.entries(prev.seen ?? {}).filter(([key]) => !seen[key]).map(([, v]) => v);
  return { seen, fresh, gone, ongoing };
}

export function listLines(items, icon, max = MAX_LINES) {
  const sorted = [...items].sort((a, b) => RANK[a.sev] - RANK[b.sev]);
  const lines = sorted.slice(0, max).map((item) => `${icon ?? ICON[item.sev]} ${item.text}`);
  if (items.length > max) lines.push(`… et ${items.length - max} autres`);
  return lines;
}

export function render({ fresh, gone, ongoing }, now) {
  if (!fresh.length && !gone.length) return "NO_REPLY";
  const stamp = new Date(now).toLocaleString("fr-FR", { timeZone: "Europe/Paris", dateStyle: "short", timeStyle: "short" });
  const lines = [`🩺 Homelab, ${stamp}`];
  const section = (title, items, icon) => {
    if (items.length) lines.push("", `${title} (${items.length})`, ...listLines(items, icon));
  };
  section("Nouveau", fresh);
  section("Résolu", gone, "✅");
  if (ongoing.length) lines.push("", `Toujours en cours : ${ongoing.length} (détail dans le briefing du matin)`);
  return lines.join("\n");
}

// Severity, text and start time only: the texts never carry a credential.
export function coderStatus(seen, now, budget = coderBudgetSeen) {
  const anomalies = Object.values(seen).sort((a, b) => RANK[a.sev] - RANK[b.sev])
    .map(({ sev, text, since }) => ({ sev, text, since: new Date(since).toISOString() }));
  const counts = { crit: 0, warn: 0, unknown: 0 };
  for (const { sev } of anomalies) counts[sev] += 1;
  return { generated_at: new Date(now).toISOString(), sources: Object.keys(checks), counts, anomalies,
    coder_budget: budget };
}

function writeCoderStatus(seen, now) {
  if (!existsSync(dirname(dirname(CODER_STATUS)))) return; // no coder agent on this Gateway
  try {
    mkdirSync(dirname(CODER_STATUS), { recursive: true, mode: 0o700 });
    writeFileSync(`${CODER_STATUS}.tmp`, JSON.stringify(coderStatus(seen, now), null, 1), { mode: 0o600 });
    renameSync(`${CODER_STATUS}.tmp`, CODER_STATUS);
  } catch {
    // Best effort: the heartbeat itself must never fail on the coder copy.
  }
}

async function main() {
  const now = Date.now();
  let prev = {};
  try {
    prev = JSON.parse(readFileSync(STATE, "utf8"));
  } catch {
    // First run or unreadable state: every current anomaly is reported as new.
  }
  const changes = diff(prev, await collect(prev), now);
  console.log(render(changes, now));
  mkdirSync(dirname(STATE), { recursive: true, mode: 0o700 });
  writeFileSync(`${STATE}.tmp`, JSON.stringify({ seen: changes.seen }), { mode: 0o600 });
  renameSync(`${STATE}.tmp`, STATE);
  writeCoderStatus(changes.seen, now);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await main();
