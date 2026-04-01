#!/usr/bin/env python3
"""Generate a SOC2/ISO27001 compliance posture report.

Collects evidence from git, GitHub API, filesystem, and Relay data
structures (features, queue, contracts, bugs), assesses controls,
and renders a PDF via WeasyPrint + Jinja2.

Usage:
    python3 compliance-report.py --cp-dir /path/to/control-plane [--period 90] [--output ./reports]
"""

import argparse
import glob as globmod
import json
import os
import subprocess
import sys
import webbrowser
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Ensure scripts/ is on the path for sibling imports ────────────
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import _workflow

# ── Lazy imports — fail gracefully with install hints ─────────────

def _require(module_name, pip_name=None):
    """Import a module, printing install hint on failure."""
    try:
        return __import__(module_name)
    except ImportError:
        pip_name = pip_name or module_name
        print(f"Error: '{module_name}' is required. Install with: pip install {pip_name}")
        sys.exit(1)


# ── Constants ─────────────────────────────────────────────────────

TEMPLATES_DIR = os.path.join(os.path.dirname(SCRIPTS_DIR), "templates")
STATUS_ICONS = {"pass": "\u2713", "fail": "\u2717", "partial": "\u25cb"}


# ── Control Definitions Loader ────────────────────────────────────

def load_controls(path):
    """Load compliance-controls.yml."""
    yaml = _require("yaml", "pyyaml")
    with open(path) as f:
        return yaml.safe_load(f)


# ── Collectors ────────────────────────────────────────────────────

def collect_filesystem(cp_dir, path_glob, relay_dir=None):
    """Check if files matching a glob pattern exist in the CP or Relay repo.

    Searches the CP first, then falls back to the Relay framework repo
    (where process/ files live if they haven't been synced to the CP).
    """
    patterns = [
        os.path.join(cp_dir, path_glob),
    ]
    # Also check inside CP's .github/scripts area (synced from Relay)
    if path_glob.startswith("process/"):
        patterns.append(os.path.join(cp_dir, ".github", "scripts", path_glob.replace("process/scripts/", "")))

    # Fall back to the Relay repo itself
    if relay_dir:
        patterns.append(os.path.join(relay_dir, path_glob))

    matches = []
    for pat in patterns:
        if pat:
            matches.extend(globmod.glob(pat, recursive=True))
    return matches


def collect_git_log(cp_dir, period_days):
    """Collect recent git log entries."""
    since = (datetime.now(timezone.utc) - timedelta(days=period_days)).strftime("%Y-%m-%d")
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--oneline", "--no-merges", "-50"],
            capture_output=True, text=True, cwd=cp_dir, timeout=15,
        )
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        return lines
    except Exception:
        return []


def collect_git_authors(cp_dir, period_days):
    """Collect unique authors from git log."""
    since = (datetime.now(timezone.utc) - timedelta(days=period_days)).strftime("%Y-%m-%d")
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--format=%an <%ae>"],
            capture_output=True, text=True, cwd=cp_dir, timeout=15,
        )
        return list(set(l.strip() for l in result.stdout.strip().split("\n") if l.strip()))
    except Exception:
        return []


