#!/usr/bin/env node
/**
 * generate-command-center.mjs — Self-contained static HTML status dashboard generator.
 *
 * Reads a control plane's features/, queue/, and optional PR data,
 * then generates a self-contained HTML page suitable for GitHub Pages.
 *
 * Zero external dependencies — all aggregation logic is inlined.
 *
 * Usage:
 *   node generate-command-center.mjs --cp-dir <path> [--pr-data <path>] [--output <path>] [--title <string>]
 */

import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync, statSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { execSync } from "node:child_process";
import assert from "node:assert";

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
      const quoted = value.match(/^(["'])(.*)\1$/);
      if (quoted) value = quoted[2];
      fields[key] = value || [];
      currentKey = key;
    } else {
      currentKey = null;
    }
  }
  return { fields, body };
}

// ── Board state aggregation (inlined from dashboard/worker/lib/board-state.js) ─

function deriveFeatureStatus(units, isArchived) {
  if (isArchived || (units.length > 0 && units.every((u) => u.status === "done"))) return "shipped";
  if (units.some((u) => u.status === "blocked")) return "blocked";
  if (units.some((u) => u.status === "done" || u.status === "in-progress")) return "in-progress";
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
    // "billed" absent = legacy task (assume billed, was run before auth tagging).
    // Explicit "false" means Max-plan OAuth — notional cost only.
    billed: String(fields["billed"] ?? "").toLowerCase() !== "false",
    auth_mode: fields["auth-mode"] || "",
    description: extractTaskDescription(body),
    title: deriveTaskTitle(filename),
    sha: sha || null,
    relPath: relPath || "",
    pr_url: fields["pr-url"] || "",
    pr_number: fields["pr-number"] || "",
  };
}

function taskToWorkUnit(t) {
  return {
    kind: "task", id: t.filename, filename: t.filename,
    title: t.title || t.filename.replace(/\.md$/, ""), description: t.description || "",
    status: t.status, priority: t.priority || "normal", wave: t.wave || 0,
    repo: t.repo || "", type: t.type || "feature",
    claimed_by: t.claimed_by || "", claimed_at: t.claimed_at || "",
    sha: t.sha || null, relPath: t.relPath || "",
    pr_url: t.pr_url || "", pr_number: t.pr_number || "",
    repos: t.repo ? [t.repo] : [], prs: t.pr_number ? { [t.repo || ""]: t.pr_number } : {},
    scenarios: [],
  };
}

function sliceToWorkUnit(s) {
  return {
    kind: "slice", id: s.id, filename: "",
    title: s.title, description: "",
    status: s.status, priority: "normal", wave: 0,
    repo: s.repos.join(", "), type: "feature",
    claimed_by: "", claimed_at: "", sha: null, relPath: "",
    pr_url: "", pr_number: "",
    repos: s.repos, prs: s.prs, scenarios: s.scenarios,
  };
}

