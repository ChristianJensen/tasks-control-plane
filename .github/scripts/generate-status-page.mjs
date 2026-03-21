#!/usr/bin/env node
/**
 * generate-status-page.mjs — Self-contained static HTML status dashboard generator.
 *
 * Reads a control plane's features/, queue/, and optional PR data,
 * then generates a self-contained HTML page suitable for GitHub Pages.
 *
 * Zero external dependencies — all aggregation logic is inlined.
 *
 * Usage:
 *   node generate-status-page.mjs --cp-dir <path> [--pr-data <path>] [--output <path>] [--title <string>]
 */

import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync, statSync } from "node:fs";
import { join, dirname, resolve } from "node:path";

// ── Frontmatter parser (inlined from dashboard/worker/lib/frontmatter.js) ───

function parseFrontmatter(content) {
  const m = content.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!m) return { fields: {}, body: content };

  const front = m[1];
  const body = content.slice(m[0].length).replace(/^\n/, "");
  const fields = {};
  let currentKey = null;

  for (const line of front.split("\n")) {
    const listMatch = line.match(/^\s+-\s+(.+)/);
    if (listMatch && currentKey) {
      if (!Array.isArray(fields[currentKey])) fields[currentKey] = [];
      fields[currentKey].push(listMatch[1].trim());
      continue;
    }
    const kvMatch = line.match(/^(\S+):\s*(.*)/);
    if (kvMatch) {
      const key = kvMatch[1];
      let value = kvMatch[2].trim().replace(/\s+#.*$/, "");
      fields[key] = value || [];
      currentKey = key;
    } else {
      currentKey = null;
    }
  }
  return { fields, body };
}

// ── Board state aggregation (inlined from dashboard/worker/lib/board-state.js) ─

function deriveFeatureStatus(tasks, isArchived) {
  if (isArchived || tasks.every((t) => t.status === "done")) return "shipped";
  if (tasks.some((t) => t.status === "blocked")) return "blocked";
  if (tasks.some((t) => t.status === "done" || t.status === "in-progress")) return "in-progress";
  return "not-started";
}