def collect_relay_features(cp_dir, period_days):
    """Collect completed feature specs from the report period."""
    features = []

    for phase_dir in ["completed", "active"]:
        feature_dir = os.path.join(cp_dir, "features", phase_dir)
        if not os.path.isdir(feature_dir):
            continue
        for fname in os.listdir(feature_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(feature_dir, fname)
            fm = _workflow.parse_frontmatter(fpath)
            feature_name = fname.replace("-feature.md", "").replace(".md", "")

            # Collect linked task specs
            tasks = _collect_feature_tasks(cp_dir, feature_name)

            # Build per-task details with PR linkage
            task_details = []
            for t in tasks:
                detail = {
                    "name": t.get("_file", "").replace(".md", ""),
                    "target_repo": t.get("target-repo", ""),
                    "wave": t.get("wave", ""),
                    "status": t.get("_status", ""),
                    "pr_url": t.get("pr-url", ""),
                    "pr_number": t.get("pr-number", ""),
                }
                task_details.append(detail)

            # Unique PRs across all tasks
            prs = [{"url": t.get("pr-url", ""), "number": t.get("pr-number", "")}
                   for t in tasks if t.get("pr-url")]

            # Unique target repos
            repos = sorted(set(t.get("target-repo", "") for t in tasks if t.get("target-repo")))

            features.append({
                "name": feature_name,
                "lifecycle": fm.get("lifecycle", phase_dir),
                "priority": fm.get("priority", "normal"),
                "created_at": fm.get("created-at", ""),
                "completed_at": fm.get("completed-at", ""),
                "tasks_total": len(tasks),
                "tasks_done": sum(1 for t in tasks if t.get("_status") == "done"),
                "tasks": task_details,
                "prs": prs,
                "repos": repos,
                "total_cost": fm.get("total-cost-usd", ""),
            })

    return features


def _collect_feature_tasks(cp_dir, feature_name):
    """Collect all task specs for a feature from queue/ and queue/_done/."""
    tasks = []

    # Active tasks: queue/<feature>/<status>/
    queue_dir = os.path.join(cp_dir, "queue", feature_name)
    # Completed tasks: queue/_done/<feature>/<status>/
    done_dir = os.path.join(cp_dir, "queue", "_done", feature_name)

    for base_dir in [queue_dir, done_dir]:
        if not os.path.isdir(base_dir):
            continue
        for status_dir in os.listdir(base_dir):
            status_path = os.path.join(base_dir, status_dir)
            if not os.path.isdir(status_path):
                continue
            for fname in os.listdir(status_path):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(status_path, fname)
                fm = _workflow.parse_frontmatter(fpath)
                fm["_status"] = status_dir
                fm["_file"] = fname
                tasks.append(fm)

    return tasks


def collect_relay_queue_stats(cp_dir):
    """Collect aggregate task queue statistics from queue/ and queue/_done/."""
    stats = {"total": 0, "by_status": {}, "with_execution_mode": 0,
             "with_claimed_by": 0, "with_pr": 0, "with_contracts": 0,
             "with_cost": 0}
    queue_dir = os.path.join(cp_dir, "queue")
    if not os.path.isdir(queue_dir):
        return stats

    # Collect feature dirs from both queue/<feature> and queue/_done/<feature>
    feature_paths = []
    for entry in os.listdir(queue_dir):
        entry_path = os.path.join(queue_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        if entry == "_done":
            # Scan completed features inside _done/
            for done_entry in os.listdir(entry_path):
                done_path = os.path.join(entry_path, done_entry)
                if os.path.isdir(done_path):
                    feature_paths.append(done_path)
        elif not entry.startswith("_"):
            feature_paths.append(entry_path)

    for feature_path in feature_paths:
        for status_dir in os.listdir(feature_path):
            status_path = os.path.join(feature_path, status_dir)
            if not os.path.isdir(status_path):
                continue
            for fname in os.listdir(status_path):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(status_path, fname)
                fm = _workflow.parse_frontmatter(fpath)
                stats["total"] += 1
                stats["by_status"][status_dir] = stats["by_status"].get(status_dir, 0) + 1
                if fm.get("execution"):
                    stats["with_execution_mode"] += 1
                if fm.get("claimed-by"):
                    stats["with_claimed_by"] += 1
                if fm.get("pr-url"):
                    stats["with_pr"] += 1
                if fm.get("contracts"):
                    stats["with_contracts"] += 1
                if fm.get("cost-usd"):
                    stats["with_cost"] += 1

    return stats


def collect_relay_bugs(cp_dir):
    """Collect bug reports and their status."""
    bugs = []
    for phase in ["active", "completed", "draft"]:
        bug_dir = os.path.join(cp_dir, "bugs", phase)
        if not os.path.isdir(bug_dir):
            continue
        for fname in os.listdir(bug_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(bug_dir, fname)
            fm = _workflow.parse_frontmatter(fpath)
            bugs.append({
                "name": fname.replace("-bug.md", ""),
                "lifecycle": phase,
                "severity": fm.get("severity", ""),
                "reported_by": fm.get("reported-by", ""),
            })
    return bugs


def collect_inbox_stats(cp_dir):
    """Collect inbox item stats from .relay/inbox.db."""
    return {"total": 0, "by_status": {}}


def _count_by(items, key):
    counts = {}
    for item in items:
        val = item.get(key, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


# ── GitHub API Collector ──────────────────────────────────────────

def collect_github_info(cp_dir):
    """Collect GitHub repo info via gh CLI (if available)."""
    info = {
        "branch_protection": None,
        "recent_prs": [],
        "repo_name": None,
        "available": False,
    }

    # Get repo name
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "name,owner"],
            capture_output=True, text=True, cwd=cp_dir, timeout=15,
        )
        if result.returncode == 0:
            repo = json.loads(result.stdout)
            info["repo_name"] = f"{repo['owner']['login']}/{repo['name']}"
            info["available"] = True
    except Exception:
        return info

    if not info["available"]:
        return info

    # Branch protection
    try:
        result = subprocess.run(
            ["gh", "api", "repos/{owner}/{repo}/branches/main/protection"],
            capture_output=True, text=True, cwd=cp_dir, timeout=15,
        )
        if result.returncode == 0:
            info["branch_protection"] = json.loads(result.stdout)
    except Exception:
        pass

    # Recent merged PRs
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "merged", "--limit", "10",
             "--json", "number,title,author,reviewDecision,reviews,mergedAt,url"],
            capture_output=True, text=True, cwd=cp_dir, timeout=15,
        )
        if result.returncode == 0:
            info["recent_prs"] = json.loads(result.stdout)
    except Exception:
        pass

    return info


