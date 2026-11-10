#!/usr/bin/env node
// Homelab health collector for the OpenClaw heartbeat (TrueNAS and Workstation).
// Read-only HTTP probes. Prints NO_REPLY unless an anomaly appeared or cleared;
// the model only relays this text. Ongoing anomalies go to the morning briefing.
import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

const TRUENAS = "172.17.0.24";
export const WORKSTATION = "172.17.0.57";
const PROM = `http://${TRUENAS}:9090`;
const HOSTS = { TrueNAS: 'job="truenas_node"', Workstation: `instance="${WORKSTATION}:9100"` };
const FS = 'fstype!~"tmpfs|devtmpfs|overlay|squashfs|ramfs|nsfs|tracefs|fusectl|autofs|fuse.lxcfs"';
const LITELLM = { TrueNAS: "http://litellm:4000", Workstation: `http://${WORKSTATION}:4000` };
export const STATE = process.env.HOMELAB_HEALTH_STATE
  ?? join(process.env.HOME ?? ".", ".openclaw/nabla-heartbeat/homelab-health.json");
const ICON = { crit: "🔴", warn: "🟠", unknown: "⚪" };
const RANK = { crit: 0, warn: 1, unknown: 2 };
const MAX_LINES = 40;

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
        const where = [labels.instance ?? labels.job, labels.mountpoint].filter(Boolean).join(" ");
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
        q(`100 * (1 - node_memory_MemAvailable_bytes{${sel}} / node_memory_MemTotal_bytes{${sel}})`),
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
    return dockerAnomalies(await get(`http://${TRUENAS}:2375/containers/json?all=1`));
  },
  async smart(get) {
    const { data } = await get(`http://${TRUENAS}:31054/api/summary`);
    return Object.entries(data.summary).filter(([, s]) => s.device.device_status !== 0)
      .map(([wwn, { device: d }]) => [`smart:${wwn}`, "crit", `Disque ${d.device_name} (${d.model_name}) : SMART en échec (Scrutiny)`]);
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
};

export async function collect(prev, get = getJson) {
  const names = Object.keys(checks);
  const results = await Promise.allSettled(names.map((name) => checks[name](get)));
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
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await main();
