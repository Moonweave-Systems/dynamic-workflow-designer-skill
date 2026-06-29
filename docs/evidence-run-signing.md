# Evidence-Run Operator-Key Signing

Task id: `server-next-rung`

Slice: `evidence-run-signing`

Date: 2026-06-29

## Summary

Depone produced an `A2-isolated-observed` evidence-run capture and emitted a
separate signed DSSE evidence bundle from the same run. The machine artifacts
are committed under `docs/evidence-run-signing/`:

- `capture-manifest.json`
- `evidence-run-summary.json`
- `observer-capture.json`
- `signed-evidence-bundle.json`
- `operator-ed25519.pub.pem`

The private key used for capture was generated outside the repo and is not
committed. The public key verifies the committed signed bundle, and
`evidence-ingest` can verify the signed bundle against the committed subject
artifacts.

Re-validate with the commands in `docs/evidence-run-signing-spec.md`.

## Honest Residuals

This is operator-key Ed25519 DSSE signing. It is not Sigstore keyless identity,
not Rekor transparency logging, and not a new assurance-label upgrade.
