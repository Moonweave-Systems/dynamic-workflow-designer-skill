# V74 Large Workflow Dogfood Spec

Status: implemented V73 control receipt over real DWM dogfood state in
`scripts/dwm_large_workflow_dogfood.py`.

## Research and Prior Art

V73 defined the six-axis control contract for large work: direction fidelity,
large-work decomposition, execution quality, efficiency, recovery ability, and
evidence quality. A contract is not enough by itself. DWM must apply that
contract to actual dogfood state so the product keeps moving toward useful
large-work execution rather than only building release scaffolding.

The existing canonical dogfood run, `out/v9/v32-semantic-dogfood`, already
contains workflow completion, human gate approval, reviewed phases, snapshots,
and resumable status. V74 turns that state into a V73-assessed control receipt.

## Product Position and Non-Goals

V74 makes V73 operational on dogfood evidence. It proves that the six-axis
large-work control evaluator can consume a real DWM run status and produce a
receipt.

Non-goals:

- do not execute live adapters,
- do not publish external benchmark superiority,
- do not claim fully autonomous completion,
- do not bypass missing human gates,
- do not hide invalidators or stale evidence.

This spec does not claim fully autonomous completion.

## Workflow Architecture

`scripts/dwm_large_workflow_dogfood.py` reads a dogfood `status.json`, derives a
workflow object, runs the V73 evaluator, and writes:

- `dogfood-control.json`,
- `dogfood-control.md`,
- `large-workflow-control.json`,
- `status.json`,
- manifest `summary.json`.

The receipt keeps both layers visible: dogfood-specific blockers and the V73
control assessment.

## Execution Model

Record the canonical dogfood control receipt:

```bash
python scripts/dwm_large_workflow_dogfood.py record --run out/v9/v32-semantic-dogfood --out out/large-workflow-dogfood/<dogfood_id>
```

Run fixture coverage:

```bash
python scripts/dwm_large_workflow_dogfood.py --manifest fixtures/v74/manifest.json --out out/large-workflow-dogfood/v74-final
```

## Safety and Verification Gates

The receipt blocks if:

- dogfood status is not `workflow-complete`,
- resume state is not `resumable`,
- invalidators are present,
- `human_gate` approval is missing,
- source snapshots are missing,
- V73 returns `large-workflow-blocked`.

Safe default: stop before continuing and repair the dogfood evidence or request
human approval at the real gate.

## Evaluation Fixtures

`fixtures/v74/manifest.json` covers:

- ready dogfood control receipt,
- missing human gate blocking,
- invalidated dogfood blocking.

## Release Plan

V74 adds dogfood control receipt generation to the release command corpus. The
next useful step is to use these receipts while selecting and executing the next
real large workflow slice.
