import assert from "node:assert/strict";
import { test } from "node:test";
import { checks, coderBudgetFrom, coderBudgetLine, coderStatus, collect, diff, dockerAnomalies, render } from "./homelab-health.mjs";

const NOON = Date.parse("2026-11-04T11:00:00Z");

test("only changes are reported, then silence", () => {
  const first = diff({}, [["gatus:a", "warn", "Sonde a en échec"]], NOON);
  assert.match(render(first, NOON), /Nouveau \(1\)\n🟠 Sonde a en échec/);
  const second = diff({ seen: first.seen }, [["gatus:a", "warn", "Sonde a en échec"]], NOON + 1);
  assert.equal(render(second, NOON + 1), "NO_REPLY");
  assert.equal(second.seen["gatus:a"].since, NOON);
  const third = diff({ seen: second.seen }, [], NOON + 2);
  assert.match(render(third, NOON + 2), /Résolu \(1\)\n✅ Sonde a en échec/);
});

test("an unreachable source keeps its anomalies instead of resolving them", async (t) => {
  const prev = { seen: { "gatus:a": { sev: "warn", text: "Sonde a", since: 1 } } };
  for (const name of Object.keys(checks)) {
    t.mock.method(checks, name, async () => (name === "gatus" ? Promise.reject(new Error("timeout")) : []));
  }
  const current = await collect(prev);
  assert.deepEqual(current, [["gatus:unreachable", "unknown", "Source gatus injoignable (timeout)"], ["gatus:a", "warn", "Sonde a"]]);
  assert.equal(diff(prev, current, NOON).gone.length, 0);
});

test("alerts name the exporter by its job, not its IP:port", async () => {
  const labels = { alertname: "NablaExporterTargetDown", instance: "172.17.0.24:9114", job: "opensearch", severity: "warning" };
  const get = async () => ({ data: { alerts: [{ state: "firing", labels }] } });
  assert.deepEqual(await checks.alerts(get), [["alerts:alertname=NablaExporterTargetDown,instance=172.17.0.24:9114,job=opensearch",
    "warn", "Alerte NablaExporterTargetDown (opensearch)"]]);
});

test("hosts: a device mounted twice is reported once, at its shortest mountpoint", async () => {
  const sample = (metric, v) => ({ metric, value: [0, String(v)] });
  const get = async (url) => {
    const q = decodeURIComponent(url.split("query=")[1]);
    const result = q.startsWith("node_memory_MemTotal_bytes") ? [sample({}, 1)]
      : q.includes(">= 85") ? [sample({ device: "/dev/vg/docker", mountpoint: "/var/lib/containerd" }, 90),
        sample({ device: "/dev/vg/docker", mountpoint: "/docker" }, 90)]
      : [];
    return { data: { result } };
  };
  assert.deepEqual((await checks.hosts(get)).map(([, , text]) => text),
    ["TrueNAS : disque /docker plein à 90 %", "Workstation : disque /docker plein à 90 %"]);
});

test("services: Workstation postgres and redis health, stale or missing file", async () => {
  const sample = (metric, v) => ({ metric, value: [0, String(v)] });
  const fake = ({ health, age = 30, up = 1 }) => async (url) => {
    const q = decodeURIComponent(url.split("query=")[1]);
    const result = q.startsWith("workstation_container_healthy") ? health
      : q.startsWith("time()") ? [sample({}, age)] : [sample({}, up)];
    return { data: { result } };
  };
  const texts = async (opts) => (await checks.services(fake(opts))).map(([, , text]) => text);
  const both = [sample({ container: "postgres" }, 1), sample({ container: "redis" }, 0)];
  assert.deepEqual(await texts({ health: both }), ["Workstation : conteneur redis arrêté ou non sain"]);
  assert.deepEqual(await texts({ health: both, age: 900 }), ["Workstation : santé de postgres et redis figée depuis 15 min"]);
  assert.deepEqual(await texts({ health: [] }), ["Workstation : santé de postgres et redis non collectée"]);
  assert.deepEqual(await texts({ health: [], up: 0 }), []);
});

test("backup: Workstation Restic freshness from the textfile mtime", async () => {
  const sample = (v) => ({ metric: {}, value: [0, String(v)] });
  const fake = ({ age, up = 1 }) => async (url) => {
    const q = decodeURIComponent(url.split("query=")[1]);
    const result = q.startsWith("time()") ? (age === undefined ? [] : [sample(age)]) : [sample(up)];
    return { data: { result } };
  };
  const found = async (opts) => (await checks.backup(fake(opts))).map(([, sev, text]) => [sev, text]);
  assert.deepEqual(await found({ age: 3 * 3600 }), []);
  assert.deepEqual(await found({ age: 30 * 3600 }), [["warn", "Workstation : dernière sauvegarde Restic réussie il y a 30 h"]]);
  assert.deepEqual(await found({ age: 80 * 3600 }), [["crit", "Workstation : dernière sauvegarde Restic réussie il y a 80 h"]]);
  assert.deepEqual(await found({}), [["unknown", "Workstation : aucune sauvegarde Restic réussie connue"]]);
  assert.deepEqual(await found({ up: 0 }), []);
});

test("docker: crashed, unhealthy and restarting containers only", () => {
  const found = dockerAnomalies([
    { Names: ["/ok"], State: "running", Status: "Up 2 hours (healthy)", Health: { Status: "healthy" } },
    { Names: ["/init"], State: "exited", Status: "Exited (0) 3 hours ago" },
    { Names: ["/sync"], State: "exited", Status: "Exited (2) 3 hours ago" },
    { Names: ["/web"], State: "running", Status: "Up 1 hour (unhealthy)", Health: { Status: "unhealthy" } },
    { Names: ["/loop"], State: "restarting", Status: "Restarting (1) 5 seconds ago" },
  ]);
  assert.deepEqual(found.map(([, , text]) => text), [
    "Conteneur TrueNAS sync : arrêté (code 2)",
    "Conteneur TrueNAS web : unhealthy",
    "Conteneur TrueNAS loop : redémarre en boucle",
  ]);
});

