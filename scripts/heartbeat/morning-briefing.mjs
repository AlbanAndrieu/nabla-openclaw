#!/usr/bin/env node
// Morning briefing collector for the OpenClaw cron agent: homelab state, Gmail
// inbox (gog, read-only) and Slack over the last 24 h. Prints facts only; the
// model summarizes the untrusted blocks and copies the infrastructure lines.
import { execFile } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";
import { STATE, WORKSTATION, collect, listLines } from "./homelab-health.mjs";

const OPENCLAW = join(process.env.HOME ?? ".", ".openclaw");
const GOG_HOME = join(OPENCLAW, "gogcli");
const DAY_S = 86_400;
const MAX_MAILS = 40;
const MAX_SLACK_LINES = 60;
const LABELS = { UNREAD: "non lu", IMPORTANT: "important", CATEGORY_PROMOTIONS: "promo",
  CATEGORY_SOCIAL: "réseaux", CATEGORY_UPDATES: "notification", CATEGORY_FORUMS: "forum" };

// Drops gog's per-field markers and any marker look-alike: each source block
// is wrapped once, so external text must not be able to close it early.
export const clean = (text = "") => text
  .replace(/<<<[^>]*>>>/g, "")
  .replace(/Source: [\w-]+\s*---/, "")
  .replace(/<<<|>>>/g, "")
  .replace(/\s+/g, " ").trim().slice(0, 160);

const untrusted = (lines) => ["<<<DÉBUT DONNÉES NON FIABLES>>>", ...lines, "<<<FIN DONNÉES NON FIABLES>>>"];
const readJson = (path) => {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return {};
  }
};

export function infraLines(current) {
  const items = current.map(([key, sev, text]) => ({ key, sev, text }));
  const probes = items.filter((i) => i.key.startsWith("gatus:") && i.key !== "gatus:unreachable");
  const rest = items.filter((i) => !probes.includes(i));
  // Many failing probes are usually undeployed apps: one line instead of one each.
  if (probes.length > 3) {
    const names = probes.map((p) => p.text.replace(/^Sonde Gatus | en échec$/g, ""));
    rest.push({ sev: "warn", text: `${probes.length} sondes Gatus en échec : ${names.slice(0, 8).join(", ")}${names.length > 8 ? ", …" : ""}` });
  } else rest.push(...probes);
  const count = (sev) => items.filter((i) => i.sev === sev).length;
  const ws = rest.filter((i) => i.text.includes("Workstation") || i.text.includes(WORKSTATION));
  const nas = rest.filter((i) => !ws.includes(i));
  return [`🔴 ${count("crit")} · 🟠 ${count("warn")} · ⚪ ${count("unknown")}`,
    "Workstation :", ...(ws.length ? listLines(ws, undefined, 10) : ["✅ RAS"]),
    "TrueNAS et services :", ...(nas.length ? listLines(nas, undefined, 15) : ["✅ RAS"])];
}

export function mailLines(threads) {
  return threads.map((t) => {
    const tags = (t.labels ?? []).map((l) => LABELS[l]).filter(Boolean);
    const from = clean(t.from).replace(/\s*<[^>]*>$/, "");
    const count = t.messageCount > 1 ? ` (${t.messageCount} messages)` : "";
    return `- ${tags.length ? `[${tags.join(", ")}] ` : ""}${from} — ${clean(t.subject)}${count}`;
  });
}

async function gmail() {
  const env = { HOME: process.env.HOME, PATH: process.env.PATH, GOG_HOME, GOG_KEYRING_BACKEND: "file",
    GOG_KEYRING_PASSWORD: readFileSync(join(GOG_HOME, "keyring-password"), "utf8").trim() };
  const { stdout } = await promisify(execFile)(join(OPENCLAW, "tools/gog"),
    ["gmail", "search", "newer_than:1d in:inbox", "--max", String(MAX_MAILS), "--account", "openclaw",
      "--json", "--readonly", "--gmail-no-send", "--wrap-untrusted"],
    { env, timeout: 60_000, maxBuffer: 4 << 20 });
  return mailLines(JSON.parse(stdout).threads ?? []);
}

