# V62 Dogfood Operator Spec

Status: implemented first deterministic dogfood acquisition recommendation loop in
`scripts/dwm_dogfood_operator.py`.

## Research and Prior Art

V56 through V61 built local measurement, direct receipt pairing, series, chart
candidate, review, and one-command acquisition. V62 adds the missing operator
decision: given the current pair and acquisition artifacts, choose the next
safe dogfood action without running live Codex or fabricating receipts.

## Product Position and Non-Goals

V62 is an acquisition recommender. It tells the operator whether to start a new
acquisition, fill an existing direct receipt template, or review existing series
evidence.

Non-goals:

- do not run live Codex,
- do not create direct receipts,
- do not create README benchmark graphs,
- do not ignore stale pair or acquisition artifacts,
- do not claim public benchmark readiness.

## Workflow Architecture

The command is:

```bash
python scripts/dwm_dogfood_operator.py recommend --out out/dogfood-operator/<operator_id>
```

It reads:

- `out/dogfood-pairs/**/comparison-pair.json`,
- matching `pair-status.json`,
- `out/dogfood-acquisitions/**/acquisition.json`,
- matching `status.json`,
- the default dogfood task corpus.

It writes:

- `dogfood-operator.json`,
- `dogfood-operator.md`,
- `status.json`.

## Execution Model

The operator first checks existing completed comparison pairs. If a
`waiting-direct-receipt` acquisition exists, it returns
`fill-existing-direct-receipt` instead of starting more work. If enough pairs
already exist, it returns `review-existing-series-before-more-acquisition`.
Otherwise it returns an executable V61 acquisition command for the next missing
task.

## Safety and Verification Gates

The gate blocks:

- `ERR_DOGFOOD_OPERATOR_STALE_PAIR` when pair artifact and status differ,
- `ERR_DOGFOOD_OPERATOR_STALE_ACQUISITION` when acquisition artifact and status
  differ,
- `ERR_DOGFOOD_OPERATOR_DIRECT_RECEIPT_REQUIRED` as a recommendation block when
  a waiting acquisition already exists,
- unsafe output, pair root, acquisition root, traversal, and symlink paths.

## Evaluation Fixtures

`fixtures/v62/manifest.json` covers:

- positive: no existing evidence recommends a V61 acquisition command,
- positive: existing waiting acquisition recommends filling the receipt,
- positive: enough completed pairs recommends series review,
- negative: stale pair artifact is blocked,
- negative: stale acquisition artifact is blocked.

## Release Plan

V62 turns dogfood collection into an operator loop: ask for the next step,
execute the recommended acquisition command, fill the direct receipt when
human-gated evidence exists, then ask again.
