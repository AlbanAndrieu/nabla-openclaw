import assert from "node:assert/strict";
import { test } from "node:test";
import { checks, coderBudgetFrom, coderBudgetLine, coderStatus, collect, diff, dockerAnomalies, failingCoderJobs, hollowCoderRuns, listLines, masterPushRuns, render } from "./homelab-health.mjs";

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

test("targets: planned exporters and alerted instances are not reported", async () => {
  const target = (job, extra = {}) => ({ health: "down", labels: { job, instance: `172.17.0.24:${job.length}`, ...extra } });
  const get = async (url) => (url.includes("/targets") ? { data: { activeTargets: [
    target("jellyfin", { operational_state: "planned" }), target("haproxy"), target("opensearch"),
    { health: "up", labels: { job: "node", instance: "x" } }] } }
    : { data: { alerts: [{ labels: { instance: "172.17.0.24:10" } }] } });
  assert.deepEqual(await checks.targets(get), [["targets:haproxy", "warn", "Cible Prometheus haproxy injoignable"]]);
});

test("list lines: the last single item replaces its overflow line", () => {
  const items = (n) => Array.from({ length: n }, (_, i) => ({ sev: "warn", text: `a${i}` }));
  assert.deepEqual(listLines(items(3), undefined, 2), ["🟠 a0", "🟠 a1", "🟠 a2"]);
  assert.deepEqual(listLines(items(4), undefined, 2), ["🟠 a0", "🟠 a1", "… et 2 autres"]);
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

test("hosts: RAM counts the reclaimable ZFS ARC as available, with a MemAvailable fallback", async () => {
  const queries = [];
  const get = async (url) => {
    const q = decodeURIComponent(url.split("query=")[1]);
    queries.push(q);
    return { data: { result: q.startsWith("node_memory_MemTotal_bytes") ? [{ metric: {}, value: [0, "1"] }] : [] } };
  };
  await checks.hosts(get);
  const mem = queries.find((q) => q.includes("MemAvailable") && q.startsWith("100 *"));
  assert.match(mem, /clamp_min\(node_zfs_arc_size\{job="truenas_node"\} - node_zfs_arc_c_min\{job="truenas_node"\}, 0\)/);
  assert.match(mem, / or node_memory_MemAvailable_bytes\{job="truenas_node"\} \* 0\)/);
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

test("coder runs: the latest ok run of a coder job that ran no tool is flagged", async () => {
  const run = (jobId, ts, durationMs, output_tokens, extra) => ({ jobId, jobName: jobId, ts, status: "ok", durationMs,
    usage: { output_tokens }, sessionKey: `agent:coder:cron:${jobId}:run:s${ts}`, ...extra });
  const entries = [
    run("daily", 1, 600_000, 5_000), // an older real run does not hide the latest one
    run("daily", 2, 23_000, 180), // 23/11: PASS in 23 s, report only
    run("daily", 3, 70_000, 900, { status: "error" }),
    run("pass", 3, 548_000, 6_000), // nabla-compose pass with real tool calls
    run("terse", 3, 90_000, 150), // long enough, but no tool call could fit in 150 tokens
    run("nousage", 3, 120_000, undefined),
    // 24/11: one model call, invented SHA and PR; a real pass reads its prompt back from cache.
    run("onecall", 3, 65_000, 795, { usage: { input_tokens: 8_760, output_tokens: 795 } }),
    run("toolloop", 3, 548_000, 2_152, { usage: { input_tokens: 45_573, output_tokens: 2_152, cache_read_tokens: 588_416 } }),
    run("digest", 3, 5_000, 100, { sessionKey: "agent:main:cron:digest:run:s3" }),
    // 28/11: a pass with nothing new answers NO_REPLY, so a hollow one is silent on Telegram.
    run("silent", 3, 9_000, 120, { summary: "NO_REPLY" }),
    run("quiet", 3, 600_000, 7_000, { summary: "NO_REPLY", usage: { input_tokens: 9_000, output_tokens: 7_000, cache_read_tokens: 400_000 } }),
  ];
  const flagged = hollowCoderRuns(entries);
  assert.deepEqual(flagged.map(([key, sev]) => [key, sev]),
    [["coderruns:daily", "warn"], ["coderruns:terse", "warn"], ["coderruns:onecall", "warn"], ["coderruns:silent", "warn"]]);
  assert.equal(flagged[0][2], "Run coder daily « ok » en 23 s, 180 tokens de sortie : aucun outil exécuté, compte rendu non fondé");
  assert.deepEqual(hollowCoderRuns([...entries, run("daily", 4, 300_000, 4_000)]).map(([key]) => key),
    ["coderruns:terse", "coderruns:onecall", "coderruns:silent"]);

  const { mkdtempSync } = await import("node:fs");
  const { tmpdir } = await import("node:os");
  let args;
  const cli = async (a) => { args = a; return JSON.stringify({ entries }); };
  assert.deepEqual(await checks.coderruns(null, {}, cli, "/nonexistent/workspace-coder"), []);
  assert.equal(args, undefined);
  assert.equal((await checks.coderruns(null, {}, cli, mkdtempSync(`${tmpdir()}/coder-`))).length, 4);
  assert.deepEqual(args.slice(0, 5), ["cron", "runs", "--all", "--limit", "200"]);
});

test("coder runs: a push refused on master in the last 24 h is flagged, whatever the status", () => {
  const now = Date.parse("2026-11-27T23:00:00Z");
  const run = (jobId, hoursAgo, summary, status = "error") => ({ jobId, jobName: jobId, ts: now - hoursAgo * 3600_000, status,
    summary, sessionKey: `agent:coder:cron:${jobId}:run:s1` });
  const flagged = masterPushRuns([
    // 27/11, quoted from the reports.
    run("bababou", 13, "Push refusé sur `master` par les règles du dépôt (`Changes must be made through a pull request`)"),
    run("yubikey", 8, "le push direct est refusé (GH013, repository rule violations)"),
    run("alban", 1, "Aucun commit, aucune PR (BLOQUÉ: push sur master refusé)", "ok"),
    run("old", 30, "GH013"),
    run("clean", 1, "PR : https://github.com/AlbanAndrieu/x/pull/3, jamais de push sur master", "ok"),
    { ...run("main", 1, "GH013"), sessionKey: "agent:main:cron:x" },
  ], now);
  assert.deepEqual(flagged.map(([key]) => key), ["coderruns:push:bababou", "coderruns:push:yubikey", "coderruns:push:alban"]);
  assert.equal(flagged[1][2], "Run coder yubikey du 27/11/2026 16:00 : push refusé sur master, la passe doit pousser sa branche et ouvrir une PR");
});

test("coder jobs: an enabled job failing two runs in a row stays open with its cause", async () => {
  const job = (id, consecutiveErrors, extra) => ({ id, name: id, enabled: true,
    state: { consecutiveErrors, lastError: "cron: isolated agent setup timed out before runner start" }, ...extra });
  const jobs = [
    job("compose", 6), // 20-26/11: setup watchdog every night
    job("yubikey", 5, { state: { consecutiveErrors: 5, lastError: `${"x".repeat(200)}\nActions tentées :` } }),
    job("referee", 0),
    job("once", 1), // a single failure is OpenClaw's own alert business
    job("off", 4, { enabled: false }),
  ];
  const flagged = failingCoderJobs(jobs);
  assert.deepEqual(flagged.map(([key, sev]) => [key, sev]), [["coderjobs:compose", "warn"], ["coderjobs:yubikey", "warn"]]);
  assert.equal(flagged[0][2], "Job coder compose en échec 6 fois de suite : cron: isolated agent setup timed out before runner start");
  assert.equal(flagged[1][2], `Job coder yubikey en échec 5 fois de suite : ${"x".repeat(160)}`);

  const { mkdtempSync } = await import("node:fs");
  const { tmpdir } = await import("node:os");
  let args;
  const cli = async (a) => { args = a; return JSON.stringify({ jobs, total: jobs.length, hasMore: false }); };
  assert.deepEqual(await checks.coderjobs(null, {}, cli, "/nonexistent/workspace-coder"), []);
  assert.equal(args, undefined);
  assert.equal((await checks.coderjobs(null, {}, cli, mkdtempSync(`${tmpdir()}/coder-`))).length, 2);
  assert.deepEqual(args.slice(0, 4), ["cron", "list", "--agent", "coder"]);
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
