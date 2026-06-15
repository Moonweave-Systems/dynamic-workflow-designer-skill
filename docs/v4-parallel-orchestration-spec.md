# V4 Parallel Orchestration Spec

Status: first slice implemented
Date: 2026-06-15

## Purpose

V4 starts parallel orchestration without opening arbitrary worker execution.
It consumes a trusted V3 runtime state and emits deterministic packets for all
currently ready phases whose dependencies are satisfied.

The goal is scheduling, not doing the work. A V4 packet is a reviewed handoff
candidate that can later enter the existing V2/V2.5 execution and review path.

## Product Position

V1 compiles the first safe packet. V2 executes one trusted packet. V2.5 reviews
that execution. V3 advances the workflow after reviewed evidence. V4 plans the
parallel frontier after V3, so independent phases can be prepared together
without losing reviewability.

V4 does not replace OMX, Codex CLI, workmux, or a future runtime. It produces
bounded packets those systems may later consume through adapters.

## Non-Goals

- Do not execute workers.
- Do not spawn subagents.
- Do not create, merge, or modify git worktrees.
- Do not run shell commands from workflow plans.
- Do not commit, push, install dependencies, deploy, access secrets, send
  external messages, delete files, rewrite history, or call paid APIs.
- Do not mark a workflow complete.

## Command Contract

```bash
python scripts/orchestrate_workflow.py --start out/v3/<run_id> --out out/v4/<run_id>
python scripts/orchestrate_workflow.py --resume out/v4/<run_id>
python scripts/orchestrate_workflow.py --self-test
```

`--start` accepts only trusted V3 runtime output with `status: advanced`.
`--resume` recomputes the schedule, packet, prompt, and journal hashes and
writes only `status.json` and `resume.md`.

## Output Model

Accepted V4 start writes:

```text
out/v4/<run_id>/
├── .orchestrate_workflow-owned.json
├── run.json
├── schedule.json
├── packets/
│   ├── 0001.<phase>.packet.json
│   └── 0001.<phase>.prompt.md
├── journal/
│   └── 0000.json
├── status.json
└── resume.md
```

`schedule.json` contains:

- completed phase IDs from the V3 packet,
- all ready phase IDs whose dependencies are satisfied,
- selected phase IDs after applying the plan concurrency cap,
- blocked phase IDs and unmet dependency IDs,
- source hashes for the V3 status, V3 next packet, and V1 plan snapshot.

## Scheduling Rules

1. Read `out/v3/<run_id>/status.json` and require `status: advanced`.
2. Read the V3 next packet and require a non-empty `completed_phase_ids` list.
3. Read the V1 plan snapshot referenced by V3 status.
4. A phase is ready when:
   - it is not already completed,
   - every `depends_on` phase is completed,
   - it has at least one worker ID.
5. Sort ready phases by their order in the plan.
6. Select up to `parallelism.concurrency_cap`; default to 1 if missing or
   malformed.
7. Emit one packet and prompt per selected phase.
8. If no phase is ready, return `blocked` with an explicit invalidator instead
   of guessing.

## Packet Contract

Each V4 packet contains:

- `packet_id`,
- `phase_id`,
- `phase_name`,
- `objective`,
- `entry_criteria`,
- `exit_criteria`,
- `expected_outputs`,
- `worker_ids`,
- resolved worker definitions,
- `handoff_inputs` from incoming handoff schemas,
- `stop_conditions`,
- `source_hashes`.

Packets are preparation artifacts only. They must include a stop condition that
forbids execution inside V4.

## Safety And Verification

V4 is safe by construction because it only reads trusted V3/V1 artifacts and
writes owned V4 artifacts. It must reject:

- non-owned V3 runtime directories,
- stale V3 status,
- tampered V3 next packets,
- malformed plans or phases,
- unknown worker IDs,
- unsafe output paths,
- symlinked output paths,
- resume against non-owned V4 directories.

## Fixtures

The first slice must cover:

- one ready phase after a linear V3 run,
- two ready phases after a fan-out plan with concurrency cap 2,
- concurrency cap limiting selected packets,
- no-ready-phase blocked status,
- unknown worker rejection,
- clean resume,
- tampered schedule invalidation,
- non-owned output rejection.

## Release Decision

V4 first slice is `keep` only if:

- self-test passes,
- V4 dogfood over `out/v3/v32-semantic-dogfood` emits `evidence_review`,
- generated packets contain workers, expected outputs, and stop conditions,
- resume is hash-bound and detects tampering,
- no worker execution or side effects are introduced.
