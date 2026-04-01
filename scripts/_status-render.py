#!/usr/bin/env python3
"""Relay status renderer — cross-references tasks with branches and PRs."""
import json, subprocess, sys, os, time, re

tasks_raw = sys.argv[1].strip()
try:
    tasks = json.loads(tasks_raw) if tasks_raw else []
except json.JSONDecodeError:
    tasks = []
branches_raw = sys.argv[2]
repo_local = sys.argv[3]
repo_nwo = sys.argv[4]
repo_name = sys.argv[5]
feature_filter = sys.argv[6]
fix_mode = sys.argv[7] == 'true'
json_mode = sys.argv[8] == 'true'
cp_dir = sys.argv[9]
json_tmp = sys.argv[10]
seen_features_file = sys.argv[11]

branches = set(b.strip() for b in branches_raw.strip().split('\n') if b.strip())

# Load previously seen features (for text mode header dedup)
seen_features = set()
if os.path.exists(seen_features_file):
    with open(seen_features_file) as f:
        seen_features = set(line.strip() for line in f if line.strip())

# Group tasks by feature
features = {}
for t in tasks:
    feat = t.get('feature', 'unknown')
    if feature_filter and feat != feature_filter:
        continue
    features.setdefault(feat, []).append(t)

if not features:
    sys.exit(0)

def derive_branch(task_path, repo_name, task_type):
    # queue/<feature>/<status>/wave-*.md — skip status dir to get feature
    dirname = os.path.basename(os.path.dirname(os.path.dirname(task_path)))
    filename = os.path.basename(task_path).replace('.md', '')
    wave_match = re.match(r'wave-(\d+)-(.*)', filename)
    if not wave_match:
        return None
    wave_num = wave_match.group(1)
    rest = wave_match.group(2)
    if rest.startswith(repo_name + '-'):
        task_slug = rest[len(repo_name) + 1:]
    else:
        task_slug = rest
    prefix = 'fix' if task_type == 'bug' else 'agent'
    return f'{prefix}/{dirname}-w{wave_num}-{task_slug}'