function extractTitle(body, fallbackSlug) {
  const m = body.match(/^#\s+(?:Feature Spec|Bug Report):\s*(.+)/m);
  return m ? m[1].trim() : fallbackSlug;
}

function extractProblemStatement(body) {
  const m = body.match(/## Problem Statement\s*\n+([\s\S]*?)(?=\n##|\n*$)/);
  if (!m) return "";
  return m[1].trim().split(/\n\n/)[0].replace(/^_|_$/g, "").trim();
}

function groupByWave(tasks) {
  const waves = {};
  for (const t of tasks) {
    const w = t.wave || 0;
    if (!waves[w]) waves[w] = [];
    waves[w].push(t);
  }
  return Object.keys(waves)
    .sort((a, b) => Number(a) - Number(b))
    .map((num) => ({
      number: Number(num),
      tasks: waves[num].map((t) => ({
        filename: t.filename, status: t.status, repo: t.repo,
        priority: t.priority, claimed_by: t.claimed_by || null,
      })),
    }));
}

function groupByRepo(tasks) {
  const repos = {};
  for (const t of tasks) {
    const r = t.repo || "unknown";
    if (!repos[r]) repos[r] = { done: 0, total: 0 };
    repos[r].total++;
    if (t.status === "done") repos[r].done++;
  }
  return repos;
}

function taskCounts(tasks) {
  const counts = { total: tasks.length, done: 0, in_progress: 0, ready: 0, pending: 0, blocked: 0, paused: 0, cancelled: 0 };
  for (const t of tasks) {
    const key = t.status.replace("-", "_");
    if (key in counts) counts[key]++;
  }
  return counts;
}

function parseTask(content, filename, featureSlug, isArchived) {
  const { fields } = parseFrontmatter(content);
  const waveMatch = filename.match(/^wave-(\d+)/);
  return {
    filename, feature: fields.feature || featureSlug,
    status: isArchived ? "done" : fields.status || "ready",
    repo: fields["target-repo"] || "", wave: waveMatch ? Number(waveMatch[1]) : 0,
    priority: fields.priority || "normal", type: fields.type || "feature",
    claimed_by: fields["claimed-by"] || "", claimed_at: fields["claimed-at"] || "",
    claimed_on: fields["claimed-on"] || "",
  };
}

function buildBoardState({ featureFiles = [], bugFiles = [], activeTaskFiles = [], archivedTaskFiles = [] }) {
  const specs = {};
  for (const f of [...featureFiles, ...bugFiles]) {
    const bname = f.path.split("/").pop();
    const slug = bname.replace(/-feature\.md$/, "").replace(/-bug\.md$/, "");
    const isBug = bname.endsWith("-bug.md");
    const { fields, body } = parseFrontmatter(f.content);
    specs[slug] = {
      slug, type: isBug ? "bug" : "feature", lifecycle: fields.lifecycle || "draft",
      title: extractTitle(body, slug), problem: extractProblemStatement(body),
      severity: isBug ? fields.severity || "" : undefined,
    };
  }

  const tasksByFeature = {};
  for (const f of activeTaskFiles) {
    const parts = f.path.split("/");
    const filename = parts.pop();
    const featureSlug = parts.pop();
    const task = parseTask(f.content, filename, featureSlug, false);
    if (!tasksByFeature[featureSlug]) tasksByFeature[featureSlug] = [];
    tasksByFeature[featureSlug].push(task);
  }
  for (const f of archivedTaskFiles) {
    const parts = f.path.split("/");
    const filename = parts.pop();
    const featureSlug = parts.pop();
    const task = parseTask(f.content, filename, featureSlug, true);
    if (!tasksByFeature[featureSlug]) tasksByFeature[featureSlug] = [];
    tasksByFeature[featureSlug].push(task);
  }

  const allSlugs = new Set([...Object.keys(specs), ...Object.keys(tasksByFeature)]);
  const features = [];
  const summary = { shipped: 0, in_progress: 0, not_started: 0, blocked: 0, bugs: 0 };

  for (const slug of allSlugs) {
    const spec = specs[slug] || { slug, type: "feature", lifecycle: "unknown", title: slug, problem: "" };
    const tasks = tasksByFeature[slug] || [];
    const isArchived = tasks.length > 0 && tasks.every((t) =>
      archivedTaskFiles.some((f) => f.path.includes(`/_done/${slug}/`))
    );
    const status = tasks.length > 0 ? deriveFeatureStatus(tasks, isArchived) : "orphaned";

    const feature = {
      slug, title: spec.title, type: spec.type, lifecycle: spec.lifecycle, status,
      problem: spec.problem, tasks: tasks.length > 0 ? taskCounts(tasks) : null,
      waves: tasks.length > 0 ? groupByWave(tasks) : [],
      repos: tasks.length > 0 ? groupByRepo(tasks) : {},
      missing: status !== "shipped"
        ? tasks.filter((t) => t.status !== "done").map((t) => ({
            filename: t.filename, status: t.status, priority: t.priority,
            wave: t.wave, claimed_by: t.claimed_by || null,
          }))
        : [],
    };

    if (spec.type === "bug") { feature.severity = spec.severity; summary.bugs++; }
    else if (status === "shipped") summary.shipped++;
    else if (status === "blocked") summary.blocked++;
    else if (status === "in-progress") summary.in_progress++;
    else if (status === "not-started") summary.not_started++;

    features.push(feature);
  }

  const statusOrder = { blocked: 0, "in-progress": 1, "not-started": 2, orphaned: 3, shipped: 4 };
  features.sort((a, b) => (statusOrder[a.status] ?? 5) - (statusOrder[b.status] ?? 5));

  return { generated_at: new Date().toISOString(), summary, features };
}

// ── CLI args ────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = { cpDir: ".", output: "status-page/index.html", prData: null, title: "Project Status" };
  for (let i = 2; i < argv.length; i++) {
    switch (argv[i]) {
      case "--cp-dir": args.cpDir = argv[++i]; break;
      case "--output": args.output = argv[++i]; break;
      case "--pr-data": args.prData = argv[++i]; break;
      case "--title": args.title = argv[++i]; break;
      case "--help":
        console.log("Usage: node generate-status-page.mjs --cp-dir <path> [--pr-data <path>] [--output <path>] [--title <string>]");
        process.exit(0);
    }
  }
  return args;
}

// ── File collection ─────────────────────────────────────────────

function listFiles(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((f) => !f.startsWith("."));
}

function collectActiveTaskFiles(cpDir) {
  const results = [];
  const queueDir = join(cpDir, "queue");
  if (!existsSync(queueDir)) return results;
  for (const feature of listFiles(queueDir)) {
    if (feature.startsWith("_")) continue;
    const featureDir = join(queueDir, feature);
    if (!statSync(featureDir).isDirectory()) continue;
    for (const file of listFiles(featureDir)) {
      if (file.startsWith("wave-") && file.endsWith(".md")) {
        results.push({ path: `queue/${feature}/${file}`, content: readFileSync(join(featureDir, file), "utf8") });
      }
    }
  }
  return results;
}

function collectArchivedTaskFiles(cpDir) {
  const results = [];
  const doneDir = join(cpDir, "queue", "_done");
  if (!existsSync(doneDir)) return results;
  for (const feature of listFiles(doneDir)) {
    const featureDir = join(doneDir, feature);
    if (!statSync(featureDir).isDirectory()) continue;
    for (const file of listFiles(featureDir)) {
      if (file.startsWith("wave-") && file.endsWith(".md")) {
        results.push({ path: `queue/_done/${feature}/${file}`, content: readFileSync(join(featureDir, file), "utf8") });
      }
    }
  }
  return results;
}

function collectFeatureFiles(cpDir, suffix) {
  const results = [];
  const featDir = join(cpDir, "features");
  if (!existsSync(featDir)) return results;
  for (const file of listFiles(featDir)) {
    if (file.endsWith(suffix)) {
      results.push({ path: `features/${file}`, content: readFileSync(join(featDir, file), "utf8") });
    }
  }
  return results;
}

// ── PR matching ─────────────────────────────────────────────────

function matchPRsToFeatures(prData) {
  const prsByFeature = {};
  for (const pr of prData) {
    const branch = pr.headRefName || "";
    const m = branch.match(/^(?:agent|fix)\/([^-]+(?:-[^-w][^-]*)*)-w(\d+)-/);
    if (m) {
      const slug = m[1];
      if (!prsByFeature[slug]) prsByFeature[slug] = [];
      prsByFeature[slug].push({ number: pr.number, title: pr.title, url: pr.url, branch, labels: (pr.labels || []).map((l) => l.name || l) });
    } else {
      const featureLabel = (pr.labels || []).find((l) => (l.name || l).startsWith("feature:"));
      if (featureLabel) {
        const slug = (featureLabel.name || featureLabel).replace("feature:", "");
        if (!prsByFeature[slug]) prsByFeature[slug] = [];
        prsByFeature[slug].push({ number: pr.number, title: pr.title, url: pr.url, branch, labels: (pr.labels || []).map((l) => l.name || l) });
      }
    }
  }
  return prsByFeature;
}

// ── HTML rendering ──────────────────────────────────────────────

function escHTML(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function statCard(label, count, bg) {
  return `<div class="stat-card" style="background:${bg}"><div class="count">${count}</div><div class="label">${label}</div></div>`;
}

function statusLabel(status) {
  return { shipped: "Shipped", "in-progress": "In Progress", "not-started": "Not Started", blocked: "Blocked", orphaned: "Orphaned" }[status] || status;
}

function renderWaves(waves) {
  if (!waves || !waves.length) return "";
  return `<div class="waves">${waves.map((w) =>
    `<span><span class="wave-label">W${w.number}:</span>${w.tasks.map((t) => `<span class="dot dot-${t.status}"></span>`).join("")}</span>`
  ).join("")}</div>`;
}

function renderRepos(repos) {
  if (!repos || !Object.keys(repos).length) return "";
  return `<div class="repos">${Object.entries(repos).map(([name, r]) => `<span class="repo-name">${escHTML(name)}:</span> ${r.done}/${r.total}`).join(" | ")}</div>`;
}

function renderPRs(prs) {
  if (!prs || !prs.length) return "";
  return `<div class="pr-list">${prs.map((pr) =>
    `<div class="pr-item"><span class="pr-icon">&#9741;</span><a href="${escHTML(pr.url)}" target="_blank">#${pr.number}</a> ${escHTML(pr.title)}</div>`
  ).join("")}</div>`;
}

function workerIcon(claimedBy) {
  if (!claimedBy) return '<span style="color:#9ca3af">&mdash;</span>';
  if (claimedBy.startsWith("agent-") || claimedBy.startsWith("cloud-"))
    return `<span title="${escHTML(claimedBy)}">&#129302;</span>`;
  return `<span title="${escHTML(claimedBy)}">&#128100;</span>`;
}

