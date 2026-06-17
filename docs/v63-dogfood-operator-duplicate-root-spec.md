# V63 Dogfood Operator Duplicate Root Spec

Status: implemented duplicate pair-root blocking in
`scripts/dwm_dogfood_operator.py`.

## Research and Prior Art

V61 acquisition can create new pairs in the default pair root, and older local
experiments may already contain a pair for the same task. V58 correctly blocks
graph-ready series when duplicate task pairs exist. V62 initially counted unique
task ids and could therefore recommend series review before the pair root was
actually graph-ready.

## Product Position and Non-Goals

V63 keeps the operator honest by aligning its recommendation with the V58 series
contract. It does not delete pairs, choose winners, or rewrite generated
evidence.

Non-goals:

- do not delete duplicate pairs,
- do not run live Codex,
- do not create direct receipts,
- do not promote README benchmark graphs,
- do not treat duplicate task pairs as graph-ready.

## Workflow Architecture

The command remains:

```bash
python scripts/dwm_dogfood_operator.py recommend --out out/dogfood-operator/<operator_id>
```

When duplicate task pairs are present and enough unique tasks exist, the
recommendation becomes `resolve-duplicate-pair-root` with
`ERR_DOGFOOD_OPERATOR_DUPLICATE_TASK`.

## Execution Model

The operator scans immediate pair-root children, records `duplicate_task_ids`,
and blocks graph-ready recommendation until the operator chooses one pair per
task or supplies a clean pair root.

## Safety and Verification Gates

The gate blocks:

- `ERR_DOGFOOD_OPERATOR_DUPLICATE_TASK` when the pair root would make V58 series
  graph readiness fail,
- stale pair artifacts,
- stale acquisition artifacts,
- waiting direct receipts.

## Evaluation Fixtures

`fixtures/v63/manifest.json` covers all V62 cases plus a duplicate pair-root
case where three unique task ids exist but one task has two pairs.

## Release Plan

V63 is a correctness hardening slice for the V62 operator. The next useful step
is a small clean-root or pair-selection command, not public graph promotion.