def get_branch_info(branch, repo_local):
    agent = None
    age_str = None
    stale = False
    try:
        result = subprocess.run(
            ['git', '-C', repo_local, 'log', f'origin/{branch}', '--format=%s', '-1'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            msg = result.stdout.strip()
            if msg.startswith('claim: '):
                agent = msg[7:]
            else:
                agent = '(working)'

        result = subprocess.run(
            ['git', '-C', repo_local, 'log', f'origin/{branch}', '--format=%ct', '-1'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            ts = int(result.stdout.strip())
            age_secs = int(time.time()) - ts
            if age_secs < 60:
                age_str = f'{age_secs}s ago'
            elif age_secs < 3600:
                age_str = f'{age_secs // 60}m ago'
            elif age_secs < 86400:
                age_str = f'{age_secs // 3600}h ago'
            else:
                age_str = f'{age_secs // 86400}d ago'
            stale = age_secs > 300
    except Exception:
        pass
    return agent, age_str, stale

def get_claimed_by(task_data):
    """Prefer frontmatter claimed-by over branch-derived agent."""
    claimed = task_data.get('claimed_by', '')
    if claimed and claimed != '""':
        return claimed
    return None

def get_pr_info(branch, repo_nwo):
    try:
        result = subprocess.run(
            ['gh', 'pr', 'list', '--repo', repo_nwo, '--head', branch,
             '--json', 'number,state,url', '--limit', '1'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            prs = json.loads(result.stdout)
            if prs:
                return prs[0]
    except Exception:
        pass
    return None

# Colors
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
BLUE = '\033[0;34m'
DIM = '\033[2m'
BOLD = '\033[1m'
NC = '\033[0m'

STATUS_COLORS = {
    'ready': BLUE,
    'in-progress': YELLOW,
    'done': GREEN,
    'blocked': RED,
    'pending': DIM,
    'paused': DIM,
    'cancelled': DIM,
}

# Load accumulated JSON from prior repos
with open(json_tmp) as f:
    json_output = json.load(f)

warnings = []
fixes = []

for feat_name in sorted(features.keys()):
    feat_tasks = features[feat_name]

    # Check feature lifecycle from phase directory
    spec_path = None
    lifecycle = 'active'
    content = ''
    for phase in ('active', 'draft', 'completed', 'cancelled'):
        for suffix in ('-feature.md', '-bug.md'):
            candidate = os.path.join(cp_dir, 'features', phase, f'{feat_name}{suffix}')
            if os.path.exists(candidate):
                spec_path = candidate
                # Infer lifecycle from directory
                lifecycle = phase if phase != 'draft' else 'draft'
                break
        if spec_path:
            break
    # Also check bugs/ directory
    if not spec_path:
        bugs_dir = os.path.join(cp_dir, 'bugs')
        if os.path.isdir(bugs_dir):
            for phase in ('active', 'draft', 'completed', 'cancelled'):
                candidate = os.path.join(bugs_dir, phase, f'{feat_name}-bug.md')
                if os.path.exists(candidate):
                    spec_path = candidate
                    lifecycle = phase if phase != 'draft' else 'draft'
                    break
    if spec_path:
        with open(spec_path) as f:
            content = f.read()

    # Read feature-level execution mode for fallback
    feature_exec = 'supervised'
    if spec_path and content:
        fm2 = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if fm2:
            for line in fm2.group(1).split('\n'):
                m = re.match(r'^execution:\s*(\S+)', line)
                if m:
                    val = m.group(1).strip().strip(chr(34)).strip(chr(39))
                    val = re.sub(r'\s+#.*$', '', val)
                    if val:
                        feature_exec = val

    if not json_mode and feat_name not in seen_features:
        print(f'\n{BOLD}{feat_name}{NC}  {DIM}(lifecycle: {lifecycle}){NC}')
        print()
        h = ['Task', 'Status', 'Exec', 'Agent', 'Branch', 'PR']
        print(f'  {h[0]:<40} {h[1]:<14} {h[2]:<13} {h[3]:<28} {h[4]:<18} {h[5]:<10}')
        seen_features.add(feat_name)

    for t in sorted(feat_tasks, key=lambda x: (x['wave'], x['rank'])):
        task_path = t['path']
        task_status = t['status']
        task_type = t.get('type', 'feature')
        filename = os.path.basename(task_path).replace('.md', '')

        # Resolve execution mode: task -> feature -> supervised
        task_exec = t.get('execution', '') or ''
        task_exec = task_exec.strip().strip(chr(34)).strip(chr(39))
        if not task_exec:
            task_exec = feature_exec

        branch = derive_branch(task_path, repo_name, task_type)
        has_branch = branch and branch in branches
        agent = None
        age_str = None
        stale = False
        pr_info = None

        # Prefer frontmatter claim over branch-derived agent
        frontmatter_agent = get_claimed_by(t)

        if has_branch and os.path.isdir(repo_local):
            agent, age_str, stale = get_branch_info(branch, repo_local)
            pr_info = get_pr_info(branch, repo_nwo)
        if frontmatter_agent:
            agent = frontmatter_agent

        branch_str = '\u2014'
        pr_str = '\u2014'
        warning = None

        if has_branch:
            branch_str = 'pushed (%s)' % (age_str or '?')
        if pr_info:
            state = pr_info['state']
            num = pr_info['number']
            if state == 'MERGED':
                pr_str = f'PR #{num} (merged)'
            elif state == 'OPEN':
                pr_str = f'PR #{num}'
            elif state == 'CLOSED':
                pr_str = f'PR #{num} (closed)'

        # Detect mismatches
        if task_status == 'in-progress' and not has_branch:
            if pr_info and pr_info['state'] == 'MERGED':
                warning = '%s: status is in-progress but PR is merged \u2192 should be done' % filename
                if fix_mode:
                    fixes.append(('done', task_path, filename))
            else:
                warning = '%s: status is in-progress but no branch exists \u2192 likely stale' % filename
                if fix_mode:
                    fixes.append(('ready', task_path, filename))
        elif task_status == 'done' and not has_branch and not (pr_info and pr_info['state'] == 'MERGED'):
            warning = '%s: status is done but no merged PR found' % filename
        elif task_status == 'ready' and has_branch:
            warning = '%s: status is ready but branch exists \u2192 should be in-progress' % filename
            if fix_mode:
                fixes.append(('in-progress', task_path, filename))

        # Check for unmet dependencies
        deps = t.get('depends_on', [])
        unmet_deps = []
        if deps:
            for dep in deps:
                dep_status = None
                for at in tasks:
                    if os.path.basename(at['path']) == dep:
                        dep_status = at.get('status')
                        break
                if dep_status != 'done':
                    unmet_deps.append(dep)

        # Check if task has a PR recorded in frontmatter (read from file)
        task_pr_url = ''
        task_pr_number = ''
        try:
            with open(task_path) as _f:
                _content = _f.read()
            _fm = re.match(r'^---\s*\n(.*?)\n---', _content, re.DOTALL)
            if _fm:
                _m = re.search(r'^pr-url:\s*(.+)', _fm.group(1), re.MULTILINE)
                if _m: task_pr_url = _m.group(1).strip().strip('"').strip("'")
                _m = re.search(r'^pr-number:\s*(.+)', _fm.group(1), re.MULTILINE)
                if _m: task_pr_number = _m.group(1).strip().strip('"').strip("'")
        except Exception:
            pass

        if not json_mode:
            color = STATUS_COLORS.get(task_status, NC)
            status_label = task_status
            if task_status == 'done' and pr_info and pr_info['state'] == 'OPEN':
                status_label = 'done (awaiting review)'

            # Show "awaiting review" for in-progress tasks with a PR
            if task_status == 'in-progress' and task_pr_url:
                status_label = 'in-progress (awaiting review)'

            status_display = f'{color}\u25cf {status_label}{NC}'
            if unmet_deps:
                dep_names = ', '.join(d.replace('.md', '') for d in unmet_deps)
                status_display = f'{RED}\u25cf blocked (deps: {dep_names}){NC}'
            agent_display = agent or '\u2014'
            exec_display = task_exec
            print(f'  {filename:<40} {status_display:<24} {exec_display:<13} {agent_display:<28} {branch_str:<18} {pr_str}')
            if warning:
                warnings.append(warning)
            # Track task in json_output for "no tasks found" check in status.sh
            json_output.append({'task': filename, 'feature': feat_name})
        else:
            task_json = {
                'task': filename,
                'feature': feat_name,
                'repo': repo_name,
                'status': task_status,
                'type': task_type,
                'execution': task_exec,
                'wave': t['wave'],
                'priority': t.get('priority', 'normal'),
                'branch': branch if has_branch else None,
                'agent': agent or None,
                'claimed_by': t.get('claimed_by', ''),
                'claimed_at': t.get('claimed_at', ''),
                'claimed_on': t.get('claimed_on', ''),
                'stale': stale if has_branch else False,
                'pr': pr_info,
                'pr_state': pr_info['state'] if pr_info else None,
                'pr_url': task_pr_url or None,
                'pr_number': task_pr_number or None,
                'awaiting_review': bool(task_pr_url),
                'depends_on': deps,
                'unmet_deps': unmet_deps,
            }
            if warning:
                task_json['warning'] = warning
            json_output.append(task_json)

# Apply fixes
if fix_mode and fixes:
    for new_status, task_path, fname in fixes:
        with open(task_path) as f:
            content = f.read()
        content = re.sub(r'^status:\s+\S+', f'status: {new_status}', content, count=1, flags=re.MULTILINE)
        with open(task_path, 'w') as f:
            f.write(content)
        if not json_mode:
            print(f'  {GREEN}Fixed:{NC} {fname} \u2192 {new_status}')
        subprocess.run(['git', '-C', cp_dir, 'add', task_path], capture_output=True)

    fix_count = len(fixes)
    subprocess.run(
        ['git', '-C', cp_dir, 'commit', '-m', f'fix: relay status --fix corrected {fix_count} task(s)'],
        capture_output=True
    )
    if not json_mode:
        print(f'\n  {GREEN}Committed {fix_count} fix(es).{NC} Run git push to sync.')

# Print warnings
if not json_mode and warnings:
    print()
    for w in warnings:
        print(f'  {YELLOW}\u26a0{NC}  {w}')
    if not fix_mode:
        print(f'  {DIM}\u2192 Run relay check --fix to auto-correct{NC}')

# Save accumulated JSON for next repo
with open(json_tmp, 'w') as f:
    json.dump(json_output, f)

# Save seen features
with open(seen_features_file, 'w') as f:
    for feat in seen_features:
        f.write(feat + '\n')