// A draft spec is "ready to activate" once every Readiness Checklist item is
// ticked — the same gate validate.py enforces at Approve & Activate. Both the
// web wizard and the CLI tick these deterministically via
// wf.tick_readiness_items, so this signal is author-agnostic (works the same
// for CLI- and browser-authored specs). Requires ≥1 item so an empty/malformed
// checklist never reads as complete.
function isSpecComplete(body) {
  const lines = body.split("\n");
  let inSection = false, checked = 0, unchecked = 0;
  for (const line of lines) {
    if (/^##\s+/.test(line)) { inSection = /^##\s+Readiness Checklist\s*$/i.test(line); continue; }
    if (!inSection) continue;
    if (/^\s*[-*]\s+\[[xX]\]/.test(line)) checked++;
    else if (/^\s*[-*]\s+\[ \]/.test(line)) unchecked++;
  }
  return checked > 0 && unchecked === 0;
}

// Single-line `Field: value` inside a US-N story body. Mirrors _bdd.py::_extract_field.
function extractStoryField(body, name) {
  const esc = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const m = body.match(new RegExp("(?:^|\\n)" + esc + "[ \\t]*:[ \\t]*([^\\n]*)"));
  return m ? m[1] : null;
}

// Parse `## User Stories` → US-N slices. Faithful JS mirror of
// _bdd.py::parse_user_stories (that file stays the source of truth).
function parseUserStories(body) {
  const section = body.match(/(?:^|\n)##[ \t]+User Stories[ \t]*\n([\s\S]*?)(?=\n##[ \t]|$)/);
  if (!section) return [];
  const sectionBody = section[1];
  const storyRe = /(?:^|\n)###[ \t]+US-(\d+):[ \t]*([^\n]*)\n([\s\S]*?)(?=\n###[ \t]+US-\d+:|$)/g;
  const stories = [];
  let m;
  while ((m = storyRe.exec(sectionBody)) !== null) {
    const id = `US-${m[1]}`;
    const title = m[2].trim();
    const sBody = m[3];
    const status = (extractStoryField(sBody, "Status") || "pending").trim();
    const reposField = extractStoryField(sBody, "Repos") || "";
    const repos = reposField.split(",").map((r) => r.trim()).filter(Boolean);
    const prs = {};
    for (const repo of repos) prs[repo] = (extractStoryField(sBody, `PR-${repo}`) || "").trim();
    const nums = [...sBody.matchAll(/\*\*BDD-(\d+)\*?\*?/g)].map((x) => Number(x[1]));
    const scenarios = [...new Set(nums)].sort((a, b) => a - b).map((n) => `BDD-${n}`);
    stories.push({ id, title, status, repos, prs, scenarios, raw: sBody });
  }
  return stories;
}

function buildBoardState({ featureFiles = [], bugFiles = [], activeTaskFiles = [], archivedTaskFiles = [], implLogFiles = {} }) {
  const specs = {};
  for (const f of [...featureFiles, ...bugFiles]) {
    const bname = f.path.split("/").pop();
    const slug = bname.replace(/-feature\.md$/, "").replace(/-bug\.md$/, "");
    const isBug = bname.endsWith("-bug.md");
    const { fields, body } = parseFrontmatter(f.content);
    const slices = isBug ? [] : parseUserStories(body);
    specs[slug] = {
      slug, type: isBug ? "bug" : "feature", lifecycle: fields.lifecycle || "draft",
      execution: fields.execution || "supervised",
      epic: (typeof fields.epic === "string" && fields.epic) ? fields.epic : "",
      epicTitle: (typeof fields["epic-title"] === "string" && fields["epic-title"]) ? fields["epic-title"] : "",
      title: fields.title || extractTitle(body, slug), problem: extractProblemStatement(body),
      specComplete: !isBug && isSpecComplete(body),
      bugDigest: isBug ? extractBugDigest(body) : undefined,
      severity: isBug ? fields.severity || "" : undefined,
      reportedBy: isBug ? fields["reported-by"] || "" : undefined,
      createdAt: fields["created-at"] || "",
      completedAt: fields["completed-at"] || "",
      sha: f.sha || null,
      specPath: f.path || "",
      slices,
      totalCostUsd: parseFloat(fields["total-cost-usd"]) || 0,
      totalTokens: parseInt(fields["total-tokens"]) || 0,
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
    const isArchived = tasks.length > 0 && tasks.every(() =>
      archivedTaskFiles.some((f) => f.path.includes(`/_done/${slug}/`))
    );
    const hasQueueTasks = tasks.length > 0;
    const units = hasQueueTasks
      ? tasks.map(taskToWorkUnit)
      : (spec.slices || []).map(sliceToWorkUnit);
    const unitKind = hasQueueTasks ? "task" : (units.length ? "slice" : "none");
    // No decomposed tasks/slices yet: a draft or a freshly-activated feature is
    // "not-started" (stays visible — Draft/Ready column), NOT "orphaned".
    // Reserve "orphaned" (hidden from the board) for specs that are closed out
    // or a lifecycle we don't recognize, so finishing a spec never makes it
    // vanish while it's waiting to be planned.
    const status = units.length > 0
      ? deriveFeatureStatus(units, isArchived)
      : (spec.lifecycle === "draft" || spec.lifecycle === "active"
          ? "not-started" : "orphaned");

    const cost = hasQueueTasks ? {
      usd: tasks.reduce((s, t) => s + (t.cost_usd || 0), 0),
      usd_billed: tasks.reduce((s, t) => s + (t.billed ? (t.cost_usd || 0) : 0), 0),
      input_tokens: tasks.reduce((s, t) => s + (t.input_tokens || 0), 0),
      output_tokens: tasks.reduce((s, t) => s + (t.output_tokens || 0), 0),
    } : {
      usd: spec.totalCostUsd || 0, usd_billed: 0,
      input_tokens: 0, output_tokens: spec.totalTokens || 0,
    };
    cost.tokens = cost.input_tokens + cost.output_tokens;

    const feature = {
      slug, title: spec.title, type: spec.type, lifecycle: spec.lifecycle, status,
      unitKind,
      specComplete: !!spec.specComplete,
      execution: spec.execution, epic: spec.epic, epicTitle: spec.epicTitle,
      createdAt: spec.createdAt || "", completedAt: spec.completedAt || "", specSha: spec.sha || null, specPath: spec.specPath || "",
      problem: spec.problem, cost,
      tasks: units.length > 0 ? taskCounts(units) : null,
      waves: units.length > 0 ? groupByWave(units) : [],
      repos: units.length > 0 ? groupByRepo(units) : {},
      missing: status !== "shipped" ? units : [],
      allTasks: units,
      implLogDigest: implLogDigest(implLogFiles[slug] || ""),
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

  // Grand total cost. total_cost_usd is the notional sum (includes Max-plan
  // work that didn't hit a bill); total_billed_cost_usd is the real spend —
  // use that for any "you were charged" UI.
  summary.total_cost_usd = features.reduce((s, f) => s + (f.cost?.usd || 0), 0);
  summary.total_billed_cost_usd = features.reduce((s, f) => s + (f.cost?.usd_billed || 0), 0);
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
        if (!workerMap[t.claimed_by]) workerMap[t.claimed_by] = { tasks: 0, features: new Set(), taskDetails: [] };
        workerMap[t.claimed_by].tasks++;
        workerMap[t.claimed_by].features.add(t.feature);
        workerMap[t.claimed_by].taskDetails.push({
          title: t.title || t.filename.replace(".md", ""),
          feature: t.feature,
          claimed_at: t.claimed_at || "",
          repo: t.repo || "",
        });
      }
    }
  }
  const activeWorkers = Object.entries(workerMap)
    .sort((a, b) => b[1].tasks - a[1].tasks)
    .map(([name, info]) => ({ name, tasks: info.tasks, features: [...info.features], taskDetails: info.taskDetails }));

  const statusOrder = { blocked: 0, "in-progress": 1, "not-started": 2, orphaned: 3, shipped: 4 };
  features.sort((a, b) => (statusOrder[a.status] ?? 5) - (statusOrder[b.status] ?? 5));

  return { generated_at: new Date().toISOString(), summary, execCounts, activeWorkers, features };
}

// ── Config ───────────────────────────────────────────────────────

function parseRelayConfig(cpDir) {
  const configPath = join(cpDir, ".relay-config");
  const config = { repos: {} };
  if (!existsSync(configPath)) return config;
  const content = readFileSync(configPath, "utf8");
  let inRepos = false;
  for (const line of content.split("\n")) {
    if (/^repos:\s*$/.test(line)) { inRepos = true; continue; }
    if (inRepos) {
      const rm = line.match(/^\s+(\S+):\s*(\S+)/);
      if (rm) { config.repos[rm[1]] = rm[2]; continue; }
      if (!line.startsWith(" ")) inRepos = false;
    }
    const m = line.match(/^([\w-]+):\s*(.+)/);
    if (m) config[m[1]] = m[2].trim();
  }
  return config;
}

// ── CLI args ────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = { cpDir: ".", output: "command-center/index.html", prData: null, title: null, selfTest: false };
  for (let i = 2; i < argv.length; i++) {
    switch (argv[i]) {
      case "--cp-dir": args.cpDir = argv[++i]; break;
      case "--output": args.output = argv[++i]; break;
      case "--pr-data": args.prData = argv[++i]; break;
      case "--title": args.title = argv[++i]; break;
      case "--self-test": args.selfTest = true; break;
      case "--help":
        console.log("Usage: node generate-command-center.mjs --cp-dir <path> [--pr-data <path>] [--output <path>] [--title <string>]");
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

function collectImplLogFiles(cpDir) {
  const map = {};
  const featDir = join(cpDir, "features");
  if (!existsSync(featDir)) return map;
  for (const phase of listFiles(featDir)) {
    const phaseDir = join(featDir, phase);
    if (!(existsSync(phaseDir) && statSync(phaseDir).isDirectory() && FEATURE_PHASES.has(phase))) continue;
    for (const file of listFiles(phaseDir)) {
      if (file.endsWith("-impl-log.md")) {
        const slug = file.replace(/-impl-log\.md$/, "");
        map[slug] = readFileSync(join(phaseDir, file), "utf8");
      }
    }
  }
  return map;
}

// Compact digest of an append-only impl-log. Each entry is a
// `## <ts> — US-N / repo — … — RELAY-COMPLETE: BDD-…` section followed by
// ### Decisions/Discoveries/Spec gaps. Returns null for a header-only stub.
function implLogDigest(content) {
  if (!content) return null;
  const entryRe = /(?:^|\n)##[ \t]+([^\n]*RELAY-COMPLETE[^\n]*)\n([\s\S]*?)(?=\n##[ \t]|$)/g;
  const entries = [];
  let m;
  while ((m = entryRe.exec(content)) !== null) entries.push({ header: m[1].trim(), body: m[2] });
  if (entries.length === 0) return null;
  const last = entries[entries.length - 1];
  const rc = (last.header.match(/RELAY-COMPLETE:\s*(.+)$/) || [])[1] || "";
  const bdd = [...rc.matchAll(/BDD-\d+/g)].map((x) => x[0]);
  const grab = (name) => {
    const mm = last.body.match(new RegExp("###[ \\t]+" + name + "[ \\t]*\\n([\\s\\S]*?)(?=\\n###[ \\t]|$)"));
    return mm ? mm[1].trim() : "";
  };
  return {
    count: entries.length, latestHeader: last.header, bdd,
    decisions: grab("Decisions"), discoveries: grab("Discoveries"), specGaps: grab("Spec gaps"),
  };
}

// ── Exit code classification ───────────────────────────────────

const EXIT_CODE_MAP = {
  1:   { cat: "general-error",     desc: "General script error",        action: "Inspect handoff; check agent environment" },
  2:   { cat: "misuse",            desc: "Shell builtin misuse",        action: "Check task instructions for syntax issues" },
  99:  { cat: "budget-exceeded",   desc: "Agent exceeded cost budget",  action: "Increase budget or simplify task" },
  124: { cat: "timeout",           desc: "Agent timed out",             action: "Increase timeout or split task" },
  126: { cat: "permission-denied", desc: "Command not executable",      action: "Check file permissions" },
  127: { cat: "command-not-found", desc: "Missing command or tool",     action: "Install missing tool or fix PATH" },
  130: { cat: "interrupted",       desc: "Agent interrupted (Ctrl-C)",  action: "Retry — likely transient" },
  137: { cat: "killed",            desc: "Agent killed (OOM)",          action: "Check memory limits" },
};

function classifyExit(code) {
  return EXIT_CODE_MAP[code] || { cat: "unknown", desc: `Unexpected exit ${code}`, action: "Inspect handoff and agent logs" };
}

// ── Handoff collection ─────────────────────────────────────────

function collectHandoffFiles(cpDir) {
  const handoffMap = {};
  const handoffsDir = join(cpDir, "handoffs");
  if (!existsSync(handoffsDir)) return handoffMap;
  for (const feature of listFiles(handoffsDir)) {
    const featureDir = join(handoffsDir, feature);
    if (!statSync(featureDir).isDirectory()) continue;
    for (const file of listFiles(featureDir)) {
      if (!file.endsWith("-handoff.md")) continue;
      try {
        const content = readFileSync(join(featureDir, file), "utf8");
        const { fields, body } = parseFrontmatter(content);
        // Extract exit code from session summary line
        const exitMatch = body.match(/\*\*Exit:\*\*\s*(\d+)/);
        const exitCode = exitMatch ? Number(exitMatch[1]) : null;
        // Extract "What Was Done" commits
        const commitsMatch = body.match(/## What Was Done\s*\n([\s\S]*?)(?=\n##|\n*$)/);
        const commits = commitsMatch ? commitsMatch[1].trim() : "";
        // Extract "Files Changed"
        const filesMatch = body.match(/## Files Changed\s*\n([\s\S]*?)(?=\n##|\n*$)/);
        const filesChanged = filesMatch ? filesMatch[1].trim() : "";
        // Derive task filename from handoff filename
        const taskFilename = file.replace(/-handoff\.md$/, ".md");
        const key = `${feature}/${taskFilename}`;
        const classified = exitCode !== null ? classifyExit(exitCode) : null;
        handoffMap[key] = {
          exitCode, category: classified?.cat || "", description: classified?.desc || "",
          action: classified?.action || "", commits, filesChanged,
          agent: fields.agent || "", timestamp: fields.timestamp || "",
        };
      } catch { /* skip malformed handoff */ }
    }
  }
  return handoffMap;
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
  return { shipped: "Done", "in-progress": "In Progress", "not-started": "Not Started", blocked: "Blocked", orphaned: "Orphaned", "needs-review": "Needs Review" }[status] || status;
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
  const icon = isBot ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><circle cx="12" cy="12" r="10"/><path d="M8 12h.01M16 12h.01M9 16s1.5 1 3 1 3-1 3-1"/></svg>` : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
  return `<span class="worker-icon" title="${escHTML(claimedBy)}">${icon}</span>`;
}

function executionLabel(mode) {
  return { autonomous: "&#129302; Auto", supervised: "Supervised", guided: "Guided" }[mode] || mode;
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
    return (generated - claimed) > 2 * 60 * 60 * 1000;
  } catch { return false; }
}

function ddToggle(cls) {
  return `onclick="event.stopPropagation();this.parentElement.querySelectorAll('.${cls}').forEach(b=>b.classList.remove('active'));this.classList.add('active')"`;
}

function renderDispatchBar(slug) {
  return `<div class="dispatch-bar">
    <div class="db-controls">
      <div class="db-group"><span class="db-label">Target</span><div class="dd-toggle"><button class="dd-target-btn" data-target="cloud" ${ddToggle("dd-target-btn")} title="Run in GitHub Actions"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg> Cloud</button><button class="dd-target-btn active" data-target="local" ${ddToggle("dd-target-btn")} title="Run on this machine"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg> Local</button></div></div>
      <div class="db-group"><span class="db-label">Agents</span><div class="dd-parallel-btns"><button class="dd-par-btn active" data-n="1" ${ddToggle("dd-par-btn")}>1</button><button class="dd-par-btn" data-n="2" ${ddToggle("dd-par-btn")}>2</button><button class="dd-par-btn" data-n="3" ${ddToggle("dd-par-btn")}>3</button><button class="dd-par-btn" data-n="4" ${ddToggle("dd-par-btn")}>4</button></div></div>
      <div class="db-group"><span class="db-label">Mode</span><div class="dd-toggle"><button class="dd-mode-btn active" data-mode="supervised" ${ddToggle("dd-mode-btn")} title="Agent opens a PR. You review before merge."><span class="dd-color" style="background:var(--accent)"></span> Supervised</button><button class="dd-mode-btn" data-mode="autonomous" ${ddToggle("dd-mode-btn")} title="Agent auto-merges. No human review."><span class="dd-color" style="background:var(--green)"></span> Autonomous</button></div></div>
    </div>
    <button class="dd-go-btn" onclick="event.stopPropagation();var bar=this.closest('.dispatch-bar'),t=bar.querySelector('.dd-target-btn.active').dataset.target,m=bar.querySelector('.dd-mode-btn.active').dataset.mode,n=+(bar.querySelector('.dd-par-btn.active')||{dataset:{n:1}}).dataset.n;dispatchAgent('${slug}',m,t,n)">&#9654; Dispatch</button>
  </div>`;
}

function formatAgentName(claimedBy) {
  if (!claimedBy) return "";
  return claimedBy.replace(/^agent-/, "").replace(/^cloud-/, "cloud: ");
}

function renderAgentStatusBar(tasks, generatedAt) {
  const inProgress = tasks.filter(t => t.status === "in-progress" && t.claimed_by);
  if (inProgress.length === 0) return "";
  const agents = {};
  for (const t of inProgress) {
    if (!agents[t.claimed_by]) agents[t.claimed_by] = { tasks: [], earliest: t.claimed_at };
    agents[t.claimed_by].tasks.push(t);
    if (t.claimed_at && (!agents[t.claimed_by].earliest || t.claimed_at < agents[t.claimed_by].earliest)) {
      agents[t.claimed_by].earliest = t.claimed_at;
    }
  }
  const rows = Object.entries(agents).map(([name, info]) => {
    const dur = formatDuration(info.earliest, generatedAt);
    const taskNames = info.tasks.map(t => escHTML(t.filename.replace(".md", ""))).join(", ");
    return `<div class="agent-bar-row">${workerIcon(name)} <span class="agent-bar-name">${escHTML(formatAgentName(name))}</span>${dur ? ` <span class="agent-bar-dur mono">${dur}</span>` : ""}<span class="agent-bar-tasks">${taskNames}</span></div>`;
  }).join("");
  return `<div class="agent-bar"><div class="agent-bar-label">Agent working</div>${rows}</div>`;
}

// ── Triage view still uses collapsible feature rows ─────────────

function renderFeatureRow(feature, prsByFeature, idx, linkContext, generatedAt) {
  const tasks = feature.tasks || { total: 0, done: 0 };
  const pct = tasks.total > 0 ? Math.round((tasks.done / tasks.total) * 100) : 0;
  const isBug = feature.type === "bug";
  const prs = prsByFeature[feature.slug] || [];
  const color = statusColor(feature.status);
  const typeIcon = isBug
    ? `<span class="type-icon type-bug" title="Bug">&#9679;</span>`
    : `<span class="type-icon type-feature" title="Feature">&#9670;</span>`;

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

  const specLinkLabel = isBug ? "Bug Report" : "Feature Specification";
  const specSha = feature.specSha || linkContext.commitSha;
  const specUrl = linkContext.githubServerUrl && linkContext.githubRepository && specSha && feature.specPath
    ? `${linkContext.githubServerUrl}/${linkContext.githubRepository}/blob/${specSha}/${feature.specPath}`
    : null;
  const specLink = specUrl
    ? `<a href="${escHTML(specUrl)}" target="_blank" rel="noopener" class="spec-link" title="View spec @ ${specSha.slice(0, 7)}">${specLinkLabel}</a>`
    : "";

  const execBadge = feature.execution
    ? `<span class="lozenge lozenge-exec-${feature.execution}">${executionLabel(feature.execution)}</span>`
    : "";

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
      <td data-label="Worker">${t.claimed_by ? `${workerIcon(t.claimed_by)} <span class="worker-name">${escHTML(formatAgentName(t.claimed_by))}</span>` : '<span class="worker-empty">&mdash;</span>'}</td>
      <td data-label="Priority">${priorityDot(t.priority)} ${t.priority}</td>
      <td class="mono" data-label="Wave">W${t.wave}</td>
      <td data-label="Execution">${executionLabel(feature.execution || "supervised")}</td>
    </tr>`;
  }).join("");

  const hasBugDigest = isBug && feature.bugDigest && feature.bugDigest.length > 0;
  const hasReadyTasks = (feature.missing || []).some(t => t.status === "ready");
  const hasInProgressTasks = (feature.missing || []).some(t => t.status === "in-progress");
  const canDispatchFeature = !isBug && feature.lifecycle === "active" && hasReadyTasks;
  const showAgentStatus = !isBug && feature.lifecycle === "active" && !hasReadyTasks && hasInProgressTasks;
  const hasDetails = tasks.total > 0 || hasBugDigest || feature.problem;

  const dispatchBarHTML = (hasBugDigest || canDispatchFeature) ? renderDispatchBar(escHTML(feature.slug)) : "";
  const agentStatusHTML = showAgentStatus ? renderAgentStatusBar(feature.missing || [], generatedAt) : "";

  const bugDigestHTML = hasBugDigest ?
    dispatchBarHTML +
    feature.bugDigest.map((s) =>
      `<div class="bug-digest-section"><div class="bug-digest-heading">${escHTML(s.heading)}</div><div class="bug-digest-body">${escHTML(s.content).replace(/\n/g, "<br>")}</div></div>`
    ).join("") +
    `<div class="bug-digest-actions"><button class="dismiss-btn" onclick="event.stopPropagation();showToast('Dismiss not yet implemented','warn')">Dismiss</button></div>`
    : "";

  // Dim only drafts still being authored — a completed (ready-to-activate)
  // draft reads as active work, so don't grey it out.
  const isDimmed = (feature.lifecycle === "draft" && !feature.specComplete) || feature.lifecycle === "paused";

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
        <span class="lozenge lozenge-${feature.status}">${statusLabel(feature.status)}</span>
        ${hasDetails ? `<span class="chevron">&#9662;</span>` : ""}
      </div>
    </div>
    ${hasDetails ? `<div class="feature-detail">
      ${hasBugDigest && tasks.total === 0 ? `<div class="bug-digest">${bugDigestHTML}</div>` : `
      ${feature.problem ? `<div class="feature-desc">${escHTML(feature.problem)}</div>` : ""}
      ${canDispatchFeature ? `<div class="feature-dispatch">${dispatchBarHTML}</div>` : ""}
      ${showAgentStatus ? `<div class="feature-dispatch">${agentStatusHTML}</div>` : ""}
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
        <table class="missing-tbl"><thead><tr><th>Task</th><th>Status</th><th>Worker</th><th>Priority</th><th>Wave</th><th>Execution</th></tr></thead><tbody>${taskRows}</tbody></table>
      </div>` : ""}
      `}
    </div>` : ""}
  </div>`;
}

function formatDuration(claimedAt, generatedAt) {
  if (!claimedAt) return "";
  const diffMs = new Date(generatedAt) - new Date(claimedAt);
  if (diffMs < 0) return "";
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m`;
}

function loadAgentDefs() {
  const scriptDir = dirname(new URL(import.meta.url).pathname);
  const agentsDir = join(scriptDir, "..", "agents");
  const defs = [];
  if (!existsSync(agentsDir)) return defs;
  for (const fname of readdirSync(agentsDir).sort()) {
    if (!fname.endsWith(".md")) continue;
    const type = fname.slice(0, -3);
    const content = readFileSync(join(agentsDir, fname), "utf8");
    const fm = {};
    if (content.startsWith("---")) {
      const parts = content.split("---", 3);
      if (parts.length >= 3) {
        for (const line of parts[1].trim().split("\n")) {
          const idx = line.indexOf(":");
          if (idx > 0) fm[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
        }
      }
    }
    defs.push({ type, name: fm.name || type, description: fm.description || "" });
  }
  return defs;
}

// ── Kanban column mapping ───────────────────────────────────────

const KANBAN_COLUMNS = [
  { key: "draft", label: "Draft", cssClass: "col-draft" },
  { key: "ready", label: "Ready", cssClass: "col-ready" },
  { key: "in-progress", label: "In Progress", cssClass: "col-progress" },
  { key: "done", label: "Done", cssClass: "col-done" },
  { key: "blocked", label: "Blocked", cssClass: "col-blocked" },
];

function assignKanbanColumn(feature) {
  // A fully-authored draft (all Readiness Checklist items ticked) is ready to
  // activate — surface it in "Ready", not "Draft". It stays in features/draft/
  // and still requires Approve & Activate; only the board column changes.
  if (feature.lifecycle === "draft") return feature.specComplete ? "ready" : "draft";
  if (feature.status === "blocked") return "blocked";
  if (feature.status === "shipped") return "done";
  if (feature.status === "in-progress") return "in-progress";
  return "ready";
}

function derivePriority(feature) {
  const tasks = feature.allTasks || [];
  if (tasks.length === 0) return "p2";
  const best = tasks.reduce((best, t) => Math.min(best, priorityOrder[t.priority] ?? 9), 9);
  return best === 0 ? "p0" : best === 1 ? "p1" : "p2";
}

// ── CSS: Kanban layout (new) ────────────────────────────────────

function renderCSS_Kanban() {
  return `
/* ── SIDEBAR ── */
.sidebar { width: var(--sidebar-width); min-width: var(--sidebar-width); background: var(--bg-sidebar); border-right: 1px solid var(--border); display: flex; flex-direction: column; height: 100vh; position: relative; z-index: 10; }
.sidebar-logo { padding: 24px 20px 20px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid var(--border); }
.sidebar-logo-icon { width: 42px; height: 42px; background: linear-gradient(135deg, var(--green), var(--blue), #ec4899); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 800; color: #fff; box-shadow: 0 0 20px rgba(129,140,248,0.3); }
.sidebar-logo-text h1 { font-size: 18px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.5px; }
.sidebar-logo-text span { font-size: 10px; font-weight: 600; color: var(--text-muted); letter-spacing: 2px; text-transform: uppercase; }
.sidebar-nav { flex: 1; overflow-y: auto; padding: 8px 12px; }
.nav-section { margin-top: 20px; }
.nav-section:first-child { margin-top: 12px; }
.nav-section-label { font-size: 10px; font-weight: 700; color: var(--text-muted); letter-spacing: 2px; text-transform: uppercase; padding: 8px 12px 6px; }
.sb-nav-item { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: var(--radius-sm); color: var(--text-secondary); cursor: pointer; transition: var(--transition); font-size: 14px; font-weight: 500; position: relative; user-select: none; }
.sb-nav-item:hover { background: rgba(255,255,255,0.05); color: var(--text-primary); }
.sb-nav-item.active { background: linear-gradient(135deg, rgba(129,140,248,0.2), rgba(99,102,241,0.15)); color: var(--text-primary); box-shadow: 0 0 20px rgba(129,140,248,0.1); }
.sb-nav-item-icon { width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 16px; opacity: 0.7; }
.sb-nav-item.active .sb-nav-item-icon { opacity: 1; }
.sb-nav-badge { margin-left: auto; background: rgba(255,255,255,0.1); color: var(--text-secondary); font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; min-width: 24px; text-align: center; }
.sb-nav-item.active .sb-nav-badge { background: rgba(129,140,248,0.3); color: var(--accent); }
.sidebar-bottom { padding: 12px; border-top: 1px solid var(--border); }
.sb-new-feature-btn { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 12px; background: linear-gradient(135deg, var(--accent), #6366f1); color: white; border: none; border-radius: var(--radius-sm); font-family: var(--font-body); font-size: 14px; font-weight: 600; cursor: pointer; transition: var(--transition); box-shadow: 0 0 20px rgba(129,140,248,0.2); }
.sb-new-feature-btn:hover { box-shadow: 0 0 30px rgba(129,140,248,0.4); transform: translateY(-1px); }

/* ── TOP BAR ── */
.topbar { display: flex; align-items: center; justify-content: flex-end; padding: 12px 28px; border-bottom: 1px solid var(--border); position: relative; z-index: 1; background: rgba(10,14,39,0.6); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); }
.topbar-time { font-size: 12px; color: var(--text-secondary); font-family: var(--font-mono); }

/* ── MAIN CONTENT ── */
.main-wrapper { position: relative; flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.main-content { flex: 1; overflow-y: auto; padding: 24px 28px; position: relative; z-index: 1; }
.view-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.view-title { font-size: 22px; font-weight: 700; }

/* ── VIEWS ── */
.kb-view { display: none; }
.kb-view.active { display: block; }

/* ── FILTER BAR ── */
.filter-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-search { padding: 8px 12px; background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text-primary); font-family: var(--font-body); font-size: 13px; width: 200px; outline: none; transition: var(--transition); }
.filter-search:focus { border-color: var(--accent); box-shadow: 0 0 15px rgba(129,140,248,0.1); }
.filter-search::placeholder { color: var(--text-muted); }
.filter-divider { width: 1px; height: 24px; background: var(--border); }
.filter-chip { padding: 5px 12px; border-radius: 16px; font-size: 12px; font-weight: 500; color: var(--text-secondary); background: var(--bg-card); border: 1px solid var(--border); cursor: pointer; transition: var(--transition); user-select: none; }
.filter-chip:hover { border-color: var(--border-hover); color: var(--text-primary); }
.filter-chip.active { background: rgba(129,140,248,0.12); border-color: rgba(129,140,248,0.3); color: var(--accent); }

/* ── KANBAN BOARD ── */
.kanban { display: flex; gap: 16px; height: calc(100vh - 200px); overflow-x: auto; padding-bottom: 8px; }
.kanban-column { min-width: 280px; width: 280px; flex-shrink: 0; display: flex; flex-direction: column; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; animation: fadeUp 0.5s ease-out both; }
.kanban-column:nth-child(2) { animation-delay: 0.06s; }
.kanban-column:nth-child(3) { animation-delay: 0.12s; }
.kanban-column:nth-child(4) { animation-delay: 0.18s; }
.kanban-column:nth-child(5) { animation-delay: 0.24s; }
.kanban-column-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid var(--border); flex-shrink: 0; cursor: pointer; user-select: none; }
.kanban-column-header:hover { background: rgba(255,255,255,0.03); }
.kanban-column-chevron { font-size: 12px; color: var(--text-muted); transition: transform 0.2s ease; margin-left: 8px; }
.kanban-column.collapsed .kanban-column-chevron { transform: rotate(-90deg); }
.kanban-column.collapsed .kanban-column-body { display: none; }
.kanban-column.collapsed { min-width: 180px; width: 180px; }
.kanban-column-title { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; display: flex; align-items: center; gap: 8px; }
.kanban-column-dot { width: 8px; height: 8px; border-radius: 50%; }
.kanban-column-count { font-size: 12px; font-weight: 600; color: var(--text-muted); background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 8px; }
.kanban-column-body { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.kanban-column-body::-webkit-scrollbar { width: 4px; }
.kanban-column-body::-webkit-scrollbar-track { background: transparent; }
.kanban-column-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
.col-draft .kanban-column-dot { background: var(--text-muted); }
.col-draft .kanban-column-title { color: var(--text-secondary); }
.col-ready .kanban-column-dot { background: var(--amber); box-shadow: var(--glow-amber); }
.col-ready .kanban-column-title { color: var(--amber); }
.col-progress .kanban-column-dot { background: var(--blue); box-shadow: var(--glow-blue); }
.col-progress .kanban-column-title { color: var(--blue); }
.col-done .kanban-column-dot { background: var(--green); box-shadow: var(--glow-green); }
.col-done .kanban-column-title { color: var(--green); }
.col-blocked .kanban-column-dot { background: var(--red); box-shadow: var(--glow-red); }
.col-blocked .kanban-column-title { color: var(--red); }

/* ── KANBAN CARDS ── */
.card { background: var(--bg-detail); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px; cursor: pointer; transition: var(--transition); }
.card:hover { background: var(--bg-card-hover); border-color: var(--border-hover); transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,0.3); }
.card-title { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 6px; line-height: 1.4; }
.card-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 10px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.card-tag { font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
.tag-autonomous { background: rgba(167,139,250,0.15); color: var(--purple); }
.tag-supervised { background: rgba(129,140,248,0.15); color: var(--blue); }
.tag-guided { background: rgba(34,211,238,0.15); color: var(--cyan); }
.tag-p0 { background: rgba(248,113,113,0.15); color: var(--red); }
.tag-p1 { background: rgba(251,191,36,0.15); color: var(--amber); }
.tag-p2 { background: rgba(148,163,184,0.15); color: var(--text-secondary); }
.tag-bug { background: rgba(248,113,113,0.15); color: var(--red); }
.tag-feature { background: rgba(129,140,248,0.15); color: var(--blue); }
.card-progress { margin-top: 10px; height: 3px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden; }
.card-progress-fill { height: 100%; border-radius: 3px; transition: width 0.6s ease; }
.card-footer { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; font-size: 11px; color: var(--text-muted); }
.card-tasks { font-family: var(--font-mono); font-size: 11px; }
.card-epic { font-size: 10px; color: var(--text-muted); padding: 2px 6px; border: 1px solid var(--border); border-radius: 4px; }

/* ── DETAIL PANEL ── */
.detail-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 100; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; }
.detail-overlay.open { opacity: 1; pointer-events: all; }
.detail-panel { position: fixed; top: 0; right: 0; width: 520px; height: 100vh; background: var(--bg-sidebar); border-left: 1px solid var(--border); z-index: 101; transform: translateX(100%); transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1); display: flex; flex-direction: column; overflow: hidden; }
.detail-overlay.open .detail-panel { transform: translateX(0); }
.dp-header { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.dp-header h2 { font-size: 18px; font-weight: 700; }
.dp-close { width: 32px; height: 32px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg-card); color: var(--text-secondary); font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: var(--transition); }
.dp-close:hover { background: var(--bg-card-hover); color: var(--text-primary); }
.dp-body { flex: 1; overflow-y: auto; padding: 24px; }
.dp-section { margin-bottom: 24px; }
.dp-section-title { font-size: 11px; font-weight: 700; color: var(--text-muted); letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 10px; }
.dp-desc { font-size: 14px; color: var(--text-secondary); line-height: 1.6; }
.dp-meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.dp-meta-item { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-xs); padding: 10px 12px; }
.dp-meta-label { font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.dp-meta-value { font-size: 14px; font-weight: 600; }
.dp-progress-bar { height: 6px; background: rgba(255,255,255,0.05); border-radius: 6px; overflow: hidden; margin-bottom: 8px; }
.dp-progress-fill { height: 100%; border-radius: 6px; transition: width 0.6s ease; }
.dp-progress-label { font-size: 12px; color: var(--text-secondary); font-family: var(--font-mono); }
.dp-task-list { display: flex; flex-direction: column; gap: 8px; }
.dp-task { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-xs); font-size: 13px; transition: var(--transition); cursor: pointer; }
.dp-task:hover { background: var(--bg-card-hover); border-color: var(--border-hover); }
.dp-task-header { display: flex; align-items: center; gap: 10px; padding: 10px 12px; }
.dp-task-chevron { font-size: 10px; color: var(--text-muted); transition: transform 0.2s ease; flex-shrink: 0; }
.dp-task.expanded .dp-task-chevron { transform: rotate(90deg); }
.dp-task-expand { max-height: 0; overflow: hidden; transition: max-height 0.3s ease; }
.dp-task.expanded .dp-task-expand { max-height: 500px; }
.dp-task-detail { padding: 0 12px 12px 30px; font-size: 12px; color: var(--text-secondary); line-height: 1.6; }
.dp-task-detail-row { display: flex; gap: 8px; margin-top: 6px; }
.dp-task-detail-label { font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; min-width: 50px; }
.dp-task-detail-value { font-size: 12px; color: var(--text-secondary); font-family: var(--font-mono); }
.dp-task-status { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dp-task-name { flex: 1; color: var(--text-primary); font-weight: 500; line-height: 1.3; }
.dp-task-wave { font-size: 10px; font-family: var(--font-mono); color: var(--text-muted); padding: 2px 6px; background: rgba(255,255,255,0.03); border-radius: 4px; }
.dp-spec-link { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 6px; background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.2); color: var(--purple); font-size: 12px; font-weight: 600; text-decoration: none; transition: var(--transition); font-family: var(--font-body); }
.dp-spec-link:hover { background: rgba(139,92,246,0.2); border-color: rgba(139,92,246,0.4); }
.dp-task-spec-link { display: inline-flex; align-items: center; gap: 4px; color: var(--purple); font-size: 11px; font-weight: 500; text-decoration: none; font-family: var(--font-mono); transition: var(--transition); }
.dp-task-spec-link:hover { color: var(--text-primary); }
.dp-task-pr-btn { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; font-family: var(--font-mono); font-weight: 600; padding: 2px 8px; border-radius: 4px; border: 1px solid var(--accent); color: var(--accent); background: transparent; cursor: pointer; text-decoration: none; transition: var(--transition); flex-shrink: 0; }
.dp-task-pr-btn:hover { background: var(--accent); color: var(--bg); }
.dp-task-pr-btn.awaiting-review { border-color: var(--amber); color: var(--amber); animation: pulse-review 2s ease-in-out infinite; }
.dp-task-pr-btn.awaiting-review:hover { background: var(--amber); color: var(--bg); }
@keyframes pulse-review { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }
.blocked-diag { background: rgba(248,113,113,0.06); border: 1px solid rgba(248,113,113,0.2); border-radius: 8px; padding: 12px; margin-top: 10px; }
.blocked-diag-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.blocked-diag-cat { font-size: 12px; font-weight: 700; color: var(--red); text-transform: uppercase; letter-spacing: 0.5px; }
.blocked-diag-exit { font-size: 10px; font-family: var(--font-mono); color: var(--text-muted); background: rgba(255,255,255,0.05); padding: 1px 6px; border-radius: 4px; }
.blocked-diag-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }
.blocked-diag-action { font-size: 12px; color: var(--amber); margin-top: 6px; }
.blocked-diag-commits { font-size: 11px; color: var(--text-muted); margin-top: 6px; font-family: var(--font-mono); }
.blocked-diag-buttons { display: flex; gap: 8px; margin-top: 10px; }
.blocked-btn-reset, .blocked-btn-triage { font-size: 11px; font-weight: 600; padding: 5px 14px; border-radius: 6px; border: 1px solid; cursor: pointer; font-family: var(--font-body); transition: var(--transition); }
.blocked-btn-reset { background: rgba(248,113,113,0.1); border-color: rgba(248,113,113,0.3); color: var(--red); }
.blocked-btn-reset:hover { background: rgba(248,113,113,0.2); border-color: rgba(248,113,113,0.5); }
.blocked-btn-triage { background: rgba(245,158,11,0.1); border-color: rgba(245,158,11,0.3); color: var(--amber); }
.blocked-btn-resume { background: rgba(99,102,241,0.1); border-color: rgba(99,102,241,0.3); color: var(--accent); }
.blocked-btn-resume:hover { background: rgba(99,102,241,0.2); border-color: rgba(99,102,241,0.5); }
.blocked-btn-triage:hover { background: rgba(245,158,11,0.2); border-color: rgba(245,158,11,0.5); }
.cost-row { display: flex; align-items: center; gap: 16px; padding: 10px 12px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-xs); }
.cost-item { display: flex; align-items: center; gap: 6px; }
.cost-label { font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }
.cost-value { font-size: 14px; font-weight: 600; color: var(--amber); font-family: var(--font-mono); }

/* ── AGENTS VIEW ── */
.agents-subtitle { font-size: 14px; color: var(--text-secondary); margin-top: 4px; margin-bottom: 28px; }
.agents-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.agent-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px; cursor: pointer; transition: var(--transition); display: flex; flex-direction: column; }
.agent-card:hover { background: var(--bg-card-hover); border-color: var(--border-hover); transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.3); }
.agent-card-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.agent-icon { width: 48px; height: 48px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 22px; }
.agent-card-badges { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.agent-status-badge { font-size: 10px; font-weight: 700; padding: 3px 10px; border-radius: 10px; letter-spacing: 0.5px; text-transform: uppercase; }
.agent-status-active { background: rgba(52,211,153,0.15); color: var(--green); }
.agent-status-idle { background: rgba(129,140,248,0.15); color: var(--blue); }
.agent-category { font-size: 10px; font-weight: 600; color: var(--text-muted); letter-spacing: 1.5px; text-transform: uppercase; }
.agent-card-name { font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; }
.agent-card-role { font-size: 13px; color: var(--text-secondary); margin-bottom: 20px; }
.agent-card-footer { margin-top: auto; padding-top: 16px; border-top: 1px solid var(--border); font-size: 12px; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; }

/* ── SETTINGS VIEW ── */
.settings-section { margin-bottom: 32px; }
.settings-section-title { font-size: 14px; font-weight: 700; margin-bottom: 16px; }
.settings-field { margin-bottom: 16px; }
.settings-label { font-size: 13px; color: var(--text-secondary); display: block; margin-bottom: 6px; }
.settings-input { width: 100%; max-width: 400px; padding: 8px 12px; background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px; color: var(--text-primary); font-family: var(--font-mono); font-size: 13px; outline: none; }
.settings-input:focus { border-color: var(--accent); }
.settings-hint { font-size: 11px; color: var(--text-muted); margin-top: 6px; }
.settings-save { padding: 8px 20px; border-radius: 8px; border: none; background: var(--accent); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer; transition: var(--transition); font-family: var(--font-body); }
.settings-save:hover { box-shadow: 0 0 20px rgba(129,140,248,0.3); }

/* ── Responsive (Kanban) ── */
@media (max-width: 1200px) { .kanban-column { min-width: 240px; width: 240px; } .agents-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 900px) {
  .sidebar { width: 60px; min-width: 60px; }
  .sidebar-logo-text, .sb-nav-item span:not(.sb-nav-item-icon):not(.sb-nav-badge), .sidebar-logo-text span { display: none; }
  .sidebar-logo { padding: 16px 12px; justify-content: center; }
  .sidebar-logo-icon { width: 36px; height: 36px; font-size: 16px; }
  .sb-nav-item { justify-content: center; padding: 10px; }
  .sb-nav-badge { display: none; }
  .sb-new-feature-btn span { display: none; }
  .detail-panel { width: 100%; }
  .kanban-column { min-width: 260px; width: 260px; }
  .topbar { padding: 10px 16px; }
  .main-content { padding: 16px; }
}
@media (max-width: 600px) {
  .sidebar { display: none; }
  body { flex-direction: column; }
  .main-wrapper { height: 100vh; }
  .kanban { flex-direction: column; height: auto; overflow-x: visible; overflow-y: auto; max-height: calc(100vh - 160px); }
  .kanban-column { min-width: 100%; width: 100%; }
  .kanban-column-body { max-height: 300px; }
  .filter-bar { gap: 6px; }
  .filter-search { width: 100%; }
  .view-title { font-size: 18px; }
  .agents-grid { grid-template-columns: 1fr; }
  .detail-panel { width: 100%; }
  .dp-meta-grid { grid-template-columns: 1fr; }
  .dispatch-bar { flex-direction: column; align-items: stretch; }
  .db-controls { flex-direction: column; gap: 10px; }
  .cost-row { flex-direction: column; align-items: flex-start; gap: 8px; }
}
`;
}

// ── CSS: Triage/feature-row styles (preserved from old layout) ──

function renderCSS_TriageCompat() {
  return `
/* ── Triage feature rows (compat) ── */
.triage-desc { color: var(--text-secondary); font-size: 13px; margin: -8px 0 16px 0; }
.empty-triage { text-align: center; color: var(--text-muted); padding: 40px; font-size: 14px; }
.feature-dispatch { margin-bottom: 16px; }
.bug-digest { padding: 4px 0; }
.bug-digest-section { margin-bottom: 16px; }
.bug-digest-heading { font-weight: 700; font-size: 13px; color: var(--text-primary); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
.bug-digest-body { font-size: 13px; color: var(--text-secondary); line-height: 1.7; font-family: var(--font-mono); white-space: pre-wrap; }
.feature-row { background: var(--bg-card); backdrop-filter: blur(24px); border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 10px; overflow: hidden; transition: all var(--transition); animation: fadeUp 0.5s ease-out both; }
.feature-row:hover { border-color: var(--border-hover); box-shadow: 0 4px 30px rgba(0,0,0,0.2); }
.feature-header { padding: 14px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; cursor: pointer; user-select: none; transition: background var(--transition); }
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
.chevron { font-size: 12px; color: var(--text-muted); transition: transform 0.2s ease; display: inline-block; }
.feature-row.expanded .chevron { transform: rotate(180deg); }
.type-icon { font-size: 16px; flex-shrink: 0; line-height: 1; }
.type-feature { color: var(--green); }
.type-bug { color: var(--red); }
.lozenge { display: inline-flex; align-items: center; padding: 3px 12px; border-radius: 20px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; white-space: nowrap; backdrop-filter: blur(8px); }
.lozenge-shipped { background: rgba(52,211,153,0.12); color: var(--green); box-shadow: 0 0 12px rgba(52,211,153,0.1); }
.lozenge-in-progress { background: rgba(129,140,248,0.12); color: var(--blue); box-shadow: 0 0 12px rgba(129,140,248,0.1); }
.lozenge-not-started { background: rgba(251,191,36,0.1); color: var(--amber); }
.lozenge-blocked { background: rgba(248,113,113,0.12); color: var(--red); box-shadow: 0 0 12px rgba(248,113,113,0.1); }
.lozenge-orphaned { background: rgba(107,114,128,0.12); color: var(--text-muted); }
.lozenge-needs-review { background: rgba(245,158,11,0.15); color: var(--amber); }
.lozenge-exec-autonomous { background: rgba(167,139,250,0.12); color: #a78bfa; }
.lozenge-exec-supervised { background: rgba(129,140,248,0.12); color: #818cf8; }
.lozenge-exec-guided { background: rgba(103,232,249,0.12); color: #67e8f9; }
.lozenge-lifecycle-draft { background: rgba(107,114,128,0.12); color: var(--text-muted); font-style: italic; }
.lozenge-lifecycle-paused { background: rgba(251,191,36,0.1); color: var(--amber); }
.lozenge-lifecycle-cancelled { background: rgba(248,113,113,0.1); color: var(--red); text-decoration: line-through; }
.lozenge-lifecycle-replanning { background: rgba(251,146,60,0.1); color: var(--orange); }
.lozenge-lifecycle-completed { background: rgba(52,211,153,0.1); color: var(--green); }
.feature-dimmed { opacity: 0.55; }
.feature-dimmed:hover { opacity: 0.85; }
.feature-detail { max-height: 0; overflow: hidden; transition: max-height 0.5s cubic-bezier(0.4,0,0.2,1), padding 0.4s; background: var(--bg-detail); border-top: 1px solid var(--border); }
.feature-row.expanded .feature-detail { max-height: 3000px; padding: 20px; }
.detail-grid { display: flex; flex-wrap: wrap; gap: 16px 24px; align-items: center; }
.detail-progress { display: flex; align-items: center; gap: 16px; }
.progress-label { flex: 1; min-width: 80px; }
.progress-bar-wrap { margin-bottom: 4px; }
.pbar { height: 4px; background: var(--ring-bg); border-radius: 2px; overflow: hidden; }
.pbar-fill { height: 100%; border-radius: 2px; box-shadow: 0 0 8px currentColor; transition: width 0.8s ease-out; }
.task-meta { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }
.detail-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-muted); margin-bottom: 8px; }
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
.repo-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.repo-chip { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 8px; background: var(--bg-input); border: 1px solid var(--border); font-size: 11px; backdrop-filter: blur(8px); }
.repo-chip-name { font-weight: 600; color: var(--text-secondary); }
.repo-chip-count { font-family: var(--font-mono); color: var(--text-primary); font-weight: 700; }
.pr-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; }
.pr-row a { color: var(--accent); text-decoration: none; }
.pr-row a:hover { text-decoration: underline; }
.detail-missing { grid-column: 1 / -1; margin-top: 4px; }
.missing-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.missing-tbl th { text-align: left; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); padding: 6px 12px 6px 0; border-bottom: 1px solid var(--border); }
.missing-tbl td { padding: 8px 12px 8px 0; border-bottom: 1px solid var(--border); color: var(--text-secondary); }
.missing-tbl tr:last-child td { border-bottom: none; }
.missing-tbl .mono { font-family: var(--font-mono); font-size: 11px; }
.missing-tbl a { color: var(--accent); text-decoration: none; }
.missing-tbl a:hover { text-decoration: underline; }
.worker-empty { color: var(--text-muted); }
.worker-icon { font-size: 14px; }
.priority-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; vertical-align: middle; margin-right: 3px; }
.stale-task { background: rgba(248,113,113,0.06); }
.stale-warn { color: var(--amber); font-size: 13px; }
.jira-pill { display: inline-flex; align-items: center; border-radius: 6px; overflow: hidden; background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.2); font-size: 10px; font-weight: 600; font-family: var(--font-mono); vertical-align: middle; margin-left: 6px; transition: all var(--transition); }
.epic-filter-toggle { padding: 1px 6px; color: #60a5fa; cursor: pointer; transition: all var(--transition); user-select: none; }
.epic-filter-toggle:hover { background: rgba(59,130,246,0.2); }
.epic-filter-toggle.epic-active { background: rgba(59,130,246,0.5); color: #fff; box-shadow: 0 0 10px rgba(59,130,246,0.5); }
.jira-link-icon { padding: 1px 5px; color: #60a5fa; text-decoration: none; border-left: 1px solid rgba(59,130,246,0.2); transition: all var(--transition); font-size: 11px; line-height: 1; }
.jira-link-icon:hover { background: rgba(59,130,246,0.2); }
.spec-link { display: inline-flex; align-items: center; gap: 3px; padding: 1px 8px; border-radius: 6px; background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.2); font-size: 10px; font-weight: 600; color: #a78bfa; text-decoration: none; vertical-align: middle; margin-left: 6px; transition: all var(--transition); }
.spec-link:hover { background: rgba(139,92,246,0.2); border-color: rgba(139,92,246,0.4); }
.dismiss-btn { padding: 6px 14px; border-radius: 8px; border: 1px solid var(--border); background: rgba(255,255,255,0.04); color: var(--text-secondary); font-size: 12px; font-weight: 600; cursor: pointer; transition: var(--transition); margin-top: 12px; margin-left: 8px; }
.dismiss-btn:hover { background: rgba(255,255,255,0.08); }
.section-hdr { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; color: var(--text-muted); margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; }
.section-hdr .section-count { background: var(--bg-input); border-radius: 10px; padding: 1px 8px; font-size: 10px; font-family: var(--font-mono); }
.orphaned-section { margin-top: 24px; }
.orphaned-item { padding: 10px 16px; background: var(--bg-card); backdrop-filter: blur(24px); border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 6px; font-size: 13px; color: var(--text-secondary); border-left: 3px solid var(--text-muted); }
`;
}

// ── Kanban card rendering ───────────────────────────────────────

function renderKanbanCard(feature) {
  const tasks = feature.tasks || { total: 0, done: 0 };
  const pct = tasks.total > 0 ? Math.round((tasks.done / tasks.total) * 100) : 0;
  const col = assignKanbanColumn(feature);
  const pri = derivePriority(feature);
  const isBug = feature.type === "bug";
  const execTag = feature.execution === "autonomous" ? "tag-autonomous" : feature.execution === "guided" ? "tag-guided" : "tag-supervised";
  const execLabel = feature.execution === "autonomous" ? "Auto" : feature.execution === "guided" ? "Guided" : "Supervised";
  const progressColor = col === "done" ? "var(--green)" : col === "blocked" ? "var(--red)" : col === "ready" ? "var(--amber)" : "var(--blue)";
  const progressGlow = col === "done" ? "var(--glow-green)" : col === "blocked" ? "var(--glow-red)" : col === "ready" ? "" : "var(--glow-blue)";

  return `<div class="card" data-slug="${escHTML(feature.slug)}" data-exec="${feature.execution || ""}" data-priority="${pri}" data-type="${feature.type}" data-title="${escHTML(feature.title.toLowerCase())}" data-epic="${escHTML(feature.epic || "")}" onclick="openDetail('${escHTML(feature.slug)}')">
  <div class="card-title">${escHTML(feature.title)}</div>
  ${feature.problem ? `<div class="card-desc">${escHTML(feature.problem)}</div>` : ""}
  <div class="card-meta">
    <span class="card-tag ${isBug ? "tag-bug" : "tag-feature"}">${isBug ? "Bug" : "Feature"}</span>
    <span class="card-tag tag-${pri}">${pri.toUpperCase()}</span>
    <span class="card-tag ${execTag}">${execLabel}</span>
  </div>
  ${tasks.total > 0 ? `<div class="card-progress"><div class="card-progress-fill" style="width:${pct}%;background:${progressColor}${progressGlow ? ";box-shadow:" + progressGlow : ""}"></div></div>
  <div class="card-footer">
    <span class="card-tasks">${tasks.done}/${tasks.total} ${feature.unitKind === "slice" ? "slices" : "tasks"}</span>
    ${feature.epic ? `<span class="card-epic">epic: ${escHTML(feature.epic)}</span>` : ""}
  </div>` : `<div class="card-footer">${feature.epic ? `<span class="card-epic">epic: ${escHTML(feature.epic)}</span>` : ""}</div>`}
</div>`;
}

// ── Kanban board rendering ──────────────────────────────────────

function renderKanbanBoard(features) {
  const columns = {};
  for (const col of KANBAN_COLUMNS) columns[col.key] = [];
  for (const f of features) {
    if (f.status === "orphaned") continue;
    const col = assignKanbanColumn(f);
    if (columns[col]) columns[col].push(f);
  }

  return `<div class="kanban">${KANBAN_COLUMNS.map(col => {
    const items = columns[col.key];
    return `<div class="kanban-column ${col.cssClass}" data-col-key="${col.key}">
      <div class="kanban-column-header" onclick="toggleKanbanCol(this)">
        <div class="kanban-column-title"><span class="kanban-column-dot"></span>${col.label}<span class="kanban-column-chevron">&#9662;</span></div>
        <span class="kanban-column-count" data-col="${col.key}">${items.length}</span>
      </div>
      <div class="kanban-column-body">${items.map(f => renderKanbanCard(f)).join("\n")}</div>
    </div>`;
  }).join("\n")}</div>`;
}

// ── Agents view rendering ───────────────────────────────────────

function renderAgentsView(agentDefs, activeWorkers) {
  const activeNames = new Set(activeWorkers.map(w => w.name));
  const agentIcons = { chat: "&#9997;", diagnostic: "&#9889;", plan: "&#9881;", dispatch: "&#9874;", audit: "&#9888;", validate: "&#10003;" };
  const agentColors = { chat: "rgba(129,140,248,0.15)", diagnostic: "rgba(251,191,36,0.15)", plan: "rgba(167,139,250,0.15)", dispatch: "rgba(34,211,238,0.15)", audit: "rgba(248,113,113,0.15)", validate: "rgba(52,211,153,0.15)" };

  return `<div class="kb-view" id="view-agents">
    <div class="view-header"><div class="view-title">Agents</div></div>
    <div class="agents-subtitle">Tap an agent to explore logs, prompts, and performance.</div>
    <div class="agents-grid">
      ${agentDefs.map(a => {
        const isActive = activeNames.has(a.type) || activeNames.has(`agent-${a.type}`) || activeNames.has(`cloud-${a.type}`);
        const icon = agentIcons[a.type] || "&#9881;";
        const color = agentColors[a.type] || "rgba(129,140,248,0.15)";
        return `<div class="agent-card" onclick="window.open('/agent/${a.type}','_blank')">
          <div class="agent-card-top">
            <div class="agent-icon" style="background:${color}">${icon}</div>
            <div class="agent-card-badges">
              <span class="agent-status-badge ${isActive ? "agent-status-active" : "agent-status-idle"}">${isActive ? "Active" : "Idle"}</span>
            </div>
          </div>
          <div class="agent-card-name">${escHTML(a.name)}</div>
          <div class="agent-card-role">${escHTML(a.description)}</div>
        </div>`;
      }).join("\n")}
    </div>
  </div>`;
}

// ── Build embedded feature JSON for client-side detail panel ────

function buildFeaturesJSON(features, prsByFeature, linkContext) {
  return features.filter(f => f.status !== "orphaned").map(f => {
    const tasks = f.tasks || { total: 0, done: 0 };
    const pct = tasks.total > 0 ? Math.round((tasks.done / tasks.total) * 100) : 0;
    const isShipped = f.status === "shipped";
    const taskList = isShipped ? (f.allTasks || []) : (f.missing || []);
    const sorted = [...taskList].sort((a, b) => (a.wave || 0) - (b.wave || 0) || (priorityOrder[a.priority] ?? 9) - (priorityOrder[b.priority] ?? 9));
    const prs = prsByFeature[f.slug] || [];

    return {
      slug: f.slug, title: f.title, type: f.type, status: f.status, lifecycle: f.lifecycle,
      execution: f.execution || "supervised", epic: f.epic || "", epicTitle: f.epicTitle || "",
      problem: f.problem || "", specPath: f.specPath || "", specSha: f.specSha || "",
      unitKind: f.unitKind || "task",
      unitNoun: f.unitKind === "slice" ? "slices" : "tasks",
      implLog: f.implLogDigest || null,
      priority: derivePriority(f), tasks, progress: pct,
      cost: f.cost && f.cost.usd > 0 ? { usd: f.cost.usd, tokens: f.cost.tokens } : null,
      bugDigest: f.bugDigest || null, severity: f.severity || null,
      prs: prs.map(p => ({ number: p.number, title: p.title, url: p.url })),
      taskList: sorted.map(t => {
        const handoffKey = `${f.slug}/${t.filename}`;
        const handoff = t.status === "blocked" ? (handoffMap[handoffKey] || null) : null;
        return {
          name: t.title || t.filename.replace(".md", ""), status: t.status,
          filename: t.filename || "", type: t.type || "feature",
          feature: f.slug || "",
          wave: t.wave || 0, repo: t.repo || "", priority: t.priority || "normal",
          desc: t.description || "", relPath: t.relPath || "", sha: t.sha || "",
          claimed_by: t.claimed_by || "", claimed_at: t.claimed_at || "",
          pr_url: t.pr_url || "", pr_number: t.pr_number || "",
          kind: t.kind || "task", id: t.id || t.filename || "",
          scenarios: t.scenarios || [], repos: t.repos || [],
          bdd: (t.scenarios || []).length,
          prs: t.prs || {},
          handoff: handoff,
        };
      }),
    };
  });
}

// ── Client-side JavaScript ──────────────────────────────────────

function renderClientJS(linkContext) {
  return `
<script>
var LINK_CONTEXT = ${JSON.stringify({ githubServerUrl: linkContext.githubServerUrl || "", githubRepository: linkContext.githubRepository || "", commitSha: linkContext.commitSha || "" })};
var FEATURES_MAP = {};
FEATURES.forEach(function(f) { FEATURES_MAP[f.slug] = f; });

function specUrl(path, sha) {
  if (!path || !LINK_CONTEXT.githubServerUrl || !LINK_CONTEXT.githubRepository) return null;
  var s = sha || LINK_CONTEXT.commitSha;
  if (!s) return null;
  return LINK_CONTEXT.githubServerUrl + '/' + LINK_CONTEXT.githubRepository + '/blob/' + s + '/' + path;
}

var fileIcon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
var extIcon = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';

var statusColors = { done: 'var(--green)', 'in-progress': 'var(--blue)', ready: 'var(--amber)', pending: 'var(--text-muted)', blocked: 'var(--red)' };
var progressColors = { 'In Progress': 'var(--blue)', 'Not Started': 'var(--amber)', Blocked: 'var(--red)', Done: 'var(--green)', Draft: 'var(--text-muted)' };

function fmtTokens(n) { if (n >= 1e6) return (n/1e6).toFixed(1)+'M'; if (n >= 1e3) return (n/1e3).toFixed(0)+'K'; return String(n); }
function fmtCost(usd) { return usd >= 1 ? '$'+usd.toFixed(2) : '$'+usd.toFixed(4); }

// ── View switching ──
function switchView(view, navEl) {
  document.querySelectorAll('.sb-nav-item').forEach(function(el) { el.classList.remove('active'); });
  if (navEl) navEl.classList.add('active');
  document.querySelectorAll('.kb-view').forEach(function(v) { v.classList.remove('active'); });
  var target = document.getElementById('view-' + view);
  if (target) target.classList.add('active');
}

// ── Detail panel ──
function openDetail(slug) {
  var f = FEATURES_MAP[slug];
  if (!f) return;
  document.getElementById('dpTitle').textContent = f.title;
  var sl = statusLabel(f.status);
  var pColor = progressColors[sl] || 'var(--blue)';

  var fUrl = specUrl(f.specPath, f.specSha);
  var specLabel = f.type === 'bug' ? 'Bug Report' : 'Feature Spec';
  var specHtml = fUrl ? '<a href="'+fUrl+'" target="_blank" rel="noopener" class="dp-spec-link" title="View '+specLabel+'">'+fileIcon+' '+specLabel+' '+extIcon+'</a>' : '';

  var costHtml = '';
  if (f.cost && f.cost.usd > 0) {
    costHtml = '<div class="dp-section"><div class="dp-section-title">Cost</div><div class="cost-row"><div class="cost-item"><span style="font-size:14px;opacity:0.7">&#128176;</span><span class="cost-label">Spend</span><span class="cost-value">'+fmtCost(f.cost.usd)+'</span></div><div class="cost-item"><span style="font-size:14px;opacity:0.7">&#9889;</span><span class="cost-label">Tokens</span><span class="cost-value">'+fmtTokens(f.cost.tokens)+'</span></div></div></div>';
  }

  var dispatchHtml = '';
  var hasReadyTasks = f.taskList && f.taskList.some(function(t) { return t.status === 'ready'; });
  var inProgressTasks = f.taskList ? f.taskList.filter(function(t) { return t.status === 'in-progress' && t.claimed_by; }) : [];
  if (f.unitKind === 'slice' && f.lifecycle === 'active' && f.status !== 'shipped') {
    var sliceUnits = (f.taskList || []).filter(function(t) { return t.kind === 'slice'; });
    var workingSlice = sliceUnits.filter(function(t) { return t.status === 'in-progress'; })[0];
    var nextSlice = sliceUnits.filter(function(t) { return t.status === 'pending'; })[0];
    if (workingSlice) {
      dispatchHtml = '<div class="dp-section"><div class="dp-section-title">Actions</div>' +
        '<div class="agent-bar"><div class="agent-bar-row"><span class="agent-bar-name">Agent working</span><span class="agent-bar-tasks">' + workingSlice.id + ': ' + workingSlice.name + '</span></div></div>' +
        '<button class="dd-go-btn" style="width:100%;margin-top:8px" onclick="event.stopPropagation();haltFeature(\\'' + slug + '\\')">&#9209; Halt</button></div>';
    } else if (nextSlice) {
      var repoNote = (nextSlice.repos && nextSlice.repos.length) ? ' <span style="opacity:0.7">(' + nextSlice.repos.join(', ') + ')</span>' : '';
      dispatchHtml = '<div class="dp-section"><div class="dp-section-title">Actions</div>' +
        '<div class="dp-desc" style="margin-bottom:8px">Next slice: <strong>' + nextSlice.id + '</strong>: ' + nextSlice.name + repoNote + '</div>' +
        '<button class="dd-go-btn" style="width:100%" onclick="event.stopPropagation();startNextSlice(\\'' + slug + '\\')">&#9654; Start next slice</button></div>';
    }
  } else if (!hasReadyTasks && inProgressTasks.length > 0) {
    var agentRows = {};
    inProgressTasks.forEach(function(t) {
      if (!agentRows[t.claimed_by]) agentRows[t.claimed_by] = [];
      agentRows[t.claimed_by].push(t.name);
    });
    var agentHtml = Object.keys(agentRows).map(function(name) {
      var displayName = name.replace(/^agent-/, '').replace(/^cloud-/, 'cloud: ');
      var taskNames = agentRows[name].join(', ');
      return '<div class="agent-bar-row"><span class="agent-bar-name">'+displayName+'</span><span class="agent-bar-tasks">'+taskNames+'</span></div>';
    }).join('');
    dispatchHtml = '<div class="dp-section"><div class="dp-section-title">Agent Working</div><div class="agent-bar">'+agentHtml+'</div></div>';
  } else if (sl !== 'Done' && f.tasks && f.tasks.total > 0 && hasReadyTasks) {
    dispatchHtml = '<div class="dp-section"><div class="dp-section-title">Actions</div><div class="dispatch-bar" data-slug="'+slug+'"><div class="db-controls"><div class="db-group"><span class="db-label">Target</span><div class="dd-toggle"><button class="dd-target-btn active" data-target="cloud" onclick="event.stopPropagation();ddToggleBtn(this,\\'dd-target-btn\\')" title="Run in GitHub Actions"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg> Cloud</button><button class="dd-target-btn" data-target="local" onclick="event.stopPropagation();ddToggleBtn(this,\\'dd-target-btn\\')" title="Run on this machine"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg> Local</button></div></div><div class="db-group"><span class="db-label">Mode</span><div class="dd-toggle"><button class="dd-mode-btn active" data-mode="supervised" onclick="event.stopPropagation();ddToggleBtn(this,\\'dd-mode-btn\\')" title="Agent opens a PR."><span class="dd-color" style="background:var(--accent)"></span> Supervised</button><button class="dd-mode-btn" data-mode="autonomous" onclick="event.stopPropagation();ddToggleBtn(this,\\'dd-mode-btn\\')" title="Agent auto-merges."><span class="dd-color" style="background:var(--green)"></span> Autonomous</button></div></div></div><button class="dd-go-btn" onclick="event.stopPropagation();var bar=this.closest(\\'.dispatch-bar\\'),t=bar.querySelector(\\'.dd-target-btn.active\\').dataset.target,m=bar.querySelector(\\'.dd-mode-btn.active\\').dataset.mode;dispatchAgent(\\''+slug+'\\',m,t,1)">&#9654; Dispatch</button></div></div>';
  }

  var prsHtml = '';
  if (f.prs && f.prs.length > 0) {
    prsHtml = '<div class="dp-section"><div class="dp-section-title">Pull Requests</div>' + f.prs.map(function(p) {
      return '<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12px"><svg width="14" height="14" viewBox="0 0 16 16" fill="var(--accent)"><path d="M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z"/></svg><a href="'+p.url+'" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none">#'+p.number+' '+p.title+'</a></div>';
    }).join('') + '</div>';
  }

  var unitsHtml = '';
  if (f.taskList && f.taskList.length) {
    var unitTitle = f.unitKind === 'slice' ? 'Slices' : 'Tasks';
    unitsHtml = '<div class="dp-section"><div class="dp-section-title">'+unitTitle+'</div><div class="dp-task-list">' +
      f.taskList.map(function(t) {
        if (t.kind === 'slice') {
          var prLinks = (t.repos || []).map(function(r) {
            var pr = (t.prs && t.prs[r]) || '';
            return '<span class="dp-task-detail-value">'+r+(pr ? ' '+pr : '')+'</span>';
          }).join(', ');
          return '<div class="dp-task" onclick="this.classList.toggle(\\'expanded\\')">' +
            '<div class="dp-task-header"><div class="dp-task-status" style="background:'+(statusColors[t.status]||'var(--text-muted)')+'"></div>' +
            '<div class="dp-task-name">'+t.id+': '+t.name+'</div>' +
            '<div class="dp-task-wave">'+t.bdd+' BDD</div><div class="dp-task-chevron">&#9654;</div></div>' +
            '<div class="dp-task-expand"><div class="dp-task-detail">' +
              '<div class="dp-task-detail-row"><span class="dp-task-detail-label">Status</span><span class="dp-task-detail-value" style="color:'+(statusColors[t.status]||'var(--text-muted)')+'">'+t.status+'</span></div>' +
              '<div class="dp-task-detail-row"><span class="dp-task-detail-label">Repos</span>'+(prLinks||'<span class="dp-task-detail-value">—</span>')+'</div>' +
              '<div class="dp-task-detail-row"><span class="dp-task-detail-label">Scenarios</span><span class="dp-task-detail-value">'+(t.scenarios||[]).join(', ')+'</span></div>' +
            '</div></div></div>';
        }
        var tUrl = specUrl(t.relPath, t.sha);
        var tLink = tUrl ? '<a href="'+tUrl+'" target="_blank" rel="noopener" class="dp-task-spec-link" onclick="event.stopPropagation()">'+fileIcon+' spec '+extIcon+'</a>' : '';
        var cmpUrl = compareUrl(t);
        var prBtn = t.pr_url
          ? '<a href="'+t.pr_url+'" target="_blank" rel="noopener" class="dp-task-pr-btn'+(t.status==='in-progress'?' awaiting-review':'')+'" onclick="event.stopPropagation()" title="'+(t.status==='in-progress'?'Awaiting review':'View PR')+'">PR #'+t.pr_number+'</a>'
          : (cmpUrl && (t.status === 'in-progress' || t.status === 'done')
            ? '<a href="'+cmpUrl+'" target="_blank" rel="noopener" class="dp-task-pr-btn" onclick="event.stopPropagation()" title="View branch diff">diff</a>'
            : '');
        var workerHtml = t.claimed_by ? '<div class="dp-task-detail-row"><span class="dp-task-detail-label">Worker</span><span class="dp-task-detail-value"><span class="worker-name">'+t.claimed_by.replace(/^agent-/,'').replace(/^cloud-/,'cloud: ')+'</span></span></div>' : '';
        var inProgressHtml = '';
        if (t.pr_url && t.status === 'done') {
          inProgressHtml = '<div class="dp-task-detail-row"><span class="dp-task-detail-label">PR</span><span class="dp-task-detail-value"><a href="'+t.pr_url+'" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none">PR #'+t.pr_number+'</a></span></div>';
        }
        if (t.status === 'in-progress' && t.claimed_at) {
          var ago = timeAgo(t.claimed_at);
          var taskStemIp = (t.filename || '').replace(/\\.md$/, '');
          inProgressHtml = '<div class="dp-task-detail-row"><span class="dp-task-detail-label">Claimed</span><span class="dp-task-detail-value">' + ago + '</span></div>';
          inProgressHtml += '<div class="blocked-diag-buttons" style="margin-top:8px">' +
            '<button class="blocked-btn-reset" onclick="event.stopPropagation();resetTask(\\''+f.slug+'\\',\\''+taskStemIp+'\\')">Reset</button>' +
            '<button class="blocked-btn-resume" onclick="event.stopPropagation();resumeTask(\\''+f.slug+'\\',\\''+taskStemIp+'\\')">Resume</button>' +
          '</div>';
        }
        var blockedDiagHtml = '';
        if (t.status === 'blocked' && t.handoff) {
          var h = t.handoff;
          var taskStem = (t.filename || '').replace(/\\.md$/, '');
          blockedDiagHtml = '<div class="blocked-diag">' +
            '<div class="blocked-diag-header">' +
              '<svg width="14" height="14" viewBox="0 0 16 16" fill="var(--red)"><path d="M8.982 1.566a1.13 1.13 0 00-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 01-1.1 0L7.1 5.995A.905.905 0 018 5zm.002 6a1 1 0 110 2 1 1 0 010-2z"/></svg>' +
              '<span class="blocked-diag-cat">'+(h.category||'unknown')+'</span>' +
              '<span class="blocked-diag-exit">exit '+(h.exitCode||'?')+'</span>' +
            '</div>' +
            '<div class="blocked-diag-desc">'+(h.description||'')+'</div>' +
            '<div class="blocked-diag-action"><strong>Suggested:</strong> '+(h.action||'Inspect logs')+'</div>' +
            (h.commits && h.commits !== '(no commits)' ? '<div class="blocked-diag-commits"><span class="dp-task-detail-label">Last activity</span> '+h.commits.split('\\n')[0]+'</div>' : '') +
            '<div class="blocked-diag-buttons">' +
              '<button class="blocked-btn-reset" onclick="event.stopPropagation();resetTask(\\''+f.slug+'\\',\\''+taskStem+'\\')">Reset Task</button>' +
              '<button class="blocked-btn-triage" onclick="event.stopPropagation();triageFeature(\\''+f.slug+'\\')">Triage Feature</button>' +
            '</div>' +
          '</div>';
        } else if (t.status === 'blocked' && !t.handoff) {
          var taskStem2 = (t.filename || '').replace(/\\.md$/, '');
          blockedDiagHtml = '<div class="blocked-diag">' +
            '<div class="blocked-diag-header">' +
              '<svg width="14" height="14" viewBox="0 0 16 16" fill="var(--red)"><path d="M8.982 1.566a1.13 1.13 0 00-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 01-1.1 0L7.1 5.995A.905.905 0 018 5zm.002 6a1 1 0 110 2 1 1 0 010-2z"/></svg>' +
              '<span class="blocked-diag-cat">blocked</span>' +
            '</div>' +
            '<div class="blocked-diag-desc">No handoff data available. Run triage for details.</div>' +
            '<div class="blocked-diag-buttons">' +
              '<button class="blocked-btn-reset" onclick="event.stopPropagation();resetTask(\\''+f.slug+'\\',\\''+taskStem2+'\\')">Reset Task</button>' +
              '<button class="blocked-btn-triage" onclick="event.stopPropagation();triageFeature(\\''+f.slug+'\\')">Triage Feature</button>' +
            '</div>' +
          '</div>';
        }
        return '<div class="dp-task" onclick="this.classList.toggle(\\'expanded\\')"><div class="dp-task-header"><div class="dp-task-status" style="background:'+(statusColors[t.status]||'var(--text-muted)')+'"></div><div class="dp-task-name">'+t.name+'</div>'+prBtn+'<div class="dp-task-wave">W'+t.wave+'</div><div class="dp-task-chevron">&#9654;</div></div><div class="dp-task-expand"><div class="dp-task-detail">'+(t.desc||'')+'<div class="dp-task-detail-row"><span class="dp-task-detail-label">Status</span><span class="dp-task-detail-value" style="color:'+(statusColors[t.status]||'var(--text-muted)')+'">'+t.status+'</span></div><div class="dp-task-detail-row"><span class="dp-task-detail-label">Repo</span><span class="dp-task-detail-value">'+t.repo+'</span></div>'+workerHtml+inProgressHtml+(tLink?'<div class="dp-task-detail-row" style="margin-top:8px">'+tLink+'</div>':'')+blockedDiagHtml+'</div></div></div>';
      }).join('') + '</div></div>';
  }

  var implLogHtml = '';
  if (f.implLog) {
    var il = f.implLog;
    var bddChips = (il.bdd || []).map(function(b) { return '<span class="card-tag tag-feature">'+b+'</span>'; }).join(' ');
    var blocks = '';
    if (il.decisions)   blocks += '<div class="dp-task-detail-row"><span class="dp-task-detail-label">Decisions</span><span class="dp-task-detail-value">'+il.decisions+'</span></div>';
    if (il.discoveries) blocks += '<div class="dp-task-detail-row"><span class="dp-task-detail-label">Discoveries</span><span class="dp-task-detail-value">'+il.discoveries+'</span></div>';
    if (il.specGaps && il.specGaps !== 'None.') blocks += '<div class="dp-task-detail-row"><span class="dp-task-detail-label">Spec gaps</span><span class="dp-task-detail-value">'+il.specGaps+'</span></div>';
    var logUrl = specUrl((f.specPath||'').replace(/-feature\\.md$/, '-impl-log.md'), f.specSha);
    var logLink = logUrl ? '<a href="'+logUrl+'" target="_blank" rel="noopener" class="dp-spec-link">'+fileIcon+' full log '+extIcon+'</a>' : '';
    implLogHtml = '<div class="dp-section"><div class="dp-section-title">Implementation Log</div>' +
      '<div class="dp-desc" style="margin-bottom:8px">'+il.count+' merged '+(il.count===1?'entry':'entries')+(bddChips?' · '+bddChips:'')+'</div>' +
      blocks + (logLink ? '<div style="margin-top:8px">'+logLink+'</div>' : '') + '</div>';
  }

  document.getElementById('dpBody').innerHTML =
    '<div class="dp-section"><div class="dp-section-title">Description</div><div class="dp-desc">'+(f.problem||'No description.')+'</div>'+(specHtml?'<div style="margin-top:12px">'+specHtml+'</div>':'')+'</div>' +
    '<div class="dp-section"><div class="dp-meta-grid"><div class="dp-meta-item"><div class="dp-meta-label">Status</div><div class="dp-meta-value" style="color:'+pColor+'">'+sl+'</div></div><div class="dp-meta-item"><div class="dp-meta-label">Priority</div><div class="dp-meta-value" style="color:'+(f.priority==='p0'?'var(--red)':f.priority==='p1'?'var(--amber)':'var(--text-secondary)')+'">'+f.priority.toUpperCase()+'</div></div><div class="dp-meta-item"><div class="dp-meta-label">Execution</div><div class="dp-meta-value">'+f.execution+'</div></div><div class="dp-meta-item"><div class="dp-meta-label">Epic</div><div class="dp-meta-value">'+(f.epic||'—')+'</div></div></div></div>' +
    (f.tasks.total > 0 ? '<div class="dp-section"><div class="dp-section-title">Progress</div><div class="dp-progress-bar"><div class="dp-progress-fill" style="width:'+f.progress+'%;background:'+pColor+'"></div></div><div class="dp-progress-label">'+f.tasks.done+' of '+f.tasks.total+' '+f.unitNoun+' complete</div></div>' : '') +
    costHtml + dispatchHtml + prsHtml + unitsHtml + implLogHtml;

  document.getElementById('detailOverlay').classList.add('open');
}

function statusLabel(s) { return {shipped:'Done','in-progress':'In Progress','not-started':'Not Started',blocked:'Blocked',orphaned:'Orphaned','needs-review':'Needs Review'}[s]||s; }

function closeDetail(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('detailOverlay').classList.remove('open');
}

function ddToggleBtn(btn, cls) {
  btn.closest('.dd-toggle').querySelectorAll('.'+cls).forEach(function(b){b.classList.remove('active')});
  btn.classList.add('active');
}

// ── Filtering ──
function applyFilters() {
  var search = document.getElementById('filterSearch').value.toLowerCase();
  var activeExec = []; var activePri = [];
  document.querySelectorAll('.filter-chip.active[data-group="exec"]').forEach(function(c){activeExec.push(c.dataset.value)});
  document.querySelectorAll('.filter-chip.active[data-group="priority"]').forEach(function(c){activePri.push(c.dataset.value)});
  var execAll = activeExec.indexOf('all') >= 0 || activeExec.length === 0;
  var priAll = activePri.length === 0;

  document.querySelectorAll('.card').forEach(function(card) {
    var t = card.dataset.title || '';
    var e = card.dataset.exec || '';
    var p = card.dataset.priority || '';
    var ep = (card.dataset.epic || '').toLowerCase();
    var matchSearch = !search || t.indexOf(search) >= 0 || ep.indexOf(search) >= 0;
    var matchExec = execAll || activeExec.indexOf(e) >= 0;
    var matchPri = priAll || activePri.indexOf(p) >= 0;
    card.style.display = (matchSearch && matchExec && matchPri) ? '' : 'none';
  });
  document.querySelectorAll('.kanban-column-body').forEach(function(body) {
    var col = body.closest('.kanban-column');
    var countEl = col.querySelector('.kanban-column-count');
    var visible = body.querySelectorAll('.card:not([style*="display: none"])').length;
    countEl.textContent = visible;
  });
}

function toggleChip(chip) {
  var group = chip.dataset.group;
  if (chip.dataset.value === 'all') {
    document.querySelectorAll('.filter-chip[data-group="'+group+'"]').forEach(function(c){c.classList.remove('active')});
    chip.classList.add('active');
  } else {
    var allChip = document.querySelector('.filter-chip[data-group="'+group+'"][data-value="all"]');
    if (allChip) allChip.classList.remove('active');
    chip.classList.toggle('active');
    if (!document.querySelector('.filter-chip.active[data-group="'+group+'"]') && allChip) allChip.classList.add('active');
  }
  applyFilters();
}

// ── Toast ──
function toggleKanbanCol(header) {
  var col = header.closest('.kanban-column');
  var key = col.dataset.colKey;
  col.classList.toggle('collapsed');
  var stored = JSON.parse(localStorage.getItem('kanban_collapsed') || '{}');
  stored[key] = col.classList.contains('collapsed');
  localStorage.setItem('kanban_collapsed', JSON.stringify(stored));
}
(function restoreKanbanState() {
  var stored = JSON.parse(localStorage.getItem('kanban_collapsed') || '{}');
  Object.keys(stored).forEach(function(key) {
    if (stored[key]) {
      var col = document.querySelector('.kanban-column[data-col-key="' + key + '"]');
      if (col) col.classList.add('collapsed');
    }
  });
})();

function showToast(msg, type) {
  document.querySelectorAll('.toast').forEach(function(el) { el.remove(); });
  var t = document.createElement('div');
  t.className = 'toast toast-' + (type || 'info');
  t.textContent = msg;
  document.getElementById('toastContainer').appendChild(t);
  requestAnimationFrame(function() { t.classList.add('toast-show'); });
  setTimeout(function() { t.classList.remove('toast-show'); setTimeout(function() { t.remove(); }, 300); }, 4000);
}

// ── Dispatch Agent ──
function dispatchAgent(slug, mode, target, agents) {
  agents = Math.max(1, Math.min(4, agents || 1));
  var modeLabels = {autonomous: 'Autonomous', supervised: 'Supervised'};
  if (target === 'local') {
    showToast('Launching local agent in ' + modeLabels[mode] + ' mode...', 'info');
    fetch('http://localhost:7433/api/dispatch/local', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: slug, mode: mode, agents: agents })
    }).then(function(r) {
      if (r.ok) r.json().then(function(d) { showToast('Local agent launched (PID ' + d.pid + ')', 'success'); });
      else r.json().then(function(d) { showToast('Failed: ' + (d.error || 'unknown'), 'error'); }).catch(function() { r.text().then(function(t) { showToast('Failed: ' + t, 'error'); }); });
    }).catch(function() { showToast('Start relay serve to use local dispatch', 'error'); });
    return;
  }
  var pat = localStorage.getItem('gh_pat');
  if (!pat) { showToast('Set GitHub PAT in Settings first', 'warn'); switchView('settings', document.querySelector('[onclick*="settings"]')); return; }
  var repo = 'ChristianJensen/tasks-control-plane';
  showToast('Dispatching cloud agent in ' + modeLabels[mode] + ' mode...', 'info');
  fetch('https://api.github.com/repos/' + repo + '/actions/workflows/dispatch-agents.yml/dispatches', {
    method: 'POST', headers: { 'Authorization': 'token ' + pat, 'Accept': 'application/vnd.github.v3+json' },
    body: JSON.stringify({ ref: 'main' })
  }).then(function(r) {
    if (r.ok || r.status === 204) showToast('Cloud agent dispatch triggered', 'success');
    else r.text().then(function(t) { showToast('Failed: ' + t, 'error'); });
  }).catch(function(e) { showToast('Error: ' + e.message, 'error'); });
}

function startNextSlice(slug) {
  showToast('Starting agent on next slice...', 'info');
  fetch('http://localhost:7433/api/feature/' + slug + '/loop/start', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ once: true })
  }).then(function(r) {
    if (r.status === 409) { showToast('An agent is already running for this feature', 'warn'); return; }
    if (r.ok) { r.json().then(function(d) { showToast('Agent started on next slice (PID ' + d.pid + ')', 'success'); }); return; }
    r.json().then(function(d) { showToast('Start failed: ' + (d.error || 'unknown'), 'error'); })
             .catch(function() { r.text().then(function(t) { showToast('Start failed: ' + t, 'error'); }); });
  }).catch(function() { showToast('Start relay serve to launch a local agent', 'error'); });
}

