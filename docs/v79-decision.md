# V79 README Graph Visibility Decision

Decision: keep

Command used:

```bash
python scripts/dwm_readme_graph_visibility.py --manifest fixtures/v79/manifest.json --out out/readme-graph-visibility/v79-final
```

Generated values:

- `suite_id`: `v79-readme-graph-visibility`
- `fixture_count`: 5
- `required_fixture_count`: 5
- `required_passed`: 5
- `passed`: 5
- `failed`: 0
- `decision`: `keep`

V79 keeps the README graph surface aligned with V78. It permits process graph
visibility when the README says it is not a public benchmark graph and does not
claim upward performance. It keeps public upward benchmark claims blocked and
does not generate graphs, edit README assets, execute queued commands, or run
adapters.
