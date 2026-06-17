# V59 Dogfood Chart Candidate Spec

Status: implemented first local dogfood chart candidate gate in
`scripts/dwm_dogfood_chart_candidate.py`.

## Research and Prior Art

V58 records a graph-readiness gate for dogfood comparison pair series. V59
keeps the next step honest: it creates local chart data only when the source
series is graph-ready, but it still does not publish a README graph.

## Product Position and Non-Goals

V59 is a local chart candidate layer. It turns a trusted pair series into data
that can be reviewed before rendering or promotion.

Non-goals:

- do not render a public graph,
- do not publish README benchmark graphs,
- do not claim direct-agent superiority,
- do not accept blocked graph readiness,
- do not accept stale `pair-series.json` or `graph-readiness.json`,
- do not treat `public_readme_ready` as true.

## Workflow Architecture

The command is:

```bash
python scripts/dwm_dogfood_chart_candidate.py candidate --series out/dogfood-pair-series/<series_id> --out out/dogfood-chart-candidates/<chart_id>
```

It reads `pair-series.json`, `status.json`, and `graph-readiness.json`.

It writes:

- `chart-candidate.json`,
- `chart-candidate.md`,
- `chart-data.csv`,
- `status.json`.

## Execution Model

The command never runs Codex, Claude, OpenCode, or external benchmark tools. It
only transforms existing V58 artifacts into reviewable local chart rows.

## Safety and Verification Gates

The gate blocks:

- `ERR_DOGFOOD_CHART_CANDIDATE_NOT_READY` when graph readiness is false,
- `ERR_DOGFOOD_CHART_CANDIDATE_STALE_SERIES` when series artifacts drift,
- `ERR_DOGFOOD_CHART_CANDIDATE_OVERCLAIM` when a series claims public graph
  readiness,
- `ERR_DOGFOOD_CHART_CANDIDATE_SERIES_MISSING` when source artifacts are
  missing.

## Evaluation Fixtures

`fixtures/v59/manifest.json` covers:

- positive: graph-ready series records a chart candidate,
- negative: not-ready series is blocked,
- negative: stale series is blocked,
- negative: overclaiming series is blocked.

## Release Plan

V59 produces the local review data that a future rendering slice can consume.
README graph promotion remains blocked until a separate review and promotion
gate accepts the candidate.