function haltFeature(slug) {
  showToast('Sending halt signal...', 'info');
  fetch('http://localhost:7433/api/feature/' + slug + '/loop/halt', { method: 'POST' })
    .then(function(r) { if (r.ok) showToast('Halt signal sent', 'success'); else r.text().then(function(t) { showToast('Halt failed: ' + t, 'error'); }); })
    .catch(function() { showToast('Server offline — cannot halt', 'error'); });
}

// ── Task Reset & Triage ──
function resetTask(feature, task) {
  showToast('Resetting task...', 'info');
  fetch('http://localhost:7433/api/task/reset', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ feature: feature, task: task })
  }).then(function(r) {
    return r.json().then(function(d) {
      if (r.ok) {
        showToast('Task reset to ready — refreshing...', 'success');
        setTimeout(function() { location.reload(); }, 1500);
      } else {
        showToast('Reset failed: ' + (d.error || 'unknown'), 'error');
      }
    });
  }).catch(function() {
    navigator.clipboard.writeText('relay reset ' + feature + ' --task ' + task).then(function() {
      showToast('Server offline — command copied to clipboard', 'warn');
    }).catch(function() {
      showToast('Server offline. Run: relay reset ' + feature + ' --task ' + task, 'error');
    });
  });
}

function triageFeature(feature) {
  showToast('Running triage...', 'info');
  fetch('http://localhost:7433/api/task/triage', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ feature: feature })
  }).then(function(r) {
    return r.json().then(function(d) {
      if (r.ok) {
        var count = (d.tasks || []).length;
        showToast('Triage complete: ' + count + ' blocked task(s). Check terminal for details.', 'success');
      } else {
        showToast('Triage failed: ' + (d.error || 'unknown'), 'error');
      }
    });
  }).catch(function() {
    navigator.clipboard.writeText('relay triage ' + feature).then(function() {
      showToast('Server offline — command copied to clipboard', 'warn');
    }).catch(function() {
      showToast('Server offline. Run: relay triage ' + feature, 'error');
    });
  });
}

