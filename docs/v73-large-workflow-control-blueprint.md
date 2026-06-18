# V73 Large Workflow Control Blueprint

## Objective

Make DWM able to judge whether a large task is still moving in the user's
intended direction with high quality, reasonable efficiency, recovery paths, and
real evidence.

## Surface

- `scripts/dwm_large_workflow_control.py`
- `fixtures/v73/manifest.json`
- `docs/v73-large-workflow-control-spec.md`
- `docs/v73-large-workflow-control.workflow.plan.json`
- `docs/v73-large-workflow-control-blueprint.md`
- `scripts/dwm.py`
- `scripts/check_contract.py`

## Phases

1. Define the six-axis control contract.
2. Implement deterministic scoring and blocker output.
3. Add fixtures for controlled, drift-missing, and overclaiming workflows.
4. Connect the new surface to release commands and contract terms.
5. Verify with self-test, manifest, plan validation, and full contract.

## Workers

- `control_designer`: owns axis semantics and scoring signals.
- `evaluator_builder`: owns CLI implementation and artifacts.
- `fixture_verifier`: owns fixture coverage and negative cases.
- `contract_reviewer`: owns release command and claim-limit checks.

## Handoffs

- `control-contract.md`: axis semantics and required signals.
- `control-artifacts.json`: evaluator output schema.
- `fixture-summary.json`: pass/block fixture results.
- `verification-log.md`: command evidence.

## Parallelism

Scoring design and fixture design can proceed in parallel after the axis
contract is fixed. Contract integration waits for the evaluator and fixture
schema to exist.

## Verification

- `python scripts/dwm_large_workflow_control.py --self-test`
- `python scripts/dwm_large_workflow_control.py --manifest fixtures/v73/manifest.json --out out/large-workflow-control/v73-final`
- `python scripts/evaluate_plan.py --plan docs/v73-large-workflow-control.workflow.plan.json`
- `python scripts/check_contract.py --self-test`
- `python scripts/check_contract.py`

## Risk Gates

No destructive action is required for this slice. Stop for production deploy,
network execution, dependency installation, secret access, history rewrite, or
external benchmark publication.

## Budget

One implementation slice. The evaluator must remain local, deterministic, and
fixture-backed.

## Resume Plan

Resume from the latest passing artifact: axis contract, evaluator, fixture,
contract integration, or verification.

## Execution Path

Direct Codex work. The first slice is the V73 evaluator plus fixture suite and
contract integration.
