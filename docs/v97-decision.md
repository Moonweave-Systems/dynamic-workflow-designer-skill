# V97 Decision

Decision: keep.

Command:

```bash
python scripts/dwm_benchmark_readiness.py --manifest fixtures/v97/manifest.json --out out/benchmark-readiness/v97-final
```

Expected summary:

- `suite_id`: `v97-benchmark-readiness`
- `fixture_count`: 4
- `required_passed`: 4
- `decision`: `keep`

The canonical assess command is:

```bash
python scripts/dwm_benchmark_readiness.py assess --ladder out/metric-ladders/v96-canonical/metric-ladder.json --out out/benchmark-readiness/v97-canonical
```

The readiness report records a real internal operator-readiness indicator while
keeping public benchmark claims gated. Public benchmark claims require promotion
evidence, and the readiness score is not a public benchmark graph.

Public benchmark claims require promotion evidence before README publication.