function resumeTask(feature, task) {
  showToast('Resuming task...', 'info');
  fetch('http://localhost:7433/api/dispatch/local', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slug: feature, mode: 'supervised', agents: 1 })
  }).then(function(r) {
    if (r.ok) {
      showToast('Agent launched to resume task', 'success');
    } else {
      r.json().then(function(d) { showToast('Resume failed: ' + (d.error || 'unknown'), 'error'); });
    }
  }).catch(function() {
    showToast('Start relay serve first', 'error');
  });
}

function deriveBranchSlug(t) {
  if (!t.filename || !t.repo || !t.feature) return '';
  var stem = t.filename.replace(/\\.md$/, '');
  var waveMatch = stem.match(/^wave-(\\d+)-/);
  var waveNum = waveMatch ? waveMatch[1] : '0';
  var taskSlug = stem.replace(new RegExp('^wave-\\\\d+-' + t.repo + '-'), '');
  var prefix = t.type === 'bug' ? 'fix' : 'agent';
  return prefix + '/' + t.feature + '-w' + waveNum + '-' + taskSlug;
}

function compareUrl(t) {
  var nwo = REPO_MAP[t.repo];
  if (!nwo) return '';
  var branch = deriveBranchSlug(t);
  if (!branch) return '';
  return 'https://github.com/' + nwo + '/compare/main...' + encodeURIComponent(branch);
}

