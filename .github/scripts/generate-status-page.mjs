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

function statusLabel(status) {
  return { shipped: "Shipped", "in-progress": "In Progress", "not-started": "Not Started", blocked: "Blocked", orphaned: "Orphaned" }[status] || status;
}

function statusColor(status) {
  return { shipped: "#10b981", "in-progress": "#3b82f6", "not-started": "#f59e0b", blocked: "#ef4444", orphaned: "#6b7280" }[status] || "#6b7280";
}

function progressRingSVG(pct, color, size = 48) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" class="progress-ring">
    <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="var(--ring-bg)" stroke-width="3"/>
    <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${offset}" transform="rotate(-90 ${size/2} ${size/2})"
      style="transition:stroke-dashoffset 1s ease-out"/>
    <text x="${size/2}" y="${size/2}" text-anchor="middle" dominant-baseline="central"
      fill="var(--text-primary)" font-size="${size < 40 ? 9 : 11}" font-weight="700" font-family="var(--font-mono)">${pct}%</text>
  </svg>`;
}

function workerIcon(claimedBy) {
  if (!claimedBy) return '<span class="worker-empty">&mdash;</span>';
  const isBot = claimedBy.startsWith("agent-") || claimedBy.startsWith("cloud-");
  return `<span class="worker-icon" title="${escHTML(claimedBy)}">${isBot ? "&#129302;" : "&#128100;"}</span>`;
}

function renderFeatureRow(feature, prsByFeature, idx) {
  const tasks = feature.tasks || { total: 0, done: 0 };
  const pct = tasks.total > 0 ? Math.round((tasks.done / tasks.total) * 100) : 0;
  const isBug = feature.type === "bug";
  const prs = prsByFeature[feature.slug] || [];
  const color = statusColor(feature.status);
  const typeIcon = isBug
    ? `<span class="type-icon type-bug" title="Bug">&#9679;</span>`
    : `<span class="type-icon type-feature" title="Feature">&#9670;</span>`;

  const wavesDots = (feature.waves || []).map((w) =>
    `<div class="wave-group"><span class="wave-lbl">W${w.number}</span>${w.tasks.map((t) =>
      `<span class="wdot wdot-${t.status}" title="${t.filename}: ${t.status}"></span>`
    ).join("")}</div>`
  ).join("");

  const repoChips = Object.entries(feature.repos || {}).map(([name, r]) =>
    `<span class="repo-chip"><span class="repo-chip-name">${escHTML(name)}</span><span class="repo-chip-count">${r.done}/${r.total}</span></span>`
  ).join("");

  const prRows = prs.map((pr) =>
    `<div class="pr-row"><svg width="14" height="14" viewBox="0 0 16 16" fill="var(--accent)"><path d="M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z"/></svg><a href="${escHTML(pr.url)}" target="_blank" rel="noopener">#${pr.number} ${escHTML(pr.title)}</a></div>`
  ).join("");

  const missingRows = (feature.missing || []).map((t) =>
    `<tr>
      <td class="mono">${escHTML(t.filename.replace(".md", ""))}</td>
      <td><span class="wdot wdot-${t.status}"></span> ${t.status}</td>
      <td>${t.priority}</td>
      <td class="mono">W${t.wave}</td>
      <td>${workerIcon(t.claimed_by)}</td>
    </tr>`
  ).join("");

  const hasDetails = tasks.total > 0;

  return `<div class="feature-row" data-status="${feature.status}" data-type="${feature.type}" data-title="${escHTML(feature.title.toLowerCase())}" style="animation-delay:${idx * 60}ms">
    <div class="feature-header" onclick="this.parentElement.classList.toggle('expanded')">
      <div class="feature-left">
        ${typeIcon}
        <div class="feature-info">
          <div class="feature-title">${escHTML(feature.title)}</div>
          ${feature.problem ? `<div class="feature-desc">${escHTML(feature.problem.length > 120 ? feature.problem.slice(0, 120) + "..." : feature.problem)}</div>` : ""}
        </div>
      </div>
      <div class="feature-right">
        ${tasks.total > 0 ? `<span class="task-count mono">${tasks.done}/${tasks.total}</span>` : ""}
        <span class="lozenge lozenge-${feature.status}">${statusLabel(feature.status)}</span>
        ${isBug && feature.severity ? `<span class="lozenge lozenge-sev-${feature.severity}">${feature.severity}</span>` : ""}
        ${hasDetails ? `<span class="chevron">&#9662;</span>` : ""}
      </div>
    </div>
    ${hasDetails ? `<div class="feature-detail">
      <div class="detail-grid">
        <div class="detail-progress">
          ${progressRingSVG(pct, color)}
          <div class="progress-label">
            <div class="progress-bar-wrap"><div class="pbar"><div class="pbar-fill" style="width:${pct}%;background:${color}"></div></div></div>
            <span class="task-meta">${tasks.done} done${tasks.in_progress > 0 ? `, ${tasks.in_progress} active` : ""}${tasks.blocked > 0 ? `, ${tasks.blocked} blocked` : ""}</span>
          </div>
        </div>
        ${wavesDots ? `<div class="detail-waves"><div class="detail-label">Waves</div><div class="waves-wrap">${wavesDots}</div></div>` : ""}
        ${repoChips ? `<div class="detail-repos"><div class="detail-label">Repositories</div><div class="repo-chips">${repoChips}</div></div>` : ""}
        ${prRows ? `<div class="detail-prs"><div class="detail-label">Pull Requests</div>${prRows}</div>` : ""}
      </div>
      ${missingRows ? `<div class="detail-missing">
        <div class="detail-label">Remaining Tasks (${feature.missing.length})</div>
        <table class="missing-tbl"><thead><tr><th>Task</th><th>Status</th><th>Priority</th><th>Wave</th><th>Worker</th></tr></thead><tbody>${missingRows}</tbody></table>
      </div>` : ""}
    </div>` : ""}
  </div>`;
}

function renderHTML(boardState, prsByFeature, title) {
  const { summary, features, generated_at } = boardState;
  const featureItems = features.filter((f) => f.type !== "bug");
  const bugItems = features.filter((f) => f.type === "bug");
  const totalTasks = features.reduce((s, f) => s + (f.tasks?.total || 0), 0);
  const doneTasks = features.reduce((s, f) => s + (f.tasks?.done || 0), 0);
  const overallPct = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : 0;

  const allRows = features.map((f, i) => renderFeatureRow(f, prsByFeature, i)).join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escHTML(title)}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&display=swap');

:root {
  --font-body: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
  --bg: #0d1117;
  --bg-card: rgba(22, 27, 34, 0.8);
  --bg-card-hover: rgba(30, 37, 48, 0.9);
  --bg-detail: rgba(13, 17, 23, 0.6);
  --bg-input: rgba(255,255,255,0.06);
  --border: rgba(255,255,255,0.08);
  --border-hover: rgba(255,255,255,0.15);
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --text-muted: #484f58;
  --accent: #58a6ff;
  --green: #10b981;
  --blue: #3b82f6;
  --amber: #f59e0b;
  --red: #ef4444;
  --orange: #f97316;
  --ring-bg: rgba(255,255,255,0.06);
  --nav-bg: rgba(13, 17, 23, 0.95);
  --glow-green: 0 0 20px rgba(16,185,129,0.15);
  --glow-blue: 0 0 20px rgba(59,130,246,0.15);
  --glow-amber: 0 0 20px rgba(245,158,11,0.15);
  --glow-red: 0 0 20px rgba(239,68,68,0.15);
  --radius: 12px;
  --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Jira Mode Overrides ── */
.jira-mode {
  --bg: #F4F5F7;
  --bg-card: #ffffff;
  --bg-card-hover: #FAFBFC;
  --bg-detail: #F4F5F7;
  --bg-input: #FAFBFC;
  --border: #DFE1E6;
  --border-hover: #C1C7D0;
  --text-primary: #172B4D;
  --text-secondary: #5E6C84;
  --text-muted: #97A0AF;
  --accent: #0052CC;
  --green: #36B37E;
  --blue: #0065FF;
  --amber: #FF991F;
  --red: #FF5630;
  --orange: #FF8B00;
  --ring-bg: #DFE1E6;
  --nav-bg: #0052CC;
  --glow-green: none; --glow-blue: none; --glow-amber: none; --glow-red: none;
  --radius: 4px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font-body);
  background: var(--bg);
  color: var(--text-primary);
  line-height: 1.6;
  transition: background var(--transition), color var(--transition);
  min-height: 100vh;
}

/* ── Background texture ── */
body::before {
  content: '';
  position: fixed; inset: 0; z-index: -1;
  background:
    radial-gradient(ellipse 80% 60% at 50% -20%, rgba(59,130,246,0.08), transparent),
    radial-gradient(ellipse 60% 40% at 80% 100%, rgba(16,185,129,0.05), transparent);
  pointer-events: none;
}
.jira-mode body::before,
.jira-mode::before { background: none; }

/* ── Nav Bar ── */
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: var(--nav-bg);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  height: 56px;
  display: flex; align-items: center; justify-content: space-between;
  transition: background var(--transition);
}
.jira-mode .navbar { border-bottom: none; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.nav-left { display: flex; align-items: center; gap: 12px; }
.nav-logo {
  width: 28px; height: 28px; border-radius: 6px;
  background: linear-gradient(135deg, var(--green), var(--blue));
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; color: #fff;
}
.jira-mode .nav-logo { background: linear-gradient(135deg, #2684FF, #0052CC); border-radius: 4px; }
.nav-title { font-weight: 700; font-size: 15px; color: var(--text-primary); }
.jira-mode .nav-title { color: #fff; }
.nav-right { display: flex; align-items: center; gap: 16px; }
.nav-time { font-size: 12px; color: var(--text-secondary); font-family: var(--font-mono); }
.jira-mode .nav-time { color: rgba(255,255,255,0.7); }

/* ── Layout ── */
.layout { max-width: 1200px; margin: 0 auto; padding: 24px; }

/* ── Stat Cards ── */
.stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 32px; }
.stat {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  text-align: center;
  transition: all var(--transition);
  backdrop-filter: blur(10px);
  position: relative;
  overflow: hidden;
  animation: fadeUp 0.6s ease-out both;
}
.stat:hover { border-color: var(--border-hover); transform: translateY(-2px); }
.stat::after {
  content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 3px;
  border-radius: 0 0 var(--radius) var(--radius);
}
.stat-shipped::after { background: var(--green); box-shadow: var(--glow-green); }
.stat-in-progress::after { background: var(--blue); box-shadow: var(--glow-blue); }
.stat-not-started::after { background: var(--amber); box-shadow: var(--glow-amber); }
.stat-blocked::after { background: var(--red); box-shadow: var(--glow-red); }
.stat-bugs::after { background: var(--orange); }
.stat-number {
  font-family: var(--font-mono);
  font-size: 2rem; font-weight: 700; line-height: 1;
  margin-bottom: 4px;
}
.stat-shipped .stat-number { color: var(--green); }
.stat-in-progress .stat-number { color: var(--blue); }
.stat-not-started .stat-number { color: var(--amber); }
.stat-blocked .stat-number { color: var(--red); }
.stat-bugs .stat-number { color: var(--orange); }
.stat-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-secondary); font-weight: 600; }

/* ── Overall Progress ── */
.overall {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 24px;
  margin-bottom: 24px;
  display: flex; align-items: center; gap: 20px;
  backdrop-filter: blur(10px);
  animation: fadeUp 0.6s ease-out 0.3s both;
}
.overall-ring { flex-shrink: 0; }
.overall-info { flex: 1; }
.overall-title { font-size: 13px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }
.overall-bar { height: 6px; background: var(--ring-bg); border-radius: 3px; overflow: hidden; }
.overall-bar-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--green), var(--blue)); transition: width 1s ease-out; }
.overall-meta { font-size: 12px; color: var(--text-muted); margin-top: 6px; font-family: var(--font-mono); }

/* ── Toolbar ── */
.toolbar {
  display: flex; align-items: center; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;
  animation: fadeUp 0.6s ease-out 0.4s both;
}
.search-wrap {
  flex: 1; min-width: 200px; position: relative;
}
.search-wrap svg { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--text-muted); }
.search {
  width: 100%; padding: 8px 12px 8px 36px;
  background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px;
  color: var(--text-primary); font-size: 13px; font-family: var(--font-body);
  outline: none; transition: border-color var(--transition);
}
.search:focus { border-color: var(--accent); }
.search::placeholder { color: var(--text-muted); }
.filters { display: flex; gap: 4px; flex-wrap: wrap; }
.filter-btn {
  padding: 6px 14px; border: 1px solid var(--border); border-radius: 20px;
  background: transparent; color: var(--text-secondary); font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all var(--transition); font-family: var(--font-body);
  white-space: nowrap;
}
.filter-btn:hover { border-color: var(--border-hover); color: var(--text-primary); }
.filter-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.jira-mode .filter-btn { border-radius: 4px; }

/* ── Section Headers ── */
.section-hdr {
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--text-muted); margin: 28px 0 12px; padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 8px;
}
.section-hdr .section-count {
  background: var(--bg-input); border-radius: 10px; padding: 1px 8px;
  font-size: 10px; font-family: var(--font-mono);
}
.section-hdr.bug-hdr { color: var(--orange); border-color: rgba(249,115,22,0.2); }

/* ── Feature Rows ── */
.feature-row {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 8px;
  overflow: hidden;
  transition: all var(--transition);
  backdrop-filter: blur(10px);
  animation: fadeUp 0.5s ease-out both;
}
.feature-row:hover { border-color: var(--border-hover); }
.jira-mode .feature-row { border-left: 4px solid var(--border); border-radius: 4px; }
.jira-mode .feature-row[data-status="shipped"] { border-left-color: var(--green); }
.jira-mode .feature-row[data-status="in-progress"] { border-left-color: var(--blue); }
.jira-mode .feature-row[data-status="not-started"] { border-left-color: var(--amber); }
.jira-mode .feature-row[data-status="blocked"] { border-left-color: var(--red); }

.feature-header {
  padding: 14px 20px;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  cursor: pointer; user-select: none;
  transition: background var(--transition);
}
.feature-header:hover { background: var(--bg-card-hover); }
.feature-left { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }
.feature-info { min-width: 0; }
.feature-title { font-weight: 600; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.feature-desc { font-size: 12px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }
.feature-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.task-count { font-size: 12px; color: var(--text-secondary); }
.chevron {
  font-size: 12px; color: var(--text-muted);
  transition: transform 0.2s ease;
  display: inline-block;
}
.feature-row.expanded .chevron { transform: rotate(180deg); }

/* Type Icons */
.type-icon { font-size: 16px; flex-shrink: 0; line-height: 1; }
.type-feature { color: var(--green); }
.type-bug { color: var(--red); }

/* ── Lozenges ── */
.lozenge {
  display: inline-flex; align-items: center; padding: 2px 10px; border-radius: 4px;
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
  white-space: nowrap;
}
.lozenge-shipped { background: rgba(16,185,129,0.15); color: var(--green); }
.lozenge-in-progress { background: rgba(59,130,246,0.15); color: var(--blue); }
.lozenge-not-started { background: rgba(245,158,11,0.1); color: var(--amber); }
.lozenge-blocked { background: rgba(239,68,68,0.15); color: var(--red); }
.lozenge-orphaned { background: rgba(107,114,128,0.15); color: var(--text-muted); }
.lozenge-sev-critical { background: rgba(239,68,68,0.15); color: var(--red); }
.lozenge-sev-high { background: rgba(249,115,22,0.15); color: var(--orange); }
.lozenge-sev-medium { background: rgba(245,158,11,0.1); color: var(--amber); }
.lozenge-sev-low { background: rgba(107,114,128,0.15); color: var(--text-muted); }
.jira-mode .lozenge-shipped { background: #E3FCEF; color: #006644; }
.jira-mode .lozenge-in-progress { background: #DEEBFF; color: #0747A6; }
.jira-mode .lozenge-not-started { background: #DFE1E6; color: #42526E; }
.jira-mode .lozenge-blocked { background: #FFEBE6; color: #BF2600; }

/* ── Feature Detail ── */
.feature-detail {
  max-height: 0; overflow: hidden;
  transition: max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1), padding 0.3s ease;
  background: var(--bg-detail); border-top: 1px solid var(--border);
}
.feature-row.expanded .feature-detail {
  max-height: 800px; padding: 20px;
}
.detail-grid { display: grid; grid-template-columns: auto 1fr; gap: 16px 24px; align-items: start; }
.detail-progress { display: flex; align-items: center; gap: 16px; grid-column: 1 / -1; }
.progress-label { flex: 1; }
.progress-bar-wrap { margin-bottom: 4px; }
.pbar { height: 4px; background: var(--ring-bg); border-radius: 2px; overflow: hidden; }
.pbar-fill { height: 100%; border-radius: 2px; transition: width 0.8s ease-out; }
.task-meta { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }
.detail-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-muted); margin-bottom: 8px; }

/* Waves */
.detail-waves, .detail-repos, .detail-prs { grid-column: 1 / -1; }
.waves-wrap { display: flex; flex-wrap: wrap; gap: 12px; }
.wave-group { display: flex; align-items: center; gap: 3px; }
.wave-lbl { font-size: 10px; font-weight: 700; color: var(--text-muted); font-family: var(--font-mono); margin-right: 2px; }
.wdot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; transition: transform 0.15s; }
.wdot:hover { transform: scale(1.4); }
.wdot-done { background: var(--green); box-shadow: 0 0 6px rgba(16,185,129,0.4); }
.wdot-in-progress { background: var(--blue); box-shadow: 0 0 6px rgba(59,130,246,0.4); }
.wdot-ready, .wdot-pending { background: var(--text-muted); opacity: 0.4; }
.wdot-blocked { background: var(--red); box-shadow: 0 0 6px rgba(239,68,68,0.4); }
.wdot-paused, .wdot-cancelled { background: var(--text-muted); opacity: 0.3; }
.jira-mode .wdot { box-shadow: none; }

/* Repo Chips */
.repo-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.repo-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; border-radius: 4px;
  background: var(--bg-input); border: 1px solid var(--border);
  font-size: 11px;
}
.repo-chip-name { font-weight: 600; color: var(--text-secondary); }
.repo-chip-count { font-family: var(--font-mono); color: var(--text-primary); font-weight: 700; }

/* PRs */
.pr-row {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 0; font-size: 12px;
}
.pr-row a { color: var(--accent); text-decoration: none; }
.pr-row a:hover { text-decoration: underline; }

/* Missing Table */
.detail-missing { grid-column: 1 / -1; margin-top: 4px; }
.missing-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.missing-tbl th {
  text-align: left; font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--text-muted);
  padding: 6px 12px 6px 0; border-bottom: 1px solid var(--border);
}
.missing-tbl td { padding: 8px 12px 8px 0; border-bottom: 1px solid var(--border); color: var(--text-secondary); }
.missing-tbl tr:last-child td { border-bottom: none; }
.missing-tbl .mono { font-family: var(--font-mono); font-size: 11px; }
.worker-empty { color: var(--text-muted); }
.worker-icon { font-size: 14px; }

/* ── Orphaned ── */
.orphaned-section { margin-top: 24px; }
.orphaned-item {
  padding: 10px 16px; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); margin-bottom: 6px; font-size: 13px; color: var(--text-secondary);
  border-left: 3px solid var(--text-muted);
}

/* ── Theme Toggle ── */
.theme-toggle {
  position: fixed; bottom: 24px; right: 24px; z-index: 200;
  display: flex; align-items: center; gap: 10px;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 28px; padding: 6px 16px 6px 12px;
  backdrop-filter: blur(20px);
  box-shadow: 0 4px 24px rgba(0,0,0,0.3);
  cursor: pointer; user-select: none;
  transition: all var(--transition);
  font-size: 12px; font-weight: 600; color: var(--text-secondary);
}
.theme-toggle:hover { border-color: var(--border-hover); transform: translateY(-1px); }
.toggle-track {
  width: 36px; height: 20px; border-radius: 10px;
  background: var(--text-muted); position: relative;
  transition: background var(--transition);
}
.jira-mode .toggle-track { background: var(--accent); }
.toggle-thumb {
  width: 16px; height: 16px; border-radius: 50%;
  background: #fff; position: absolute; top: 2px; left: 2px;
  transition: transform var(--transition);
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.jira-mode .toggle-thumb { transform: translateX(16px); }

/* ── Footer ── */
.page-footer {
  text-align: center; padding: 32px 0 16px;
  font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);
  letter-spacing: 0.05em;
}

/* ── Animations ── */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .stats { grid-template-columns: repeat(3, 1fr); }
  .layout { padding: 16px; }
  .detail-grid { grid-template-columns: 1fr; }
  .feature-desc { display: none; }
  .search-wrap { min-width: 120px; }
}
@media (max-width: 480px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .stat { padding: 14px; }
  .stat-number { font-size: 1.5rem; }
  .navbar { padding: 0 16px; }
  .filters { gap: 2px; }
  .filter-btn { padding: 4px 10px; font-size: 11px; }
  .feature-right .task-count { display: none; }
}

/* ── Print ── */
@media print {
  body, .jira-mode { background: #fff !important; }
  .navbar, .theme-toggle, .toolbar { display: none !important; }
  .feature-row { break-inside: avoid; border: 1px solid #ddd !important; }
  .feature-detail { max-height: none !important; padding: 16px !important; }
  .stat, .lozenge, .wdot, .pbar-fill { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
}
</style>
</head>
<body>

<nav class="navbar">
  <div class="nav-left">
    <div class="nav-logo">R</div>
    <span class="nav-title">${escHTML(title)}</span>
  </div>
  <div class="nav-right">
    <span class="nav-time">${new Date(generated_at).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}</span>
  </div>
</nav>

<div class="layout">

  <div class="stats">
    <div class="stat stat-shipped" style="animation-delay:0ms"><div class="stat-number" data-count="${summary.shipped}">0</div><div class="stat-label">Shipped</div></div>
    <div class="stat stat-in-progress" style="animation-delay:60ms"><div class="stat-number" data-count="${summary.in_progress}">0</div><div class="stat-label">In Progress</div></div>
    <div class="stat stat-not-started" style="animation-delay:120ms"><div class="stat-number" data-count="${summary.not_started}">0</div><div class="stat-label">Not Started</div></div>
    <div class="stat stat-blocked" style="animation-delay:180ms"><div class="stat-number" data-count="${summary.blocked}">0</div><div class="stat-label">Blocked</div></div>
    <div class="stat stat-bugs" style="animation-delay:240ms"><div class="stat-number" data-count="${summary.bugs}">0</div><div class="stat-label">Bugs</div></div>
  </div>

  <div class="overall">
    <div class="overall-ring">${progressRingSVG(overallPct, "url(#grad)", 56)}</div>
    <div class="overall-info">
      <div class="overall-title">Overall Progress</div>
      <div class="overall-bar"><div class="overall-bar-fill" style="width:${overallPct}%"></div></div>
      <div class="overall-meta">${doneTasks} of ${totalTasks} tasks completed across ${features.length} features</div>
    </div>
  </div>

  <div class="toolbar">
    <div class="search-wrap">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M11.5 7a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zm-.82 4.74a6 6 0 111.06-1.06l3.04 3.04a.75.75 0 11-1.06 1.06l-3.04-3.04z"/></svg>
      <input type="text" class="search" placeholder="Search features..." id="searchInput">
    </div>
    <div class="filters">
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="in-progress">In Progress</button>
      <button class="filter-btn" data-filter="not-started">Not Started</button>
      <button class="filter-btn" data-filter="blocked">Blocked</button>
      <button class="filter-btn" data-filter="shipped">Shipped</button>
      <button class="filter-btn" data-filter="bug">Bugs</button>
    </div>
  </div>

  ${featureItems.length > 0 ? `<div class="section-hdr"><span>Features</span><span class="section-count">${featureItems.length}</span></div>` : ""}
  ${bugItems.length > 0 ? `<div class="section-hdr bug-hdr"><span>Bug Fixes</span><span class="section-count">${bugItems.length}</span></div>` : ""}

  <div id="featureList">
    ${allRows}
  </div>

  ${renderOrphaned(features)}

  <div class="page-footer">RELAY STATUS PAGE</div>
</div>

<div class="theme-toggle" id="themeToggle" title="Toggle Jira mode">
  <div class="toggle-track"><div class="toggle-thumb"></div></div>
  <span id="themeLabel">Jira Mode</span>
</div>

<svg width="0" height="0"><defs><linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="var(--green)"/><stop offset="100%" stop-color="var(--blue)"/></linearGradient></defs></svg>

<script>
// ── Theme Toggle ──
const toggle = document.getElementById('themeToggle');
const body = document.body;
if (localStorage.getItem('relay-jira') === '1') body.classList.add('jira-mode');
toggle.addEventListener('click', () => {
  body.classList.toggle('jira-mode');
  localStorage.setItem('relay-jira', body.classList.contains('jira-mode') ? '1' : '0');
});

// ── Animated Counters ──
document.querySelectorAll('.stat-number[data-count]').forEach(el => {
  const target = parseInt(el.dataset.count);
  if (target === 0) return;
  const dur = 800;
  const start = performance.now();
  function tick(now) {
    const p = Math.min((now - start) / dur, 1);
    const ease = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(target * ease);
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
});

// ── Filter Tabs ──
const filterBtns = document.querySelectorAll('.filter-btn');
const rows = document.querySelectorAll('.feature-row');
filterBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    filterBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const f = btn.dataset.filter;
    rows.forEach(row => {
      if (f === 'all') { row.style.display = ''; return; }
      if (f === 'bug') { row.style.display = row.dataset.type === 'bug' ? '' : 'none'; return; }
      row.style.display = row.dataset.status === f ? '' : 'none';
    });
  });
});

// ── Search ──
const searchInput = document.getElementById('searchInput');
searchInput.addEventListener('input', () => {
  const q = searchInput.value.toLowerCase();
  rows.forEach(row => {
    const title = row.dataset.title || '';
    row.style.display = title.includes(q) ? '' : 'none';
  });
  // Reset filter buttons
  if (q) filterBtns.forEach(b => b.classList.remove('active'));
  else filterBtns[0].classList.add('active');
});
</script>

</body>
</html>`;
}

function renderOrphaned(features) {
  const orphanedFeatures = features.filter((f) => f.status === "orphaned" && f.type !== "bug");
  const orphanedBugs = features.filter((f) => f.status === "orphaned" && f.type === "bug");
  let html = "";
  if (orphanedFeatures.length > 0) {
    html += `<div class="orphaned-section"><div class="section-hdr"><span>Orphaned Features</span><span class="section-count">${orphanedFeatures.length}</span></div>
    ${orphanedFeatures.map((f) => `<div class="orphaned-item">${escHTML(f.title)}</div>`).join("")}</div>`;
  }
  if (orphanedBugs.length > 0) {
    html += `<div class="orphaned-section"><div class="section-hdr bug-hdr"><span>Orphaned Bugs</span><span class="section-count">${orphanedBugs.length}</span></div>
    ${orphanedBugs.map((f) => `<div class="orphaned-item">${escHTML(f.title)}</div>`).join("")}</div>`;
  }
  return html;
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
