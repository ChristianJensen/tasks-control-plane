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
import { execSync } from "node:child_process";

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

function extractBugDigest(body) {
  const sections = ["Observed Behavior", "Root Cause Analysis", "Affected Code Paths", "Fix Strategy", "Reproduction Steps", "Acceptance Criteria"];
  const parts = [];
  for (const name of sections) {
    const m = body.match(new RegExp(`##+ ${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\n+([\\s\\S]*?)(?=\\n##|$)`));
    if (m && m[1].trim() && !m[1].trim().startsWith("_")) {
      parts.push({ heading: name, content: m[1].trim() });
    }
  }
  return parts;
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
        description: t.description || "", title: t.title || "",
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

function extractTaskDescription(body) {
  const m = body.match(/## Description\s*\n+([\s\S]*?)(?=\n##|\n*$)/);
  if (!m) return "";
  return m[1].trim().split(/\n\n/)[0].trim();
}

function deriveTaskTitle(filename) {
  // wave-1-api-sort-endpoint.md → Sort Endpoint
  return filename
    .replace(/\.md$/, "")
    .replace(/^wave-\d+-[^-]+-/, "")
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

const TASK_STATUSES = new Set(["pending", "ready", "in-progress", "done", "blocked", "paused", "cancelled"]);
const FEATURE_PHASES = new Set(["draft", "active", "completed", "cancelled"]);

function statusFromPath(relPath) {
  const parts = relPath.split("/");
  // e.g. queue/feature/ready/wave-1-api-foo.md → "ready"
  if (parts.length >= 2) {
    const parent = parts[parts.length - 2];
    if (TASK_STATUSES.has(parent) || FEATURE_PHASES.has(parent)) return parent;
  }
  return "";
}

function parseTask(content, filename, featureSlug, isArchived, sha, relPath) {
  const { fields, body } = parseFrontmatter(content);
  const waveMatch = filename.match(/^wave-(\d+)/);
  const dirStatus = relPath ? statusFromPath(relPath) : "";
  return {
    filename, feature: fields.feature || featureSlug,
    status: isArchived ? "done" : dirStatus || "ready",
    repo: fields["target-repo"] || "", wave: waveMatch ? Number(waveMatch[1]) : 0,
    priority: fields.priority || "normal", type: fields.type || "feature",
    execution: fields.execution || "",
    claimed_by: fields["claimed-by"] || "", claimed_at: fields["claimed-at"] || "",
    claimed_on: fields["claimed-on"] || "",
    cost_usd: parseFloat(fields["cost-usd"]) || 0,
    input_tokens: parseInt(fields["input-tokens"]) || 0,
    output_tokens: parseInt(fields["output-tokens"]) || 0,
    description: extractTaskDescription(body),
    title: deriveTaskTitle(filename),
    sha: sha || null,
    relPath: relPath || "",
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
      execution: fields.execution || "supervised",
      epic: (typeof fields.epic === "string" && fields.epic) ? fields.epic : "",
      epicTitle: (typeof fields["epic-title"] === "string" && fields["epic-title"]) ? fields["epic-title"] : "",
      title: extractTitle(body, slug), problem: extractProblemStatement(body),
      bugDigest: isBug ? extractBugDigest(body) : undefined,
      severity: isBug ? fields.severity || "" : undefined,
      reportedBy: isBug ? fields["reported-by"] || "" : undefined,
      createdAt: fields["created-at"] || "",
      completedAt: fields["completed-at"] || "",
      sha: f.sha || null,
      specPath: f.path || "",
    };
  }

  const tasksByFeature = {};
  for (const f of activeTaskFiles) {
    const parts = f.path.split("/");
    const filename = parts.pop();       // wave-*.md
    parts.pop();                         // status dir
    const featureSlug = parts[parts.length - 1];
    const task = parseTask(f.content, filename, featureSlug, false, f.sha, f.path);
    if (!tasksByFeature[featureSlug]) tasksByFeature[featureSlug] = [];
    tasksByFeature[featureSlug].push(task);
  }
  for (const f of archivedTaskFiles) {
    const parts = f.path.split("/");
    const filename = parts.pop();       // wave-*.md
    parts.pop();                         // status dir
    const featureSlug = parts[parts.length - 1];
    const task = parseTask(f.content, filename, featureSlug, true, f.sha, f.path);
    if (!tasksByFeature[featureSlug]) tasksByFeature[featureSlug] = [];
    tasksByFeature[featureSlug].push(task);
  }

  const allSlugs = new Set([...Object.keys(specs), ...Object.keys(tasksByFeature)]);
  const features = [];
  const summary = { shipped: 0, in_progress: 0, not_started: 0, blocked: 0, bugs: 0 };

  for (const slug of allSlugs) {
    const spec = specs[slug] || { slug, type: "feature", lifecycle: "unknown", execution: "supervised", epic: "", epicTitle: "", title: slug, problem: "" };
    const tasks = tasksByFeature[slug] || [];
    const isArchived = tasks.length > 0 && tasks.every((t) =>
      archivedTaskFiles.some((f) => f.path.includes(`/_done/${slug}/`))
    );
    const status = tasks.length > 0
      ? deriveFeatureStatus(tasks, isArchived)
      : (spec.lifecycle === "draft" ? "not-started" : "orphaned");

    const cost = {
      usd: tasks.reduce((s, t) => s + (t.cost_usd || 0), 0),
      input_tokens: tasks.reduce((s, t) => s + (t.input_tokens || 0), 0),
      output_tokens: tasks.reduce((s, t) => s + (t.output_tokens || 0), 0),
    };
    cost.tokens = cost.input_tokens + cost.output_tokens;

    const feature = {
      slug, title: spec.title, type: spec.type, lifecycle: spec.lifecycle, status,
      execution: spec.execution, epic: spec.epic, epicTitle: spec.epicTitle,
      createdAt: spec.createdAt || "", completedAt: spec.completedAt || "", specSha: spec.sha || null, specPath: spec.specPath || "",
      problem: spec.problem, cost, tasks: tasks.length > 0 ? taskCounts(tasks) : null,
      waves: tasks.length > 0 ? groupByWave(tasks) : [],
      repos: tasks.length > 0 ? groupByRepo(tasks) : {},
      missing: status !== "shipped"
        ? tasks.filter((t) => t.status !== "done").map((t) => ({
            filename: t.filename, status: t.status, priority: t.priority,
            wave: t.wave, claimed_by: t.claimed_by || null,
            claimed_at: t.claimed_at || null,
            description: t.description || "", title: t.title || "",
            sha: t.sha || null, relPath: t.relPath || "",
          }))
        : [],
      allTasks: tasks.map((t) => ({
        filename: t.filename, status: t.status, priority: t.priority,
        wave: t.wave, claimed_by: t.claimed_by || null,
        claimed_at: t.claimed_at || null,
        description: t.description || "", title: t.title || "",
        repo: t.repo || "",
        sha: t.sha || null, relPath: t.relPath || "",
      })),
    };

    if (spec.type === "bug") {
      feature.severity = spec.severity;
      feature.reportedBy = spec.reportedBy;
      feature.bugDigest = spec.bugDigest;
      if (spec.reportedBy === "telemetry" && feature.status === "orphaned") feature.status = "needs-review";
      summary.bugs++;
    }
    else if (status === "shipped") summary.shipped++;
    else if (status === "blocked") summary.blocked++;
    else if (status === "in-progress") summary.in_progress++;
    else if (status === "not-started") summary.not_started++;

    features.push(feature);
  }

  // Grand total cost
  summary.total_cost_usd = features.reduce((s, f) => s + (f.cost?.usd || 0), 0);
  summary.total_tokens = features.reduce((s, f) => s + (f.cost?.tokens || 0), 0);

  // Execution mode counts
  const execCounts = { autonomous: 0, supervised: 0, guided: 0 };
  for (const f of features) {
    if (f.execution && execCounts[f.execution] !== undefined) execCounts[f.execution]++;
  }

  // Active workers (in-progress tasks)
  const workerMap = {};
  for (const slug of Object.keys(tasksByFeature)) {
    for (const t of tasksByFeature[slug]) {
      if (t.status === "in-progress" && t.claimed_by) {
        if (!workerMap[t.claimed_by]) workerMap[t.claimed_by] = { tasks: 0, features: new Set() };
        workerMap[t.claimed_by].tasks++;
        workerMap[t.claimed_by].features.add(t.feature);
      }
    }
  }
  const activeWorkers = Object.entries(workerMap)
    .sort((a, b) => b[1].tasks - a[1].tasks)
    .map(([name, info]) => ({ name, tasks: info.tasks, features: [...info.features] }));

  const statusOrder = { blocked: 0, "in-progress": 1, "not-started": 2, orphaned: 3, shipped: 4 };
  features.sort((a, b) => (statusOrder[a.status] ?? 5) - (statusOrder[b.status] ?? 5));

  return { generated_at: new Date().toISOString(), summary, execCounts, activeWorkers, features };
}

// ── Config ───────────────────────────────────────────────────────

function parseRelayConfig(cpDir) {
  const configPath = join(cpDir, ".relay-config");
  const config = {};
  if (!existsSync(configPath)) return config;
  const content = readFileSync(configPath, "utf8");
  for (const line of content.split("\n")) {
    const m = line.match(/^(status-page-\S+):\s*(.+)/);
    if (m) config[m[1]] = m[2].trim();
  }
  return config;
}

// ── CLI args ────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = { cpDir: ".", output: "status-page/index.html", prData: null, title: null };
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

function getFileLastCommitSha(cpDir, relativePath) {
  try {
    return execSync(`git log -1 --format=%H -- "${relativePath}"`, { cwd: cpDir, encoding: "utf8" }).trim() || null;
  } catch { return null; }
}


function collectActiveTaskFiles(cpDir) {
  const results = [];
  const queueDir = join(cpDir, "queue");
  if (!existsSync(queueDir)) return results;
  for (const feature of listFiles(queueDir)) {
    if (feature.startsWith("_")) continue;
    const featureDir = join(queueDir, feature);
    if (!statSync(featureDir).isDirectory()) continue;
    // New layout: queue/<feature>/<status>/wave-*.md
    for (const entry of listFiles(featureDir)) {
      const entryPath = join(featureDir, entry);
      if (statSync(entryPath).isDirectory() && TASK_STATUSES.has(entry)) {
        for (const file of listFiles(entryPath)) {
          if (file.startsWith("wave-") && file.endsWith(".md")) {
            const relPath = `queue/${feature}/${entry}/${file}`;
            results.push({ path: relPath, content: readFileSync(join(entryPath, file), "utf8"), sha: getFileLastCommitSha(cpDir, relPath) });
          }
        }
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
    // New layout: queue/_done/<feature>/<status>/wave-*.md
    for (const entry of listFiles(featureDir)) {
      const entryPath = join(featureDir, entry);
      if (statSync(entryPath).isDirectory() && TASK_STATUSES.has(entry)) {
        for (const file of listFiles(entryPath)) {
          if (file.startsWith("wave-") && file.endsWith(".md")) {
            const relPath = `queue/_done/${feature}/${entry}/${file}`;
            results.push({ path: relPath, content: readFileSync(join(entryPath, file), "utf8"), sha: getFileLastCommitSha(cpDir, relPath) });
          }
        }
      }
    }
  }
  return results;
}

function collectFeatureFiles(cpDir, suffix) {
  const results = [];
  const featDir = join(cpDir, "features");
  if (!existsSync(featDir)) return results;
  // New layout: features/<phase>/*-feature.md
  for (const entry of listFiles(featDir)) {
    const entryPath = join(featDir, entry);
    if (existsSync(entryPath) && statSync(entryPath).isDirectory() && FEATURE_PHASES.has(entry)) {
      for (const file of listFiles(entryPath)) {
        if (file.endsWith(suffix)) {
          const relPath = `features/${entry}/${file}`;
          results.push({ path: relPath, content: readFileSync(join(entryPath, file), "utf8"), sha: getFileLastCommitSha(cpDir, relPath) });
        }
      }
    }
  }
  return results;
}

function collectBugFiles(cpDir) {
  const results = [];
  const bugsDir = join(cpDir, "bugs");
  if (!existsSync(bugsDir)) return results;
  for (const entry of listFiles(bugsDir)) {
    const entryPath = join(bugsDir, entry);
    if (existsSync(entryPath) && statSync(entryPath).isDirectory() && FEATURE_PHASES.has(entry)) {
      for (const file of listFiles(entryPath)) {
        if (file.endsWith("-bug.md")) {
          const relPath = `bugs/${entry}/${file}`;
          results.push({ path: relPath, content: readFileSync(join(entryPath, file), "utf8"), sha: getFileLastCommitSha(cpDir, relPath) });
        }
      }
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

function formatDate(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch { return ""; }
}

function statusLabel(status) {
  return { shipped: "Shipped", "in-progress": "In Progress", "not-started": "Not Started", blocked: "Blocked", orphaned: "Orphaned", "needs-review": "Needs Review" }[status] || status;
}

function statusColor(status) {
  return { shipped: "#10b981", "in-progress": "#3b82f6", "not-started": "#f59e0b", blocked: "#ef4444", orphaned: "#6b7280", "needs-review": "#f59e0b" }[status] || "#6b7280";
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

function executionLabel(mode) {
  return { autonomous: "&#129302; Auto", supervised: "&#128065; Supervised", guided: "&#128100; Guided" }[mode] || mode;
}

function priorityDot(priority) {
  const colors = { critical: "var(--red)", high: "var(--orange)", normal: "var(--text-muted)", low: "rgba(107,114,128,0.4)" };
  const color = colors[priority] || colors.normal;
  return `<span class="priority-dot" style="background:${color}" title="${priority}"></span>`;
}

const priorityOrder = { critical: 0, high: 1, normal: 2, low: 3 };

function fmtTokens(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function fmtCost(usd) {
  return usd >= 1 ? `$${usd.toFixed(2)}` : `$${usd.toFixed(4)}`;
}

function isStaleTask(t, generatedAt) {
  if (!t.claimed_at || t.status !== "in-progress") return false;
  try {
    const claimed = new Date(t.claimed_at).getTime();
    const generated = new Date(generatedAt).getTime();
    return (generated - claimed) > 2 * 60 * 60 * 1000; // 2 hours
  } catch { return false; }
}

function renderDispatchDropdown(slug) {
  const modeBtn = (mode, label, color, title, target) =>
    `<button onclick="event.stopPropagation();dispatchAgent('${slug}','${mode}','${target}')" title="${title}"><span class="dd-color" style="background:var(--${color})"></span> ${label}</button>`;
  return `<div class="dispatch-wrap">
    <button class="dispatch-trigger" onclick="event.stopPropagation();this.nextElementSibling.classList.toggle('open')">Dispatch Agent &#9662;</button>
    <div class="dispatch-dropdown">
      <div class="dd-group-label">Cloud Agent</div>
      ${modeBtn("autonomous", "Autonomous", "green", "Cloud agent auto-merges. No human review.", "cloud")}
      ${modeBtn("supervised", "Supervised", "accent", "Cloud agent opens a PR. You review before merge.", "cloud")}
      ${modeBtn("guided", "Guided", "amber", "Cloud agent follows guided workflow.", "cloud")}
      <div class="dd-divider"></div>
      <div class="dd-group-label">Local Agent</div>
      ${modeBtn("autonomous", "Autonomous", "green", "Local agent auto-merges. No human review.", "local")}
      ${modeBtn("supervised", "Supervised", "accent", "Local agent opens a PR. You review before merge.", "local")}
      ${modeBtn("guided", "Guided", "amber", "You run locally. Agent assists interactively.", "local")}
    </div>
  </div>`;
}

function renderFeatureRow(feature, prsByFeature, idx, linkContext, generatedAt) {
  const tasks = feature.tasks || { total: 0, done: 0 };
  const pct = tasks.total > 0 ? Math.round((tasks.done / tasks.total) * 100) : 0;
  const isBug = feature.type === "bug";
  const prs = prsByFeature[feature.slug] || [];
  const color = statusColor(feature.status);
  const typeIcon = isBug
    ? `<span class="type-icon type-bug" title="Bug">&#9679;</span>`
    : `<span class="type-icon type-feature" title="Feature">&#9670;</span>`;

  // Jira epic link — split pill: left = filter toggle, right = external Jira link
  const epicDisplay = feature.epicTitle
    ? `Jira: ${feature.epic}: ${feature.epicTitle}`
    : `Jira: ${feature.epic}`;
  const jiraLink = feature.epic
    ? `<span class="jira-pill">`
      + `<span class="epic-filter-toggle" data-epic="${escHTML(feature.epic)}" title="Filter by epic ${escHTML(feature.epic)}">${escHTML(epicDisplay)}</span>`
      + (linkContext.jiraBaseUrl
        ? `<a href="${escHTML(linkContext.jiraBaseUrl)}/browse/${escHTML(feature.epic)}" target="_blank" rel="noopener" class="jira-link-icon" title="Open in Jira">&#8599;</a>`
        : "")
      + `</span>`
    : "";

  // SHA-pinned spec link
  const specLinkLabel = isBug ? "Bug Report" : "Feature Specification";
  const specSha = feature.specSha || linkContext.commitSha;
  const specUrl = linkContext.githubServerUrl && linkContext.githubRepository && specSha && feature.specPath
    ? `${linkContext.githubServerUrl}/${linkContext.githubRepository}/blob/${specSha}/${feature.specPath}`
    : null;
  const specLink = specUrl
    ? `<a href="${escHTML(specUrl)}" target="_blank" rel="noopener" class="spec-link" title="View spec @ ${specSha.slice(0, 7)}">${specLinkLabel}</a>`
    : "";

  // Execution mode badge
  const execBadge = feature.execution
    ? `<span class="lozenge lozenge-exec-${feature.execution}">${executionLabel(feature.execution)}</span>`
    : "";

  // Lifecycle badge (only for non-active states)
  const lifecycleBadge = feature.lifecycle && feature.lifecycle !== "active" && feature.lifecycle !== "completed"
    ? `<span class="lozenge lozenge-lifecycle-${feature.lifecycle}">${feature.lifecycle}</span>`
    : "";

  const wavesDots = (feature.waves || []).map((w) =>
    `<div class="wave-group"><span class="wave-lbl">W${w.number}</span>${w.tasks.map((t) =>
      `<span class="wdot wdot-${t.status}" title="${t.title || t.filename}: ${t.status}"></span>`
    ).join("")}</div>`
  ).join("");

  const repoChips = Object.entries(feature.repos || {}).map(([name, r]) =>
    `<span class="repo-chip"><span class="repo-chip-name">${escHTML(name)}</span><span class="repo-chip-count">${r.done}/${r.total}</span></span>`
  ).join("");

  const prRows = prs.map((pr) =>
    `<div class="pr-row"><svg width="14" height="14" viewBox="0 0 16 16" fill="var(--accent)"><path d="M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z"/></svg><a href="${escHTML(pr.url)}" target="_blank" rel="noopener">#${pr.number} ${escHTML(pr.title)}</a></div>`
  ).join("");

  // Use allTasks for shipped features, missing for others
  const isShipped = feature.status === "shipped";
  const taskList = isShipped ? (feature.allTasks || []) : (feature.missing || []);
  const sortedTaskList = [...taskList].sort((a, b) =>
    (a.wave || 0) - (b.wave || 0) || (priorityOrder[a.priority] ?? 9) - (priorityOrder[b.priority] ?? 9)
  );
  const taskTableLabel = isShipped ? "All Tasks" : "Remaining Tasks";

  const taskRows = sortedTaskList.map((t) => {
    const taskSha = t.sha || linkContext.commitSha;
    const taskUrl = linkContext.githubServerUrl && linkContext.githubRepository && taskSha && t.relPath
      ? `${linkContext.githubServerUrl}/${linkContext.githubRepository}/blob/${taskSha}/${t.relPath}`
      : null;
    const taskLabel = escHTML(t.filename.replace(".md", ""));
    const taskLink = taskUrl
      ? `<a href="${escHTML(taskUrl)}" target="_blank" rel="noopener">${taskLabel}</a>`
      : taskLabel;
    const stale = isStaleTask(t, generatedAt);
    return `<tr class="${stale ? "stale-task" : ""}">
      <td class="mono" data-label="Task">${taskLink}</td>
      <td data-label="Status"><span class="wdot wdot-${t.status}"></span> ${t.status}${stale ? ' <span class="stale-warn" title="In progress for over 2 hours">&#9888;</span>' : ""}</td>
      <td data-label="Priority">${priorityDot(t.priority)} ${t.priority}</td>
      <td class="mono" data-label="Wave">W${t.wave}</td>
      <td data-label="Execution">${executionLabel(feature.execution || "supervised")}</td>
    </tr>`;
  }).join("");

  const hasBugDigest = isBug && feature.bugDigest && feature.bugDigest.length > 0;
  const canDispatchFeature = !isBug && feature.lifecycle === "active" && tasks.total > 0;
  const hasDetails = tasks.total > 0 || hasBugDigest || feature.problem;

  const dispatchDropdownHTML = (hasBugDigest || canDispatchFeature) ? renderDispatchDropdown(escHTML(feature.slug)) : "";

  const bugDigestHTML = hasBugDigest ?
    dispatchDropdownHTML +
    feature.bugDigest.map((s) =>
      `<div class="bug-digest-section"><div class="bug-digest-heading">${escHTML(s.heading)}</div><div class="bug-digest-body">${escHTML(s.content).replace(/\n/g, "<br>")}</div></div>`
    ).join("") +
    `<div class="bug-digest-actions"><button class="dismiss-btn" onclick="event.stopPropagation();showToast('Dismiss not yet implemented','warn')">Dismiss</button></div>`
    : "";

  const isDimmed = feature.lifecycle === "draft" || feature.lifecycle === "paused";

  return `<div class="feature-row${isDimmed ? " feature-dimmed" : ""}" data-status="${feature.status}" data-type="${feature.type}" data-execution="${feature.execution || ""}" data-title="${escHTML(feature.title.toLowerCase())}" data-epic="${escHTML(feature.epic)}" data-epic-title="${escHTML((feature.epicTitle || '').toLowerCase())}" style="animation-delay:${idx * 60}ms">
    <div class="feature-header">
      <div class="feature-left">
        ${typeIcon}
        <div class="feature-info">
          <div class="feature-title">${escHTML(feature.title)} ${jiraLink} ${specLink}</div>
        </div>
      </div>
      <div class="feature-right">
        ${lifecycleBadge}
        ${tasks.total > 0 ? `<span class="task-count mono">${tasks.done}/${tasks.total}</span>` : ""}
        ${feature.createdAt || feature.completedAt ? `<span class="feature-dates mono">${feature.createdAt ? formatDate(feature.createdAt) : ""}${feature.createdAt && feature.completedAt ? ` &rarr; ` : ""}${feature.completedAt ? formatDate(feature.completedAt) : ""}</span>` : ""}
        ${feature.lifecycle === "draft" && tasks.total === 0 ? `<button class="plan-btn plan-btn-check" disabled onclick="event.stopPropagation();nfPlanFeature('${escHTML(feature.slug)}')" title="Start relay serve to enable">Plan</button>` : ""}
        <span class="lozenge lozenge-${feature.status}">${statusLabel(feature.status)}</span>
        ${hasDetails ? `<span class="chevron">&#9662;</span>` : ""}
      </div>
    </div>
    ${hasDetails ? `<div class="feature-detail">
      ${hasBugDigest && tasks.total === 0 ? `<div class="bug-digest">${bugDigestHTML}</div>` : `
      ${feature.problem ? `<div class="feature-desc">${escHTML(feature.problem)}</div>` : ""}
      ${canDispatchFeature ? `<div class="feature-dispatch">${dispatchDropdownHTML}</div>` : ""}
      <div class="detail-grid">
        <div class="detail-progress">
          ${progressRingSVG(pct, color)}
          <div class="progress-label">
            <div class="progress-bar-wrap"><div class="pbar"><div class="pbar-fill" style="width:${pct}%;background:${color}"></div></div></div>
            <span class="task-meta">${tasks.done} done${tasks.in_progress > 0 ? `, ${tasks.in_progress} active` : ""}${tasks.blocked > 0 ? `, ${tasks.blocked} blocked` : ""}</span>
          </div>
        </div>
        ${wavesDots ? `<div class="detail-waves"><div class="detail-label">Waves</div><div class="waves-wrap">${wavesDots}</div></div>` : ""}
        ${repoChips || (feature.cost && feature.cost.usd > 0) ? `<div class="detail-repos"><div class="detail-label">Repositories</div><div class="repos-cost-row">${repoChips ? `<div class="repo-chips">${repoChips}</div>` : ""}${feature.cost && feature.cost.usd > 0 ? `<span class="cost-chip mono">&#128176; ${fmtCost(feature.cost.usd)} &middot; ${fmtTokens(feature.cost.tokens)}</span>` : ""}</div></div>` : ""}
        ${prRows ? `<div class="detail-prs"><div class="detail-label">Pull Requests</div>${prRows}</div>` : ""}
      </div>
      ${taskRows ? `<div class="detail-missing">
        <div class="detail-label">${taskTableLabel} (${sortedTaskList.length})</div>
        <table class="missing-tbl"><thead><tr><th>Task</th><th>Status</th><th>Priority</th><th>Wave</th><th>Execution</th></tr></thead><tbody>${taskRows}</tbody></table>
      </div>` : ""}
      `}
    </div>` : ""}
  </div>`;
}

function renderActiveWorkers(workers) {
  if (workers.length === 0) return "";
  const rows = workers.map((w) => {
    const isBot = w.name.startsWith("agent-") || w.name.startsWith("cloud-");
    const icon = isBot ? "&#129302;" : "&#128100;";
    return `<div class="worker-row">
      <span class="worker-icon">${icon}</span>
      <span class="worker-name">${escHTML(w.name)}</span>
      <span class="worker-tasks mono">${w.tasks} task${w.tasks > 1 ? "s" : ""}</span>
      <span class="worker-features">${w.features.map((f) => escHTML(f)).join(", ")}</span>
    </div>`;
  }).join("");
  return `<div class="workers-section">
    <div class="workers-header" onclick="this.parentElement.classList.toggle('workers-expanded')">
      <div class="detail-label">Active Workers <span class="section-count">${workers.length}</span></div>
      <span class="chevron">&#9662;</span>
    </div>
    <div class="workers-body">${rows}</div>
  </div>`;
}

function renderExecSummary(execCounts) {
  const total = execCounts.autonomous + execCounts.supervised + execCounts.guided;
  if (total === 0) return "";
  const pctAuto = Math.round((execCounts.autonomous / total) * 100);
  const pctSuper = Math.round((execCounts.supervised / total) * 100);
  const pctGuided = 100 - pctAuto - pctSuper;
  return `<div class="exec-summary">
    <div class="detail-label">Execution Mode</div>
    <div class="exec-bar">
      ${pctAuto > 0 ? `<div class="exec-bar-seg exec-bar-autonomous" style="width:${pctAuto}%" title="Autonomous: ${execCounts.autonomous}"></div>` : ""}
      ${pctSuper > 0 ? `<div class="exec-bar-seg exec-bar-supervised" style="width:${pctSuper}%" title="Supervised: ${execCounts.supervised}"></div>` : ""}
      ${pctGuided > 0 ? `<div class="exec-bar-seg exec-bar-guided" style="width:${pctGuided}%" title="Guided: ${execCounts.guided}"></div>` : ""}
    </div>
    <div class="exec-legend">
      ${execCounts.autonomous > 0 ? `<span class="exec-leg-item"><span class="exec-dot" style="background:#a78bfa"></span>Auto ${execCounts.autonomous}</span>` : ""}
      ${execCounts.supervised > 0 ? `<span class="exec-leg-item"><span class="exec-dot" style="background:#818cf8"></span>Supervised ${execCounts.supervised}</span>` : ""}
      ${execCounts.guided > 0 ? `<span class="exec-leg-item"><span class="exec-dot" style="background:#67e8f9"></span>Guided ${execCounts.guided}</span>` : ""}
    </div>
  </div>`;
}

function renderHTML(boardState, prsByFeature, title, linkContext = {}, branding = {}) {
  const { summary, execCounts, activeWorkers, features, generated_at } = boardState;
  const featureItems = features.filter((f) => f.type !== "bug" && f.status !== "orphaned");
  const triageItems = features.filter((f) => f.type === "bug" && f.reportedBy === "telemetry");
  const bugItems = features.filter((f) => f.type === "bug" && f.status !== "orphaned" && f.reportedBy !== "telemetry");
  const totalTasks = features.reduce((s, f) => s + (f.tasks?.total || 0), 0);
  const doneTasks = features.reduce((s, f) => s + (f.tasks?.done || 0), 0);
  const overallPct = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : 0;

  // Group features by epic
  function groupByEpic(items) {
    const groups = new Map();
    for (const f of items) {
      const key = f.epic || "__ungrouped__";
      if (!groups.has(key)) {
        groups.set(key, { epicKey: f.epic, epicTitle: f.epicTitle || "", items: [] });
      }
      if (f.epicTitle && !groups.get(key).epicTitle) {
        groups.get(key).epicTitle = f.epicTitle;
      }
      groups.get(key).items.push(f);
    }
    return groups;
  }

  const epicGroups = groupByEpic(featureItems);
  const hasAnyEpic = [...epicGroups.keys()].some((k) => k !== "__ungrouped__");
  let rowIndex = 0;
  let featureRowsHTML = "";

  if (!hasAnyEpic) {
    // No epics — render flat like before
    featureRowsHTML = featureItems.map((f, i) =>
      renderFeatureRow(f, prsByFeature, i, linkContext, generated_at)
    ).join("\n");
  } else {
    for (const [key, group] of epicGroups) {
      const label = key === "__ungrouped__"
        ? "Other Features"
        : (group.epicTitle ? `Jira: ${group.epicKey}: ${group.epicTitle}` : `Jira: ${group.epicKey}`);
      const jiraUrl = key !== "__ungrouped__" && linkContext.jiraBaseUrl
        ? `${linkContext.jiraBaseUrl}/browse/${group.epicKey}`
        : null;
      const jiraIcon = jiraUrl
        ? ` <a href="${escHTML(jiraUrl)}" target="_blank" rel="noopener" class="epic-group-jira" title="Open in Jira">&#8599;</a>`
        : "";
      featureRowsHTML += `<div class="epic-group" data-epic-group="${escHTML(group.epicKey)}">`;
      featureRowsHTML += `<div class="epic-group-hdr" onclick="this.parentElement.classList.toggle('epic-expanded')">`
        + `<span class="epic-group-chevron">&#9662;</span>`
        + `<span class="epic-group-label">${escHTML(label)}</span>${jiraIcon}`
        + `<span class="section-count">${group.items.length}</span>`
        + `</div>`;
      featureRowsHTML += `<div class="epic-group-body">`;
      for (const f of group.items) {
        featureRowsHTML += renderFeatureRow(f, prsByFeature, rowIndex++, linkContext, generated_at);
      }
      featureRowsHTML += `</div></div>`;
    }
  }

  const bugRowsHTML = bugItems.map((f, i) =>
    renderFeatureRow(f, prsByFeature, featureItems.length + i, linkContext, generated_at)
  ).join("\n");

  const needsReviewCount = triageItems.filter(f => f.status === "needs-review").length;

  const triageRowsHTML = triageItems.map((f, i) =>
    renderFeatureRow(f, prsByFeature, featureItems.length + bugItems.length + i, linkContext, generated_at)
  ).join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escHTML(title)}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%2334d399'/><stop offset='50%25' stop-color='%23818cf8'/><stop offset='100%25' stop-color='%23ec4899'/></linearGradient></defs><rect width='32' height='32' rx='8' fill='url(%23g)'/><text x='16' y='22' text-anchor='middle' font-family='sans-serif' font-weight='800' font-size='18' fill='white'>${escHTML(branding.logo || 'R')}</text></svg>">
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&display=swap');

:root {
  --font-body: 'DM Sans', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --bg: #0a0e27;
  --bg-card: rgba(255,255,255,0.04);
  --bg-card-hover: rgba(255,255,255,0.07);
  --bg-detail: rgba(0,0,0,0.2);
  --bg-input: rgba(255,255,255,0.05);
  --border: rgba(255,255,255,0.08);
  --border-hover: rgba(255,255,255,0.18);
  --text-primary: #e8ecf4;
  --text-secondary: #94a3b8;
  --text-muted: #475569;
  --accent: #818cf8;
  --green: #34d399;
  --blue: #818cf8;
  --amber: #fbbf24;
  --red: #f87171;
  --orange: #fb923c;
  --ring-bg: rgba(255,255,255,0.06);
  --nav-bg: rgba(10,14,39,0.8);
  --glow-green: 0 0 30px rgba(52,211,153,0.15);
  --glow-blue: 0 0 30px rgba(129,140,248,0.15);
  --glow-amber: 0 0 30px rgba(251,191,36,0.15);
  --glow-red: 0 0 30px rgba(248,113,113,0.15);
  --radius: 16px;
  --transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font-body);
  background: var(--bg);
  color: var(--text-primary);
  line-height: 1.6;
  min-height: 100vh;
  overflow-x: hidden;
}

/* ── Animated Aurora Background ── */
body::before {
  content: '';
  position: fixed; inset: 0; z-index: -1;
  background:
    radial-gradient(ellipse 50% 50% at 20% 30%, rgba(0,212,170,0.12), transparent),
    radial-gradient(ellipse 40% 40% at 80% 20%, rgba(124,58,237,0.10), transparent),
    radial-gradient(ellipse 45% 45% at 60% 80%, rgba(59,130,246,0.08), transparent),
    radial-gradient(ellipse 35% 35% at 10% 80%, rgba(236,72,153,0.06), transparent);
  animation: aurora 20s ease-in-out infinite;
  pointer-events: none;
}
@keyframes aurora {
  0%, 100% { background-position: 0% 50%, 100% 50%, 50% 0%, 0% 100%; }
  25% { background-position: 100% 0%, 0% 100%, 50% 50%, 100% 0%; }
  50% { background-position: 50% 100%, 50% 0%, 0% 50%, 50% 50%; }
  75% { background-position: 0% 50%, 100% 50%, 100% 100%, 0% 0%; }
}

/* ── Nav Bar ── */
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: var(--nav-bg);
  backdrop-filter: blur(30px);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  height: 56px;
  display: flex; align-items: center; justify-content: space-between;
}
.nav-left { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.nav-logo {
  width: 28px; height: 28px; border-radius: 10px;
  background: linear-gradient(135deg, var(--green), var(--blue), #ec4899);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; color: #fff;
  box-shadow: 0 0 20px rgba(129,140,248,0.3);
}
.nav-title { font-weight: 700; font-size: 15px; }
.nav-tabs { display: flex; gap: 4px; margin-left: 24px; }
.nav-tab { background: none; border: none; color: var(--text-secondary); font-family: var(--font-body); font-size: 13px; font-weight: 600; padding: 8px 16px; cursor: pointer; border-radius: 8px; transition: var(--transition); }
.nav-tab:hover { color: var(--text-primary); background: rgba(255,255,255,0.05); }
.nav-tab.active { color: var(--text-primary); background: rgba(255,255,255,0.08); }
.triage-badge { display: inline-block; background: var(--red); color: #fff; font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 10px; margin-left: 6px; }
.nav-right { display: flex; align-items: center; gap: 16px; }
.nav-time { font-size: 12px; color: var(--text-secondary); font-family: var(--font-mono); }
.triage-hdr span:first-child { color: var(--red); }
.triage-desc { color: var(--text-secondary); font-size: 13px; margin: -8px 0 16px 0; }
.empty-triage { text-align: center; color: var(--text-muted); padding: 40px; font-size: 14px; }
.feature-dispatch { margin-bottom: 12px; }
.bug-digest { padding: 4px 0; }
.bug-digest-section { margin-bottom: 16px; }
.bug-digest-heading { font-weight: 700; font-size: 13px; color: var(--text-primary); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
.bug-digest-body { font-size: 13px; color: var(--text-secondary); line-height: 1.7; font-family: var(--font-mono); white-space: pre-wrap; }
.settings-btn { background: none; border: none; color: var(--text-secondary); font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 6px; transition: var(--transition); }
.settings-btn:hover { color: var(--text-primary); background: rgba(255,255,255,0.05); }
.modal-overlay { position: fixed; inset: 0; z-index: 200; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px); }
.modal-box { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px; width: 400px; max-width: 90vw; }
.modal-title { font-weight: 700; font-size: 16px; margin-bottom: 16px; }
.modal-label { font-size: 13px; color: var(--text-secondary); display: block; margin-bottom: 6px; }
.modal-input { width: 100%; padding: 8px 12px; background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px; color: var(--text-primary); font-family: var(--font-mono); font-size: 13px; }
.modal-input:focus { outline: none; border-color: var(--accent); }
.modal-hint { font-size: 11px; color: var(--text-muted); margin-top: 6px; }
.modal-actions { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }
.modal-btn { padding: 6px 16px; border-radius: 8px; border: none; font-size: 13px; font-weight: 600; cursor: pointer; background: var(--accent); color: #fff; }
.modal-btn-secondary { background: rgba(255,255,255,0.08); color: var(--text-secondary); }
.dispatch-wrap { position: relative; display: inline-block; margin-bottom: 16px; }
.dispatch-trigger { padding: 8px 16px; border-radius: 8px; border: 1px solid var(--accent); background: rgba(129,140,248,0.1); color: var(--accent); font-size: 13px; font-weight: 600; cursor: pointer; transition: var(--transition); }
.dispatch-trigger:hover { background: rgba(129,140,248,0.2); }
.dispatch-dropdown { display: none; position: absolute; top: 100%; left: 0; margin-top: 4px; background: var(--bg); border: 1px solid var(--border); border-radius: 10px; min-width: 220px; z-index: 50; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
.dispatch-dropdown.open { display: block; }
.dispatch-dropdown button { display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 14px; border: none; background: none; color: var(--text-secondary); font-size: 13px; font-weight: 500; cursor: pointer; text-align: left; transition: var(--transition); font-family: var(--font-body); }
.dispatch-dropdown button:hover { background: rgba(255,255,255,0.05); color: var(--text-primary); }
.dd-color { width: 3px; height: 16px; border-radius: 2px; flex-shrink: 0; }
.dd-group-label { padding: 8px 14px 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); }
.dd-divider { height: 1px; background: var(--border); margin: 4px 0; }
.toast { position: fixed; bottom: 24px; right: 24px; padding: 12px 20px; border-radius: 10px; font-size: 13px; font-weight: 500; color: #fff; z-index: 300; transform: translateY(20px); opacity: 0; transition: all 0.3s ease; pointer-events: none; max-width: 400px; }
.toast-show { transform: translateY(0); opacity: 1; }
.toast-info { background: rgba(129,140,248,0.9); backdrop-filter: blur(8px); }
.toast-success { background: rgba(52,211,153,0.9); backdrop-filter: blur(8px); }
.toast-warn { background: rgba(251,191,36,0.9); color: #1a1a2e; backdrop-filter: blur(8px); }
.toast-error { background: rgba(248,113,113,0.9); backdrop-filter: blur(8px); }
.dismiss-btn { padding: 6px 14px; border-radius: 8px; border: 1px solid var(--border); background: rgba(255,255,255,0.04); color: var(--text-secondary); font-size: 12px; font-weight: 600; cursor: pointer; transition: var(--transition); margin-top: 12px; margin-left: 8px; }
.dismiss-btn:hover { background: rgba(255,255,255,0.08); }

/* ── Layout ── */
.layout { max-width: 1200px; margin: 0 auto; padding: 24px; }

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
  width: 100%; padding: 10px 14px 10px 40px;
  background: var(--bg-input); backdrop-filter: blur(10px);
  border: 1px solid var(--border); border-radius: 12px;
  color: var(--text-primary); font-size: 13px; font-family: var(--font-body);
  outline: none; transition: all var(--transition);
}
.search:focus { border-color: var(--accent); box-shadow: 0 0 20px rgba(129,140,248,0.15); }
.search::placeholder { color: var(--text-muted); }
.filters { display: flex; gap: 4px; flex-wrap: wrap; }
.filter-btn {
  padding: 7px 16px; border: 1px solid var(--border); border-radius: 20px;
  background: var(--bg-input); backdrop-filter: blur(10px);
  color: var(--text-secondary); font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all var(--transition); font-family: var(--font-body);
  white-space: nowrap;
}
.filter-btn:hover { border-color: var(--border-hover); color: var(--text-primary); }
.filter-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); box-shadow: 0 0 20px rgba(129,140,248,0.3); }

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
  backdrop-filter: blur(24px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 10px;
  overflow: hidden;
  transition: all var(--transition);
  animation: fadeUp 0.5s ease-out both;
}
.feature-row:hover { border-color: var(--border-hover); box-shadow: 0 4px 30px rgba(0,0,0,0.2); }

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
.feature-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; line-height: 1.6; }
.feature-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.task-count { font-size: 12px; color: var(--text-secondary); }
.feature-dates { font-size: 11px; color: var(--text-muted); }
.cost-chip { font-size: 12px; color: var(--amber); margin-left: auto; white-space: nowrap; }
.repos-cost-row { display: flex; align-items: center; gap: 6px; width: 100%; }
.cost-summary { font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; font-family: var(--font-mono); }
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
  display: inline-flex; align-items: center; padding: 3px 12px; border-radius: 20px;
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
  white-space: nowrap; backdrop-filter: blur(8px);
}
.lozenge-shipped { background: rgba(52,211,153,0.12); color: var(--green); box-shadow: 0 0 12px rgba(52,211,153,0.1); }
.lozenge-in-progress { background: rgba(129,140,248,0.12); color: var(--blue); box-shadow: 0 0 12px rgba(129,140,248,0.1); }
.lozenge-not-started { background: rgba(251,191,36,0.1); color: var(--amber); }
.lozenge-blocked { background: rgba(248,113,113,0.12); color: var(--red); box-shadow: 0 0 12px rgba(248,113,113,0.1); }
.lozenge-orphaned { background: rgba(107,114,128,0.12); color: var(--text-muted); }
.lozenge-needs-review { background: rgba(245,158,11,0.15); color: var(--amber); }
.lozenge-sev-critical { background: rgba(248,113,113,0.12); color: var(--red); }
.lozenge-sev-high { background: rgba(251,146,60,0.12); color: var(--orange); }
.lozenge-sev-medium { background: rgba(251,191,36,0.1); color: var(--amber); }
.lozenge-sev-low { background: rgba(107,114,128,0.12); color: var(--text-muted); }

/* ── Feature Detail ── */
.feature-detail {
  max-height: 0; overflow: hidden;
  transition: max-height 0.5s cubic-bezier(0.4,0,0.2,1), padding 0.4s;
  background: var(--bg-detail); border-top: 1px solid var(--border);
}
.feature-row.expanded .feature-detail {
  max-height: 3000px; padding: 20px;
}
.detail-grid { display: flex; flex-wrap: wrap; gap: 16px 24px; align-items: center; }
.detail-progress { display: flex; align-items: center; gap: 16px; }
.progress-label { flex: 1; min-width: 80px; }
.progress-bar-wrap { margin-bottom: 4px; }
.pbar { height: 4px; background: var(--ring-bg); border-radius: 2px; overflow: hidden; }
.pbar-fill { height: 100%; border-radius: 2px; box-shadow: 0 0 8px currentColor; transition: width 0.8s ease-out; }
.task-meta { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }
.detail-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-muted); margin-bottom: 8px; }

/* Waves */
.detail-prs { flex-basis: 100%; }
.waves-wrap { display: flex; flex-wrap: wrap; gap: 12px; }
.wave-group { display: flex; align-items: center; gap: 3px; }
.wave-lbl { font-size: 10px; font-weight: 700; color: var(--text-muted); font-family: var(--font-mono); margin-right: 2px; }
.wdot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; transition: transform 0.15s; }
.wdot:hover { transform: scale(1.5); }
.wdot-done { background: var(--green); box-shadow: 0 0 8px rgba(52,211,153,0.5); }
.wdot-in-progress { background: var(--blue); box-shadow: 0 0 8px rgba(129,140,248,0.5); }
.wdot-ready, .wdot-pending { background: var(--text-muted); opacity: 0.3; }
.wdot-blocked { background: var(--red); box-shadow: 0 0 8px rgba(248,113,113,0.5); }
.wdot-paused, .wdot-cancelled { background: var(--text-muted); opacity: 0.2; }

/* Repo Chips */
.repo-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.repo-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; border-radius: 8px;
  background: var(--bg-input); border: 1px solid var(--border);
  font-size: 11px; backdrop-filter: blur(8px);
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
  padding: 10px 16px; background: var(--bg-card); backdrop-filter: blur(24px);
  border: 1px solid var(--border);
  border-radius: var(--radius); margin-bottom: 6px; font-size: 13px; color: var(--text-secondary);
  border-left: 3px solid var(--text-muted);
}

/* ── Epic Groups ── */
.epic-group { margin-bottom: 4px; }
.epic-group-hdr {
  font-size: 12px; font-weight: 600; letter-spacing: 0.04em;
  color: var(--text-secondary); margin: 20px 0 8px; padding: 10px 16px;
  display: flex; align-items: center; gap: 10px;
  background: var(--bg-card); backdrop-filter: blur(24px);
  border: 1px solid var(--border); border-left: 3px solid #60a5fa;
  border-radius: var(--radius);
  cursor: pointer; user-select: none;
  transition: all var(--transition);
}
.epic-group-hdr:hover { background: var(--bg-card-hover); border-color: var(--border-hover); border-left-color: #93bbfc; }
.epic-group-chevron {
  font-size: 12px; color: var(--text-muted);
  transition: transform 0.2s ease;
  display: inline-block;
}
.epic-group:not(.epic-expanded) .epic-group-chevron { transform: rotate(-90deg); }
.epic-group-body { overflow: hidden; }
.epic-group:not(.epic-expanded) .epic-group-body { display: none; }
.epic-group-hdr .epic-group-label { color: #60a5fa; }
.epic-group-hdr .section-count {
  background: var(--bg-input); border-radius: 10px; padding: 1px 8px;
  font-size: 10px; font-family: var(--font-mono);
}
.epic-group-jira {
  color: #60a5fa; text-decoration: none; font-size: 11px;
  transition: all var(--transition);
}
.epic-group-jira:hover { color: #93bbfc; }

/* ── Jira & Spec Links ── */
.jira-pill {
  display: inline-flex; align-items: center;
  border-radius: 6px; overflow: hidden;
  background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.2);
  font-size: 10px; font-weight: 600; font-family: var(--font-mono);
  vertical-align: middle; margin-left: 6px;
  transition: all var(--transition);
}
.epic-filter-toggle {
  padding: 1px 6px; color: #60a5fa; cursor: pointer;
  transition: all var(--transition); user-select: none;
}
.epic-filter-toggle:hover { background: rgba(59,130,246,0.2); }
.epic-filter-toggle.epic-active { background: rgba(59,130,246,0.5); color: #fff; box-shadow: 0 0 10px rgba(59,130,246,0.5); }
.jira-link-icon {
  padding: 1px 5px; color: #60a5fa; text-decoration: none;
  border-left: 1px solid rgba(59,130,246,0.2);
  transition: all var(--transition); font-size: 11px; line-height: 1;
}
.jira-link-icon:hover { background: rgba(59,130,246,0.2); }
.spec-link {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 1px 8px; border-radius: 6px;
  background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.2);
  font-size: 10px; font-weight: 600; color: #a78bfa;
  text-decoration: none; vertical-align: middle; margin-left: 6px;
  transition: all var(--transition);
}
.spec-link:hover { background: rgba(139,92,246,0.2); border-color: rgba(139,92,246,0.4); }
.missing-tbl a { color: var(--accent); text-decoration: none; }
.missing-tbl a:hover { text-decoration: underline; }

/* ── Execution Mode Lozenges ── */
.lozenge-exec-autonomous { background: rgba(167,139,250,0.12); color: #a78bfa; }
.lozenge-exec-supervised { background: rgba(129,140,248,0.12); color: #818cf8; }
.lozenge-exec-guided { background: rgba(103,232,249,0.12); color: #67e8f9; }

/* ── Lifecycle Lozenges ── */
.lozenge-lifecycle-draft { background: rgba(107,114,128,0.12); color: var(--text-muted); font-style: italic; }
.lozenge-lifecycle-paused { background: rgba(251,191,36,0.1); color: var(--amber); }
.lozenge-lifecycle-cancelled { background: rgba(248,113,113,0.1); color: var(--red); text-decoration: line-through; }
.lozenge-lifecycle-replanning { background: rgba(251,146,60,0.1); color: var(--orange); }
.lozenge-lifecycle-completed { background: rgba(52,211,153,0.1); color: var(--green); }
.feature-dimmed { opacity: 0.55; }
.feature-dimmed:hover { opacity: 0.85; }

/* ── Priority Dots ── */
.priority-dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  vertical-align: middle; margin-right: 3px;
}

/* ── Stale Task Highlighting ── */
.stale-task { background: rgba(248,113,113,0.06); }
.stale-warn { color: var(--amber); font-size: 13px; }

/* ── Execution Summary Bar ── */
.exec-summary { margin-left: auto; min-width: 160px; }
.exec-bar {
  display: flex; height: 6px; border-radius: 3px; overflow: hidden;
  background: var(--ring-bg); margin: 6px 0 4px;
}
.exec-bar-seg { transition: width 0.8s ease-out; }
.exec-bar-autonomous { background: #a78bfa; }
.exec-bar-supervised { background: #818cf8; }
.exec-bar-guided { background: #67e8f9; }
.exec-legend { display: flex; gap: 10px; flex-wrap: wrap; }
.exec-leg-item { display: flex; align-items: center; gap: 4px; font-size: 10px; color: var(--text-secondary); font-family: var(--font-mono); }
.exec-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }

/* ── Active Workers ── */
.workers-section {
  background: var(--bg-card); backdrop-filter: blur(24px);
  border: 1px solid var(--border); border-radius: var(--radius);
  margin-bottom: 24px; overflow: hidden;
  animation: fadeUp 0.6s ease-out 0.35s both;
}
.workers-header {
  padding: 14px 20px; display: flex; align-items: center; justify-content: space-between;
  cursor: pointer; user-select: none;
}
.workers-header:hover { background: var(--bg-card-hover); }
.workers-body { max-height: 0; overflow: hidden; transition: max-height 0.4s ease, padding 0.3s; }
.workers-section.workers-expanded .workers-body { max-height: 400px; padding: 0 20px 14px; }
.workers-section.workers-expanded .chevron { transform: rotate(180deg); }
.worker-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 0; font-size: 12px;
  border-bottom: 1px solid var(--border);
}
.worker-row:last-child { border-bottom: none; }
.worker-name { font-weight: 600; color: var(--text-primary); min-width: 120px; }
.worker-tasks { color: var(--text-secondary); min-width: 60px; }
.worker-features { color: var(--text-muted); font-size: 11px; }

/* ── Filter Label ── */
.filter-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-muted); padding: 7px 4px; }

/* ── Theme Toggle (hidden — single theme) ── */
.theme-toggle { display: none; }

/* ── New Feature Button + Modal ── */
.new-feature-btn {
  padding: 6px 16px; border-radius: 8px; border: none;
  background: var(--accent); color: #fff;
  font-size: 13px; font-weight: 600; font-family: var(--font-body);
  cursor: pointer; transition: all var(--transition);
  box-shadow: 0 0 20px rgba(129,140,248,0.2);
}
.new-feature-btn:hover {
  box-shadow: 0 0 30px rgba(129,140,248,0.4);
  transform: translateY(-1px);
}
.nf-overlay {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.nf-modal {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 28px;
  width: 480px; max-width: 90vw;
  animation: fadeUp 0.3s ease-out;
}
.nf-modal h2 {
  font-size: 16px; font-weight: 700; color: var(--text-primary);
  margin: 0 0 8px;
}
.nf-modal p {
  font-size: 13px; color: var(--text-secondary);
  margin: 0 0 20px; line-height: 1.5;
}
.nf-options { display: flex; flex-direction: column; gap: 12px; }
.nf-option {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 16px; border-radius: 12px;
  background: var(--bg-card); border: 1px solid var(--border);
  cursor: pointer; transition: all var(--transition);
  text-decoration: none;
}
.nf-option:hover {
  border-color: var(--border-hover);
  background: var(--bg-card-hover);
}
.nf-option-icon {
  font-size: 20px; width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 10px; background: rgba(129,140,248,0.1);
  flex-shrink: 0;
}
.nf-option-text h3 {
  font-size: 14px; font-weight: 600; color: var(--text-primary);
  margin: 0 0 2px;
}
.nf-option-text p {
  font-size: 12px; color: var(--text-secondary);
  margin: 0;
}
.nf-status {
  font-size: 11px; color: var(--text-muted);
  margin-top: 16px; text-align: center;
  font-family: var(--font-mono);
}
.nf-status.nf-connected { color: var(--green); }
.nf-copy-wrap {
  display: flex; align-items: center; gap: 8px;
  margin-top: 12px;
}
.nf-copy-cmd {
  flex: 1; padding: 8px 12px;
  background: var(--bg-input); border: 1px solid var(--border);
  border-radius: 8px; color: var(--text-primary);
  font-family: var(--font-mono); font-size: 12px;
}
.nf-copy-btn {
  padding: 8px 12px; border-radius: 8px; border: none;
  background: rgba(255,255,255,0.08); color: var(--text-secondary);
  font-size: 12px; font-weight: 600; cursor: pointer;
  transition: all var(--transition);
}
.nf-copy-btn:hover { background: rgba(255,255,255,0.14); color: var(--text-primary); }

/* ── Plan Button ── */
.plan-btn {
  padding: 4px 12px; border-radius: 6px; border: 1px solid var(--accent);
  background: rgba(129,140,248,0.1); color: var(--accent);
  font-size: 11px; font-weight: 600; font-family: var(--font-body);
  cursor: pointer; transition: all var(--transition);
}
.plan-btn:hover:not(:disabled) {
  background: rgba(129,140,248,0.2);
  box-shadow: 0 0 12px rgba(129,140,248,0.2);
}
.plan-btn:disabled {
  opacity: 0.3; cursor: not-allowed;
}

/* ── Footer ── */
.page-footer {
  text-align: center; padding: 32px 0 16px;
  font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);
  letter-spacing: 0.05em;
}

/* ── Animations ── */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Responsive ── */

/* Hamburger (hidden on desktop) */
.hamburger-btn {
  display: none; background: none; border: 1px solid var(--border);
  color: var(--text-primary); font-size: 20px; padding: 4px 10px;
  border-radius: 8px; cursor: pointer; line-height: 1;
}

@media (max-width: 768px) {
  .layout { padding: 16px; }
  .detail-grid { flex-direction: column; align-items: stretch; }
  .search-wrap { flex-basis: 100%; min-width: unset; }
  .filters { flex-basis: 100%; }
  .navbar { height: auto; min-height: 48px; flex-wrap: wrap; padding: 8px 16px; gap: 8px; }
  .nav-time { display: none; }
  .nav-title { font-size: 13px; }
  .feature-header { flex-wrap: wrap; padding: 12px 16px; }
  .feature-left { flex-basis: 100%; }
  .feature-right { flex-basis: 100%; justify-content: flex-start; padding-left: 28px; gap: 8px; }
  .feature-title { white-space: normal; }
  .detail-missing { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .epic-group-hdr { flex-wrap: wrap; gap: 6px; }
}

@media (max-width: 480px) {
  .hamburger-btn { display: flex; align-items: center; }
  .nav-tabs { display: none; width: 100%; order: 3; flex-direction: column; gap: 2px; padding-top: 8px; border-top: 1px solid var(--border); margin-left: 0; }
  .nav-tabs.mobile-open { display: flex; }
  .nav-tab { padding: 10px 16px; font-size: 14px; text-align: left; }
  .nav-title { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .new-feature-btn { padding: 6px 10px; font-size: 11px; }
  .filters { gap: 4px; }
  .filter-btn { padding: 8px 12px; font-size: 11px; min-height: 36px; }
  .feature-header { padding: 10px 12px; }
  .feature-dates { display: none; }
  .feature-right .task-count { display: none; }
  .lozenge { font-size: 9px; padding: 2px 8px; }
  .feature-row.expanded .feature-detail { padding: 12px; }
  .cost-summary { font-size: 12px; }
  .section-hdr { font-size: 10px; }
  .feature-desc { font-size: 12px; }
  .epic-group-hdr { padding: 8px 12px; font-size: 11px; }
  .epic-group-jira { font-size: 9px; }
  .repo-chip { font-size: 10px; padding: 2px 8px; }
  /* Table → stacked card layout on phone */
  .missing-tbl thead { display: none; }
  .missing-tbl tr { display: block; padding: 8px 0; border-bottom: 1px solid var(--border); }
  .missing-tbl tr:last-child { border-bottom: none; }
  .missing-tbl td { display: block; padding: 3px 0; border-bottom: none; font-size: 12px; }
  .missing-tbl td::before {
    content: attr(data-label);
    display: inline-block; width: 72px;
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.08em; color: var(--text-muted);
    vertical-align: middle;
  }
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
    <div class="nav-logo">${escHTML(branding.logo || "R")}</div>
    <span class="nav-title">${escHTML(title)}</span>
  </div>
  <div class="nav-tabs" id="navTabs">
    <button class="nav-tab active" data-tab="features">Features</button>
    ${triageItems.length > 0 ? `<button class="nav-tab" data-tab="triage">Production Alerts${needsReviewCount > 0 ? ` <span class="triage-badge">${needsReviewCount}</span>` : ""}</button>` : ""}
  </div>
  <div class="nav-right">
    <button class="new-feature-btn" id="newFeatureBtn">+ New Feature</button>
    <button class="settings-btn" onclick="document.getElementById('settingsModal').style.display='flex'" title="Settings">&#9881;</button>
    <button class="hamburger-btn" aria-label="Menu" onclick="document.getElementById('navTabs').classList.toggle('mobile-open')">&#9776;</button>
    <span class="nav-time">${new Date(generated_at).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}</span>
  </div>
</nav>

<div id="settingsModal" class="modal-overlay" style="display:none" onclick="if(event.target===this)this.style.display='none'">
  <div class="modal-box">
    <div class="modal-title">Settings</div>
    <label class="modal-label">GitHub Personal Access Token</label>
    <input type="password" id="patInput" class="modal-input" placeholder="ghp_..." value="">
    <p class="modal-hint">Required for Dispatch Agent. Stored in browser only.</p>
    <div class="modal-actions">
      <button class="modal-btn" onclick="localStorage.setItem('gh_pat',document.getElementById('patInput').value);document.getElementById('settingsModal').style.display='none'">Save</button>
      <button class="modal-btn modal-btn-secondary" onclick="document.getElementById('settingsModal').style.display='none'">Cancel</button>
    </div>
  </div>
</div>

<div id="nfOverlay" class="nf-overlay" style="display:none" onclick="if(event.target===this)this.style.display='none'">
  <div class="nf-modal">
    <h2>Start a New Feature</h2>
    <p>Define a feature through an AI-guided interview that produces a validated spec.</p>
    <div class="nf-options">
      <div class="nf-option" id="nfBrowserOption" onclick="nfLaunchBrowser()">
        <div class="nf-option-icon">&#127760;</div>
        <div class="nf-option-text">
          <h3>Browser Interview</h3>
          <p>Step-by-step wizard with live AI chat</p>
        </div>
      </div>
      <div class="nf-option" onclick="nfShowTerminal()">
        <div class="nf-option-icon">&#9000;</div>
        <div class="nf-option-text">
          <h3>Terminal</h3>
          <p>Run the interview in your terminal</p>
        </div>
      </div>
    </div>
    <div id="nfTerminalInstructions" style="display:none">
      <div class="nf-copy-wrap">
        <code class="nf-copy-cmd">relay new</code>
        <button class="nf-copy-btn" onclick="navigator.clipboard.writeText('relay new');this.textContent='Copied!';setTimeout(()=>this.textContent='Copy',1500)">Copy</button>
      </div>
    </div>
    <div id="nfServerStatus" class="nf-status"></div>
  </div>
</div>

<div class="layout tab-content" id="featuresTab">

  ${renderActiveWorkers(activeWorkers)}

  <div class="toolbar">
    <div class="search-wrap">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M11.5 7a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zm-.82 4.74a6 6 0 111.06-1.06l3.04 3.04a.75.75 0 11-1.06 1.06l-3.04-3.04z"/></svg>
      <input type="text" class="search" placeholder="Search features..." id="searchInput">
    </div>
    <div class="filters" id="statusFilters">
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="in-progress">In Progress</button>
      <button class="filter-btn" data-filter="not-started">Not Started</button>
      <button class="filter-btn" data-filter="blocked">Blocked</button>
      <button class="filter-btn" data-filter="shipped">Shipped</button>
    </div>
    <div class="filters" id="execFilters">
      <span class="filter-label">Execution:</span>
      <button class="filter-btn active" data-exec-filter="all">All</button>
      <button class="filter-btn" data-exec-filter="autonomous">&#129302; Auto</button>
      <button class="filter-btn" data-exec-filter="supervised">&#128065; Supervised</button>
      <button class="filter-btn" data-exec-filter="guided">&#128100; Guided</button>
    </div>
  </div>

  ${summary.total_cost_usd > 0 ? `<div class="cost-summary">Total AI spend: <strong>${fmtCost(summary.total_cost_usd)}</strong> &middot; ${fmtTokens(summary.total_tokens)} tokens</div>` : ""}

  ${featureItems.length > 0 ? `<div class="section-hdr"><span>Features</span><span class="section-count">${featureItems.length}</span></div>` : ""}

  <div id="featureList">
    ${featureRowsHTML}
  </div>

  ${bugItems.length > 0 ? `<div class="section-hdr bug-hdr"><span>Bugs</span><span class="section-count">${bugItems.length}</span></div>` : ""}

  <div id="bugList">
    ${bugRowsHTML}
  </div>
</div>

<div class="layout tab-content" id="triageTab" style="display:none">
  <div class="section-hdr triage-hdr"><span>&#128680; Production Alerts</span><span class="section-count">${triageItems.length}</span></div>
  <p class="triage-desc">Issues auto-detected from production telemetry. Review the diagnosis, then decide: plan a fix, dispatch an agent, or dismiss.</p>
  <div id="triageList">
    ${triageRowsHTML}
  </div>
  ${triageItems.length === 0 ? `<div class="empty-triage">No production alerts pending. All clear.</div>` : ""}
</div>

<div class="layout">
  ${renderOrphaned(features)}

  ${branding.footer ? `<div class="page-footer">${escHTML(branding.footer)}</div>` : ""}
</div>

<svg width="0" height="0"><defs><linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="var(--green)"/><stop offset="100%" stop-color="var(--blue)"/></linearGradient></defs></svg>

<script>
// ── Tab Navigation ──
document.querySelectorAll('.nav-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    document.getElementById('featuresTab').style.display = tab === 'features' ? '' : 'none';
    const triageTab = document.getElementById('triageTab');
    if (triageTab) triageTab.style.display = tab === 'triage' ? '' : 'none';
  });
});

// ── Close dropdowns on outside click ──
document.addEventListener('click', (e) => {
  if (!e.target.closest('.dispatch-wrap')) {
    document.querySelectorAll('.dispatch-dropdown.open').forEach(d => d.classList.remove('open'));
  }
});

// ── Toast notifications ──
function showToast(msg, type) {
  const t = document.createElement('div');
  t.className = 'toast toast-' + (type || 'info');
  t.textContent = msg;
  document.body.appendChild(t);
  requestAnimationFrame(() => t.classList.add('toast-show'));
  setTimeout(() => { t.classList.remove('toast-show'); setTimeout(() => t.remove(), 400); }, 4000);
}

// ── Dispatch Agent (cloud or local) ──
function dispatchAgent(slug, mode, target) {
  const modeLabels = {autonomous: 'Autonomous', supervised: 'Supervised', guided: 'Guided'};
  const targetLabels = {cloud: 'Cloud', local: 'Local'};
  document.querySelectorAll('.dispatch-dropdown.open').forEach(d => d.classList.remove('open'));

  if (target === 'local') {
    showToast('Launching local agent in ' + modeLabels[mode] + ' mode...', 'info');
    fetch('http://localhost:7433/api/dispatch/local', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: slug, mode: mode })
    }).then(r => {
      if (r.ok) r.json().then(d => showToast('Local agent launched (PID ' + d.pid + ') in ' + modeLabels[mode] + ' mode', 'success'));
      else r.json().then(d => showToast('Failed: ' + (d.error || 'unknown error'), 'error')).catch(() => r.text().then(t => showToast('Failed: ' + t, 'error')));
    }).catch(() => showToast('Start relay serve to use local dispatch', 'error'));
    return;
  }

  // Cloud dispatch — requires GitHub PAT
  const pat = localStorage.getItem('gh_pat');
  if (!pat) {
    document.getElementById('settingsModal').style.display = 'flex';
    showToast('Configure your GitHub PAT first', 'warn');
    return;
  }
  const repo = 'ChristianJensen/tasks-control-plane';
  showToast('Dispatching cloud agent in ' + modeLabels[mode] + ' mode...', 'info');
  fetch('https://api.github.com/repos/' + repo + '/actions/workflows/set-execution-mode.yml/dispatches', {
    method: 'POST',
    headers: { 'Authorization': 'token ' + pat, 'Accept': 'application/vnd.github.v3+json' },
    body: JSON.stringify({ ref: 'main', inputs: { slug: slug, execution_mode: mode } })
  }).then(r => {
    if (r.ok || r.status === 204) showToast('Cloud agent dispatched in ' + modeLabels[mode] + ' mode', 'success');
    else r.text().then(t => showToast('Failed: ' + t, 'error'));
  }).catch(e => showToast('Error: ' + e.message, 'error'));
}

// Load saved PAT into settings input
const savedPat = localStorage.getItem('gh_pat');
if (savedPat) document.getElementById('patInput').value = savedPat;

// ── Combined Filters (status + execution, intersection logic) ──
const rows = document.querySelectorAll('.feature-row');
const statusBtns = document.querySelectorAll('#statusFilters .filter-btn');
const execBtns = document.querySelectorAll('#execFilters .filter-btn');
const searchInput = document.getElementById('searchInput');
let activeStatus = 'all';
let activeExec = 'all';
let activeEpic = null;

function applyFilters() {
  const q = searchInput.value.toLowerCase();
  rows.forEach(row => {
    let show = true;
    // Search filter (matches title, epic key, and epic title)
    if (q && !(row.dataset.title || '').includes(q) && !(row.dataset.epic || '').toLowerCase().includes(q) && !(row.dataset.epicTitle || '').includes(q)) show = false;
    // Status filter
    if (show && activeStatus !== 'all') {
      if (row.dataset.status !== activeStatus) show = false;
    }
    // Execution filter
    if (show && activeExec !== 'all') {
      if (row.dataset.execution !== activeExec) show = false;
    }
    // Epic filter
    if (show && activeEpic) {
      if ((row.dataset.epic || '') !== activeEpic) show = false;
    }
    row.style.display = show ? '' : 'none';
  });
  // Hide epic groups with no visible rows
  document.querySelectorAll('.epic-group').forEach(g => {
    const body = g.querySelector('.epic-group-body') || g;
    const visible = body.querySelectorAll('.feature-row:not([style*="display: none"])');
    g.style.display = visible.length > 0 ? '' : 'none';
  });
}

statusBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    statusBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeStatus = btn.dataset.filter;
    applyFilters();
  });
});

execBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    execBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeExec = btn.dataset.execFilter;
    applyFilters();
  });
});

// ── Search ──
searchInput.addEventListener('input', applyFilters);
document.addEventListener('keydown', e => {
  if (e.key === '/' && document.activeElement !== searchInput) {
    e.preventDefault();
    searchInput.focus();
  }
  if (e.key === 'Escape' && document.activeElement === searchInput) {
    searchInput.blur();
  }
});

// ── Epic Filtering ──
function setEpicFilter(epicKey) {
  activeEpic = epicKey;
  document.querySelectorAll('.epic-filter-toggle').forEach(el => {
    el.classList.toggle('epic-active', el.dataset.epic === epicKey);
  });
  applyFilters();
}

document.addEventListener('click', e => {
  const toggle = e.target.closest('.epic-filter-toggle');
  if (toggle) {
    e.preventDefault();
    e.stopPropagation();
    const epic = toggle.dataset.epic;
    setEpicFilter(activeEpic === epic ? null : epic);
    return;
  }
  const header = e.target.closest('.feature-header');
  if (header && !e.target.closest('a')) {
    header.parentElement.classList.toggle('expanded');
  }
});

// ── URL param: ?epic=KEY ──
const epicParam = new URLSearchParams(window.location.search).get('epic');
if (epicParam) setEpicFilter(epicParam);