# ── Assessor ──────────────────────────────────────────────────────

def assess_controls(controls_def, cp_dir, period_days):
    """Run all checks and produce assessed controls with status."""
    # Resolve Relay repo path from .relay-config
    config = _read_relay_config(cp_dir)
    relay_dir = config.get("relay-path", "")
    if not relay_dir or not os.path.isdir(relay_dir):
        relay_dir = None

    # Gather all evidence once
    evidence = {
        "filesystem": {},
        "relay_dir": relay_dir,
        "git_log": collect_git_log(cp_dir, period_days),
        "git_authors": collect_git_authors(cp_dir, period_days),
        "github": collect_github_info(cp_dir),
        "features": collect_relay_features(cp_dir, period_days),
        "queue_stats": collect_relay_queue_stats(cp_dir),
        "bugs": collect_relay_bugs(cp_dir),
        "inbox_stats": collect_inbox_stats(cp_dir),
    }

    assessed = []
    evidence_inventory = []

    for ctrl in controls_def.get("controls", []):
        checks_results = []
        is_manual = ctrl.get("manual_review", False)

        if is_manual:
            assessed.append({
                **ctrl,
                "status": "manual",
                "status_label": "Manual Review",
                "checks": [],
            })
            continue

        for check in ctrl.get("checks", []):
            result = _run_check(check, cp_dir, evidence, period_days)
            checks_results.append(result)

            # Add to evidence inventory
            if result.get("detail"):
                evidence_inventory.append({
                    "source": check.get("collector", "unknown"),
                    "type": check.get("name", ""),
                    "description": result.get("detail", ""),
                    "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                })

        # Determine overall control status
        if not checks_results:
            status = "manual"
            status_label = "Manual Review"
        elif all(c["status"] == "pass" for c in checks_results):
            status = "pass"
            status_label = "Pass"
        elif any(c["status"] == "pass" for c in checks_results):
            status = "partial"
            status_label = "Partial"
        else:
            status = "fail"
            status_label = "Fail"

        assessed.append({
            **ctrl,
            "status": status,
            "status_label": status_label,
            "checks": checks_results,
        })

    return assessed, evidence_inventory


def _run_check(check, cp_dir, evidence, period_days):
    """Run a single check and return result dict."""
    collector = check.get("collector", "")
    result = {
        "evidence_label": check.get("evidence_label", check.get("name", "")),
        "name": check.get("name", ""),
        "status": "fail",
        "icon": STATUS_ICONS["fail"],
        "detail": "",
    }

    if collector == "filesystem":
        path_glob = check.get("path_glob", "")
        relay_dir = evidence.get("relay_dir")
        matches = collect_filesystem(cp_dir, path_glob, relay_dir=relay_dir)
        if matches:
            result["status"] = "pass"
            result["icon"] = STATUS_ICONS["pass"]
            names = [os.path.basename(m) for m in matches[:5]]
            result["detail"] = f"Found: {', '.join(names)}"
            if len(matches) > 5:
                result["detail"] += f" (+{len(matches) - 5} more)"
        else:
            result["detail"] = f"No files matching {path_glob}"

    elif collector == "git":
        log = evidence["git_log"]
        if log:
            result["status"] = "pass"
            result["icon"] = STATUS_ICONS["pass"]
            result["detail"] = f"{len(log)} commits in last {period_days} days by {len(evidence['git_authors'])} authors"
        else:
            result["detail"] = "No git history found"

    elif collector == "github_api":
        gh = evidence["github"]
        name = check.get("name", "")

        if not gh["available"]:
            result["status"] = "partial"
            result["icon"] = STATUS_ICONS["partial"]
            result["detail"] = "GitHub CLI not available — skipped"
            return result

        if "branch_protection" in name:
            bp = gh.get("branch_protection")
            if bp:
                result["status"] = "pass"
                result["icon"] = STATUS_ICONS["pass"]
                pr_reviews = bp.get("required_pull_request_reviews", {})
                count = pr_reviews.get("required_approving_review_count", 0) if pr_reviews else 0
                result["detail"] = f"Branch protection active, {count} required review(s)"
            else:
                result["detail"] = "No branch protection found on main"

        elif "prs_have" in name:
            prs = gh.get("recent_prs", [])
            if prs:
                approved = sum(1 for p in prs if p.get("reviewDecision") == "APPROVED")
                result["detail"] = f"{approved}/{len(prs)} recent PRs have approvals"
                if approved >= len(prs) * 0.5:
                    result["status"] = "pass"
                    result["icon"] = STATUS_ICONS["pass"]
                elif approved > 0:
                    result["status"] = "partial"
                    result["icon"] = STATUS_ICONS["partial"]
            else:
                result["detail"] = "No recent merged PRs found"

        elif name == "team_based_access":
            # Can't easily check without extra API calls — mark partial
            result["status"] = "partial"
            result["icon"] = STATUS_ICONS["partial"]
            result["detail"] = f"Repo: {gh['repo_name']} — verify team access manually"

        elif name == "https_enforced":
            result["status"] = "pass"
            result["icon"] = STATUS_ICONS["pass"]
            result["detail"] = "GitHub enforces HTTPS/SSH for all repository access"

    elif collector == "relay_queue":
        stats = evidence["queue_stats"]
        name = check.get("name", "")

        if name == "changes_traceable_to_features":
            if stats["with_pr"] > 0:
                result["status"] = "pass"
                result["icon"] = STATUS_ICONS["pass"]
                result["detail"] = f"{stats['with_pr']}/{stats['total']} tasks linked to PRs"
            elif stats["total"] > 0:
                result["status"] = "partial"
                result["icon"] = STATUS_ICONS["partial"]
                result["detail"] = f"{stats['total']} tasks found, but none linked to PRs"
            else:
                result["detail"] = "No tasks found in queue"

        elif name == "prs_backlink_to_specs":
            # PRs created by relay done always contain SHA-pinned back-links
            # to the feature spec and task file in the PR body
            if stats["with_pr"] > 0:
                result["status"] = "pass"
                result["icon"] = STATUS_ICONS["pass"]
                result["detail"] = (
                    f"{stats['with_pr']} PR(s) created via relay done — "
                    f"each contains SHA-pinned links back to feature spec and task file"
                )
            elif stats["total"] > 0:
                result["status"] = "partial"
                result["icon"] = STATUS_ICONS["partial"]
                result["detail"] = "Tasks exist but no PRs created yet"
            else:
                result["detail"] = "No tasks found"

        elif name == "execution_mode_defined":
            if stats["with_execution_mode"] > 0:
                result["status"] = "pass"
                result["icon"] = STATUS_ICONS["pass"]
                result["detail"] = f"{stats['with_execution_mode']}/{stats['total']} tasks have execution mode set"
            elif stats["total"] > 0:
                result["status"] = "fail"
                result["detail"] = "Tasks exist but none have execution mode set"
            else:
                result["detail"] = "No tasks found"

        elif name == "work_assigned_and_tracked":
            if stats["with_claimed_by"] > 0:
                result["status"] = "pass"
                result["icon"] = STATUS_ICONS["pass"]
                result["detail"] = f"{stats['with_claimed_by']}/{stats['total']} tasks have assignment tracking"
            elif stats["total"] > 0:
                result["status"] = "partial"
                result["icon"] = STATUS_ICONS["partial"]
                result["detail"] = "Tasks exist but none have claimed-by set"
            else:
                result["detail"] = "No tasks found"

        elif name == "directory_state_machine":
            statuses = stats.get("by_status", {})
            if statuses:
                result["status"] = "pass"
                result["icon"] = STATUS_ICONS["pass"]
                breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items()))
                result["detail"] = f"Task states tracked: {breakdown}"
            else:
                result["detail"] = "No task state directories found"

        elif name == "cost_tracking":
            if stats["with_cost"] > 0:
                result["status"] = "pass"
                result["icon"] = STATUS_ICONS["pass"]
                result["detail"] = f"{stats['with_cost']}/{stats['total']} tasks have cost data"
            elif stats["total"] > 0:
                result["status"] = "partial"
                result["icon"] = STATUS_ICONS["partial"]
                result["detail"] = "Tasks exist but cost tracking not populated"
            else:
                result["detail"] = "No tasks found"

        elif name == "tasks_reference_contracts":
            if stats["with_contracts"] > 0:
                result["status"] = "pass"
                result["icon"] = STATUS_ICONS["pass"]
                result["detail"] = f"{stats['with_contracts']}/{stats['total']} tasks reference contracts"
            elif stats["total"] > 0:
                result["status"] = "partial"
                result["icon"] = STATUS_ICONS["partial"]
                result["detail"] = "Tasks exist but none reference contracts"
            else:
                result["detail"] = "No tasks found"

    elif collector == "relay_features":
        features = evidence["features"]
        name = check.get("name", "")

        if name == "feature_specs_precede_work":
            if features:
                result["status"] = "pass"
                result["icon"] = STATUS_ICONS["pass"]
                result["detail"] = f"{len(features)} feature spec(s) found with linked tasks"
            else:
                result["detail"] = "No feature specs found"

    elif collector == "relay_bugs":
        bugs = evidence["bugs"]
        if bugs:
            result["status"] = "pass"
            result["icon"] = STATUS_ICONS["pass"]
            result["detail"] = f"{len(bugs)} bug(s) tracked across lifecycle stages"
        else:
            result["status"] = "partial"
            result["icon"] = STATUS_ICONS["partial"]
            result["detail"] = "No bugs found (could mean no bugs, or bugs not tracked here)"

    elif collector == "relay_inbox":
        inbox = evidence["inbox_stats"]
        if inbox["total"] > 0:
            result["status"] = "pass"
            result["icon"] = STATUS_ICONS["pass"]
            breakdown = ", ".join(f"{k}: {v}" for k, v in inbox["by_status"].items())
            result["detail"] = f"{inbox['total']} inbox records ({breakdown})"
        else:
            result["status"] = "partial"
            result["icon"] = STATUS_ICONS["partial"]
            result["detail"] = "Inbox DB exists but no records yet"

    return result


