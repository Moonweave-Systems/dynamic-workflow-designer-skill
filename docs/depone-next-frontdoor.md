# Depone Next Front Door

Slice: `depone-next-frontdoor`

`depone next` / `evidence-next` consumes an existing `depone run` artifact
directory and independently re-validates it before selecting a next safe action.
It does not execute the next action.

The decision is based on recomputed machine facts:

- `capture-manifest.json` validates with `validate_capture_manifest`.
- `runner-receipt.json`, when present, validates with `validate_runner_receipt`.
- `evidence-bundle.json` statement subjects match the capture and runner receipt.
- The DSSE envelope is re-ingested against present artifact files; the recorded
  `ingest-verdict.json` is reported but not trusted as the decision source.

Decision meanings:

- `continue`: artifacts re-validate and the next safe action is
  `run_next_evidence_slice`.
- `blocked`: one or more artifacts are missing, malformed, stale, or digest
  mismatched; the next safe action is `repair_evidence_artifacts`.

Re-validate the committed A2 runner-receipt evidence:

```bash
python3 -m depone next \
  --evidence-dir docs/depone-run-receipt-frontdoor \
  --out docs/depone-next-frontdoor/evidence-next-decision.json \
  --json
```

Observed output:

```text
decision: continue
next_action: run_next_evidence_slice
assurance: A2-isolated-observed
verified_subject_count: 4
blocking_reasons: []
```

Honest boundary: this is a verifier/selector front door, not a scheduler. It
reduces the repeated human "what next?" step by making the next action
machine-readable, but another loop or operator must still execute it.