// ── Workers Toggle ──
document.querySelectorAll('.workers-header').forEach(h => {
  h.addEventListener('click', () => h.parentElement.classList.toggle('workers-expanded'));
});

// ── New Feature Modal ──
document.getElementById('newFeatureBtn').addEventListener('click', function() {
  document.getElementById('nfOverlay').style.display = 'flex';
  document.getElementById('nfTerminalInstructions').style.display = 'none';
  nfCheckServer();
});

function nfCheckServer() {
  var statusEl = document.getElementById('nfServerStatus');
  var browserOption = document.getElementById('nfBrowserOption');
  statusEl.textContent = 'Checking for local server...';
  statusEl.className = 'nf-status';

  fetch('http://localhost:7433/api/health', { mode: 'cors' })
    .then(function(r) { return r.json(); })
    .then(function() {
      statusEl.textContent = '\\u25cf relay serve is running';
      statusEl.className = 'nf-status nf-connected';
      browserOption.style.opacity = '1';
      browserOption.style.pointerEvents = 'auto';
    })
    .catch(function() {
      statusEl.textContent = 'Server not running \\u2014 start with: relay serve';
      statusEl.className = 'nf-status';
      browserOption.style.opacity = '0.4';
      browserOption.style.pointerEvents = 'none';
    });
}

