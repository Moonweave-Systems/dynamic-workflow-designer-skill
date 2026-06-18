# V73 Large Workflow Control Spec

Status: implemented large-workflow control-plane fitness evaluator in
`scripts/dwm_large_workflow_control.py`.

## Research and Prior Art

DWM has release timing, history, queues, dogfood receipts, review gates, and
benchmark guardrails. Those artifacts are useful, but the product north star is
larger: carry large work in the user's intended direction, decompose it well,
execute with high quality, reduce waste, recover from drift, and preserve real
evidence.

Modern agent harnesses often optimize launch, routing, or UI. DWM's stronger
position is the deterministic control-plane above those surfaces: it should make
large work inspectable, resumable, measurable, and repairable without pretending
that every task should be fully autonomous.

## Product Position and Non-Goals

V73 defines the six-axis large-workflow control contract:

1. Direction fidelity.
2. Large-work decomposition.
3. Execution quality.
4. Efficiency.
5. Recovery ability.
6. Evidence quality.

The goal is not to add another decorative gate. The goal is to prevent DWM from
optimizing only release scaffolding while missing whether a large task is still
moving toward the user's real outcome.

Non-goals:

- do not publish external benchmark superiority claims,
- do not claim fully autonomous completion,
- do not execute destructive, networked, dependency, production, secret, or
  history-rewrite actions,
- do not replace human approval at real risk gates,
- do not score typography, polish, or narrative confidence as direction
  fitness.

This spec does not claim fully autonomous completion.

## Workflow Architecture

`scripts/dwm_large_workflow_control.py` evaluates a workflow object and writes:

- `large-workflow-control.json`,
- `large-workflow-control.md`,
- `status.json`,
- manifest `summary.json`.

Each axis has required control signals:

| Axis | Required signals |
| --- | --- |
| Direction fidelity | objective, user intent trace, success criteria, drift checks |
| Large-work decomposition | phases, phase dependencies, packet sizing, parallelism |
| Execution quality | verification, review/repair loop, artifact contracts, quality gates |
| Efficiency | budget, cost tracking, automation, human gate minimization |
| Recovery ability | resume points, invalidators, repair paths, safe defaults |
| Evidence quality | receipts, source hashes, measurable metrics, claim limits |

Every axis scores `0`, `1`, or `2`. A workflow is `large-workflow-controlled`
only when every axis scores `2` and no overclaim is detected. Missing control
signals produce `large-workflow-blocked` with improvement surfaces.

## Execution Model

Assess one workflow:

```bash
python scripts/dwm_large_workflow_control.py assess --workflow workflow.json --out out/large-workflow-control/<control_id>
```

Run fixture coverage:

```bash
python scripts/dwm_large_workflow_control.py --manifest fixtures/v73/manifest.json --out out/large-workflow-control/v73-final
```

The workflow plan for this slice is
`docs/v73-large-workflow-control.workflow.plan.json`. The human-readable
blueprint is `docs/v73-large-workflow-control-blueprint.md`.

## Safety and Verification Gates

The evaluator blocks:

- missing direction fidelity signals,
- weak decomposition,
- absent review/repair or verification contracts,
- missing budget and cost tracking,
- missing resume, invalidation, repair, or safe-default controls,
- evidence without receipts, source hashes, measurable metrics, or claim limits,
- overclaims such as external benchmark superiority, guaranteed best quality,
  always autonomous, or no human gate needed.

Safe default: if a workflow is blocked, repair the missing control signals
before execution. If the blocker is a real destructive or external risk gate,
preserve artifacts and ask the user.

## Evaluation Fixtures

`fixtures/v73/manifest.json` covers:

- a fully controlled large workflow,
- a workflow missing direction drift checks,
- an overclaiming workflow.

The fixture suite proves the six-axis gate can pass real control signals and
block workflows that look busy but are directionally unsafe.

## Release Plan

V73 adds the six-axis evaluator, spec, blueprint, workflow plan, fixtures, and
release command coverage. The next implementation should use this control
output while dogfooding a real larger task, not keep adding release-only
infrastructure indefinitely.
