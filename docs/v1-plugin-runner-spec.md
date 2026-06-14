# V1 Plugin Runner Spec

Status: draft
Date: 2026-06-14

## Purpose

V0.5 proved that `dynamic-workflow-designer` can emit deterministic,
schema-valid workflow plans and that those plans can be scored through a
file-backed evaluator. V1 should close the next practical gap: turn a
`workflow.plan.json` into a small, inspectable execution packet that a Codex
agent can run phase by phase without inventing orchestration structure again.

V1 is not a full workflow runtime. It is a plugin-ready runner adapter and
artifact contract that makes the first execution slice reproducible, resumable
at file boundaries, and reviewable before any destructive action.

## Product Position

| Layer | Responsibility | V1 stance |
| --- | --- | --- |
| `workflow-router` | choose the smallest suitable workflow | unchanged |
| `dynamic-workflow-designer` | design phases, workers, gates, handoffs | source of `workflow.plan.json` |
| V1 plugin runner | materialize a plan into execution packets and status files | implement now |
| Future runtime | durable orchestration, monitoring, automatic subagent scheduling | defer |

V1 should feel closer to Claude Dynamic Workflows than V0.5 because the plan no
longer lives only as prose and JSON. It should still avoid the biggest runtime
commitments: no background daemon, no dashboard, no automatic multi-agent
scheduler, and no hidden mutation of repositories.

## Goals

- Compile one `workflow.plan.json` into a workspace containing execution
  packets, prompts, handoff schemas, risk gates, and status files.
- Let a Codex agent run the first slice from files without rereading the entire
  original conversation.
- Make resume boundaries explicit: completed packets can be skipped only when
  their inputs, plan hash, and declared invalidators still match.
- Preserve user control over risky actions through generated approval gates and
  safe defaults.
- Keep all generated execution evidence under `out/v1/` or a user-provided run
  directory; tracked source remains the plan, schema, scripts, and fixtures.
- Provide deterministic tests that prove runner behavior without live model
  execution.

## Non-Goals

- Do not automatically spawn subagents.
- Do not execute shell commands from the plan without an explicit runner command
  and risk-gate check.
- Do not implement a web viewer or persistent service.
- Do not claim that a compiled packet proves the workflow has been completed.
- Do not replace Codex's existing subagent tools; emit prompts and handoff files
  that the current environment can use.
- Do not vendor Claude Dynamic Workflow runtimes.

## User Stories

1. A user asks for a repo-wide migration workflow. The designer emits
   `workflow.plan.json`; the V1 runner compiles it into phase prompts, handoff
   templates, and a first-slice execution packet.
2. A user resumes after context loss. The runner reads `status.json`, validates
   plan and input hashes, and reports which packets can be resumed, rerun, or
   invalidated.
3. A reviewer audits a planned workflow. The runner exposes all worker prompts,
   forbidden actions, gates, and expected artifacts as files before execution.
4. A cautious user wants no mutation. The runner compiles the plan and marks all
   write, network, dependency, database, production, secret, and history actions
   as blocked until approved.

## Artifacts

Given:

```text
workflow.plan.json
```

The V1 runner writes:

```text
out/v1/<run_id>/
├── run.json
├── status.json
├── plan.snapshot.json
├── plan.sha256
├── packets/
│   ├── 001-<phase-id>.packet.json
│   └── 001-<phase-id>.prompt.md
├── handoffs/
│   └── <handoff-id>.schema.json
├── gates/
│   └── <gate-id>.approval.md
├── evidence/
│   └── README.md
└── resume.md
```

### `run.json`

Required fields:

- `run_id`
- `schema_version`
- `created_at`
- `source_plan`
- `plan_hash`
- `runner_version`
- `mode`: `compile-only`, `first-slice`, or `resume-check`
- `risk_policy`: `block-all`, `prompt`, or `approved-list`

### `status.json`

Required fields:

- `run_id`
- `plan_hash`
- `packets`: list of packet statuses
- `handoffs`: list of handoff statuses
- `gates`: list of gate statuses
- `resume_state`: `fresh`, `resumable`, `invalidated`, or `complete`
- `invalidators`: concrete reasons that force rerun

Packet statuses:

- `pending`
- `ready`
- `blocked-risk-gate`
- `running`
- `completed`
- `failed`
- `invalidated`

### Packet JSON

Each packet is derived from one phase, first slice, or worker assignment.

Required fields:

