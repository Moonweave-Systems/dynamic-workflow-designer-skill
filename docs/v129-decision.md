# V129 Decision

Status: accepted as an append-only capture-chain integrity slice. Date: 2026-06-29.

V129 makes an omitted, reordered, or tampered intermediate capture detectable
instead of silent. It adds a content-addressed chain link across capture
manifests and a whole-chain verifier, without changing the trust model.

## Why

A non-executing verifier inherits the trust level of its capture layer. Through
V128 each capture manifest was hash-bound on its own, but nothing linked one
capture to the next: a multi-step run could drop or reorder an intermediate
capture and no check would break. The 2026 consensus for handing a decision
trail to a human is "append, do not overwrite, so the human sees the full trail";
the load-bearing property is that an omission is *detectable*. V129 supplies that
property in software, which is the part not blocked by this environment (unlike
A2 privilege isolation and A3 signing).

## Implemented

- Chain link on the capture manifest:
  - `build_capture_manifest(..., prev_capture_hash=None)` records an optional
    `prev_capture_hash`.
  - The link is the canonical SHA-256 of the immediate predecessor manifest
    (`canonical_hash` and `capture_bridge._sha256_json` agree), and it is
    committed into this manifest's own canonical hash.
  - `None` (or an absent field, for pre-V129 captures) marks the chain genesis.
  - `validate_capture_manifest` accepts an absent field and rejects a present
    `prev_capture_hash` that is neither null nor a 64-char sha256 hex string.
- Portable link:
  - `build_intoto_statement_from_capture` adds a `prev_capture` subject when the
    link is present, so an external verifier that also holds the predecessor
    manifest re-verifies the link through the existing subject-digest ingest
    path. A broken link is a digest mismatch, which ingest already blocks.
- Whole-chain verifier:
  - `verify_capture_chain(manifests)` returns `pass`, `blocked`, or
    `inconclusive` with per-link results.
  - `blocked` on a non-genesis head, a predecessor-hash mismatch (dropped,
    reordered, or tampered step), or a structurally invalid manifest in the
    chain. `inconclusive` on an empty list.

## Boundary

- The chain is content-addressed, not signed. It makes drop/reorder/edit of an
  intermediate step within a presented chain detectable; it does not make the
  chain un-forgeable by an adversary that controls the whole capture process
  (same uid, no signature). DSSE `signatures` stays `[]`.
- This does not raise assurance. A1 remains A1; A2 privilege isolation and A3
  Sigstore signing remain deferred for environment reasons.
- No fixtures were edited; the field is optional and absence is treated as
  genesis, so all pre-V129 captures stay valid.
- `verify_capture_chain` is exposed as the `evidence-chain` CLI command; wiring
  it into the `evidence-run` product loop remains a separate follow-on.

## Evidence

- `depone agent-fabric-evidence-substrate --self-test` now also validates an
  intact three-step chain (pass), an empty chain (inconclusive), a non-genesis
  head (blocked), a dropped intermediate step (blocked), a reordered chain
  (blocked), a tampered predecessor (blocked), and a broken `prev_capture` link
  re-verified through ingest (blocked).
- `depone agent-fabric-capture-bridge --self-test`, `depone verify --self-test`,
  `depone agent-fabric-evidence-ingest --self-test`, and
  `python scripts/check_contract.py --tier changed` pass.
