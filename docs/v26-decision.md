# V26 Benchmark Attempt Harness Decision

Decision: keep

Command used to regenerate the V26 summary:

```bash
python scripts/dwm_benchmark_attempts.py --manifest fixtures/v26/manifest.json --out out/benchmark-attempts/v26-final
```

Generated summary values:

- `suite_id`: `v26-final`
- `fixture_count`: 5
- `required_fixture_count`: 5
- `required_passed`: 5
- `passed`: 5
- `failed`: 0
- `skipped`: 0
- `decision`: `keep`

The accepted V26 suite covers the `scripted-fixture` adapter, `attempt.json`,
`changes.json`, `verification.json`, `ERR_BENCHMARK_ATTEMPTS_MISSING_TASKS`,
`ERR_BENCHMARK_ATTEMPTS_STALE_PLAN`, and
`ERR_BENCHMARK_ATTEMPTS_UNSAFE_PATH`.

This decision covers deterministic benchmark attempt evidence only. It does not
claim live model execution, live Codex task execution, Claude execution,
OpenCode/OMO execution, hosted evaluation, or model quality superiority.
