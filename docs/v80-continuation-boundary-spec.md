# V80 Continuation Boundary Spec

Status: implemented continuation boundary gate in
`scripts/dwm_continuation_boundary.py`.

V80 answers how far DWM can continue without asking the user again. The answer
is source-only control-plane work through V83. DWM must stop before queued
command execution, live adapter execution, destructive or external actions, and
public upward benchmark promotion.

Rule phrase: must stop before queued command execution.

## Inputs

The canonical boundary consumes:

- `out/large-workflow-queue-preflight/v77-canonical/queue-preflight.json`;
- `out/graph-timing/v78-canonical/graph-timing.json`;
- `out/readme-graph-visibility/v79-canonical/readme-graph-visibility.json`.

## Outputs

The gate writes `continuation-boundary.json`, `continuation-boundary.md`,
`status.json`, and manifest `summary.json` under `out/continuation-boundaries/`.

## Policy

The safe batchable slices are V80 continuation boundary, V81 multi-slice batch
planner, V82 execution receipt schema preflight, and V83 runner receipt dry-run
gate. V84 is the first human gate because it can cross into actual queued
command execution or live adapter execution.

Hard-stop risks include write, delete, network, deploy, secret, dependency,
database, external-message, and history-rewrite actions.

## Release Commands

```bash
python scripts/dwm_continuation_boundary.py --self-test
python scripts/dwm_continuation_boundary.py --manifest fixtures/v80/manifest.json --out out/continuation-boundaries/v80-final
python scripts/dwm_continuation_boundary.py assess --preflight out/large-workflow-queue-preflight/v77-canonical/queue-preflight.json --timing out/graph-timing/v78-canonical/graph-timing.json --visibility out/readme-graph-visibility/v79-canonical/readme-graph-visibility.json --out out/continuation-boundaries/v80-canonical
```