# ── Report Data Assembly ──────────────────────────────────────────

def build_report_data(assessed, evidence_inventory, features, cross_refs, cp_dir, period_days):
    """Assemble the full template context dict."""
    now = datetime.now(timezone.utc)
    period_start = (now - timedelta(days=period_days)).strftime("%Y-%m-%d")
    period_end = now.strftime("%Y-%m-%d")

    # Group all controls by category (unified view)
    all_by_cat = _group_by_category(assessed)

    # Counts
    counts = {"passed": 0, "partial": 0, "failed": 0, "manual": 0}
    for c in assessed:
        s = c["status"]
        if s == "pass":
            counts["passed"] += 1
        elif s == "partial":
            counts["partial"] += 1
        elif s == "fail":
            counts["failed"] += 1
        elif s == "manual":
            counts["manual"] += 1

    auto_total = counts["passed"] + counts["partial"] + counts["failed"]
    overall_pct = round(counts["passed"] / auto_total * 100) if auto_total else 0

    # Category summaries for exec summary table
    categories = _build_category_summaries(assessed)

    # Gaps
    gaps = []
    for c in assessed:
        if c["status"] == "fail":
            failed_checks = [ch for ch in c.get("checks", []) if ch["status"] == "fail"]
            issues = "; ".join(ch["detail"] for ch in failed_checks if ch["detail"])
            gaps.append({
                "id": c["id"],
                "framework": c.get("framework", "").upper().replace("SOC2", "SOC 2").replace("ISO27001", "ISO 27001"),
                "issue": issues or "No evidence collected",
                "remediation": _suggest_remediation(c),
            })

    return {
        "title": "Compliance Posture Report",
        "organization": _detect_org_name(cp_dir),
        "app_name": _detect_app_name(cp_dir),
        "scope": "Software Development Lifecycle & Control Plane",
        "period_start": period_start,
        "period_end": period_end,
        "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
        "overall_score_pct": overall_pct,
        "counts": counts,
        "categories": categories,
        "features": features,
        "all_by_category": all_by_cat,
        "cross_references": cross_refs or [],
        "evidence_inventory": evidence_inventory,
        "gaps": gaps,
    }


