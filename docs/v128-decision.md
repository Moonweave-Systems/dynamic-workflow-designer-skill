# V128 Decision

Status: accepted as first evidence-substrate slice with external ingest
hardening. Date: 2026-06-28.

V128 now emits Depone's existing observed capture evidence in consensus-shaped
JSON without changing the trust model.

Implemented substrate:

- in-toto Statement v1:
  - `_type`: `https://in-toto.io/Statement/v1`
  - `predicateType`: `https://depone.dev/attestations/evidence/v1`
  - subjects bind the capture manifest, source fixture, and observer capture
    SHA-256 digests.
- DSSE envelope:
  - `payloadType`: `application/vnd.in-toto+json`
  - `payload`: base64 canonical in-toto Statement JSON
  - `signatures`: `[]`
- Static OTel GenAI-shaped spans:
  - `gen_ai.operation.name: invoke_agent`
  - `gen_ai.operation.name: execute_tool`
  - `gen_ai.usage.*` is omitted unless observed.
- External ingest:
  - `depone agent-fabric-evidence-ingest`
  - accepts a bare in-toto Statement or DSSE envelope plus optional OTel spans
  - re-hashes present subject artifacts from disk via `--artifact name=path`
  - defaults to raw file-byte SHA-256 for vendor-neutral in-toto subjects
  - supports `--artifact name=path:json` for Depone-native canonical JSON hashes
  - returns `pass`, `inconclusive`, or `blocked`

Boundary:

- The DSSE envelope is unsigned and content-addressed. Empty `signatures` means
  no cryptographic signature exists.
- Non-empty DSSE `signatures` are blocked as unverifiable in V128.
- Emitting in-toto/DSSE or OTel-shaped evidence does not raise assurance.
- A3 remains deferred to a later Sigstore/Rekor signing milestone.
- External statement ingest is `blocked` on a present digest mismatch, malformed
  DSSE, wrong statement types, or unverifiable claimed signatures.
- External statement ingest is `inconclusive` when a subject artifact is absent
  from disk or there are no subjects to verify.
- Foreign predicates are accepted for subject-binding checks and reported as
  `predicate_recognized: false`; Depone does not interpret SLSA predicate
  semantics or raise assurance from them in V128.

Evidence:

- `depone agent-fabric-evidence-substrate --self-test` validates statement
  digest round-trip, unsigned DSSE decoding, OTel span shape, tamper rejection,
  and external statement mismatch handling.
- `depone agent-fabric-evidence-ingest --self-test` validates the real
  non-Depone SLSA fixture, raw-byte subject verification, Depone-native JSON
  subject verification, missing artifacts, tamper, malformed DSSE,
  unverifiable signatures, and OTel structural errors.
- A V126 governed capture can be exported to
  `out/v128-evidence-substrate/bundle.json`.
