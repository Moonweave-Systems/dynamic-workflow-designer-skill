# V36 README Benchmark Graph Decision

Decision: keep

Command used to regenerate the V36 summary:

```bash
python scripts/dwm_readme_benchmark_graph.py --manifest fixtures/v36/manifest.json --out out/readme-benchmark-graphs/v36-final
```

Generated summary values:

- `suite_id`: `v36-final`
- `fixture_count`: 5
- `required_fixture_count`: 5
- `required_passed`: 5
- `passed`: 5
- `failed`: 0
- `skipped`: 0
- `decision`: `keep`

The accepted V36 suite covers `benchmark-graph.json`, `benchmark-graph.svg`,
`README-snippet.md`, `ERR_README_GRAPH_ARTIFACT_MISSING`,
`ERR_README_GRAPH_STALE_REPORT`, and `ERR_README_GRAPH_METRICS_INVALID`.

This decision covers README benchmark graph artifact generation only. It does
not claim live model execution, live Codex task superiority, Claude superiority,
OpenCode/OMO superiority, hosted evaluation, or external benchmark authority.