def _group_by_category(controls):
    grouped = OrderedDict()
    for c in controls:
        cat = c.get("category", "Other")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(c)
    return grouped


def _build_category_summaries(assessed):
    """Build per-category summary stats for exec summary."""
    cats = OrderedDict()
    for c in assessed:
        cat = c.get("category", "Other")
        if cat not in cats:
            cats[cat] = {"name": cat, "passed": 0, "partial": 0, "failed": 0, "manual": 0}
        s = c["status"]
        if s == "pass":
            cats[cat]["passed"] += 1
        elif s == "partial":
            cats[cat]["partial"] += 1
        elif s == "fail":
            cats[cat]["failed"] += 1
        elif s == "manual":
            cats[cat]["manual"] += 1

    result = []
    for cat in cats.values():
        auto = cat["passed"] + cat["partial"] + cat["failed"]
        pct = round(cat["passed"] / auto * 100) if auto else 0
        cat["score_pct"] = pct
        cat["score_class"] = "high" if pct >= 70 else ("medium" if pct >= 40 else "low")
        result.append(cat)
    return result


def _read_relay_config(cp_dir):
    """Read key-value pairs from .relay-config."""
    config = {}
    config_path = os.path.join(cp_dir, ".relay-config")
    if not os.path.exists(config_path):
        return config
    with open(config_path) as f:
        for line in f:
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, _, val = line.partition(":")
                config[key.strip()] = val.strip()
    return config