function timeAgo(isoStr) {
  if (!isoStr) return '';
  var ms = Date.now() - new Date(isoStr).getTime();
  var min = Math.floor(ms / 60000);
  if (min < 1) return 'just now';
  if (min < 60) return min + 'm ago';
  var hr = Math.floor(min / 60);
  if (hr < 24) return hr + 'h ' + (min % 60) + 'm ago';
  return Math.floor(hr / 24) + 'd ago';
}

// ── Compliance Report ──
function generateComplianceReport() {
  showToast('Generating compliance report...', 'info');
  fetch('http://localhost:7433/api/report/compliance', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ period: 90, format: 'pdf' })
  }).then(function(r) {
    if (r.ok) showToast('Report generation started — PDF will be saved to reports/', 'success');
    else r.json().then(function(d) { showToast('Failed: ' + (d.error || 'unknown'), 'error'); }).catch(function() { showToast('Failed to start report', 'error'); });
  }).catch(function() { showToast('Start relay serve first', 'error'); });
}

// ── Settings ──
var savedPat = localStorage.getItem('gh_pat');
if (savedPat) document.getElementById('ghPat').value = savedPat;
function savePat() {
  var v = document.getElementById('ghPat').value.trim();
  if (v) { localStorage.setItem('gh_pat', v); showToast('Token saved', 'success'); }
}

