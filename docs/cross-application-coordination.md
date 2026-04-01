# Cross-Application Coordination

**Design Spec — Federated Coordination with Contract-as-Dependency**

> How separate applications (each with their own control plane and code repos) coordinate via shared data contracts and event schemas without a monolithic shared repo.

---

## 1. Repository Structure

### Contract Registry

A dedicated, standalone repo owned jointly by all participating teams. It holds the canonical versioned schemas that applications share.

```
contract-registry/
├── schemas/
│   ├── order-placed.v1.json          # Versioned event schema
│   ├── order-placed.v2.json          # New version (v1 still active)
│   ├── user-profile.v1.json          # Shared data contract
│   └── inventory-reserved.v1.json
├── proposals/
│   ├── 001-order-placed-add-currency.md   # RFC for schema change
│   └── 002-new-shipment-tracking-event.md
├── CODEOWNERS                        # Joint ownership rules
├── CHANGELOG.md                      # Cross-app audit trail
└── README.md                         # Registry purpose and contribution guide
```

**Key decisions:**
- One schema file per version (not overwritten in place) — consumers pin to a version
- `proposals/` uses an RFC-style numbered process — changes are negotiated, not dictated
- `CODEOWNERS` enforces that schema changes require approval from all consuming teams

### Per-Application Control Plane (Extended)

Each application's control plane gains two new directories for tracking external dependencies:

```
control-plane/                      # Existing structure unchanged
├── contracts/
│   ├── tasks-api.json                # Internal contract (existing)
│   └── external/                     # NEW — external contract mirrors
│       ├── order-placed.v1.json      # Pulled from contract-registry
│       └── user-profile.v1.json
├── external-contracts.lock           # NEW — dependency manifest
├── features/                     # features/<phase>/<name>.md
│   ├── draft/
│   ├── active/
│   ├── completed/
│   └── cancelled/
├── queue/                        # queue/<feature>/<status>/wave-*.md
├── CLAUDE.md
└── ...
```

The `contracts/external/` directory contains **read-only copies** of schemas from the contract-registry. These are synced automatically (see Section 2) and should never be hand-edited.

---

## 2. Contract Lifecycle

### Proposal Process

1. **Author drafts an RFC** in `contract-registry/proposals/NNN-<description>.md`
2. **RFC includes:** motivation, schema diff, affected applications, migration path, rollback plan
3. **Review via PR** — `CODEOWNERS` routes to leads from all affected applications
4. **Approval requires sign-off** from at least one reviewer per consuming application
5. **On merge:** the schema file is added/updated in `schemas/`, `CHANGELOG.md` is appended

### RFC Template

```markdown
# Proposal NNN: <Title>

## Motivation
Why this change is needed.

## Affected Applications
- [ ] Sunshine (producer)
- [ ] Rainyday (consumer)

## Schema Change
\```diff
# Diff against current version
\```

## Migration Path
How consuming applications adopt this change.

## Rollback Plan
How to revert if the change causes issues.

## Status
Draft | Under Review | Accepted | Rejected | Superseded
```

### Versioned Schemas

- Schemas follow `<name>.v<N>.json` naming
- Major version bumps for breaking changes; minor changes extend the existing version
- Old versions are never deleted — they remain until all consumers have migrated
- Each schema file includes a `$id` and `version` field in its JSON Schema metadata

### Automated Sync

A GitHub Action in the contract-registry repo opens PRs in consuming control planes when schemas change:

```yaml
# contract-registry/.github/workflows/sync-consumers.yml
name: Sync schema changes to consumers

on:
  push:
    branches: [main]
    paths: ['schemas/**']

jobs:
  sync:
    strategy:
      matrix:
        consumer:
          - repo: ChristianJensen/sunshine-control-plane
            lock-file: external-contracts.lock
          - repo: ChristianJensen/rainyday-control-plane
            lock-file: external-contracts.lock
    steps:
      - uses: actions/checkout@v6
      - name: Identify changed schemas
        id: changes
        run: |
          git diff --name-only HEAD~1 -- schemas/ > changed.txt
      - name: Open PR in consumer repo
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.CROSS_REPO_TOKEN }}
          repository: ${{ matrix.consumer.repo }}
          title: "chore: sync external contracts"
          body: |
            Updated schemas from contract-registry:
            $(cat changed.txt)
          branch: chore/sync-external-contracts
```

