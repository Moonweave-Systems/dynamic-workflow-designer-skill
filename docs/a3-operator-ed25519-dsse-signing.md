# A3 Step 2b: Operator-Key Ed25519 DSSE Signing

`depone agent-fabric-sign` signs an existing V128 evidence bundle's DSSE
envelope with an operator-held Ed25519 private key through the `openssl` CLI.
No Python crypto package is used; `openssl` is an external binary invoked with
`subprocess`, like the existing `git` integrations.

This is a real asymmetric DSSE signature. It is publicly verifiable by anyone
who trusts and holds the corresponding public key:

```bash
python -m depone agent-fabric-sign \
  --bundle evidence-substrate-bundle.json \
  --private-key operator-ed25519.pem \
  --key-id operator-key-2026-06 \
  --out signed-evidence-substrate-bundle.json

python -m depone agent-fabric-verify-signature \
  --bundle signed-evidence-substrate-bundle.json \
  --public-key operator-ed25519.pub.pem
```

The default V128 emit path remains unsigned with `signatures: []`; signing is an
explicit opt-in step. Trust is rooted in the operator key and how its public key
is distributed. This is not Fulcio keyless identity, not Rekor transparency-log
inclusion, and not Sigstore keyless A3. The private key must be held outside the
runner's reach, with the same custody concern as observer HMAC seals.

Signing does not prove direct-agent superiority, does not turn n=1 into a
benchmark, and does not by itself raise assurance to keyless A3.