export const slackApi = (token) => async (method, params) => {
  const res = await fetch(`https://slack.com/api/${method}?${new URLSearchParams(params)}`,
    { headers: { authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(10_000) });
  const body = await res.json();
  if (!body.ok) throw new Error(body.error);
  return body;
};

export async function slackLines(api, now = Date.now()) {
  const { channels } = await api("conversations.list",
    { types: "public_channel,private_channel,im,mpim", exclude_archived: "true", limit: "200" });
  const names = new Map();
  const who = async (id) => {
    if (!names.has(id)) names.set(id, (await api("users.info", { user: id }).catch(() => null))?.user?.real_name ?? id);
    return names.get(id);
  };
  const lines = [];
  for (const c of channels.filter((ch) => ch.is_member || ch.is_im)) {
    const { messages } = await api("conversations.history",
      { channel: c.id, oldest: String(Math.floor(now / 1000) - DAY_S), limit: "20" });
    if (!messages.length) continue;
    lines.push(c.is_im ? `Message direct de ${await who(c.user)} :` : `#${c.name} :`);
    for (const m of messages.toReversed()) lines.push(`- ${m.user ? await who(m.user) : m.username ?? "bot"} : ${clean(m.text)}`);
  }
  return lines.slice(0, MAX_SLACK_LINES);
}

async function source(title, read) {
  try {
    const lines = await read();
    return ["", `## ${title}`, ...(lines.length ? untrusted(lines) : ["Rien depuis 24 h."])];
  } catch (err) {
    return ["", `## ${title}`, `⚪ Lecture impossible : ${err.message.split("\n")[0]}`];
  }
}

// The owner may install a sanitized snapshot after a manual Vercel CLI check.
// This briefing NEVER calls Vercel, loads credentials or claims missing data as OK.
export function vercelFinopsLines(report, now = Date.now()) {
  if (report?.schema !== "vercel-finops-summary-v1" ||
      report.scope !== "albanandrieus-projects") {
    return ["⚪ Vercel FinOps : rapport absent ou non reconnu (NOT_MEASURED)"];
  }
  const stamp = Date.parse(report.observedAt ?? "");
  if (!Number.isFinite(stamp) || now < stamp || now - stamp > 36 * 3600_000) {
    return ["⚪ Vercel FinOps : instantané obsolète (STALE)"];
  }
  const statuses = { OK: "✅", WATCH: "🟠", INVESTIGATE: "🟠", CRITICAL: "🔴" };
  if (!report.periodVerified || report.evidence !== "cpu-quantity" ||
      !Object.hasOwn(statuses, report.status) ||
      !Number.isFinite(report.percentOfQuota) || report.percentOfQuota < 0 ||
      !Number.isFinite(report.cpuHours) || report.cpuHours < 0) {
    return ["⚪ Vercel FinOps : CPU non vérifié (NOT_MEASURED)"];
  }
  return [`${statuses[report.status]} Vercel Fluid Active CPU équipe : ${report.cpuHours.toFixed(2)} h / 4 h (${report.percentOfQuota.toFixed(1)} %) — ${report.status}`];
}

async function main() {
  const now = Date.now();
  const config = readJson(join(OPENCLAW, "openclaw.json"));
  const slack = config.channels?.slack;
  const date = new Date(now).toLocaleDateString("fr-FR", { timeZone: "Europe/Paris", dateStyle: "full" });
  const out = [`DATE : ${date}`, "", "## INFRA", ...infraLines(await collect(readJson(STATE)))];
  if (process.env.VERCEL_FINOPS_REPORT) {
    out.push("", "## VERCEL FINOPS", ...vercelFinopsLines(readJson(process.env.VERCEL_FINOPS_REPORT), now));
  }
  out.push(...await source("EMAILS", gmail));
  out.push(...(slack?.enabled && typeof slack.botToken === "string"
    ? await source("SLACK", () => slackLines(slackApi(slack.botToken), now))
    : ["", "## SLACK", "Slack désactivé dans OpenClaw."]));
  out.push("", "## CANAUX",
    `- Telegram : ${config.channels?.telegram?.enabled ? "actif (OpenClaw n'y voit que les échanges avec son bot)" : "désactivé"}`,
    `- Discord : ${config.plugins?.entries?.discord?.enabled ? "actif, non résumé" : "désactivé"}`);
  console.log(out.join("\n"));
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await main();