function renderMissing(missing) {
  if (!missing || !missing.length) return "";
  return `<details>
    <summary>What's Missing (${missing.length})</summary>
    <table class="missing-table">
      <thead><tr><th>Task</th><th>Status</th><th>Priority</th><th>Wave</th><th>Worker</th></tr></thead>
      <tbody>${missing.map((t) =>
        `<tr><td>${escHTML(t.filename.replace(".md", ""))}</td><td><span class="dot dot-${t.status}" style="width:8px;height:8px;"></span> ${t.status}</td><td>${t.priority}</td><td>W${t.wave}</td><td>${workerIcon(t.claimed_by)}</td></tr>`
      ).join("")}</tbody>
    </table>
  </details>`;
}

function featureCard(feature, prsByFeature) {
  const tasks = feature.tasks || { total: 0, done: 0 };
  const pct = tasks.total > 0 ? Math.round((tasks.done / tasks.total) * 100) : 0;
  const isBug = feature.type === "bug";
  const prs = prsByFeature[feature.slug] || [];

  return `<div class="card">
    <div class="card-header">
      <div>
        <div class="title">${escHTML(feature.title)}</div>
        ${feature.problem ? `<div class="problem">${escHTML(feature.problem)}</div>` : ""}
      </div>
      <div style="display:flex;gap:4px;flex-shrink:0;">
        <span class="badge badge-${feature.status}">${statusLabel(feature.status)}</span>
        ${isBug && feature.severity ? `<span class="badge sev-${feature.severity}">${feature.severity}</span>` : ""}
      </div>
    </div>
    ${tasks.total > 0 ? `<div class="card-body">
      <div class="progress-row">
        <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
        <span class="progress-pct">${pct}%</span>
      </div>
      <div class="task-meta">
        ${tasks.done}/${tasks.total} tasks done${tasks.in_progress > 0 ? ` &middot; ${tasks.in_progress} in progress` : ""}${tasks.blocked > 0 ? ` &middot; ${tasks.blocked} blocked` : ""}
      </div>
      ${renderWaves(feature.waves)}
      ${renderRepos(feature.repos)}
      ${renderPRs(prs)}
      ${renderMissing(feature.missing)}
    </div>` : ""}
  </div>`;
}

