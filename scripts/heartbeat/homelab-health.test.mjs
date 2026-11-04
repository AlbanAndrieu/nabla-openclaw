import assert from "node:assert/strict";
import { test } from "node:test";
import { checks, collect, diff, dockerAnomalies, recapDue, render } from "./homelab-health.mjs";

const NOON = Date.parse("2026-11-04T11:00:00Z");

test("only changes are reported, then silence", () => {
  const first = diff({}, [["gatus:a", "warn", "Sonde a en échec"]], NOON);
  assert.match(render(first, false, NOON), /Nouveau \(1\)\n🟠 Sonde a en échec/);
  const second = diff({ seen: first.seen }, [["gatus:a", "warn", "Sonde a en échec"]], NOON + 1);
  assert.equal(render(second, false, NOON + 1), "NO_REPLY");
  assert.equal(second.seen["gatus:a"].since, NOON);
  const third = diff({ seen: second.seen }, [], NOON + 2);
  assert.match(render(third, false, NOON + 2), /Résolu \(1\)\n✅ Sonde a en échec/);
});

test("daily recap lists ongoing anomalies once per Paris day, after 08:00", () => {
  const { seen } = diff({}, [["smart:x", "crit", "Disque sda"]], NOON);
  assert.match(render(diff({ seen }, [["smart:x", "crit", "Disque sda"]], NOON), true, NOON), /Toujours en cours \(1\)\n🔴 Disque sda/);
  assert.equal(recapDue({ recapDay: "2026-11-04" }, NOON), false);
  assert.equal(recapDue({ recapDay: "2026-11-03" }, NOON), true);
  assert.equal(recapDue({}, Date.parse("2026-11-04T06:00:00Z")), false);
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
