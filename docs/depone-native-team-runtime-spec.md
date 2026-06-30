# Depone Native Team Runtime Spec

Status: planning spec for the next implementation waves
Date: 2026-06-30
Base: `origin/main` after source install readiness smoke

## Purpose

Depone has enough control-plane pieces to stop adding one-off evidence gates and
start connecting them into a small native team runtime. This spec defines the
next product boundary: Depone may prepare, preflight, and later launch local
team lanes only when every lane has a deterministic evidence path. It must not
claim that a chat summary, a planned lane, or an external cloud fact proves work
completion.

The first target is not a full OMX or LazyCodex replacement. The target is a
minimal, auditable local team loop that can run beside Codex, Claude Code,
OpenCode, shell, OMX, or cloud adapters while keeping Depone as the evidence and
control layer.

## Current Truth

Implemented enough to build on:

- A0/A1/A2 capture assurance and fail-closed capture-manifest validation.
- Real uid/container A2 evidence artifacts committed under `docs/`.
- Evidence substrate, evidence ingest, signing/sealing, `evidence-next`, and
  `advance`.
- Team Ledger v0 fan-in validation.
- Team Ledger PR artifact validation.
- Local worktree lane receipts.
- Planning-only `team-dry-run` artifacts.
- Observed cloud lane artifacts.
- Source install readiness smoke in the changed-tier contract.

Not implemented yet:

- Depone does not launch worker agents.
- Depone does not create or own durable lane sessions.
- Depone does not create per-lane worktrees automatically.
- Depone does not run Codex, Claude Code, OpenCode, OMX, or cloud workers.
- Depone does not derive merge receipts from real git merge/rebase evidence.
- Depone does not own cloud execution, cloud secrets, or provider runtime
  isolation attestations.

## Product Boundary

Depone native team work has three layers:

1. **Plan and preflight**: create lane records, planned worktree paths, safety
   checks, expected evidence paths, and blocked Team Ledger skeletons.
2. **Launch and observe**: run a single lane through a supported adapter only
   after preflight passes, capturing command receipts and lane evidence outside
   the lane's own claim surface.
3. **Fan-in and advance**: validate every lane through Team Ledger, require
   merge receipts for overlaps, and run exactly one verified continuation
   through `advance` when the ledger permits it.

The next waves implement layer 1 first. Layer 2 and layer 3 remain blocked until
layer 1 has committed machine artifacts and a green changed-tier contract.

## Roles

Depone keeps role names as contracts, not personality brands:

| Role | Responsibility | Cannot Do |
| --- | --- | --- |
| `planner` | write lane packets, ownership, budgets, and stop rules | mark execution complete |
| `explorer` | map current repo state and impact surface | edit files unless upgraded |
| `worker` | implement one bounded packet | approve its own result |
| `reviewer` | find bugs, regressions, missing tests, contract drift | repair findings without a new packet |
| `verifier` | run tests, smokes, renders, artifact checks | declare product success from prose |
| `operator` | report status and next safe action | bypass gates |

Product aliases can be added later, but the evidence schema should keep these
stable role ids.

## Minimal Native Team Loop

The intended loop is:

```text
objective -> team plan -> lane preflight -> lane launch -> lane evidence
  -> lane review -> repair if needed -> lane verification -> Team Ledger fan-in
  -> merge receipt if needed -> evidence-next -> advance one step -> stop
```

Every phase writes machine JSON. A human-readable Markdown report may summarize
the JSON, but Markdown is never the authority.

## New Concepts

### Team Launch Preflight

`team-launch-preflight` is the next missing bridge between `team-dry-run` and a
real launcher. It is still non-executing. It verifies that a proposed lane can be
launched later without silently crossing a privilege, git, path, or evidence
boundary.

Required input:

- a `team-dry-run` JSON artifact;
- repository root;
- current base commit;
- desired output directory;
- launch intent, either `plan-only` or `launch-ready`;
- optional adapter availability declarations.

Required output:

