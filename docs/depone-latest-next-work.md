# Depone Latest Next Work

Status: current agent-facing execution note after PR #53 merge.
Date: 2026-06-30
Base: `origin/main` at `c53a96d` (`Add Codex local capability receipt (#53)`)

## Current Truth

Depone has reached the first Codex adapter readiness rung:

- PR #51 merged the canonical agent operating contract under
  `packaging/depone-agent-operating-contract.json`.
- `team-shell-lane-launch` can run exactly one allowlisted argv command and
  write a receipt plus transcript under `docs/team-shell-lane-launch/`.
- The shell-lane receipt records `agent_contract_hash`, the resolved
  `agent_contract` facts, transcript hash, stdout/stderr hashes, and boundary
  flags.
- The committed shell-lane artifact revalidates through
  `scripts/check_contract.py --tier changed`.
- PR #53 added `codex-local-capability`, a capability-only detector that records
  local Codex adapter readiness facts under `docs/codex-local-capability/`.
- The committed Codex capability artifact revalidates locally with
  `validate_codex_local_capability(...) -> []`.
- This is still capability evidence. It is not a Codex model session launch, not
  a coding task, not a scheduler, not A2/container evidence, and not an
  assurance upgrade.

## Next Slice

The next implementation work should follow
`docs/superpowers/plans/2026-06-30-depone-agent-team-wave-backlog.md`.

That document is the large-unit wave backlog for agents. It starts from the
post-PR #53 state and orders the next work as capability pass readiness, bounded
Codex local launch receipt, local lane fan-in, PR/check artifacts,
verifier/reviewer receipts, minimal native team command, observed cloud lanes,
signing, and a small benchmark corpus.

## Why This Comes Next

The shell lane proved that Depone can bind a local command receipt to a shared
agent contract. The Codex capability slice proved that adapter readiness can be
recorded without launching a model session. The next missing layer is now a
bounded launch receipt and then Team Ledger fan-in over real lane artifacts.

This keeps the direction aligned with the broader agent-tool market:

- agents run through adapter surfaces such as Codex, Claude Code, OpenCode,
  cloud agents, or team runtimes;
- Depone should control and verify launch facts, receipts, changed files,
  transcripts, and continuation gates;
- adapter claims must degrade honestly when the local environment is not ready.

## Proposed PR Sequence

Use one PR per wave from
`docs/superpowers/plans/2026-06-30-depone-agent-team-wave-backlog.md`:

1. `codex/codex-capability-pass-readiness` if a pass can be proven without
   secrets or interactive auth; otherwise keep Wave 1 as a blocked-safe doc and
   test refinement.
2. `codex/codex-local-launch-receipt` for the first bounded launch receipt.
3. `codex/local-lane-fanin` for Team Ledger consumption of local lane artifacts.
4. `codex/pr-artifact-evidence` for PR/check JSON validation.
5. `codex/lane-verifier-reviewer-receipts` for deterministic verifier receipts
   and advisory reviewer receipts.
6. `codex/native-team-run-v0` only after launch and fan-in receipts are stable.

## Stop Conditions

Stop and report blocked when:

- detecting Codex readiness would require reading secrets or interactive auth;
- launching Codex would be required in a capability-only wave;
- the adapter cannot record the instruction files, repo state, changed files, or
  verification commands it claims to have used;
- the implementation would need non-stdlib Python dependencies;
- the next step would raise assurance without independently revalidatable facts.

## Follow-On Order

After the Codex capability slice lands:

1. Codex local launch receipt for one bounded packet.
2. Local lane fan-in through Team Ledger.
3. PR/check artifact fan-in.
4. Reviewer/verifier receipt over the changed files and deterministic tests.
5. Minimal native team command over stable local lane receipts.
6. Claude Code/OpenCode capability adapters only after the Codex pattern is
   stable.
7. Owned cloud launch only after observed cloud artifacts and local adapters are
   boring.
