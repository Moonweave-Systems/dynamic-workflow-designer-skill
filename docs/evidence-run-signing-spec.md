# Evidence-Run Operator-Key Signing Spec

Task id: `server-next-rung`

Slice: `evidence-run-signing`

Status: implementation-ready spec

Date: 2026-06-29

## Decision

The next Depone wave wires the existing Ed25519 DSSE signing path into
`evidence-run`. This is the smallest signing slice that improves real use:
`evidence-run` can now emit the normal unsigned content-addressed bundle for the
existing ingest path and, when explicitly configured, a separate signed evidence
bundle that can be verified with a distributed public key.

This is operator-key signing, not Sigstore keyless identity. It must not raise
A2 evidence to keyless A3 or claim transparency-log inclusion.

## Trust Model

Required facts for a signed evidence bundle:

- `--sign-private-key` and `--sign-key-id` are provided together.
- The DSSE payload is signed with the existing OpenSSL-backed Ed25519 helper.
- `signed-evidence-bundle.json` contains one DSSE signature and
  `signing_status: signed-ed25519-operator-key`.
- If `--sign-public-key` is provided, `evidence-run` verifies the signed bundle
  before returning success for the signing step.
- Independent reviewers can run `agent-fabric-verify-signature` against the
  committed signed bundle and public key.

Fail-closed cases:

- OpenSSL is unavailable.
- The private key, key id, or DSSE envelope is missing.
- The signed bundle does not verify with the supplied public key.
- A consumer tampers with the unsigned top-level statement or assurance fields
  that mirror the signed statement payload.
- A consumer tampers with the top-level operator-key signing metadata into a
  keyless or transparency-logged claim.

## Implementation Boundary

This slice:

- Adds `--sign-private-key`, `--sign-key-id`, and `--sign-public-key` to
  `evidence-run`.
- Writes `signed-evidence-bundle.json` alongside the existing unsigned
  `evidence-bundle.json`.
- Keeps the existing unsigned ingest path unchanged.
- Reuses a shared `sign_evidence_bundle(...)` helper for both `evidence-run` and
  `agent-fabric-sign`.
- Commits re-validatable machine artifacts under `docs/evidence-run-signing/`.

It deliberately does not add Python dependencies, Sigstore, Rekor, OIDC, or an
assurance-label upgrade.

## Independent Re-Validation

```bash
python3 - <<'PY'
import json
from depone.agent_fabric.capture_bridge import validate_capture_manifest
from depone.agent_fabric.sign import verify_signed_bundle
from depone.agent_fabric.isolation import verify_isolation_boundary

m = json.load(open("docs/evidence-run-signing/capture-manifest.json"))
b = json.load(open("docs/evidence-run-signing/signed-evidence-bundle.json"))
errs = validate_capture_manifest(m)
iso = m.get("isolation", {})
print("assurance        :", m.get("assurance"))
print("validate errors  :", errs)
print("boundary reverify:", verify_isolation_boundary(iso).get("boundary"))
print("signing_status   :", b.get("signing_status"))
print("signature_count  :", len(b.get("dsse_envelope", {}).get("signatures", [])))
print("signature verify :", verify_signed_bundle(b, "docs/evidence-run-signing/operator-ed25519.pub.pem"))
print("MERGE_OK:", (
    m.get("assurance") == "A2-isolated-observed"
    and errs == []
    and verify_isolation_boundary(iso).get("boundary") is True
    and b.get("signing_status") == "signed-ed25519-operator-key"
    and verify_signed_bundle(b, "docs/evidence-run-signing/operator-ed25519.pub.pem") is True
))
PY

python3 -m depone agent-fabric-verify-signature \
  --bundle docs/evidence-run-signing/signed-evidence-bundle.json \
  --public-key docs/evidence-run-signing/operator-ed25519.pub.pem
```

Expected successful output must include:

```text
MERGE_OK: True
verified: true
```

## Honest Residuals

The committed public key verifies the committed signed bundle, but it is not a
keyless identity proof and is not transparency logged. Trust is rooted in the
operator-held private key used during capture and the distributed public key.
