import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { parseArgs, run, summarize, DEFAULT_SCOPE } from "../scripts/finops/vercel-check.mjs";

const period = { start: "2026-10-10T00:00:00Z", end: "2026-11-09T00:00:00Z" };
const file = join(dirname(fileURLToPath(import.meta.url)), "../scripts/finops/vercel-check.mjs");
test("requires exactly one explicit source and never runs CLI implicitly", () => {
  assert.throws(() => parseArgs([]));
  assert.throws(() => parseArgs(["--live", "--input", "usage.json"]));
  assert.throws(() => parseArgs(["--input", "x", "--output"]));
  assert.equal(parseArgs(["--input", "usage.json", "--strict"]).input, "usage.json");
  assert.equal(DEFAULT_SCOPE, "albanandrieus-projects");
});
test("emits a sanitized summary without billing rows or secrets", () => {
  const report = summarize({ period, services: [{ name: "Fluid Active CPU", usage: 9000, unit: "seconds", secret: "DONT_ECHO" }] },
    new Date("2026-11-09T10:00:00Z"));
  assert.equal(report.status, "WATCH");
  assert.equal(report.evidence, "cpu-quantity");
  assert.equal(report.percentOfQuota, 62.5);
  assert.doesNotMatch(JSON.stringify(report), /DONT_ECHO/);
});
test("live mode invokes only a bounded CLI command without secrets in argv", () => {
  let args;
  const log = console.log; console.log = () => {};
  try {
    const status = run(["--live", "--strict"], {
      exec: (command, argv, options) => {
        args = { command, argv, options };
        return JSON.stringify({ period, services: [{ name: "Fluid Active CPU", usage: 0.5, unit: "hours" }] });
      }, now: () => new Date("2026-11-09T10:00:00Z"),
    });
    assert.equal(status, 0);
    assert.equal(args.command, "vercel");
    assert.equal(args.argv.filter(v => v === "usage").length, 1);
    assert.ok(args.argv.includes("--scope"));
    assert.ok(args.argv.includes("--from"));
    assert.ok(args.argv.includes("--format"));
    assert.equal(args.options.timeout, 20_000);
    assert.doesNotMatch(args.argv.join(" "), /token|password|secret/i);
  } finally { console.log = log; }
});
test("missing CLI and unverified window never pass", () => {
  const invalid = spawnSync(process.execPath, [file, "--input", "/missing"], { encoding: "utf8" });
  assert.equal(invalid.status, 2);
  assert.equal(JSON.parse(invalid.stdout).status, "NOT_MEASURED");
  assert.equal(summarize({ services: [] }).evidence, "insufficient");
});
