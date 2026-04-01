#!/usr/bin/env python3
"""Relay compile-constitution — merge rule manifests into a single constitution file.

Usage:
    compile-constitution.py [--cp-dir <path>] [--dry-run] [--output <path>] [--validate] [target-dir]

Reads manifests from up to 3 tiers (relay, control plane, code repo), merges
rules with inner-overrides-outer precedence, and emits a compiled constitution.
"""

import argparse, datetime, os, re, subprocess, sys

# ── ANSI helpers (to stderr, consistent with existing scripts) ───
GREEN, YELLOW, BLUE, RED = "\033[0;32m", "\033[1;33m", "\033[0;34m", "\033[0;31m"
DIM, BOLD, NC = "\033[2m", "\033[1m", "\033[0m"

def _p(icon, color, msg): print(f"  {color}{icon}{NC} {msg}", file=sys.stderr)
def print_ok(m):   _p("✓", GREEN, m)
def print_fail(m): _p("✗", RED, m)
def print_warn(m): _p("⚠", YELLOW, m)
def print_info(m): _p("→", BLUE, m)
def print_header(m): print(f"\n{BOLD}{m}{NC}", file=sys.stderr)

# ── Manifest parsing ────────────────────────────────────────────

def parse_manifest(path):
    """Parse rules manifest (md with YAML frontmatter + table).
    Returns (metadata_dict, [rule_dicts]) or (None, []) if missing."""
    if not os.path.exists(path):
        return None, []
    with open(path) as f:
        content = f.read()
    metadata = {}
    fm = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm:
        for line in fm.group(1).split("\n"):
            kv = re.match(r"^(\S+):\s*(.*)", line)
            if kv:
                metadata[kv.group(1)] = kv.group(2).strip()
    rules, in_table, sep_seen = [], False, False
    for line in content.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            if in_table: break
            continue
        cells = [c.strip() for c in s.split("|")[1:-1]]
        if len(cells) < 4:
            continue
        if not in_table:          # header row
            in_table = True; continue
        if not sep_seen:          # separator row
            if re.match(r"^[-:\s|]+$", s):
                sep_seen = True; continue
            sep_seen = True
        rules.append(dict(topic=cells[0], description=cells[1],
                          level=cells[2], path=cells[3]))
    return metadata, rules


def strip_frontmatter(content):
    m = re.match(r"^---\s*\n.*?\n---\s*\n?", content, re.DOTALL)
    return content[m.end():] if m else content


def get_git_sha(d):
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"

# ── Config helpers ──────────────────────────────────────────────

