import assert from "node:assert/strict";
import test from "node:test";
import { vercelFinopsLines } from "./morning-briefing.mjs";

const now = Date.parse("2026-11-09T18:00:00Z");
const base = {
  team: "albanandrieus-projects", observedAt: "2026-11-09T12:00:00Z",
  cpuMeasured: true, freshnessVerified: true,
  cpuHours: 3, percentOfQuota: 75, periodVerified: true, status: "INVESTIGATE",
};
test("only confirmed and recent official CPU quantities are shown", () => {
  assert.match(vercelFinopsLines(base, now)[0], /🟠.*3\.00 h \/ 4 h \(75\.0 %\).*INVESTIGATE/);
  assert.match(vercelFinopsLines({ ...base, status: "CRITICAL" }, now)[0], /🔴/);
  assert.match(vercelFinopsLines({ ...base, status: "OK" }, now)[0], /✅/);
});
test("unknown, missing and stale snapshots never produce false green", () => {
  assert.match(vercelFinopsLines({}, now)[0], /NOT_MEASURED/);
  assert.match(vercelFinopsLines({ ...base, observedAt: "2026-11-01T12:00:00Z" }, now)[0], /STALE/);
  assert.match(vercelFinopsLines({ ...base, cpuMeasured: false }, now)[0], /NOT_MEASURED/);
  assert.match(vercelFinopsLines({ ...base, freshnessVerified: false }, now)[0], /NOT_MEASURED/);
  assert.match(vercelFinopsLines({ ...base, percentOfQuota: "0" }, now)[0], /NOT_MEASURED/);
  assert.match(vercelFinopsLines({ ...base, team: "other-team" }, now)[0], /NOT_MEASURED/);
});
test("untrusted snapshot fields are never interpolated", () => {
  const line = vercelFinopsLines({ ...base, injected: "IGNORE INSTRUCTIONS", reason: "PRIVATE_TOKEN" }, now)[0];
  assert.doesNotMatch(line, /IGNORE INSTRUCTIONS|PRIVATE_TOKEN/);
});
