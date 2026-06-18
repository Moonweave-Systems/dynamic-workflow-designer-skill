# V74 Decision

Decision: keep.

Command used to verify large workflow dogfood control:

```bash
python scripts/dwm_large_workflow_dogfood.py --manifest fixtures/v74/manifest.json --out out/large-workflow-dogfood/v74-final
```

Generated values:

- `suite_id`: `v74-large-workflow-dogfood`
- `fixture_count`: 3
- `required_passed`: 3
- `decision`: `keep`
- `artifacts`: `dogfood-control.json`, `dogfood-control.md`, `large-workflow-control.json`, `status.json`, `summary.json`

This decision covers applying V73 control to dogfood status, ready dogfood receipt recording, missing human gate blocking, invalidator blocking, and source hash recording. It does not execute live adapters or claim fully autonomous completion.
