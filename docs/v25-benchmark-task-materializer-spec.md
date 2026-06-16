# V25 Benchmark Task Materializer Spec

Status: implemented first benchmark task materializer in
`scripts/dwm_benchmark_tasks.py`.

## Research and Prior Art

V23 defined the benchmark scoring corpus and V24 captured local evidence over
that corpus. The next missing layer is an executable task substrate: before DWM
can compare direct Codex, DWM-over-Codex, Claude, OpenCode, or OMO, every task
must materialize into a deterministic workspace with verifier evidence.

## Product Position and Non-Goals

V25 creates task workspaces. It does not solve those tasks and does not invoke
live model adapters. The expected initial state is `needs-solution`; a clean
V25 run proves that the challenge is reproducible, not that an agent completed
it.

Non-goals:

- do not claim task solving,
- do not run live Codex, Claude, OpenCode, or OMO,
- do not execute arbitrary task-provided commands,
- do not allow absolute paths or parent traversal in task files,
- do not let generated task workspaces become source truth.

## Workflow Architecture

`packaging/dwm-benchmark-tasks.json` is the source template registry. It must
match the V23 corpus task order:

- `failing-test-fix`,
- `small-refactor`,
- `auth-permission-audit`,
- `ui-render-regression`,
- `docs-code-consistency`,
- `multi-file-migration`.

`scripts/dwm_benchmark_tasks.py` materializes each task under
`out/benchmark-tasks/` with:

- `prompt.md`,
- `task.json`,
- `verifier.json`,
- `initial-verification.json`,
- `workspace/` files.

## Execution Model

```bash
python scripts/dwm_benchmark_tasks.py materialize --out out/benchmark-tasks/<suite_id>
python scripts/dwm_benchmark_tasks.py verify --out out/benchmark-tasks/<suite_id>
python scripts/dwm_benchmark_tasks.py --manifest fixtures/v25/manifest.json --out out/benchmark-tasks/v25-final
```

Every output directory is guarded by a benchmark-task ownership sentinel.

## Safety and Verification Gates

The gate blocks:

- `ERR_BENCHMARK_TASKS_CORPUS_MISMATCH` when task templates drift from the V23
  corpus,
- `ERR_BENCHMARK_TASKS_UNSAFE_PATH` when a template tries absolute or parent
  traversal paths,
- `ERR_BENCHMARK_TASKS_STALE_TEMPLATE` when expected template hashes no longer
  match.

## Evaluation Fixtures

`fixtures/v25/manifest.json` covers:

- positive: materialize the full task suite,
- positive: verify the initial `needs-solution` task state,
- negative: corpus mismatch is blocked,
- negative: unsafe file path is blocked,
- negative: stale template hash is blocked.

## Release Plan

V25 is the task substrate for future live harness runs. Later versions can add
adapter-driven attempts only if they keep the same template hashes, safe path
rules, generated workspace boundary, and initial verifier evidence.
