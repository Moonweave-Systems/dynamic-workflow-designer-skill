# V100 Decision

Decision: keep.

Command used to verify the promotion evidence ledger:

```bash
python scripts/dwm_promotion_evidence.py --manifest fixtures/v100/manifest.json --out out/promotion-evidence/v100-final
```

Canonical command:

```bash
python scripts/dwm_promotion_evidence.py record --receipt out/wave-receipts/v99-canonical/wave-receipt.json --readiness out/benchmark-readiness/v97-canonical/benchmark-readiness.json --out out/promotion-evidence/v100-canonical
```

Generated suite values:

- `suite_id`: `v100-promotion-evidence`
- `fixture_count`: 4
- `required_passed`: 4
- `decision`: `keep`

The accepted suite covers internal evidence recording, promotion-ready evidence
that still requires human review, blocked V99 receipts, and public benchmark
overclaim blocking.

The V100 promotion evidence ledger does not execute commands, publish assets,
edit README graphs, or grant public benchmark publication approval.