def _read_kv(path, key):
    """Read key: value from a plain or markdown config file."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        content = f.read()
    # Frontmatter first
    fm = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    text = fm.group(1) + "\n" + content if fm else content
    m = re.search(rf"^{re.escape(key)}:\s*(.+)", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _resolve_path(base, raw):
    """Expand ~ and resolve relative paths against base."""
    if not raw:
        return None
    p = os.path.expanduser(raw)
    if not os.path.isabs(p):
        p = os.path.normpath(os.path.join(base, p))
    return p if os.path.isdir(p) else None

# ── Tier detection ──────────────────────────────────────────────

def detect_context(target_dir, explicit_cp_dir=None):
    """Resolve tier paths. Returns dict with relay_dir, cp_dir, code_dir."""
    t = {"relay_dir": None, "cp_dir": None, "code_dir": None}
    code_cfg = os.path.join(target_dir, ".relay", "config.md")
    if os.path.exists(code_cfg):
        t["code_dir"] = target_dir
        cp = explicit_cp_dir or _read_kv(code_cfg, "control-plane-path")
        t["cp_dir"] = _resolve_path(target_dir, cp)
    elif explicit_cp_dir and os.path.isdir(explicit_cp_dir):
        t["cp_dir"] = explicit_cp_dir
    cp_cfg = os.path.join(target_dir, ".relay-config")
    if os.path.exists(cp_cfg) and not t["cp_dir"]:
        t["cp_dir"] = target_dir
    if t["cp_dir"]:
        rp = _read_kv(os.path.join(t["cp_dir"], ".relay-config"), "relay-path")
        t["relay_dir"] = _resolve_path(t["cp_dir"], rp)
    if not t["relay_dir"]:
        scripts = os.path.dirname(os.path.abspath(__file__))
        cand = os.path.dirname(os.path.dirname(scripts))
        if os.path.exists(os.path.join(cand, "VERSION")):
            t["relay_dir"] = cand
    if not t["relay_dir"] and os.path.exists(os.path.join(target_dir, "VERSION")):
        t["relay_dir"] = target_dir
    return t

# ── Merge ───────────────────────────────────────────────────────

def merge_rules(tier_rules_list):
    """Merge rules outer-to-inner. Inner overrides outer for same topic."""
    merged = {}
    for tier_name, tier_root, rules in tier_rules_list:
        for r in rules:
            topic, level = r["topic"], r["level"]
            if topic in merged and level == "exclude":
                if merged[topic]["level"] == "advisory":
                    del merged[topic]
                elif merged[topic]["level"] == "mandatory":
                    print_warn(f"Cannot exclude mandatory topic '{topic}' "
                               f"(from {merged[topic]['tier']})")
                continue
            if level == "exclude":
                continue
            merged[topic] = {**r, "tier": tier_name,
                             "abs_path": os.path.normpath(
                                 os.path.join(tier_root, r["path"]))}
    return list(merged.values())

# ── Validation ──────────────────────────────────────────────────

def validate_rules(rules):
    errors, seen, mand_bytes = [], set(), 0
    for r in rules:
        if r["topic"] in seen:
            errors.append(f"Duplicate topic: {r['topic']}")
        seen.add(r["topic"])
        if not os.path.exists(r["abs_path"]):
            errors.append(f"Missing rule file for '{r['topic']}': {r['abs_path']}")
        elif r["level"] == "mandatory":
            mand_bytes += os.path.getsize(r["abs_path"])
    if mand_bytes / 4 > 50000:
        errors.append(f"Mandatory rules ~{int(mand_bytes/4)} tokens "
                      f"(consider moving some to advisory)")
    return errors

# ── Output generation ───────────────────────────────────────────

def build_constitution(rules, tiers, target_dir):
    today = datetime.date.today().isoformat()
    sha_parts = []
    for label, key in [("Relay","relay_dir"),("Control Plane","cp_dir"),
                       ("Code Repo","code_dir")]:
        if tiers.get(key):
            sha_parts.append(f"{label}: {get_git_sha(tiers[key])}")
    sha_line = ", ".join(sha_parts) or "none"
    mandatory = [r for r in rules if r["level"] == "mandatory"]
    advisory  = [r for r in rules if r["level"] == "advisory"]

    L = [
        "# Constitution", "",
        f"> Auto-generated by `relay compile-constitution` on {today}.",
        f"> Source SHAs — {sha_line}",
        "> Re-run `relay compile-constitution` if rules may have changed.",
        "", "## Mandatory Rules",
    ]
    if not mandatory:
        L += ["", "_No mandatory rules found._"]
    else:
        for r in mandatory:
            L += ["", f"### {r['topic'].title()} (from: {r['tier']})", ""]
            if os.path.exists(r["abs_path"]):
                with open(r["abs_path"]) as f:
                    L.append(strip_frontmatter(f.read()).strip())
            else:
                L.append(f"_Rule file not found: {r['abs_path']}_")
            L += ["", "---"]

    L += ["", "## Advisory Rules", "",
          "<!-- These rules apply when working on the relevant topic. "
          "Read the full rule file when needed. -->"]
    if not advisory:
        L += ["", "_No advisory rules found._"]
    else:
        L += ["", "| Topic | Description | Full rule |",
              "|-------|-------------|-----------|"]
        for r in advisory:
            rp = os.path.relpath(r["abs_path"], target_dir)
            L.append(f"| {r['topic']} | {r['description']} | Read: `{rp}` |")

    L += ["", "## How to Use Additional Rules", "",
          "When your current task involves a topic in Advisory Rules above:",
          '1. Read the file at the path shown in the "Full rule" column',
          "2. Follow those rules for the duration of your current task",
          "3. If the file does not exist at the specified path, skip it",
          "", "All paths are relative to this repository's root directory.", ""]
    return "\n".join(L)


def _output_path(tiers, target_dir, override):
    if override:
        return override
    if tiers.get("code_dir"):
        return os.path.join(tiers["code_dir"], ".relay", "constitution.md")
    if tiers.get("cp_dir"):
        return os.path.join(tiers["cp_dir"], ".relay", "constitution.md")
    return os.path.join(target_dir, "constitution.md")


def _minimal_constitution():
    return ("# Constitution\n\n"
            "> Auto-generated by `relay compile-constitution` on "
            f"{datetime.date.today().isoformat()}.\n"
            "> No rule manifests found. Add a manifest.md to "
            "configure rules.\n")

# ── Pipeline ────────────────────────────────────────────────────

MANIFEST_LOCATIONS = [
    ("relay",         "relay_dir", os.path.join("process", "manifest.md")),
    ("control-plane", "cp_dir",    os.path.join(".relay", "manifest.md")),
    ("code-repo",     "code_dir",  os.path.join(".relay", "manifest.md")),
]

def compile_constitution(target_dir, cp_dir_override=None, dry_run=False,
                         output_override=None, validate_only=False):
    print_header("Compile Constitution")
    tiers = detect_context(target_dir, explicit_cp_dir=cp_dir_override)
    ctx = []
    for label, key in [("relay","relay_dir"),("cp","cp_dir"),("code","code_dir")]:
        if tiers[key]: ctx.append(f"{label}={os.path.basename(tiers[key])}")
    if not ctx:
        print_fail("No tiers detected. Run from a relay, CP, or code repo.")
        sys.exit(1)
    print_ok(f"Context: {', '.join(ctx)}")

    tier_rules = []
    for tier_label, tier_key, subpath in MANIFEST_LOCATIONS:
        tp = tiers.get(tier_key)
        if not tp: continue
        meta, rules = parse_manifest(os.path.join(tp, subpath))
        if meta is not None:
            print_ok(f"{tier_label} manifest: {len(rules)} rule(s)")
            tier_rules.append((tier_label, tp, rules))
        else:
            print_info(f"{tier_label} manifest: not found (skipped)")

    if not tier_rules:
        print_warn("No manifests found in any tier")
        text = _minimal_constitution()
        if dry_run:
            print(text); return
        out = _output_path(tiers, target_dir, output_override)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as f: f.write(text)
        print_ok(f"Wrote minimal constitution: {out}"); return

    merged = merge_rules(tier_rules)
    mc = sum(1 for r in merged if r["level"] == "mandatory")
    ac = sum(1 for r in merged if r["level"] == "advisory")
    print_ok(f"Merged: {len(merged)} rule(s) ({mc} mandatory, {ac} advisory)")

    if validate_only:
        print_header("Validation")
        errs = validate_rules(merged)
        if errs:
            for e in errs: print_fail(e)
            sys.exit(1)
        print_ok("All rules valid"); return

    constitution = build_constitution(merged, tiers, target_dir)
    if dry_run:
        print(constitution); print_info("Dry run — nothing written"); return

    out = _output_path(tiers, target_dir, output_override)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f: f.write(constitution)
    print_ok(f"Wrote: {out}")

# ── CLI ─────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Compile rule manifests into a constitution file.")
    p.add_argument("target_dir", nargs="?", default=os.getcwd(),
                   help="Directory to compile for (default: cwd)")
    p.add_argument("--cp-dir", dest="cp_dir",
                   help="Explicit control plane directory")
    p.add_argument("--dry-run", action="store_true",
                   help="Print to stdout instead of writing file")
    p.add_argument("--output", dest="output_path",
                   help="Override output path")
    p.add_argument("--validate", action="store_true",
                   help="Validate manifest entries (paths, duplicates, token budget)")
    args = p.parse_args()
    target = os.path.abspath(args.target_dir)
    if not os.path.isdir(target):
        print_fail(f"Target directory does not exist: {target}"); sys.exit(1)
    compile_constitution(target, args.cp_dir, args.dry_run,
                         args.output_path, args.validate)

if __name__ == "__main__":
    main()
