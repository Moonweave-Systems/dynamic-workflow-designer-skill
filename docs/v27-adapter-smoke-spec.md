# V27 Adapter Smoke Spec

Status: implemented first adapter smoke evidence in
`scripts/dwm_adapter_smoke.py`.

## Research and Prior Art

V26 proved deterministic attempt ledgers. V27 checks whether an external
adapter command can be bound to a benchmark task without yet executing a live
model attempt.

## Product Position and Non-Goals

V27 is an adapter smoke gate. It records command availability, version evidence,
task binding, and skipped status for missing adapters. It does not ask Codex,
Claude, OpenCode, OMO, or any model to solve a task.

Non-goals:

- do not claim live model execution,
- do not send benchmark prompts to an adapter,
- do not require Codex to be installed,
- do not auto-install or authenticate adapters,
- do not accept shell fragments as adapter commands.

## Workflow Architecture

`scripts/dwm_adapter_smoke.py` binds one benchmark task prompt to one adapter
command and writes:

- `adapter-smoke.json`,
- `status.json`,
- `summary.json` for manifest runs.

The smoke command only checks `--version`. Missing adapters produce structured
`skipped` evidence.

## Execution Model

```bash
python scripts/dwm_adapter_smoke.py smoke --adapter-command codex --task-id failing-test-fix --out out/adapter-smoke/<smoke_id>
python scripts/dwm_adapter_smoke.py --manifest fixtures/v27/manifest.json --out out/adapter-smoke/v27-final
```

Every output directory is guarded by an adapter-smoke ownership sentinel.

## Safety and Verification Gates

The gate blocks or skips:

- `ERR_ADAPTER_SMOKE_UNAVAILABLE` when an adapter command is absent or fails
  version probing,
- `ERR_ADAPTER_SMOKE_UNSAFE_COMMAND` when the command is not a bare executable
  name,
- `ERR_ADAPTER_SMOKE_UNKNOWN_TASK` when a task is not part of the benchmark
  corpus,
- `ERR_ADAPTER_SMOKE_STALE_TEMPLATE` when the expected template hash no longer
  matches.

## Evaluation Fixtures

`fixtures/v27/manifest.json` covers:

- positive: local adapter smoke is captured,
- skip: missing optional adapter is recorded,
- negative: unsafe command is blocked,
- negative: unknown task is blocked,
- negative: stale template hash is blocked.

## Release Plan

V27 is the safe preflight for live adapter attempts. V28 can use this evidence
to decide whether to run a real Codex task attempt or record a deterministic
skip.
