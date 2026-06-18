# V81 Multi-Slice Batch Spec

Status: implemented multi-slice batch planner in
`scripts/dwm_multi_slice_batch.py`.

V81 consumes the V80 continuation boundary and emits a batch plan for the next
safe slices. It does not execute commands. It is a plan-only bridge that lets
DWM proceed through several source-only slices while preserving the V84 human
gate before actual queued command execution.

Rule phrase: V84 human gate.

## Inputs

The canonical planner consumes
`out/continuation-boundaries/v80-canonical/continuation-boundary.json`.

## Outputs

The planner writes `multi-slice-batch.json`, `multi-slice-batch.md`,
`status.json`, and manifest `summary.json` under `out/multi-slice-batches/`.

## Policy

The batch may include V81, V82, and V83 commands only when V80 says
`continue_source_control_plane` and `can_continue_without_human: true`.

The batch blocks if the boundary is blocked, if a human gate is required, if a
slice has no registered safe command, or if a command contains forbidden terms
such as `git push`, `rm`, `curl`, dependency install, deploy, secret, or
network.

## Release Commands

```bash
python scripts/dwm_multi_slice_batch.py --self-test
python scripts/dwm_multi_slice_batch.py --manifest fixtures/v81/manifest.json --out out/multi-slice-batches/v81-final
python scripts/dwm_multi_slice_batch.py plan --boundary out/continuation-boundaries/v80-canonical/continuation-boundary.json --out out/multi-slice-batches/v81-canonical
```