function renderOrphaned(features) {
  const orphanedFeatures = features.filter((f) => f.status === "orphaned" && f.type !== "bug");
  const orphanedBugs = features.filter((f) => f.status === "orphaned" && f.type === "bug");
  let html = "";
  if (orphanedFeatures.length > 0) {
    html += `<h2>Orphaned Features</h2>
    <p style="font-size:0.875rem;color:#6b7280;">Planned but not yet decomposed into tasks.</p>
    <ul class="orphaned-list">${orphanedFeatures.map((f) => `<li>${escHTML(f.title)}</li>`).join("")}</ul>`;
  }
  if (orphanedBugs.length > 0) {
    html += `<h2 class="bug-header">Orphaned Bug Reports</h2>
    <p style="font-size:0.875rem;color:#6b7280;">Reported but not yet triaged into tasks.</p>
    <ul class="orphaned-list">${orphanedBugs.map((f) => `<li>${escHTML(f.title)}</li>`).join("")}</ul>`;
  }
  return html;
}

function renderHTML(boardState, prsByFeature, title) {
  const { summary, features, generated_at } = boardState;
  const featureItems = features.filter((f) => f.type !== "bug");
  const bugItems = features.filter((f) => f.type === "bug");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escHTML(title)}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f9fafb; color: #111827; margin: 0; padding: 0;
    line-height: 1.5; font-size: 16px;
  }
  .container { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
  h1 { font-size: 1.5rem; font-weight: 700; margin: 0 0 4px 0; }
  h2 { font-size: 0.875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; margin: 24px 0 12px 0; }
  h2.bug-header { color: #ea580c; }
  .timestamp { font-size: 0.75rem; color: #9ca3af; }
  .summary { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
  .stat-card { border-radius: 8px; padding: 16px 24px; color: #fff; text-align: center; min-width: 120px; flex: 1; }
  .stat-card .count { font-size: 1.75rem; font-weight: 700; }
  .stat-card .label { font-size: 0.8rem; opacity: 0.9; }
  .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 16px; overflow: hidden; }
  .card-header { padding: 16px 20px; border-bottom: 1px solid #f3f4f6; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
  .card-header .title { font-size: 1rem; font-weight: 600; color: #111827; margin: 0; }
  .card-header .problem { font-size: 0.875rem; color: #6b7280; margin: 4px 0 0 0; }
  .card-body { padding: 16px 20px; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; color: #fff; white-space: nowrap; }
  .badge-shipped { background: #16a34a; }
  .badge-in-progress { background: #2563eb; }
  .badge-not-started { background: #d97706; }
  .badge-blocked { background: #dc2626; }
  .badge-orphaned { background: #6b7280; }
  .sev-critical { background: #dc2626; }
  .sev-high { background: #ea580c; }
  .sev-medium { background: #d97706; }
  .sev-low { background: #6b7280; }
  .progress-row { display: flex; align-items: center; gap: 8px; }
  .progress-bar { height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; flex: 1; }
  .progress-fill { height: 100%; border-radius: 4px; background: #16a34a; }
  .progress-pct { font-size: 0.75rem; color: #6b7280; width: 40px; text-align: right; }
  .task-meta { font-size: 0.75rem; color: #9ca3af; margin-top: 4px; }
  .waves { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; font-size: 0.75rem; color: #6b7280; }
  .wave-label { font-weight: 500; margin-right: 2px; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin: 0 2px; vertical-align: middle; }
  .dot-done { background: #16a34a; }
  .dot-in-progress { background: #2563eb; }
  .dot-ready, .dot-pending { background: #d1d5db; }
  .dot-blocked { background: #dc2626; }
  .dot-paused, .dot-cancelled { background: #9ca3af; }
  .repos { font-size: 0.75rem; color: #6b7280; margin-top: 4px; }
  .repos .repo-name { font-weight: 500; }
  .pr-list { margin-top: 8px; }
  .pr-item { font-size: 0.8rem; color: #374151; padding: 4px 0; display: flex; align-items: center; gap: 6px; }
  .pr-item a { color: #2563eb; text-decoration: none; }
  .pr-item a:hover { text-decoration: underline; }
  .pr-icon { color: #16a34a; font-weight: bold; }
  details { margin-top: 12px; }
  summary { font-size: 0.75rem; color: #6b7280; cursor: pointer; }
  summary:hover { color: #374151; }
  .missing-table { width: 100%; font-size: 0.75rem; margin-top: 8px; border-collapse: collapse; }
  .missing-table th { text-align: left; color: #9ca3af; border-bottom: 1px solid #e5e7eb; padding: 4px 8px 4px 0; }
  .missing-table td { padding: 4px 8px 4px 0; color: #374151; border-bottom: 1px solid #f3f4f6; }
  .orphaned-list { font-size: 0.875rem; color: #6b7280; padding-left: 20px; }
  .orphaned-list li { margin-bottom: 4px; }
  footer { text-align: center; font-size: 0.75rem; color: #9ca3af; padding: 24px 0; }
  @media print {
    body { background: #fff; }
    .card { box-shadow: none; break-inside: avoid; }
    .stat-card, .badge, .dot, .progress-fill { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  }
  @media (max-width: 640px) {
    .stat-card { min-width: 80px; padding: 12px 16px; }
    .stat-card .count { font-size: 1.25rem; }
    .card-header { flex-direction: column; }
  }
</style>
</head>
<body>
<div class="container">
  <header style="margin-bottom: 24px;">
    <h1>${escHTML(title)}</h1>
    <div class="timestamp">Generated ${new Date(generated_at).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}</div>
  </header>
  <div class="summary">
    ${statCard("Shipped", summary.shipped, "#16a34a")}
    ${statCard("In Progress", summary.in_progress, "#2563eb")}
    ${statCard("Not Started", summary.not_started, "#d97706")}
    ${statCard("Blocked", summary.blocked, "#dc2626")}
    ${statCard("Bug Fixes", summary.bugs, "#ea580c")}
  </div>
  ${featureItems.length > 0 ? `<h2>Features</h2>\n${featureItems.map((f) => featureCard(f, prsByFeature)).join("\n")}` : ""}
  ${bugItems.length > 0 ? `<h2 class="bug-header">Bug Fixes</h2>\n${bugItems.map((f) => featureCard(f, prsByFeature)).join("\n")}` : ""}
  ${renderOrphaned(features)}
  <footer>Generated by Relay Status Page</footer>
</div>
</body>
</html>`;
}

// ── Main ────────────────────────────────────────────────────────

const args = parseArgs(process.argv);
const cpDir = resolve(args.cpDir);

console.log(`Generating status page from: ${cpDir}`);

const featureFiles = collectFeatureFiles(cpDir, "-feature.md");
const bugFiles = collectFeatureFiles(cpDir, "-bug.md");
const activeTaskFiles = collectActiveTaskFiles(cpDir);
const archivedTaskFiles = collectArchivedTaskFiles(cpDir);

console.log(`  Features: ${featureFiles.length}, Bugs: ${bugFiles.length}`);
console.log(`  Active tasks: ${activeTaskFiles.length}, Archived: ${archivedTaskFiles.length}`);

const boardState = buildBoardState({ featureFiles, bugFiles, activeTaskFiles, archivedTaskFiles });

let prsByFeature = {};
if (args.prData && existsSync(args.prData)) {
  const prData = JSON.parse(readFileSync(args.prData, "utf8"));
  prsByFeature = matchPRsToFeatures(prData);
  const totalMatched = Object.values(prsByFeature).reduce((s, prs) => s + prs.length, 0);
  console.log(`  PRs loaded: ${prData.length}, matched to features: ${totalMatched}`);
}

const html = renderHTML(boardState, prsByFeature, args.title);

const outputPath = resolve(args.output);
mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, html, "utf8");

console.log(`\nStatus page written to: ${outputPath}`);
console.log(`Summary: ${boardState.summary.shipped} shipped, ${boardState.summary.in_progress} in progress, ${boardState.summary.not_started} not started, ${boardState.summary.blocked} blocked, ${boardState.summary.bugs} bugs`);