function nfLaunchBrowser() {
  window.open('http://localhost:7433/interview', '_blank');
  document.getElementById('nfOverlay').style.display = 'none';
}

function nfShowTerminal() {
  document.getElementById('nfTerminalInstructions').style.display = 'block';
}

// Check if relay serve is running — enable plan buttons if so
fetch('http://localhost:7433/api/health', { mode: 'cors' })
  .then(function(r) { return r.json(); })
  .then(function() {
    document.querySelectorAll('.plan-btn-check').forEach(function(btn) {
      btn.disabled = false;
      btn.title = 'Plan this feature';
    });
  })
  .catch(function() {});

function nfPlanFeature(slug) {
  fetch('http://localhost:7433/api/health', { mode: 'cors' })
    .then(function(r) { return r.json(); })
    .then(function() {
      window.open('http://localhost:7433/plan/' + slug, '_blank');
    })
    .catch(function() {
      var cmd = 'relay plan ' + slug;
      var msg = 'relay serve is not running.\\n\\nStart it with: relay serve\\n\\nOr plan from the terminal: ' + cmd;
      alert(msg);
    });
}
</script>

</body>
</html>`;
}

function renderOrphaned(features) {
  const orphanedFeatures = features.filter((f) => f.status === "orphaned" && f.type !== "bug");
  const orphanedBugs = features.filter((f) => f.status === "orphaned" && f.type === "bug" && f.reportedBy !== "telemetry");
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
const relayConfig = parseRelayConfig(cpDir);

// CLI args override config, config overrides defaults
const title = args.title || relayConfig["status-page-title"] || "Task Tracker - Delivery Report";
const branding = {
  logo: relayConfig["status-page-logo"] || "R",
  footer: relayConfig["status-page-footer"] || "",
};

console.log(`Generating status page from: ${cpDir}`);

const featureFiles = collectFeatureFiles(cpDir, "-feature.md");
const bugFiles = [...collectFeatureFiles(cpDir, "-bug.md"), ...collectBugFiles(cpDir)];
const activeTaskFiles = collectActiveTaskFiles(cpDir);
const archivedTaskFiles = collectArchivedTaskFiles(cpDir);

console.log(`  Features: ${featureFiles.length}, Bugs: ${bugFiles.length}`);
console.log(`  Active tasks: ${activeTaskFiles.length}, Archived: ${archivedTaskFiles.length}`);

const boardState = buildBoardState({ featureFiles, bugFiles, activeTaskFiles, archivedTaskFiles });

// Link context from environment (GitHub Actions provides GITHUB_* automatically)
const linkContext = {
  githubBaseUrl: process.env.GITHUB_SERVER_URL && process.env.GITHUB_REPOSITORY && process.env.GITHUB_SHA
    ? `${process.env.GITHUB_SERVER_URL}/${process.env.GITHUB_REPOSITORY}/blob/${process.env.GITHUB_SHA}`
    : null,
  githubServerUrl: process.env.GITHUB_SERVER_URL || null,
  githubRepository: process.env.GITHUB_REPOSITORY || null,
  jiraBaseUrl: process.env.JIRA_BASE_URL ? process.env.JIRA_BASE_URL.replace(/\/$/, "") : null,
  commitSha: process.env.GITHUB_SHA || null,
};

if (linkContext.githubBaseUrl) console.log(`  GitHub links: SHA ${linkContext.commitSha.slice(0, 7)}`);
if (linkContext.jiraBaseUrl) console.log(`  Jira links: ${linkContext.jiraBaseUrl}`);

let prsByFeature = {};
if (args.prData && existsSync(args.prData)) {
  const prData = JSON.parse(readFileSync(args.prData, "utf8"));
  prsByFeature = matchPRsToFeatures(prData);
  const totalMatched = Object.values(prsByFeature).reduce((s, prs) => s + prs.length, 0);
  console.log(`  PRs loaded: ${prData.length}, matched to features: ${totalMatched}`);
}

const html = renderHTML(boardState, prsByFeature, title, linkContext, branding);

const outputPath = resolve(args.output);
mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, html, "utf8");

console.log(`\nStatus page written to: ${outputPath}`);
console.log(`Summary: ${boardState.summary.shipped} shipped, ${boardState.summary.in_progress} in progress, ${boardState.summary.not_started} not started, ${boardState.summary.blocked} blocked, ${boardState.summary.bugs} bugs`);
