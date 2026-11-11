import assert from "node:assert/strict";
import { test } from "node:test";
import { diff, render } from "./homelab-health.mjs";
import {
  vercelFinopsAnomalies, readVercelReport, vercelFinopsCheck, vercelReportPath,
} from "./vercel-finops.mjs";

const now = Date.parse("2026-11-11T12:00:00Z");
const sample = (hours, status) => ({
  team: "albanandrieus-projects", source: "vercel-usage-json",
  observedAt: "2026-11-11T11:00:00Z", cpuHours: hours,
  percentOfQuota: hours / 4 * 100, quotaHours: 4,
  cpuMeasured: true, periodVerified: true, freshnessVerified: true, status,
});

test("fresh verified Vercel 30-day usage emits alert only at 50/75/90 %", () => {
  for (const [hours, status, severity] of [
    [1.99, "OK", null], [2, "WATCH", "warn"],
    [3, "INVESTIGATE", "warn"], [3.6, "CRITICAL", "crit"],
  ]) {
    const output = vercelFinopsAnomalies(sample(hours, status), {}, now);
    assert.equal(output.length, severity ? 1 : 0);
    if (severity) {
      assert.equal(output[0][0], `vercel:cpu:${status}`);
      assert.equal(output[0][1], severity);
      assert.match(output[0][2], /Fluid Active CPU/);
    }
  }
});

test("hourly heartbeat only alerts on change, not every run", () => {
  const first = diff({}, vercelFinopsAnomalies(sample(2, "WATCH"), {}, now), now);
  assert.match(render(first, now), /Vercel Fluid Active CPU/);
  const same = diff({ seen: first.seen }, vercelFinopsAnomalies(sample(2.1, "WATCH"), { seen: first.seen }, now + 1), now + 1);
  assert.equal(render(same, now + 1), "NO_REPLY");
  const worse = diff({ seen: same.seen }, vercelFinopsAnomalies(sample(3.7, "CRITICAL"), { seen: same.seen }, now + 2), now + 2);
  assert.match(render(worse, now + 2), /CRITICAL/);
  const recovered = diff({ seen: worse.seen }, vercelFinopsAnomalies(sample(1, "OK"), { seen: worse.seen }, now + 3), now + 3);
  assert.match(render(recovered, now + 3), /Résolu/);
});

test("unavailable or stale evidence never resolves a previous critical alert", () => {
  const prev = { seen: { "vercel:cpu:CRITICAL": {
    sev: "crit", text: "Vercel Fluid Active CPU : 3.70 h / 4 h (92.5 %) — CRITICAL", since: now - 1000,
  } } };
  for (const bad of [null, {}, { ...sample(0.1, "OK"), observedAt: "2026-11-08T00:00:00Z" },
    { ...sample(0.1, "OK"), freshnessVerified: false }]) {
    const state = vercelFinopsAnomalies(bad, prev, now);
    assert.ok(state.some(([key]) => key === "vercel:cpu:CRITICAL"));
    assert.ok(state.some(([key]) => key.startsWith("vercel:evidence:")));
    assert.equal(diff(prev, state, now).gone.length, 0);
  }
});

test("false green, inconsistent CPU status and untrusted content are rejected", () => {
  for (const bad of [
    { ...sample(3.9, "OK") },
    { ...sample(0, "OK"), cpuMeasured: false },
    { ...sample(0, "OK"), periodVerified: false },
    { ...sample(0, "OK"), team: "wrong-team" },
    { ...sample(0, "OK"), source: "user-message" },
    { ...sample(0, "OK"), percentOfQuota: 999 },
  ]) {
    const out = vercelFinopsAnomalies(bad, {}, now);
    assert.equal(out[0][1], "unknown");
    assert.doesNotMatch(JSON.stringify(out), /wrong-team|user-message|999/);
  }
});

test("only private bounded regular files are accepted as snapshots", () => {
  const body = JSON.stringify(sample(2.5, "WATCH"));
  const fake = (mode = 0o100600, size = body.length, symbolic = false) => ({
    lstatSync: () => ({ isFile: () => true, isSymbolicLink: () => symbolic, mode, size }),
    readFileSync: () => body,
  });
  assert.equal(readVercelReport("/private", fake()).cpuHours, 2.5);
  assert.equal(readVercelReport("/private", fake(0o100644)), null);
  assert.equal(readVercelReport("/private", fake(0o100600, 9000)), null);
  assert.equal(readVercelReport("/private", fake(0o100600, 50, true)), null);
  assert.equal(vercelFinopsCheck({}, "/missing", now, { lstatSync: () => { throw Error("secret"); } })[0][1], "unknown");
  assert.equal(vercelReportPath("/tmp/homelab-health.json", {}), "/tmp/vercel-finops.json");
});

test("no Vercel API or network call: snapshot reader alone supplies state", () => {
  const body = JSON.stringify(sample(3, "INVESTIGATE"));
  const io = {
    lstatSync: () => ({ isFile: () => true, isSymbolicLink: () => false, mode: 0o100600, size: body.length }),
    readFileSync: () => body,
  };
  const report = vercelFinopsCheck({}, "/local/private.json", now, io);
  assert.equal(report[0][0], "vercel:cpu:INVESTIGATE");
});
