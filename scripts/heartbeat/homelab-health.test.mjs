import assert from "node:assert/strict";
import { test } from "node:test";
import { checks, collect, diff, dockerAnomalies, render } from "./homelab-health.mjs";

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
