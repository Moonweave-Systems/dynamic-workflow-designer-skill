# V36 README Benchmark Graph Spec

Status: implemented first README benchmark graph artifact generator in
`scripts/dwm_readme_benchmark_graph.py`.

## Research and Prior Art

V35 records graph-ready benchmark metrics in `report.json.graph_metrics`. V36
turns those metrics into deterministic README-ready artifacts without manually
copying benchmark values into prose.

## Product Position and Non-Goals

V36 generates graph artifacts. It does not decide benchmark success and does not
embed the graph into README yet. The source of truth remains the V35 report.

Non-goals:

- do not recompute benchmark values from logs,
- do not publish graph values from markdown text,
- do not execute live model attempts,
- do not claim model superiority,
- do not edit README automatically.

## Workflow Architecture

`scripts/dwm_readme_benchmark_graph.py` reads a V35 report directory and writes:

- `benchmark-graph.json`,
- `benchmark-graph.svg`,
- `README-snippet.md`,
- `status.json`,
- `summary.json` for manifest suites.

The JSON and SVG are generated only from `report.json.graph_metrics`.

## Execution Model

```bash
python scripts/dwm_readme_benchmark_graph.py generate --report out/live-reports/<report_id> --out out/readme-benchmark-graphs/<graph_id>
python scripts/dwm_readme_benchmark_graph.py --manifest fixtures/v36/manifest.json --out out/readme-benchmark-graphs/v36-final
```

Every output directory is guarded by a README benchmark graph ownership
sentinel.

## Safety and Verification Gates

The gate blocks:

- `ERR_README_GRAPH_ARTIFACT_MISSING` when report artifacts are missing,
- `ERR_README_GRAPH_STALE_REPORT` when report hashes drift,
- `ERR_README_GRAPH_METRICS_INVALID` when graph metrics are missing or
  internally inconsistent.

## Evaluation Fixtures

`fixtures/v36/manifest.json` covers:

- positive: published benchmark report produces graph artifacts,
- positive: refuted report produces graph artifacts without hiding status,
- negative: stale report hash is blocked,
- negative: invalid metrics are blocked,
- negative: missing report artifact is blocked.

## Release Plan

V36 prepares the README benchmark graph pipeline. A later slice can choose a
specific generated graph artifact to promote into `assets/` and embed in README.
