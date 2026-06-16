# V26 Benchmark Attempt Harness Spec

Status: implemented first benchmark attempt harness in
`scripts/dwm_benchmark_attempts.py`.

## Research and Prior Art

V25 created reproducible benchmark tasks. V26 adds the missing attempt layer:
each task now has a controlled adapter attempt, file-change ledger, and verifier
result. This makes later Codex, Claude, OpenCode, or OMO runs comparable to the
same artifact contract instead of to chat summaries.

## Product Position and Non-Goals

V26 uses the deterministic `scripted-fixture` adapter. It is a schema and
evidence slice, not a live model benchmark.

Non-goals:

- do not claim live model execution,
- do not run Codex, Claude, OpenCode, or OMO,
- do not execute arbitrary task commands,
- do not write outside `out/benchmark-attempts/`,
- do not treat scripted fixture success as model quality evidence.

## Workflow Architecture

`packaging/dwm-benchmark-attempts.json` defines the `scripted-fixture` attempt
plan. `scripts/dwm_benchmark_attempts.py` materializes the V25 task suite, then
applies deterministic changes and writes per-task artifacts:

- `attempt.json`,
- `changes.json`,
- `verification.json`.

The suite also writes:

- `status.json`,
- `ledger.json`,
- `summary.json` for manifest runs.

## Execution Model

```bash
python scripts/dwm_benchmark_attempts.py attempt --out out/benchmark-attempts/<suite_id>
python scripts/dwm_benchmark_attempts.py verify --out out/benchmark-attempts/<suite_id>
python scripts/dwm_benchmark_attempts.py --manifest fixtures/v26/manifest.json --out out/benchmark-attempts/v26-final
```

Every output directory is guarded by a benchmark-attempt ownership sentinel.

## Safety and Verification Gates

The gate blocks:

- `ERR_BENCHMARK_ATTEMPTS_MISSING_TASKS` when required materialized task or
  ledger artifacts are absent,
- `ERR_BENCHMARK_ATTEMPTS_STALE_PLAN` when the attempt plan no longer matches
  the workspace or expected hash,
- `ERR_BENCHMARK_ATTEMPTS_UNSAFE_PATH` when an attempt change uses an unsafe
  path.

## Evaluation Fixtures

`fixtures/v26/manifest.json` covers:

- positive: `scripted-fixture` solves all six tasks,
- positive: attempt ledger verification sees all six task artifacts,
- negative: missing task suite is blocked,
- negative: stale attempt plan is blocked,
- negative: unsafe attempt path is blocked.

## Release Plan

V26 is the final deterministic bridge before optional live adapter attempts. A
future live Codex or Claude run should produce the same artifact names and
status semantics, then be scored by a separate benchmark ingestion gate.