test("heartbeat passes previous state to the Vercel snapshot check without network", async (t) => {
  const previous = { seen: { "vercel:cpu:WATCH": { sev: "warn", text: "previous", since: 1 } } };
  let visited = false;
  for (const name of Object.keys(checks)) {
    t.mock.method(checks, name, async (_get, prev) => {
      if (name === "vercel") {
        visited = true;
        assert.equal(prev, previous);
      }
      return [];
    });
  }
  assert.deepEqual(await collect(previous, () => { throw Error("HTTP must not run"); }), []);
  assert.equal(visited, true);
});

test("coder status: anomalies ranked by severity, counted, dated, nothing else", () => {
  const seen = {
    "gatus:a": { sev: "warn", text: "Sonde Gatus web/a en échec", since: 1_000 },
    "litellm:TrueNAS": { sev: "crit", text: "LiteLLM TrueNAS : down, base ?", since: 2_000 },
  };
  const status = coderStatus(seen, 3_000);
  assert.equal(status.generated_at, new Date(3_000).toISOString());
  assert.deepEqual(status.counts, { crit: 1, warn: 1, unknown: 0 });
  assert.deepEqual(status.anomalies.map((a) => a.sev), ["crit", "warn"]);
  assert.deepEqual(Object.keys(status.anomalies[0]), ["sev", "text", "since"]);
  assert.ok(status.sources.includes("gatus") && status.sources.includes("alerts"));
});

test("coder budget: spend and cap from /key/info, nothing else, junk refused", () => {
  const payload = { key: "hashed", info: { key_alias: "openclaw-coder", spend: 3.14159, max_budget: 11,
    budget_duration: "7d", budget_reset_at: "2026-11-25T00:00:00Z", token: "never-copied" } };
  const budget = coderBudgetFrom(payload);
  assert.deepEqual(budget, { spend: 3.14, max_budget: 11, budget_duration: "7d", budget_reset_at: "2026-11-25T00:00:00.000Z" });
  assert.match(coderBudgetLine(budget), /^✅ Budget LiteLLM du coder : 3\.14 \/ 11 USD \(29 %\), remise à zéro le 25\/11\/2026$/);
  assert.match(coderBudgetLine({ ...budget, spend: 9 }), /^🟠 /);
  assert.match(coderBudgetLine({ ...budget, spend: 11 }), /^🔴 /);
  assert.equal(coderBudgetLine(null), "⚪ Budget LiteLLM du coder : non mesuré");
  for (const info of [{}, { spend: -1, max_budget: 11 }, { spend: 1, max_budget: 0 }, { spend: Number.NaN, max_budget: 11 }]) {
    assert.equal(coderBudgetFrom({ info }), null);
  }
});

test("coder budget check: silent without a key file, warns from 80 %", async (t) => {
  assert.deepEqual(await checks.coderbudget(null, {}, "/nonexistent/coder.key"), []);
  const { mkdtempSync, writeFileSync } = await import("node:fs");
  const { tmpdir } = await import("node:os");
  const keyFile = `${mkdtempSync(`${tmpdir()}/coder-`)}/coder.key`;
  writeFileSync(keyFile, "sk-test\n");
  let auth;
  t.mock.method(globalThis, "fetch", async (url, init) => {
    auth = init.headers.Authorization;
    assert.match(String(url), /\/key\/info$/);
    return new Response(JSON.stringify({ info: { spend: 9.5, max_budget: 11 } }));
  });
  const [[key, sev, text]] = await checks.coderbudget(null, {}, keyFile);
  assert.equal(auth, "Bearer sk-test");
  assert.equal(key, "coderbudget:high");
  assert.equal(sev, "warn");
  assert.match(text, /^Budget LiteLLM du coder : 9\.50 \/ 11 USD \(86 %\)$/);
  assert.equal(coderStatus({}, 0).coder_budget.spend, 9.5);
});

test("digest check: no archive after 09:10 Paris flags an invented digest", async () => {
  const { mkdtempSync, writeFileSync } = await import("node:fs");
  const { tmpdir } = await import("node:os");
  const dir = mkdtempSync(`${tmpdir()}/digest-`);
  const at = (iso) => checks.digest(null, {}, Date.parse(iso), dir);
  assert.deepEqual(await checks.digest(null, {}, NOON, `${dir}/none`), []);
  // 09:05 Paris: today's job may still run, so yesterday's archive is checked.
  assert.equal((await at("2026-11-23T08:05:00Z"))[0][0], "digest:2026-11-22");
  writeFileSync(`${dir}/daily-2026-11-22.md`, "- [Titre]\n");
  assert.deepEqual(await at("2026-11-23T08:05:00Z"), []);
  const [[key, sev, text]] = await at("2026-11-23T08:30:00Z");
  assert.deepEqual([key, sev], ["digest:2026-11-23", "warn"]);
  assert.match(text, /^Digest tech du 2026-11-23 sans archive/);
  // Overnight the anomaly stays open instead of "resolving" at midnight.
  assert.equal((await at("2026-11-23T23:30:00Z"))[0][0], "digest:2026-11-23");
  writeFileSync(`${dir}/daily-2026-11-23.md`, "- [Titre]\n");
  assert.deepEqual(await at("2026-11-23T08:30:00Z"), []);
});
