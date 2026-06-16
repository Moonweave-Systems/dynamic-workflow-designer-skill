# V29 Live Runner Preflight Spec

Status: implemented first live runner preflight gate in
`scripts/dwm_live_runner_preflight.py`.

## Research and Prior Art

V28 creates a command plan but intentionally does not run it. V29 verifies that
the command plan is fresh, manual-only, and complete enough for a human to run
later.

## Product Position and Non-Goals

V29 is a runner preflight gate. It does not execute adapters. It converts
planned command artifacts into `ready-for-human-run`, `skipped`, or `blocked`
evidence.

Non-goals:

- do not execute live model attempts,
- do not claim live Codex task execution,
- do not bypass human approval,
- do not accept stale command-plan hashes,
- do not treat `ready-for-human-run` as benchmark success.

## Workflow Architecture

`scripts/dwm_live_runner_preflight.py` reads a V28 plan directory and writes:

- `preflight.json`,
- `status.json`,
- `summary.json` for manifest suites.

The preflight requires `command-plan.json`, `status.json`, a planned status,
and the V28 `planned-only; do not execute in V28` execution policy.

## Execution Model

```bash
python scripts/dwm_live_runner_preflight.py preflight --plan out/live-attempt-plans/<plan_id> --out out/live-runner-preflight/<preflight_id>
python scripts/dwm_live_runner_preflight.py --manifest fixtures/v29/manifest.json --out out/live-runner-preflight/v29-final
```

Every output directory is guarded by a live-runner-preflight ownership sentinel.

## Safety and Verification Gates

The gate blocks or skips:

- `ERR_LIVE_RUNNER_PLAN_SKIPPED` when the upstream command plan was skipped,
- `ERR_LIVE_RUNNER_STALE_PLAN` when the expected command-plan hash does not
  match,
- `ERR_LIVE_RUNNER_POLICY_BLOCKED` when execution policy is not manual-safe,
- `ERR_LIVE_RUNNER_ARTIFACT_MISSING` when required V28 artifacts are absent.

## Evaluation Fixtures

`fixtures/v29/manifest.json` covers:

- positive: a captured V28 plan becomes `ready-for-human-run`,
- skip: a skipped V28 plan stays skipped,
- negative: stale command plan is blocked,
- negative: unsafe execution policy is blocked,
- negative: missing plan artifact is blocked.

## Release Plan

V29 is still pre-execution. The next slice can add an explicitly gated,
isolated runner that consumes only `ready-for-human-run` artifacts and records
actual execution evidence separately.