### external-contracts.lock

Tracks which external schemas this application depends on, their versions, and their role.

```yaml
# external-contracts.lock
registry: ChristianJensen/contract-registry
synced-at: 2026-03-12T14:30:00Z

contracts:
  - schema: order-placed.v1.json
    version: 1
    local-path: contracts/external/order-placed.v1.json
    role: consumer           # producer | consumer | both
    synced-sha: abc123f      # commit SHA in contract-registry

  - schema: user-profile.v1.json
    version: 1
    local-path: contracts/external/user-profile.v1.json
    role: producer
    synced-sha: def456a
```

**Semantics:**
- `role: producer` — this application emits data conforming to this schema
- `role: consumer` — this application ingests data conforming to this schema
- `role: both` — this application both produces and consumes
- `synced-sha` — enables drift detection (is our local copy current?)
- Lock file is updated by the sync GitHub Action PR, reviewed by the owning team

---

## 3. Human Planning Workflow

### Initiating Cross-App Features

When a PM identifies a feature that spans applications:

1. **Feature Definition with cross-app context.** The PM runs a feature definition in their application's control plane, but includes awareness of the other application(s). The feature spec's frontmatter gains new fields:

```yaml
# File lives in features/draft/ (phase directory is authoritative for lifecycle)
---
lifecycle: draft
version: 1
cross-app-feature: true                    # NEW — flags this as cross-app
related-control-planes:                        # NEW — other apps involved
  - name: rainyday
    repo: ChristianJensen/rainyday-control-plane
    role: consumer
external-contracts:                        # NEW — shared schemas needed
  - schema: order-placed.v1.json
    status: exists                         # exists | proposed | new
  - schema: shipment-tracking.v1.json
    status: new                            # needs RFC in contract-registry
---
```

2. **Schema negotiation.** For `status: new` or `status: proposed` contracts, the PM (or architect) authors an RFC in `contract-registry/proposals/`. This happens before decomposition — both teams need the schema agreed upon before they can independently decompose their half.

3. **Independent decomposition.** Once schemas are accepted, each application's architect decomposes their half independently. The external contract in `contracts/external/` is the coordination boundary — architects don't need to talk to each other about implementation details.

4. **Integration readiness gates.** Each team signals readiness by updating a lightweight status in their feature spec:

```yaml
integration-readiness:
  - contract: order-placed.v1.json
    status: ready                          # not-started | in-progress | ready
    verified-at: 2026-03-15T10:00:00Z
```

### Cross-App Feature Lifecycle

The cross-app feature lifecycle mirrors the single-app lifecycle but adds a coordination phase between draft and active. Phase directories are authoritative for lifecycle state:

```
features/draft/ → (schema-negotiation, tracked in frontmatter) → features/active/ → ... → features/completed/
```

| State | Directory | Meaning |
|-------|-----------|---------|
| `draft` | `features/draft/` | Feature captured, cross-app dependencies identified |
| `schema-negotiation` | `features/draft/` (frontmatter sub-state) | RFCs submitted to contract-registry, awaiting approval |
| `active` | `features/active/` | Schemas accepted, decomposition and execution proceed |

The `schema-negotiation` state is optional — if all needed schemas already exist, the feature moves directly from `features/draft/` to `features/active/`.

---

## 4. Agent Execution Model

### Discovering External Contracts

Agents discover external contracts the same way they discover internal ones — by reading the `contracts/` directory. The `contracts/external/` subdirectory is structurally identical to internal contracts.

The key difference is behavioral: agents treat external contracts as **immutable inputs**. They implement against them but never modify them. Only the contract-registry sync process updates files in `contracts/external/`.

### Watcher Changes

The watcher gains one new pre-flight step:

```
1. git pull --ff-only                           # existing — refresh queue
2. CHECK external-contracts.lock for drift      # NEW
   - Compare synced-sha against contract-registry HEAD
   - If drift detected: log warning, continue (don't block)
   - If breaking version bump: block task pickup, alert human
3. Scan queue/*/ready/wave-*.md → filter target-repo       # existing (directory-based)
...
```

