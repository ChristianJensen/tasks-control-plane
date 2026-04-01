#!/usr/bin/env python3
"""Relay Compact — generate a deterministic feature summary on completion.

Usage:
    _compact.py <feature-slug> --cp-dir <path>

Reads the feature spec, all task files, and retro-log entries to produce
a summary at features/_summaries/<feature>-summary.md. No AI required.
"""

import argparse
import glob
import os
import re
import sys
from datetime import datetime, timezone

# Add scripts directory to path for _workflow import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _workflow import parse_frontmatter, parse_frontmatter_string


def extract_section(content, heading):
    """Extract the content of a markdown section by heading name."""
    pattern = rf"(?:^|\n)##\s+{re.escape(heading)}\s*\n(.*?)(?:\n##\s|\Z)"
    m = re.search(pattern, content, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def load_retro_entries(cp_dir, feature_slug):
    """Load retro-log entries matching the feature name."""
    entries = []
    # Check both cp_dir/retrospectives and relay_dir/process/retrospectives
    for retro_path in [
        os.path.join(cp_dir, "retrospectives", "retro-log.md"),
    ]:
        if not os.path.exists(retro_path):
            continue
        with open(retro_path) as f:
            content = f.read()
        # Split on ### headings and filter by feature slug
        sections = re.split(r"\n(?=### )", content)
        for section in sections:
            if feature_slug in section:
                entries.append(section.strip())
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature", help="Feature slug (e.g., add-due-dates)")
    parser.add_argument("--cp-dir", required=True, help="Control plane directory")
    args = parser.parse_args()

    cp_dir = args.cp_dir
    feature_slug = args.feature

    # ── Load feature spec ─────────────────────────────────────
    spec_path = None
    for phase in ["active", "completed", "draft", "cancelled"]:
        for suffix in ["-feature.md", "-bug.md"]:
            path = os.path.join(cp_dir, "features", phase, f"{feature_slug}{suffix}")
            if os.path.exists(path):
                spec_path = path
                break
        if spec_path:
            break
    # Also check bugs/ directory
    if not spec_path:
        bugs_dir = os.path.join(cp_dir, "bugs")
        if os.path.isdir(bugs_dir):
            for phase in ["active", "completed", "draft", "cancelled"]:
                path = os.path.join(bugs_dir, phase, f"{feature_slug}-bug.md")
                if os.path.exists(path):
                    spec_path = path
                    break

    spec_content = ""
    if spec_path:
        with open(spec_path) as f:
            spec_content = f.read()

    # ── Load task files ───────────────────────────────────────
    queue_dir = os.path.join(cp_dir, "queue", feature_slug)
    task_paths = sorted(glob.glob(os.path.join(queue_dir, "*", "wave-*.md")))

    tasks_by_wave = {}
    all_contracts = set()
    implementation_notes = []

    for tp in task_paths:
        with open(tp) as f:
            content = f.read()
        fields = parse_frontmatter_string(content)
        wave = int(fields.get("wave", 0))
        repo = fields.get("target-repo", "unknown")
        filename = os.path.basename(tp).replace(".md", "")

        # Extract description from body
        desc = extract_section(content, "Description") or filename

        # Extract cost data
        def safe_float(v):
            try: return float(v) if v else 0.0
            except (ValueError, TypeError): return 0.0
        def safe_int(v):
            try: return int(v) if v else 0
            except (ValueError, TypeError): return 0

        tasks_by_wave.setdefault(wave, []).append({
            "filename": filename,
            "repo": repo,
            "description": desc,
            "cost_usd": safe_float(fields.get("cost-usd")),
            "input_tokens": safe_int(fields.get("input-tokens")),
            "output_tokens": safe_int(fields.get("output-tokens")),
            "duration_ms": safe_int(fields.get("duration-ms")),
        })

        # Collect contracts
        contracts = fields.get("contracts", [])
        if isinstance(contracts, str):
            contracts = [contracts] if contracts else []
        all_contracts.update(contracts)

        # Collect implementation notes
        impl_notes = extract_section(content, "Implementation Notes")
        if impl_notes and impl_notes != "_Architectural guidance, constraints, edge cases._":
            implementation_notes.append(f"**{filename}:** {impl_notes}")

    # ── Load retro entries ────────────────────────────────────
    retro_entries = load_retro_entries(cp_dir, feature_slug)

    # ── Extract spec sections ─────────────────────────────────
    problem = extract_section(spec_content, "Problem Statement")
    requirements = extract_section(spec_content, "Requirements")
    overview = problem or requirements or "(No spec content available)"

    # ── Aggregate costs ───────────────────────────────────────
    total_cost_usd = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    total_duration_ms = 0
    for wave_tasks in tasks_by_wave.values():
        for task in wave_tasks:
            total_cost_usd += task.get("cost_usd", 0)
            total_input_tokens += task.get("input_tokens", 0)
            total_output_tokens += task.get("output_tokens", 0)
            total_duration_ms += task.get("duration_ms", 0)
    total_tokens = total_input_tokens + total_output_tokens

    # ── Build summary ─────────────────────────────────────────
    total_tasks = len(task_paths)
    total_waves = len(tasks_by_wave)
    completed_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = []
    lines.append("---")
    lines.append(f"feature: {feature_slug}")
    lines.append(f"completed: {completed_date}")
    lines.append(f"tasks: {total_tasks}")
    lines.append(f"waves: {total_waves}")
    if total_cost_usd > 0:
        lines.append(f"total-cost-usd: {round(total_cost_usd, 4)}")
        lines.append(f"total-tokens: {total_tokens}")
    lines.append("---")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(overview)
    lines.append("")
    lines.append("## What Was Built")
    lines.append("")
    for wave_num in sorted(tasks_by_wave.keys()):
        lines.append(f"### Wave {wave_num}")
        lines.append("")
        for task in tasks_by_wave[wave_num]:
            lines.append(f"- **{task['repo']}** — {task['description']}")
        lines.append("")

    lines.append("## Key Decisions")
    lines.append("")
    if implementation_notes:
        for note in implementation_notes:
            lines.append(f"- {note}")
    else:
        lines.append("(No implementation notes recorded)")
    lines.append("")

    lines.append("## Contracts Affected")
    lines.append("")
    if all_contracts:
        for c in sorted(all_contracts):
            lines.append(f"- {c}")
    else:
        lines.append("(No contracts referenced)")
    lines.append("")

    lines.append("## Cost Summary")
    lines.append("")
    if total_cost_usd > 0:
        lines.append(f"**Total: ${total_cost_usd:.4f}** ({total_tokens:,} tokens, {total_duration_ms / 1000:.0f}s)")
        lines.append("")
        lines.append("| Wave | Task | Cost | Tokens |")
        lines.append("|------|------|------|--------|")
        for wave_num in sorted(tasks_by_wave.keys()):
            for task in tasks_by_wave[wave_num]:
                c = task.get("cost_usd", 0)
                t = task.get("input_tokens", 0) + task.get("output_tokens", 0)
                if c > 0:
                    lines.append(f"| W{wave_num} | {task['filename']} | ${c:.4f} | {t:,} |")
    else:
        lines.append("(No cost data recorded)")
    lines.append("")

    lines.append("## Retrospective Notes")
    lines.append("")
    if retro_entries:
        for entry in retro_entries:
            lines.append(entry)
            lines.append("")
    else:
        lines.append("(No retrospective entries)")
    lines.append("")

    # ── Write output ──────────────────────────────────────────
    output_dir = os.path.join(cp_dir, "features", "_summaries")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{feature_slug}-summary.md")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Summary written: {os.path.relpath(output_path, cp_dir)}")


if __name__ == "__main__":
    main()
