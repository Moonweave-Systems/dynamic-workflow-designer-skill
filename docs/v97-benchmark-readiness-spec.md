# V97 Benchmark Readiness Spec

Status: implemented benchmark readiness report.

V97 adds `scripts/dwm_benchmark_readiness.py`, a source-only report that turns
the V96 metric ladder into explicit benchmark publication readiness. It keeps
three states separate:

- process progress is measurable;
- operator readiness is measurable;
- public benchmark claims require promotion evidence.

The tool writes `benchmark-readiness.json`, `benchmark-readiness.md`, and
`status.json` under `out/benchmark-readiness/<report_id>`.

## Command

```bash
python scripts/dwm_benchmark_readiness.py --manifest fixtures/v97/manifest.json --out out/benchmark-readiness/v97-final
python scripts/dwm_benchmark_readiness.py assess --ladder out/metric-ladders/v96-canonical/metric-ladder.json --out out/benchmark-readiness/v97-canonical
```

## Claim Policy

The readiness report records:

- `readiness_score_is_public_benchmark: false`
- `requires_promotion_for_public_graph: true`
- `requires_human_review_for_readme_publication: true`

The readiness score is an internal operator indicator. It is not a public
benchmark graph, not an upward trend claim, and not README publication approval.
Public benchmark claims require promotion evidence from the benchmark promotion
pipeline plus human review before tracked README assets change.

In short: the V97 readiness report is not a public benchmark graph.

## Blocking Rules

V97 blocks when:

- the input was not produced by `dwm_metric_ladder.py`;
- the metric ladder decision is not `metric_ladder_ready`;
- the metric ladder lacks public benchmark promotion policy;
- process progress or operator readiness is not ready.

Missing public benchmark promotion evidence is recorded as a blocker for public
publication, but does not block the internal readiness report when process and
operator readiness are both valid.

## Fixtures

`fixtures/v97/manifest.json` covers:

- operator-ready but public-benchmark-blocked readiness;
- public-promotion-ready readiness;
- blocked ladder input;
- missing promotion policy.

## Contract

V97 adds benchmark readiness reporting to the changed-surface contract tier and
the product doctor command corpus. It does not execute queued commands, create
worktrees, call live adapters, use the network, or publish benchmark claims.