// ── Triage feature row expand ──
document.addEventListener('click', function(e) {
  var header = e.target.closest('.feature-header');
  if (header && !e.target.closest('a')) { header.parentElement.classList.toggle('expanded'); }
});

// ── Keyboard shortcuts ──
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeDetail();
  if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
    e.preventDefault(); document.getElementById('filterSearch').focus();
  }
});

// ── URL param: ?epic=KEY ──
var epicParam = new URLSearchParams(window.location.search).get('epic');
if (epicParam) {
  document.getElementById('filterSearch').value = epicParam;
  applyFilters();
}

// ── Clock ──
function updateTime() {
  var el = document.getElementById('topbarTime');
  if (el) el.textContent = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}
updateTime(); setInterval(updateTime, 60000);

// ── Inbox badge ──
fetch('http://localhost:7433/api/inbox?status=new').then(function(r) { return r.json(); }).then(function(items) {
  var badge = document.getElementById('inboxBadge');
  if (badge && items.length > 0) {
    badge.textContent = items.length;
    badge.style.display = '';
    badge.style.background = 'rgba(248,113,113,0.2)';
    badge.style.color = 'var(--red)';
  }
}).catch(function() {});
<\/script>`;
}

// ── Main renderHTML ─────────────────────────────────────────────

function renderHTML(boardState, prsByFeature, title, linkContext = {}, branding = {}) {
  const { summary, execCounts, activeWorkers, features, generated_at } = boardState;
  const agentDefs = loadAgentDefs();
  const triageItems = features.filter((f) => f.type === "bug" && f.reportedBy === "telemetry");
  const allNonOrphan = features.filter(f => f.status !== "orphaned");

  const triageRowsHTML = triageItems.map((f, i) =>
    renderFeatureRow(f, prsByFeature, i, linkContext, generated_at)
  ).join("\n");

  const featuresJSON = buildFeaturesJSON(features, prsByFeature, linkContext);

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
  --bg-sidebar: #070b1e;
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
  --cyan: #22d3ee;
  --purple: #a78bfa;
  --ring-bg: rgba(255,255,255,0.06);
  --nav-bg: rgba(10,14,39,0.8);
  --glow-green: 0 0 30px rgba(52,211,153,0.15);
  --glow-blue: 0 0 30px rgba(129,140,248,0.15);
  --glow-amber: 0 0 30px rgba(251,191,36,0.15);
  --glow-red: 0 0 30px rgba(248,113,113,0.15);
  --radius: 16px;
  --radius-sm: 10px;
  --radius-xs: 6px;
  --transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  --sidebar-width: 260px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body { font-family: var(--font-body); background: var(--bg); color: var(--text-primary); min-height: 100vh; display: flex; overflow: hidden; line-height: 1.6; }

/* Aurora */
.main-wrapper::before { content: ''; position: fixed; inset: 0; z-index: -1; background: radial-gradient(ellipse 50% 50% at 20% 30%, rgba(0,212,170,0.12), transparent), radial-gradient(ellipse 40% 40% at 80% 20%, rgba(124,58,237,0.10), transparent), radial-gradient(ellipse 45% 45% at 60% 80%, rgba(59,130,246,0.08), transparent), radial-gradient(ellipse 35% 35% at 10% 80%, rgba(236,72,153,0.06), transparent); animation: aurora 20s ease-in-out infinite; pointer-events: none; }
@keyframes aurora { 0%, 100% { background-position: 0% 50%, 100% 50%, 50% 0%, 0% 100%; } 25% { background-position: 100% 0%, 0% 100%, 50% 50%, 100% 0%; } 50% { background-position: 50% 100%, 50% 0%, 0% 50%, 50% 50%; } 75% { background-position: 0% 50%, 100% 50%, 100% 100%, 0% 0%; } }
@keyframes fadeUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

/* Dispatch bar */
.dispatch-bar { display: flex; align-items: center; gap: 12px; padding: 10px 16px; background: rgba(129,140,248,0.06); border: 1px solid var(--border); border-radius: 10px; flex-wrap: wrap; }
.db-controls { display: flex; align-items: center; gap: 16px; flex: 1; flex-wrap: wrap; }
.db-group { display: flex; align-items: center; gap: 6px; }
.db-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); }
.dd-color { width: 3px; height: 14px; border-radius: 2px; flex-shrink: 0; }
.dd-toggle { display: flex; gap: 4px; }
.dd-target-btn { display: flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border); background: none; color: var(--text-secondary); font-size: 12px; font-weight: 600; cursor: pointer; transition: var(--transition); font-family: var(--font-body); }
.dd-target-btn:hover { border-color: var(--accent); color: var(--text-primary); }
.dd-target-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.dd-target-btn svg { flex-shrink: 0; }
.dd-parallel-btns { display: flex; gap: 4px; }
.dd-par-btn { width: 28px; height: 28px; border-radius: 6px; border: 1px solid var(--border); background: none; color: var(--text-secondary); font-size: 13px; font-weight: 600; cursor: pointer; transition: var(--transition); font-family: var(--font-mono); display: flex; align-items: center; justify-content: center; }
.dd-par-btn:hover { border-color: var(--accent); color: var(--text-primary); }
.dd-par-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.dd-mode-btn { display: flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border); background: none; color: var(--text-secondary); font-size: 12px; font-weight: 600; cursor: pointer; transition: var(--transition); font-family: var(--font-body); }
.dd-mode-btn:hover { border-color: var(--accent); color: var(--text-primary); }
.dd-mode-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.dd-go-btn { padding: 8px 20px; border-radius: 8px; border: none; background: var(--accent); color: #fff; font-size: 13px; font-weight: 700; cursor: pointer; transition: var(--transition); font-family: var(--font-body); letter-spacing: 0.02em; }
.dd-go-btn:hover { background: #6366f1; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(99,102,241,0.4); }
.agent-bar { padding: 10px 16px; background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.2); border-radius: 10px; }
.agent-bar-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--green); margin-bottom: 6px; }
.agent-bar-row { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 2px 0; }
.agent-bar-name { font-weight: 600; color: var(--text-primary); }
.agent-bar-dur { font-size: 12px; color: var(--text-secondary); }
.agent-bar-tasks { font-size: 12px; color: var(--text-secondary); margin-left: auto; }
.worker-name { font-size: 12px; color: var(--text-secondary); }

/* Toast */
.toast { position: fixed; bottom: 24px; right: 24px; padding: 12px 20px; border-radius: 10px; font-size: 13px; font-weight: 500; color: #fff; z-index: 300; transform: translateY(20px); opacity: 0; transition: all 0.3s ease; pointer-events: none; max-width: 400px; }
.toast-show { transform: translateY(0); opacity: 1; }
.toast-info { background: rgba(129,140,248,0.9); backdrop-filter: blur(8px); }
.toast-success { background: rgba(52,211,153,0.9); backdrop-filter: blur(8px); }
.toast-warn { background: rgba(251,191,36,0.9); color: #1a1a2e; backdrop-filter: blur(8px); }
.toast-error { background: rgba(248,113,113,0.9); backdrop-filter: blur(8px); }

${renderCSS_Kanban()}
${renderCSS_TriageCompat()}

@media print {
  .sidebar, .topbar, .detail-overlay { display: none !important; }
  body { display: block; overflow: visible; }
  .main-wrapper { overflow: visible; }
  .kanban { flex-wrap: wrap; height: auto; }
  .kanban-column { break-inside: avoid; }
}
</style>
</head>
<body>

<!-- SIDEBAR -->
<aside class="sidebar">
  <div class="sidebar-logo">
    <div class="sidebar-logo-icon">${escHTML(branding.logo || "R")}</div>
    <div class="sidebar-logo-text">
      <h1>${escHTML(title.split(" - ")[0] || "Relay")}</h1>
      <span>Command Center</span>
    </div>
  </div>
  <nav class="sidebar-nav">
    <div class="nav-section">
      <div class="nav-section-label">Overview</div>
      <div class="sb-nav-item active" onclick="switchView('kanban', this)">
        <span class="sb-nav-item-icon">&#9776;</span>
        <span>Kanban Board</span>
      </div>
      <a class="sb-nav-item" href="http://localhost:7433/agents" style="text-decoration:none;color:inherit;">
        <span class="sb-nav-item-icon">&#9881;</span>
        <span>Agents</span>
        ${agentDefs.length > 0 ? `<span class="sb-nav-badge">${agentDefs.length}</span>` : ""}
      </a>
    </div>
    <div class="nav-section">
      <div class="nav-section-label">Compliance Readiness</div>
      <div class="sb-nav-item" onclick="generateComplianceReport()" title="Generate SOC2 / ISO 27001 compliance readiness report">
        <span class="sb-nav-item-icon">&#9745;</span>
        <span>Generate Report</span>
      </div>
    </div>
    <div class="nav-section">
      <div class="nav-section-label">Operations</div>
      <div class="sb-nav-item" onclick="window.location.href='http://localhost:7433/inbox'">
        <span class="sb-nav-item-icon">&#9993;</span>
        <span>Inbox</span>
        <span class="sb-nav-badge" id="inboxBadge" style="display:none"></span>
      </div>
      <div class="sb-nav-item" onclick="switchView('settings', this)">
        <span class="sb-nav-item-icon">&#9881;</span>
        <span>Settings</span>
      </div>
    </div>
  </nav>
  <div class="sidebar-bottom">
    <button class="sb-new-feature-btn" onclick="window.open('http://localhost:7433/interview','_blank')">
      + <span>New Feature</span>
    </button>
  </div>
</aside>

<!-- MAIN -->
<div class="main-wrapper">
  <div class="topbar">
    <div class="topbar-time" id="topbarTime">${new Date(generated_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}</div>
  </div>

  <div class="main-content">
    <!-- KANBAN VIEW -->
    <div class="kb-view active" id="view-kanban">
      <div class="view-header"><div class="view-title">Kanban Board</div></div>
      <div class="filter-bar">
        <input class="filter-search" id="filterSearch" placeholder="Search features... (/)" oninput="applyFilters()" />
        <div class="filter-divider"></div>
        <span class="filter-chip active" data-group="exec" data-value="all" onclick="toggleChip(this)">All</span>
        <span class="filter-chip" data-group="exec" data-value="autonomous" onclick="toggleChip(this)">Autonomous</span>
        <span class="filter-chip" data-group="exec" data-value="supervised" onclick="toggleChip(this)">Supervised</span>
        <span class="filter-chip" data-group="exec" data-value="guided" onclick="toggleChip(this)">Guided</span>
        <div class="filter-divider"></div>
        <span class="filter-chip" data-group="priority" data-value="p0" onclick="toggleChip(this)">P0</span>
        <span class="filter-chip" data-group="priority" data-value="p1" onclick="toggleChip(this)">P1</span>
        <span class="filter-chip" data-group="priority" data-value="p2" onclick="toggleChip(this)">P2</span>
      </div>
      ${renderKanbanBoard(allNonOrphan)}
    </div>

    <!-- AGENTS VIEW -->
    ${renderAgentsView(agentDefs, activeWorkers)}

    <!-- TRIAGE VIEW -->
    <div class="kb-view" id="view-triage">
      <div class="view-header"><div class="view-title">Triage</div></div>
      <div class="triage-desc">Issues auto-detected from production telemetry. Review the diagnosis, then decide: plan a fix, dispatch an agent, or dismiss.</div>
      ${triageRowsHTML}
      ${triageItems.length === 0 ? `<div class="empty-triage">No production alerts pending. All clear.</div>` : ""}
    </div>

    <!-- SETTINGS VIEW -->
    <div class="kb-view" id="view-settings">
      <div class="view-header"><div class="view-title">Settings</div></div>
      <div class="settings-section">
        <div class="settings-section-title">GitHub Integration</div>
        <div class="settings-field">
          <label class="settings-label">Personal Access Token</label>
          <input class="settings-input" id="ghPat" type="password" placeholder="ghp_..." />
          <div class="settings-hint">Required for dispatch agent functionality. Stored in browser localStorage.</div>
        </div>
        <button class="settings-save" onclick="savePat()">Save Token</button>
      </div>
    </div>

    <!-- ORPHANED -->
    ${renderOrphaned(features)}
  </div>
</div>

<!-- DETAIL PANEL -->
<div class="detail-overlay" id="detailOverlay" onclick="closeDetail(event)">
  <div class="detail-panel" onclick="event.stopPropagation()">
    <div class="dp-header">
      <h2 id="dpTitle">Feature Title</h2>
      <button class="dp-close" onclick="closeDetail()">&times;</button>
    </div>
    <div class="dp-body" id="dpBody"></div>
  </div>
</div>

<div id="toastContainer"></div>

<script>var FEATURES = ${JSON.stringify(featuresJSON)};var REPO_MAP = ${JSON.stringify(relayConfig.repos || {})};<\/script>
${renderClientJS(linkContext)}

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

function runSelfTest() {
  // parseUserStories: gamification-shaped spec — 1 story, 2 scenarios.
  const spec = [
    "## User Stories",
    "",
    "### US-1: As a user, I want to see progress",
    "",
    "Status: pending",
    "Repos: frontend",
    "",
    "**Scenarios:**",
    "- **BDD-1** GIVEN a WHEN b THEN c",
    "- **BDD-2** GIVEN a WHEN b THEN c",
    "",
    "## Constraints",
  ].join("\n");
  const stories = parseUserStories(spec);
  assert.strictEqual(stories.length, 1, "one story");
  assert.strictEqual(stories[0].id, "US-1");
  assert.strictEqual(stories[0].status, "pending");
  assert.deepStrictEqual(stories[0].repos, ["frontend"]);
  assert.deepStrictEqual(stories[0].scenarios, ["BDD-1", "BDD-2"]);
  // No User Stories section → empty.
  assert.deepStrictEqual(parseUserStories("## Problem\n\nx"), []);
  // deriveFeatureStatus over units.
  const U = (status) => ({ status });
  assert.strictEqual(deriveFeatureStatus([U("pending"), U("pending")], false), "not-started");
  assert.strictEqual(deriveFeatureStatus([U("in-progress"), U("pending")], false), "in-progress");
  assert.strictEqual(deriveFeatureStatus([U("done"), U("done")], false), "shipped");
  assert.strictEqual(deriveFeatureStatus([U("blocked"), U("pending")], false), "blocked");
  // Source selection: queue tasks win even when a spec has User Stories.
  const bs = buildBoardState({
    featureFiles: [{ path: "features/active/demo-feature.md", content: "---\nlifecycle: active\n---\n# Feature Spec: Demo\n\n## User Stories\n\n### US-1: x\n\nStatus: pending\nRepos: web\n\n**Scenarios:**\n- **BDD-1** a\n", sha: null }],
    activeTaskFiles: [{ path: "queue/demo/ready/wave-1-web-x.md", content: "---\ntarget-repo: web\n---\n## Description\n\nx\n", sha: null }],
  });
  const demo = bs.features.find((f) => f.slug === "demo");
  assert.strictEqual(demo.unitKind, "task", "queue tasks win over slices");
  // Slice feature with no queue tasks.
  const bs2 = buildBoardState({
    featureFiles: [{ path: "features/active/slc-feature.md", content: "---\nlifecycle: active\n---\n# Feature Spec: Slc\n\n## User Stories\n\n### US-1: x\n\nStatus: pending\nRepos: frontend\n\n**Scenarios:**\n- **BDD-1** a\n- **BDD-2** b\n", sha: null }],
  });
  const slc = bs2.features.find((f) => f.slug === "slc");
  assert.strictEqual(slc.unitKind, "slice");
  assert.strictEqual(slc.status, "not-started");
  assert.strictEqual(slc.tasks.total, 1);
  assert.strictEqual(slc.tasks.done, 0);
  // implLogDigest: header-only stub → null; one real entry → digest.
  assert.strictEqual(implLogDigest("# Implementation Log — X\n\n"), null);
  const log = [
    "# Implementation Log — X",
    "",
    "## 2026-07-03T10:00:00Z — US-1 / frontend — agent-a — PR-frontend: #12 — RELAY-COMPLETE: BDD-1, BDD-2",
    "",
    "### Decisions",
    "Chose the existing fetch lifecycle.",
    "",
    "### Discoveries",
    "countsByStatus.done can be undefined.",
    "",
    "### Spec gaps",
    "None.",
  ].join("\n");
  const d = implLogDigest(log);
  assert.strictEqual(d.count, 1);
  assert.deepStrictEqual(d.bdd, ["BDD-1", "BDD-2"]);
  assert.match(d.decisions, /existing fetch lifecycle/);
  assert.match(d.discoveries, /undefined/);
  console.log("self-test: OK");
}

// ── Main ────────────────────────────────────────────────────────

const args = parseArgs(process.argv);
if (args.selfTest) { runSelfTest(); process.exit(0); }
const cpDir = resolve(args.cpDir);
const relayConfig = parseRelayConfig(cpDir);

// CLI args override config, config overrides defaults
const title = args.title || relayConfig["command-center-title"] || relayConfig["status-page-title"] || "Command Center";
const branding = {
  logo: relayConfig["command-center-logo"] || relayConfig["status-page-logo"] || "R",
  footer: relayConfig["command-center-footer"] || relayConfig["status-page-footer"] || "",
};

console.log(`Generating status page from: ${cpDir}`);

const featureFiles = collectFeatureFiles(cpDir, "-feature.md");
const bugFiles = [...collectFeatureFiles(cpDir, "-bug.md"), ...collectBugFiles(cpDir)];
const activeTaskFiles = collectActiveTaskFiles(cpDir);
const archivedTaskFiles = collectArchivedTaskFiles(cpDir);
const implLogFiles = collectImplLogFiles(cpDir);

console.log(`  Features: ${featureFiles.length}, Bugs: ${bugFiles.length}`);
console.log(`  Active tasks: ${activeTaskFiles.length}, Archived: ${archivedTaskFiles.length}`);

const handoffMap = collectHandoffFiles(cpDir);
const boardState = buildBoardState({ featureFiles, bugFiles, activeTaskFiles, archivedTaskFiles, implLogFiles });

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
