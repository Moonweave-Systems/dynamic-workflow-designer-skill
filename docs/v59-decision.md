# V59 Decision

Decision: keep.

Command used to verify the local dogfood chart candidate gate:

```bash
python scripts/dwm_dogfood_chart_candidate.py --manifest fixtures/v59/manifest.json --out out/dogfood-chart-candidates/v59-final
```

The accepted suite covers `chart-candidate.json`, `chart-candidate.md`,
`chart-data.csv`, not-ready series blocking, stale series blocking, and
overclaim blocking.

This decision does not claim README graph promotion, public benchmark graph
rendering, external benchmark authority, direct-agent superiority, or generated
`out/` directories as source truth.