**Drift detection** is advisory, not blocking — schema changes go through PRs, so the lock file is always intentionally updated. But if a breaking change lands and the lock file hasn't been updated, the watcher warns before an agent implements against a stale schema.

### Task Frontmatter Extension

Tasks that depend on external contracts declare them in frontmatter:

```yaml
---
status: ready
target-repo: api
wave: 1
priority: high
feature: cross-app-order-sync
type: feature
contracts:
  - contracts/tasks-api.json
external-contracts:                        # NEW
  - contracts/external/order-placed.v1.json
  - contracts/external/user-profile.v1.json
---
```

This gives the implementer agent explicit pointers to the external schemas it must conform to.

### Constitution (CLAUDE.md) Updates

Each application's `CLAUDE.md` gains a section on external contracts:

```markdown
## External Contracts

Files in `contracts/external/` are shared schemas from the contract-registry.

- **Read-only.** Never modify files in `contracts/external/`. They are synced
  from the contract-registry and updated only via automated PRs.
- **Implement against them.** When a task references an external contract,
  read the schema and ensure your implementation conforms to it.
- **Report mismatches.** If an external contract doesn't match what you need,
  set the task to `status: blocked` and note the mismatch in Implementation Notes.
  Do not attempt to "work around" a schema mismatch.
```

### Boundary Rule

**Agents never cross application boundaries.** An agent in the Sunshine ecosystem never reads code from, writes to, or creates branches in a Rainyday repo. The only shared artifact is the schema in `contracts/external/`, which arrived via a reviewed, automated PR.

This is the same principle as the existing "one agent per repo" rule (Section 3 of Relay), extended to the application level: **one agent per repo, one control plane per application, schemas as the only bridge.**

---

## 5. Cross-App Wave Coordination

### No Shared Wave System

Each application runs its own wave system independently. There is no cross-application wave numbering, no shared promotion schedule, and no cross-app watcher. This preserves team autonomy — Sunshine can ship wave 3 while Rainyday is still on wave 1.

### Integration Readiness Gates

The coordination mechanism is the **integration readiness gate** — a declaration by each team that their side of a shared contract is implemented, tested, and deployed.

```
Sunshine wave 2 (producer): implements order-placed.v1 → marks ready
Rainyday wave 1 (consumer): implements order-placed.v1 consumer → marks ready
                                                          ↓
                                              Integration test triggered
```

Readiness is tracked in each application's feature spec (see Section 3) and is visible to both teams via the contract-registry's `CHANGELOG.md` and each control plane's feature spec.

### Parallel Development Pattern

When both applications can develop against the schema independently:

1. Schema is accepted in contract-registry
2. Both teams decompose independently
3. Both teams implement against the schema in parallel
4. Each team writes contract-compliance tests against the schema
5. When both signal `ready`, an integration test runs (manual or CI)
6. Issues found flow back as bug reports or contract-registry proposals

**This is the common case.** Most cross-app features involve a producer and consumer that can be built independently once the schema is agreed upon.

### Sequential Dependency Pattern

When one application must ship before the other can start:

1. Schema is accepted in contract-registry
2. Producer team decomposes and implements first
3. Producer signals `ready` and deploys to a staging/preview environment
4. Consumer team decomposes against the live producer + schema
5. Consumer implements and tests against the staging producer

**Track this in the feature spec:**

```yaml
dependency-order:
  - application: sunshine
    role: producer
    must-ship-before: rainyday
  - application: rainyday
    role: consumer
    blocked-until: sunshine-ready
```

The watcher in the consumer application checks this field — if `blocked-until` references another application that hasn't signaled ready, tasks remain in `pending`.

---

## 6. Retrospectives and Learning

### New Root Cause Category

The retro log (`retrospectives/retro-log.md`) gains a new root cause category:

| Category | Meaning |
|----------|---------|
| `cross-app-contract-gap` | Failure caused by an incomplete, ambiguous, or stale external contract |

This sits alongside the existing categories: `ambiguous-requirement`, `bad-decomposition`, `missing-edge-case`, `contract-gap`, `tooling-issue`.

### Feedback Loop to Contract Registry

