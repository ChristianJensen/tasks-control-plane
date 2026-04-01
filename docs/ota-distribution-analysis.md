# OTA Rule Distribution: Analysis & Demo Scenarios

## How It Works Today

Relay has a **3-tier constitution system** that distributes rules from corporate (Relay repo) down through control planes to individual code repos:

```
Relay Repo (corporate)         process/manifest.md + process/rules/*.md
    ↓ relay upgrade
Control Plane (app)            .relay/manifest.md + rules/*.md
    ↓ relay upgrade --repos
Code Repo (per-repo)           .relay/manifest.md + .relay/rules/*.md
    ↓ compile-constitution.py
Compiled:                      .relay/constitution.md (inlined into agent context)
```

### What Gets Distributed

| Artifact | Mechanism | Destination |
|----------|-----------|-------------|
| **Rules** (security, testing, api-design) | Constitution compiler merges 3 tiers | `.relay/constitution.md` in every repo |
| **CLAUDE.md** (agent behavior) | Template substitution from `CLAUDE.md.tmpl` | Root `CLAUDE.md` in CP and code repos |
| **Workflows** (spec, plan, relay, bug) | Referenced by path in CLAUDE.md | Agents read from `<relay-path>/process/workflows/` |
| **Templates** (feature-spec, task, bug-report) | Referenced by path | Agents read from `<relay-path>/process/templates/` |
| **GitHub Actions** (dispatch, validate, status) | File copy during upgrade | `.github/workflows/` in CP and code repos |
| **Scripts** (status-page, serve.py) | File copy during upgrade | `.github/scripts/` in CP |

### Constitution Mechanics

- **Mandatory rules** are fully inlined into `constitution.md` (always in agent context window)
- **Advisory rules** appear as a reference table with file paths (read on demand)
- **Inner tiers override outer tiers** for the same topic (code-repo can exclude advisory rules)
- Token budget: mandatory rules capped at ~50K tokens
- Freshness check: `relay check-rules` compares recorded SHAs vs current HEAD

### Current Rules in `process/manifest.md`

| Topic | Level | Content |
|-------|-------|---------|
| security | mandatory | Input validation, auth, secrets, deps, OWASP |
| testing | mandatory | TDD, naming, coverage, isolation, test pyramid |
| api-design | advisory | REST naming, versioning, error shapes, pagination |

---

## What Works Well

1. **Single source of truth** -- rules live in one place (Relay repo), flow downstream automatically
2. **3-tier override model** -- corporate sets baseline, app teams and repos can customize or exclude advisory rules
3. **Mandatory vs advisory** -- critical rules always in context; advisory loaded on demand (saves tokens)
4. **Freshness detection** -- `check-rules` catches drift between compiled constitution and source repos
5. **Dry-run support** -- `compile-constitution.py --dry-run` previews changes before applying
6. **Token budget guard** -- compiler warns if mandatory rules exceed 50K tokens
7. **CLAUDE.md template system** -- agent behavior instructions distributed consistently via variable substitution

---

## Gaps Identified

### Gap 1: No automatic recompilation trigger

Rules changes in the Relay repo don't automatically propagate. Someone must manually run `relay upgrade` on each CP, then `relay upgrade --repos` for code repos. No CI workflow detects stale constitutions and alerts or auto-upgrades.

### Gap 2: Workflows and templates are path-referenced, not versioned

CLAUDE.md points agents to `{{RELAY_PATH}}/process/workflows/relay.md`. If Relay updates a workflow, agents immediately get the new version on next read -- no controlled rollout, no ability to pin a workflow version per-app.

### Gap 3: No changelog or diff visibility for rule changes

When `relay upgrade` recompiles constitutions, there's no diff shown of what changed in the rules themselves. The upgrade script shows file-level diffs for scripts/workflows but not for rule content changes.

### Gap 4: Code repo CLAUDE.md not re-templated on upgrade

`upgrade.sh` regenerates CP's CLAUDE.md from template, but code repo CLAUDE.md files (from `code-repo-setup/CLAUDE.md.tmpl`) are only created during bootstrap -- not updated on upgrade. If the template changes, existing code repos keep the old version.

### Gap 5: No rule categories beyond coding

Current rules cover security, testing, and API design. There are no rules governing **planning processes**, **documentation standards**, **observability/logging**, or **PR review expectations** -- all areas where corporate standards could be enforced.

### Gap 6: No per-repo rule compliance reporting

While `check-rules` detects staleness, there's no way to audit which repos actually comply with rules. The compliance-controls.yml exists but isn't integrated into the constitution pipeline.

---

## Demo Scenarios

### Demo 1: "All Code Must Include Structured Logging" (New Mandatory Rule)

**Story:** Corporate mandates structured JSON logging across all services for SOC2 audit trail compliance.

**Steps:**

1. Create `process/rules/observability.md` in Relay repo with mandatory structured logging rules (log levels, JSON format, correlation IDs, PII redaction)
2. Add row to `process/manifest.md`: `| observability | Structured logging, correlation IDs, PII redaction | mandatory | process/rules/observability.md |`
3. Run `relay upgrade` on each control plane -- constitution recompiles automatically
4. Run `relay upgrade --repos` -- every code repo gets updated `.relay/constitution.md`
5. **Result:** Next time any agent picks up a task in any repo, the observability rules are in its context window. It writes structured logging by default.

**Why it's compelling:** One file added, one manifest line changed, one command run -- and every agent across every repo immediately follows the new corporate standard. No PRs to every repo, no Slack announcements hoping developers read it.

### Demo 2: "Feature Specs Must Include Success Metrics" (Process Change)

**Story:** Product leadership wants every feature spec to include measurable success criteria before development begins, to improve outcome tracking.

**Steps:**

1. Edit `process/templates/feature-spec.md` to add a required "## Success Metrics" section with guidance (e.g., "Define 1-3 measurable outcomes with target values and measurement method")
2. Edit `process/workflows/spec.md` to add an interview question about success metrics during the spec capture flow
3. Run `relay upgrade` on control planes -- templates and workflow paths already point to Relay repo, so changes take effect immediately (no recompilation needed for templates/workflows)
4. **Result:** Next time anyone runs `relay spec`, the agent asks about success metrics and includes them in the spec. Every future feature has measurable outcomes baked in from day one.

**Why it's compelling:** Shows Relay governing *process*, not just code. The change flows through the spec workflow and template simultaneously -- agents can't skip the step because it's in the interview flow.

### Demo 3: "App-Level Override -- Data Team Excludes API Design Rules" (Tier Override)

**Story:** The data team's control plane manages internal ETL pipelines with gRPC, not REST APIs. The corporate api-design rules (REST conventions) are noise for their agents.

**Steps:**

1. In the data team's CP, edit `.relay/manifest.md` to add: `| api-design | Not applicable for gRPC services | exclude | - |`
2. Add a team-specific rule: create `rules/grpc-design.md` with gRPC conventions, add to manifest as advisory
3. Run `relay upgrade --repos` from Relay -- constitution recompiles, corporate api-design rule disappears, grpc-design appears
4. **Result:** Data team agents follow gRPC conventions; all other teams still get REST API rules. Corporate security and testing rules remain mandatory everywhere -- can't be excluded.

**Why it's compelling:** Shows the override model in action. Corporate keeps control of mandatory rules (security, testing) while teams customize advisory rules for their domain. No fork of the framework needed.
