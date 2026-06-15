# V8 Frontier Review Ingestion Spec

Status: first slice implemented
Date: 2026-06-15

## Purpose

V8 consumes V7.5 reviewed frontier-result evidence and turns it back into
runtime frontier state. It is the first slice where a second-loop V7.5 review can
satisfy a phase dependency.

The workflow is:

```text
V6 frontier
-> V6.5 frontier dispatch
-> V7 controlled frontier result
-> V7.5 reviewed frontier result
-> V8 ingested runtime frontier
```

V8 does not execute the next frontier packet. It only records that a reviewed
frontier phase is complete and emits the next ready packet.

## Workflow Design

Source plan: `docs/v8-frontier-review-ingestion.workflow.plan.json`.

Patterns:

- Sequential
- Resume And Cache
- Adversarial Verify

Phases:

1. Review validation: require an owned V7.5 directory that resumes to
   `review-approved`.
2. Lineage reconstruction: follow review -> V7 result -> V6.5 dispatch -> V6
   frontier -> V4/V3/V1 plan snapshot.
3. Frontier ingestion: append the reviewed frontier phase to
   `completed_phase_ids` and compute next ready phases from the original plan.
4. Resume verification: recompute source, state, packet, prompt, journal, and
   hashes.

## Command Contract

```bash
python scripts/ingest_frontier_review.py --review out/v7.5/<run_id> --out out/v8/<run_id>
python scripts/ingest_frontier_review.py --resume out/v8/<run_id>
python scripts/ingest_frontier_review.py --self-test
```

## Accepted Inputs

V8 accepts only:

- an owned V7.5 review directory,
- `status.json` with `status: review-approved`,
- clean V7.5 resume,
- `review.json` with verdict `approve`,
- a reviewed source phase that was selected by the V6 frontier,
- a recoverable V6.5 dispatch, V6 frontier, V4 schedule, and V1 plan snapshot.

V8 rejects:

- stale or malformed V7.5 review artifacts,
- `needs-human`, `changes-requested`, or `invalid` reviews,
- reviewed phases not selected by the V6 frontier,
- duplicate completion of an already completed phase,
- missing V7/V6.5/V6/V4/V3/V1 lineage,
- symlinked or outside-`out/v8` output paths.

## Output Model

```text
out/v8/<run_id>/
├── .ingest_frontier_review-owned.json
├── run.json
├── state.json
├── hashes.json
├── packets/
│   ├── 0001.<phase>.packet.json
│   └── 0001.<phase>.prompt.md
├── journal/0000.json
├── status.json
└── resume.md
```

`state.json` records:

- `completed_phase_ids`,
- `reviewed_phase_ids` preserving earlier trusted review history,
- `ready_phase_ids`,
- `selected_phase_ids`,
- `blocked_phases`,
- `reviewed_results`.

## First Slice Rules

For the dogfood result, V8 should mark `release_decision` complete and select
`human_gate` as the next frontier packet. It should not claim workflow
completion while `human_gate` remains ready. The emitted state should preserve
the earlier `evidence_review` review history and append `release_decision`.
If no phase is ready while unfinished phases remain blocked, V8 reports
`blocked` rather than `workflow-complete`.

Approve path requires:

1. V7.5 review status is `review-approved`.
2. V7.5 resume is `resumable`.
3. `review.json.verdict` is `approve`.
4. `review.json.source_phase_id` is selected by the V6 frontier.
5. The source phase is not already completed.
6. The V7 result, V6.5 dispatch, V6 frontier, V4 schedule, V3 runtime, and V1
   plan hashes still validate.
7. Generated `state.json`, packet, prompt, and journal match resume
   recomputation.

## Non-Goals

- Do not execute the next frontier packet.
- Do not call Codex CLI, OMX, subagents, network APIs, or paid APIs.
- Do not merge worker outputs into the repository.
- Do not implement arbitrary multi-result fan-in yet.
- Do not bypass `needs-human` or rejected V7.5 reviews.

## Release Criteria

The slice is `keep` only if:

- `python scripts/ingest_frontier_review.py --self-test` passes,
- dogfood ingestion over `out/v7.5/v32-semantic-dogfood` returns
  `frontier-ready`,
- clean resume returns `resume_state: resumable`,
- dogfood selected frontier is `human_gate`,
- tampered generated state invalidates resume,
- no worker execution or runtime backend execution is introduced.

## Next Slice

After V8, the next slice should dispatch the V8 `human_gate` frontier under an
explicit human-gate contract rather than pretending the workflow is complete.