```json
{
  "kind": "depone-team-launch-preflight",
  "schema_version": "0.1",
  "decision": "pass",
  "launch_intent": "plan-only",
  "team_plan_hash": "sha256...",
  "base_commit": "abc123",
  "lanes": [
    {
      "lane_id": "lane-1",
      "decision": "pass",
      "planned_worktree": "out/team/worktrees/lane-1",
      "evidence_dir": "lane-1",
      "receipt_path": "lane-1/worktree-receipt.json",
      "adapter": {
        "runner_adapter_kind": "codex",
        "team_adapter_kind": "depone-native",
        "available": false,
        "availability_required": false,
        "availability_source": "declared-unavailable"
      },
      "git_boundary": {
        "repo_root": ".",
        "base_commit_exists": true,
        "planned_path_repo_relative": true,
        "path_escapes_repo": false
      }
    }
  ],
  "boundary": {
    "executes_commands": false,
    "launches_agents": false,
    "mutates_worktree": false,
    "creates_worktrees": false,
    "raises_assurance": false
  }
}
```

`launch_intent` has fail-closed semantics:

- `plan-only`: validates paths, commits, lane ids, evidence paths, receipt
  paths, and adapter kinds. Adapter availability may be absent or unavailable,
  but the output must record `availability_required: false` and cannot be used
  as a launch receipt.
- `launch-ready`: validates the same fields and additionally requires an
  adapter availability declaration for every lane runner adapter. Missing or
  unavailable adapters block the preflight.

`decision` is `pass` only when every lane satisfies the selected launch intent.
The output must record whether availability was observed, declared unavailable,
or not required for plan-only preflight.

The preflight output must also bind the Team Ledger skeleton that will be used
for fan-in. The skeleton can be embedded or written as a sibling artifact, but
it must be generated from the same input and preflight lane records. Reviewers
must be able to compare lane ids, evidence directories, planned worktrees, and
receipt paths between the preflight artifact and the Team Ledger skeleton.

### Lane Launch Receipt

This is a later concept, not part of the first implementation wave. A launch
receipt is allowed to run commands and create worktrees, so it must be a separate
command from preflight. It records:

- the exact adapter command launched;
- environment variables deliberately passed;
- cwd;
- worktree path;
- process id or session id when available;
- transcript path;
- expected evidence directory;
- stop rule;
- whether the launcher created or selected the worktree.

No launch receipt can mark a lane as passed. It only proves launch provenance.

### Fan-In Gate

Team Ledger remains the fan-in authority. A future `depone team fan-in` may wrap
Team Ledger, but it must call the same validator and return the same blocked/pass
semantics. It cannot approve merges by itself.

## Fail-Closed Rules

- Planned lanes are blocked until evidence exists.
- A lane with no machine evidence cannot pass.
- A dirty worktree receipt cannot pass fan-in unless the dirty files are
  explicitly part of a later, reviewed repair receipt.
- Same-file overlap between passed lanes requires a passing merge receipt.
- Cloud artifacts remain observed external facts, not Depone-owned runtime
  isolation.
- Adapter availability is an input fact, not permission to launch.
- A verifier may report evidence, but cannot raise assurance.
- A worker may write code, but cannot seal or validate its own success.

## Non-Goals

- No cloud provisioning.
- No secrets management.
- No provider-specific SDK dependency.
- No branch deletion.
- No automatic PR merge.
- No background worker daemon.
- No public benchmark or superiority claim.
- No product alias/personality renaming in schema ids.

## Acceptance Bar For The First Code Wave

The first code wave is complete only when all of the following are true:

- `python3 -m depone team-launch-preflight --self-test` passes.
- A committed fixture under `docs/team-launch-preflight/` revalidates locally.
- `python3 -m depone team-launch-preflight --team-dry-run docs/team-dry-run/team-dry-run.json --out docs/team-launch-preflight/team-launch-preflight.json --json` prints `decision: pass` or an intentionally documented blocked decision.
- `python3 -m depone team-ledger --ledger docs/team-launch-preflight/team-ledger.json --json` revalidates the skeleton.
- `python3 scripts/check_contract.py --tier changed` passes.
- `python3 scripts/dwm.py doctor` passes.
- README or command reference states the honest boundary: preflight does not
  launch workers or create worktrees.

## Residual Risk

The largest remaining trust residual after preflight is launch provenance:
Depone will know a lane was launchable, but not yet that Depone actually
launched it or that the worker ran under a separate boundary. That residual is
acceptable for the first wave because the output remains blocked/non-executing.
The next wave must close that residual with a launch receipt before claiming any
native team execution.
