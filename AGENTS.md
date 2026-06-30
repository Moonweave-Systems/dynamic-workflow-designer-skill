# Depone - Agent Context

Depone (engine: **DWM Core**, the Deterministic Workflow Machine) is a
control-plane for large AI-native work: workflow design, packet compilation,
bounded runner gates, review/repair evidence, and scoring artifacts. The tooling
is pure-stdlib Python under `scripts/` plus one `.cjs` reference implementation.
The installed skill is `depone`; the entry doc is `SKILL.md`.

This file exists so Codex Cloud or local Codex agents that clone the repo with
no other context know how to work here. Keep it short and current.

## Current direction (read first)

`docs/v125-direction-check-roadmap.md` is the current product-direction source of
truth. Bottom line: Depone should be the independent evidence and control plane
for increasingly automated agent-team work. Keep the non-executing design+verify
plane, but move by executed evidence, not by adding source-only control layers.

Current state:

- V126 captured a real Codex direct-vs-governed run and promoted the governed
  arm into an observed A1 capture fixture.
- V127 made claim evaluation honest: required unevaluated claims are
  `inconclusive`, not `pass`; "hash-signed" wording was corrected.
- V128 emits the first stdlib-only in-toto/DSSE plus OTel GenAI evidence bundle.
- V129 through PR #37 added `depone advance`, a revalidating one-step gate over
  `next` plus one evidence-producing continuation.

Next work: `docs/v125-direction-check-roadmap.md` remains the source of truth.
Use `docs/depone-agent-execution-roadmap.md` as its agent-facing execution plan:
first close the V128 ingest/dogfood gap and stabilize the canonical
`capture-manifest.prev_capture_hash` / `evidence-chain` continuity seam before
adding container isolation, signing, loops, or team ledgers. Do not revive the
V124 Agent OS draft as a product milestone now; it is a source-only meta layer
and remains parked unless it directly helps capture, ingest, verify, or trust
real evidence.

## Verify after any change

Run before claiming work is done or opening a PR:

```bash
python scripts/check_contract.py --tier changed   # release contract (changed tier)
python scripts/dwm.py doctor                       # operator-state sanity
python scripts/check_readme_quality.py README.md   # only if README changed
```

Full contract sweep: `python scripts/check_contract.py`. Many scripts also carry
a `--self-test`; run the one for any script you touch.

## Invariants

- **No external dependencies.** Scripts use the Python standard library only.
  Never add a third-party package, a requirements/pyproject file at the root, or
  a new runtime to make something work.
- Type hints on all new function signatures; prefer `str | None` over
  `Optional[str]`. Use f-strings, not `.format()` or `%`.
- Artifacts and source hashes are the source of truth. Never hand-edit generated
  files under `out/` or fixtures under `fixtures/` to make a check pass.
- Keep planned work and executed work separate - never present an unrun step as
  done. This is the core discipline the tool enforces; respect it in your own
  changes.

## Commit style

Imperative subject focused on *why*, not what. One commit per logical change.
Do not amend existing commits.