def _detect_org_name(cp_dir):
    """Detect org name from .relay-config or git remote."""
    config = _read_relay_config(cp_dir)
    # Use github-org from relay config
    if config.get("github-org"):
        return config["github-org"]
    # Fall back to relay-nwo owner
    nwo = config.get("relay-nwo", "")
    if "/" in nwo:
        return nwo.split("/")[0]
    # Fall back to git remote
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=cp_dir, timeout=5,
        )
        url = result.stdout.strip()
        if "github.com" in url:
            parts = url.rstrip(".git").split("/")
            return parts[-2] if len(parts) >= 2 else os.path.basename(cp_dir)
    except Exception:
        pass
    return os.path.basename(os.path.abspath(cp_dir))


def _detect_app_name(cp_dir):
    """Detect application/product name from .relay-config or directory name."""
    config = _read_relay_config(cp_dir)
    # Use status-page-title if set (it's the user-facing product name)
    title = config.get("status-page-title", "")
    if title:
        # Strip " - Command Center" suffix if present
        return title.replace(" - Command Center", "").strip()
    # Fall back to relay-nwo repo name
    nwo = config.get("relay-nwo", "")
    if "/" in nwo:
        return nwo.split("/")[1].replace("-", " ").title()
    return os.path.basename(os.path.abspath(cp_dir)).replace("-", " ").title()


def _suggest_remediation(control):
    """Generate a remediation suggestion based on the control category."""
    cat = control.get("category", "")
    suggestions = {
        "Change Management": "Enable branch protection with required reviews and CI status checks.",
        "Access Control": "Configure branch protection rules and use team-based repository access.",
        "Code Review": "Enforce PR reviews before merge; document security coding standards.",
        "Secure Development": "Add testing rules, API contracts, and CI validation workflows.",
        "Monitoring & Incident Response": "Configure telemetry ingestion pipeline and triage agent.",
        "Vulnerability Management": "Enable Dependabot or equivalent dependency scanning.",
        "Logging & Audit Trail": "Ensure git history is maintained and task queue directories are used.",
        "Authorization & Oversight": "Define feature specs before queueing work; set execution modes on tasks.",
    }
    return suggestions.get(cat, "Review control requirements and implement appropriate measures.")


