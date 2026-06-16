# V27 Adapter Smoke Decision

Decision: keep

Command used to regenerate the V27 summary:

```bash
python scripts/dwm_adapter_smoke.py --manifest fixtures/v27/manifest.json --out out/adapter-smoke/v27-final
```

Generated summary values:

- `suite_id`: `v27-final`
- `fixture_count`: 5
- `required_fixture_count`: 5
- `required_passed`: 5
- `passed`: 5
- `failed`: 0
- `skipped`: 1
- `decision`: `keep`

The accepted V27 suite covers adapter smoke evidence, `adapter-smoke.json`,
`ERR_ADAPTER_SMOKE_UNAVAILABLE`, `ERR_ADAPTER_SMOKE_UNSAFE_COMMAND`,
`ERR_ADAPTER_SMOKE_UNKNOWN_TASK`, and `ERR_ADAPTER_SMOKE_STALE_TEMPLATE`.

This decision covers adapter preflight evidence only. It does not claim live
model execution, live Codex task execution, Claude execution, OpenCode/OMO
execution, hosted evaluation, or model quality superiority.