When a retrospective identifies `cross-app-contract-gap`:

1. The architect files a proposal in `contract-registry/proposals/` to fix the gap
2. The proposal references the retro entry (link to retro-log.md line)
3. The proposal follows the standard RFC process (Section 2)
4. Once merged, the fix flows to all consumers via the automated sync

This closes the loop: **failure in one app → schema improvement → all apps benefit.**

### CHANGELOG.md as Audit Trail

The contract-registry's `CHANGELOG.md` serves as the cross-application audit trail:

```markdown
# Changelog

## 2026-03-15
- **order-placed.v2.json** — Added `currency` field (proposal #001)
  - Producer: Sunshine (ready: 2026-03-14)
  - Consumer: Rainyday (ready: 2026-03-15)
  - Integration verified: 2026-03-15

## 2026-03-10
- **order-placed.v1.json** — Initial schema
  - Producer: Sunshine
  - Consumer: Rainyday
```

Each entry records what changed, who was affected, and when integration was verified. This replaces cross-team Slack threads and status meetings as the canonical record of cross-app coordination.

---

## 7. Scaling Considerations

### Adding a New Application

When a new application (e.g., "Stormy") joins the ecosystem:

1. **Create the application's control plane** with standard structure
2. **Add `contracts/external/` and `external-contracts.lock`** to the control plane
3. **Add the new repo to `contract-registry/CODEOWNERS`** for schemas it consumes or produces
4. **Add the new repo to the sync GitHub Action's consumer matrix** in the contract-registry
5. **Existing schemas don't change.** Stormy pins to the versions it needs. No disruption to Sunshine or Rainyday.

**Cost to existing teams: zero.** Adding a new application doesn't require changes to existing control planes, schemas, or workflows. The new team adds themselves to the registry; existing teams only notice when a shared schema proposal appears for review.

### Multiple Integration Points

When two applications share multiple contracts (e.g., Sunshine and Rainyday share `order-placed`, `user-profile`, and `inventory-reserved`):

- Each contract is independent — versioned, proposed, and synced separately
- `external-contracts.lock` lists all of them
- Tasks reference only the specific contracts they need
- Integration readiness is tracked per-contract, not per-application

### N-Way Integrations

When 3+ applications share a contract (e.g., `user-profile.v1.json` consumed by Sunshine, Rainyday, and Stormy):

- `CODEOWNERS` in the contract-registry requires approval from all three teams
- The sync GitHub Action's consumer matrix includes all three control planes
- Each application independently implements against the schema
- Integration readiness is tracked per-application in each control plane's feature spec
- Integration testing fans out: producer tests with each consumer independently

**Coordination scales linearly.** Each new consumer adds one entry to `CODEOWNERS` and one entry to the sync matrix. There is no combinatorial explosion because applications don't integrate with each other — they integrate with the schema.

### When NOT to Use Cross-App Coordination

This design is for **shared data contracts and event schemas.** It is not appropriate for:

- **Shared libraries or packages** — use a package manager (npm, Maven, etc.)
- **Shared UI components** — use a component library with its own versioning
- **Direct service-to-service calls** — use internal API contracts within a single application's `contracts/` directory
- **Shared infrastructure** — use platform engineering practices, not schema coordination

---

## Appendix: Compatibility with Existing Relay

This design extends Relay without breaking changes:

| Existing Concept | Extension |
|-----------------|-----------|
| `contracts/` directory | Gains `external/` subdirectory |
| Task frontmatter `contracts:` | Gains sibling `external-contracts:` field |
| Feature spec frontmatter | Gains `cross-app-feature`, `related-control-planes`, `external-contracts` fields |
| `CLAUDE.md` constitution | Gains "External Contracts" section |
| Watcher pre-flight | Gains drift-detection step |
| Retro root causes | Gains `cross-app-contract-gap` category |
| Wave system | Unchanged — each app runs independently |
| Branch-claim protocol | Unchanged — scoped to single repo |
| Service catalog | Each app maintains its own; no shared catalog |

**No existing files are modified.** The design is purely additive — new directories, new frontmatter fields, and a new external repo (contract-registry). Teams that don't participate in cross-app coordination are unaffected.