- `packet_id`
- `phase_id`
- `worker_id`
- `objective`
- `inputs`
- `allowed_tools`
- `forbidden_actions`
- `risk_gates`
- `handoff_outputs`
- `verification`
- `completion_check`
- `resume_inputs`
- `prompt_path`

### Packet Prompt

Packet prompts are generated Markdown files. They should contain:

1. Objective.
2. Exact inputs and paths.
3. Ownership boundary.
4. Allowed tools and forbidden actions.
5. Required output artifact.
6. Verification commands or falsifiers.
7. Risk gate stop conditions.
8. Handoff schema.

The prompt must not imply that the worker may ignore `forbidden_actions` because
the broader plan approved the workflow.

## Commands

V1 should add a stdlib-only script:

```bash
python scripts/compile_workflow.py --plan workflow.plan.json --out out/v1/<run_id>
```

Required modes:

```bash
python scripts/compile_workflow.py --plan workflow.plan.json --out out/v1/<run_id> --mode compile-only
python scripts/compile_workflow.py --plan workflow.plan.json --out out/v1/<run_id> --mode first-slice
python scripts/compile_workflow.py --resume out/v1/<run_id>
python scripts/compile_workflow.py --self-test
```

The script must:

- validate the plan with the existing evaluator schema path
- refuse downgrade artifacts unless `--allow-downgrade` is passed
- write a fresh output directory only under `out/v1/` by default
- reject `--out .`, repository root, or parent directories
- generate deterministic packet IDs
- compute hashes for the source plan and packet prompts
- leave status as `blocked-risk-gate` when the first slice requests risky
  actions that are not approved
- avoid shelling out except for optional validation commands explicitly invoked
  by the user

## Risk Model

The runner treats these as gated by default:

- write actions outside the run directory
- dependency install
- database migration
- production deploy
- public API change
- external network calls
- secret access
- force push, branch deletion, hard reset, history rewrite
- deletion of files or directories outside `out/v1/<run_id>`

Default behavior is `block-all`: compile packets and status, but do not execute
the packet. A future execution mode may ask the user to approve a named gate,
but V1 only needs to make gates visible and machine-checkable.

## Resume Semantics

A packet can be resumed only if all of these match:

- `plan_hash`
- packet input hashes
- declared `resume.invalidators`
- handoff schema hash
- risk gate state

If any value changes, the packet becomes `invalidated`. The runner should write
the reason to `status.json` and `resume.md` rather than trying to repair the run.

## Evaluation

Add fixtures under `fixtures/v1/` only after the compiler exists. Until then,
the spec defines the target behavior.

Minimum V1 fixture set:

- positive: activated repo-wide migration plan compiles to packets
- positive: research workflow compiles to read-only packets
- negative: downgrade artifact is refused without `--allow-downgrade`
- negative: output path outside `out/v1/` is rejected
- risk: first slice with dependency install becomes `blocked-risk-gate`
- resume: modified plan hash invalidates prior status

Each fixture should validate:

- generated file set
- deterministic packet IDs
- status transitions
- blocked risk gates
- prompt/packet agreement
- resume invalidation reasons

## Acceptance Criteria

V1 is releasable when:

- `scripts/compile_workflow.py --self-test` passes.
- Existing V0/V0.5 checks still pass.
- At least six V1 fixtures pass through the compiler.
- Generated packet prompts agree with packet JSON fields.
- Risky first slices are blocked unless explicitly approved.
- Resume checks invalidate stale plan, input, handoff, or gate state.
- README documents the compile and resume commands.
- `docs/v1-decision.md` records keep/kill based on compiler fixtures.

## Implementation Slices

1. Add `scripts/compile_workflow.py --self-test` with plan loading, output path
   safety, and deterministic hashing.
2. Generate `run.json`, `plan.snapshot.json`, `plan.sha256`, and `status.json`
   from one activated V0.5 sample plan.
3. Generate first-slice packet JSON and prompt Markdown.
4. Add risk-gate blocking for first-slice forbidden actions.
5. Add `--resume` mode that validates hashes and reports invalidators.
6. Add V1 fixtures and `docs/v1-decision.md`.
7. Update `SKILL.md` only if the compiler changes the expected output contract.

## Open Questions

- Should `compile_workflow.py` live as a standalone script forever, or become a
  plugin command once the interface stabilizes?
- Should approval state be represented as hand-edited Markdown, JSON, or both?
- Should future execution mode use Codex subagents directly, or only emit worker
  prompts for the user/agent to dispatch?
- Should V2 introduce a viewer, or is a textual `status.json` plus `resume.md`
  enough for the next measured step?
