# V103 Decision

Decision: keep for deterministic comparison schema; live two-arm comparison pending explicit approval.

Commands used to verify the deterministic recorder:

```bash
python scripts/dwm_live_proof.py --self-test
python scripts/dwm_live_proof.py --manifest fixtures/v103/manifest.json --out out/v103/final
```

Recorded deterministic suite:

- `suite_id`: `v103-live-proof-comparison`
- `fixture_count`: 4
- `required_passed`: 4
- `decision`: `keep`

The live comparison command was not executed:

```bash
python scripts/dwm_live_proof.py compare --seed fixtures/live-proof/seed --plan fixtures/live-proof/live-proof-1.workflow.plan.json --out out/live-proofs/live-proof-2 --i-approve-live-codex
```

Until that command is explicitly approved and run, V103 proves only that the
comparison schema and deterministic fixtures distinguish the `direct-codex` and
`dwm-controlled` evidence surfaces. It makes no pass-rate, speed, cost, or
direct-agent superiority claim.