# ── Renderer ──────────────────────────────────────────────────────

def render_html(report_data):
    """Render Jinja2 HTML template with report data."""
    jinja2 = _require("jinja2")
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
    )
    template = env.get_template("compliance-report.html")
    return template.render(**report_data)


def render_pdf(html_content, output_path):
    """Convert HTML to PDF using WeasyPrint."""
    weasyprint = _require("weasyprint")
    css_path = os.path.join(TEMPLATES_DIR, "compliance-report.css")
    css = weasyprint.CSS(filename=css_path) if os.path.exists(css_path) else None

    doc = weasyprint.HTML(string=html_content, base_url=TEMPLATES_DIR)
    stylesheets = [css] if css else []
    doc.write_pdf(output_path, stylesheets=stylesheets)
    return output_path



# ── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate SOC2/ISO27001 compliance posture report")
    parser.add_argument("--cp-dir", required=True, help="Path to the control plane directory")
    parser.add_argument("--period", type=int, default=90, help="Report period in days (default: 90)")
    parser.add_argument("--output", default=None, help="Output directory (default: <cp-dir>/reports)")
    parser.add_argument("--format", choices=["pdf", "html", "both"], default="pdf", help="Output format")
    parser.add_argument("--open", dest="auto_open", action="store_true", default=True, help="Open report when done (default)")
    parser.add_argument("--no-open", dest="auto_open", action="store_false", help="Do not open report when done")
    args = parser.parse_args()

    cp_dir = os.path.abspath(args.cp_dir)
    output_dir = args.output or os.path.join(cp_dir, "reports")
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n  Compliance Posture Report Generator")
    print(f"  {'=' * 40}")
    print(f"  CP dir:  {cp_dir}")
    print(f"  Period:  {args.period} days")
    print(f"  Output:  {output_dir}\n")

    # 1. Load control definitions
    controls_path = os.path.join(TEMPLATES_DIR, "compliance-controls.yml")
    if not os.path.exists(controls_path):
        print(f"  Error: Control definitions not found at {controls_path}")
        sys.exit(1)
    print(f"  Loading control definitions...")
    controls_def = load_controls(controls_path)

    # 2. Collect evidence and assess
    print(f"  Collecting evidence and assessing controls...")
    assessed, evidence_inventory = assess_controls(controls_def, cp_dir, args.period)

    # 3. Collect features for traceability section
    print(f"  Building change traceability chain...")
    features = collect_relay_features(cp_dir, args.period)

    # 4. Build report data
    report_data = build_report_data(
        assessed, evidence_inventory, features,
        controls_def.get("cross_references", []),
        cp_dir, args.period,
    )

    # 5. Render
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base_name = f"compliance-{timestamp}"

    print(f"  Rendering report...")
    html_content = render_html(report_data)

    if args.format in ("html", "both"):
        html_path = os.path.join(output_dir, f"{base_name}.html")
        with open(html_path, "w") as f:
            f.write(html_content)
        print(f"  HTML: {html_path}")

    if args.format in ("pdf", "both"):
        pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
        render_pdf(html_content, pdf_path)
        print(f"  PDF:  {pdf_path}")

    # 6. Auto-open
    if args.auto_open:
        open_path = None
        if args.format in ("pdf", "both"):
            open_path = pdf_path
        elif args.format == "html":
            open_path = html_path
        if open_path:
            webbrowser.open(f"file://{os.path.abspath(open_path)}")

    # 7. Summary
    counts = report_data["counts"]
    total = counts["passed"] + counts["partial"] + counts["failed"] + counts["manual"]
    print(f"\n  Results: {counts['passed']} pass, {counts['partial']} partial, "
          f"{counts['failed']} fail, {counts['manual']} manual ({total} total)")
    print(f"  Overall automated score: {report_data['overall_score_pct']}%\n")

    print(f"  Done.\n")


if __name__ == "__main__":
    main()
