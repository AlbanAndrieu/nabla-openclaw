import assert from "node:assert/strict";
import test from "node:test";
import { evaluate, run, TEAM } from "./check-vercel-team.mjs";

const now = new Date("2026-11-10T12:00:00Z");
const data = (cpu, period = {start:"2026-10-11T00:00:00Z",end:"2026-11-10T00:00:00Z"}) =>
  JSON.stringify({period,services:[{name:"Fluid Active CPU",quantity:cpu,unit:"hours"}]});

test("current 30-day CPU value is classified from real usage, not amount", () => {
  const r = evaluate(data(3), now);
  assert.equal(r.status, "INVESTIGATE");
  assert.equal(r.percentOfQuota, 75);
  assert.equal(r.cpuMeasured, true);
  assert.equal(r.team, TEAM);
});

test("stale, one-day and currency-only exports never report healthy", () => {
  assert.equal(evaluate(data(0.1, {start:"2026-10-01",end:"2026-10-31"}), now).status, "STALE_USAGE");
  assert.equal(evaluate(data(0.1, {start:"2026-11-09",end:"2026-11-10"}), now).status, "WINDOW_UNVERIFIED");
  assert.equal(evaluate(JSON.stringify({period:{start:"2026-10-11",end:"2026-11-10"},services:[{name:"Fluid Active CPU",amount:100,unit:"hours"}]}),now).status,"NOT_MEASURED");
});

test("malformed exports are redacted", () => {
  const r = evaluate('{"token":"secret', now);
  assert.equal(r.status,"NOT_MEASURED");
  assert.doesNotMatch(JSON.stringify(r), /secret/);
});

test("no implicit Vercel command; explicit flags are required", () => {
  assert.equal(run([], {spawn:()=>{throw new Error("should not run");}}),2);
  assert.equal(run(["--live","--input","/tmp/x"]),2);
});

test("CLI errors become NOT_MEASURED, not fake zero CPU", () => {
  let argv;
  const result=run(["--live"], {now,spawn:(_command,args,settings)=>{
    argv=args;
    assert.equal(settings.timeout,20000);
    return {status:1,stdout:'{"token":"secret-raw"}',stderr:"secret-error"};
  }});
  assert.equal(result,2);
  assert.deepEqual(argv,["usage","--scope","albanandrieus-projects","--format","json"]);
});

test("strict mode fails when Vercel team reaches WATCH", () => {
  const result=run(["--input","ignored","--strict"], {read:()=>data(2.2),now});
  assert.equal(result,1);
});
