# Depone Next Work Plan

Status: refreshed native-team and evidence backlog after PR #57 and PR #55
merged.
Date: 2026-07-01.
Base: `origin/main` at `a3b9db5` (`Add Codex capability readiness probe
(#55)`), after `20caeff` (`Add Team PR artifact producer (#57)`).
Current follow-up: PR #56, `codex/wave-backlog-refresh`, is this docs-only
backlog refresh.

## Purpose

This note is the current operator-facing work order for Depone. It consolidates
the first A2 captures, signed evidence path, `evidence-next` / `advance`, Team
Ledger v0, local team lane preparation, shell lane launch, cloud lane artifact
validation, Team PR artifact production, and Codex local capability readiness
into one sequence.

It is not a public benchmark claim and it is not a new assurance rung. The goal
is to keep the next agents moving through small, reviewable waves that improve
real evidence, local usability, and team execution without drifting into
source-only scaffolding.

The executable wave checklist lives in:

- `docs/superpowers/plans/2026-06-30-depone-wave-execution-backlog.md`

## Current Position

### Completed Strong Layers

- A0/A1/A2 assurance is implemented around capture manifests, observer capture,
  isolation facts, and fail-closed validation.
- Real A2 artifacts exist for uid isolation:
  `docs/a2-first-isolated-evidence/`.
- Real container-isolated A2 artifacts exist:
  `docs/container-isolated-a2/`.
- Evidence bundles can be represented as in-toto/DSSE-shaped artifacts and
  OTel-shaped spans.
- The key-based signing path has tests and committed evidence under
  `docs/evidence-run-signing/`.
- `evidence-next` revalidates evidence before continuation.
- `advance` runs exactly one continuation after a passing `next` decision and
  then stops.
- Team Ledger v0 validates externally run lanes. Passed lanes need machine
  evidence, a passing `evidence-next` verdict, non-empty touched files, and a
  merge receipt when passed lanes overlap.
- Local team preparation is now staged:
  - `team-dry-run` writes planning artifacts without launching workers.
  - `team-launch-preflight` validates planned lanes without creating worktrees.
  - `team-worktree-prep` creates or selects local worktrees only behind an
    explicit flag.
  - `team-shell-lane-launch` runs exactly one allowlisted shell command and
    writes a receipt plus transcript.
- Cloud lanes can be represented as observed external facts through
  `cloud_artifact`, without claiming provider runtime attestation.
- Source install readiness is covered by `scripts/install_smoke.py` in the
  changed-tier contract.
- Team PR artifact production is implemented by PR #57:
  `depone team-pr-artifact` validates saved or live GitHub PR facts and commits
  a revalidatable artifact under `docs/team-pr-artifact/`.
- Codex local capability readiness is implemented by PR #55:
  `depone codex-local-capability` records `codex --version` readiness facts,
  validates instruction-file hashes, and keeps the claim explicitly
  capability-only.

### Active Draft Work

PR #56 is a docs-only backlog refresh:

- PR: <https://github.com/Moonweave-Systems/Depone/pull/56>
- Branch: `codex/wave-backlog-refresh`
- Scope: update this work plan and the executable wave plan after PR #57 and
  PR #55 landed.
- Non-claim: it does not add a new assurance rung, run adapters, or change
  evidence validation behavior.

### Weak Or Missing Layers

- Depone does not yet launch and manage a durable multi-agent coding team by
  itself.
- Depone does not yet assign coding tasks to Codex, Claude Code, OpenCode, OMX,
  or cloud adapters and collect full lane evidence end to end.
- Cloud lanes are observed external facts, not provider runtime isolation
  attestations.
- PR and check status can be captured by `team-pr-artifact`, but Team Ledger
  integration still needs to be tightened around real merge attempts.
- Merge receipts are still command-input artifacts, not derived from real git
  merge or conflict attempts.
- Key-based signing is useful, but keyless identity and transparency-log
  inclusion remain future work.
- The local `/home/ubuntu/depone` `main` branch may contain old OMX
  auto-checkpoint history. New work must start from `origin/main`, not local
  `main`, unless the maintainer explicitly chooses a cleanup path.
- Older stacked PRs (#9 through #27, plus #7) remain open and need a separate
  close-or-rescue audit. Do not merge them blindly.

## Product Ladder

The next useful order is:

1. Keep using clean branches from `origin/main`; do not rely on divergent local
   `main`.
2. Audit and resolve stale PR stack state without force operations.
3. Add a real git merge attempt receipt so fan-in can bind conflict evidence.
4. Build a minimal local `depone team` loop over existing dry-run, preflight,
   worktree, shell-lane, ledger, and `next` commands.
5. Add coding-adapter launch receipts one adapter at a time, starting with
   Codex now that capability readiness has landed.
6. Add cloud adapter receipts from observed provider artifacts before owning
   cloud runtime provisioning.
7. Tighten A3 signing ergonomics and keyless feasibility after evidence and team
   flows are useful enough to sign.
8. Build a small benchmark harness only after the run, team, and receipt layers
   can produce re-runnable artifacts.

## Wave Order

### Wave 0: Repository Hygiene

Goal: make the repo safe for continued work without destructive history edits.

State: completed for PR #55 on 2026-07-01. PR #55 was revalidated from a clean
worktree and merged as `a3b9db5`. Older stacked PRs still need a separate
close-or-rescue audit.

Actions:

- Revalidate PR #55 from a clean checkout.
- Decide whether PR #55 is still the next merge candidate.
- Inventory stale PRs and mark each as keep, close, or rebuild.
- Do not reset local `main`; use fresh branches from `origin/main`.

Acceptance:

- PR #55 has fresh verification output or a clear close reason.
- The stale PR stack has a written decision table.
- No branch deletion, force push, hard reset, or broad cleanup occurs.

### Wave 1: PR Artifact Producer

Goal: turn GitHub PR state into a local JSON artifact consumable by Team Ledger.

State: completed by PR #57 as `20caeff`.

Actions:

- Add `team-pr-artifact` core and CLI.
- Read `gh pr view --json` output or a saved JSON input.
- Write `docs/team-pr-artifact/pr-artifact.json`.
- Validate head SHA, base SHA, state, mergeability, check summary, PR URL, and
  captured timestamp.

Acceptance:

- `team-ledger` accepts a matching PR artifact.
- Head SHA mismatch, stale artifact, failed checks, and malformed input block.
- Network access is optional because committed JSON fixtures can revalidate.

### Wave 2: Git Merge Attempt Receipt

Goal: derive merge evidence from git instead of trusting operator-entered merge
receipt fields.

Actions:

- Add `team-merge-attempt` core and CLI.
- Run a no-commit merge attempt in a temporary or explicit throwaway worktree.
- Record base, heads, files, conflict events, exit code, and cleanup state.
- Feed the result into Team Ledger as the merge receipt source.

Acceptance:

- Clean non-overlap passes.
- Overlap without conflicts records the exact files.
- Conflict blocks fan-in with machine evidence.
- The command refuses to run on a dirty target worktree unless explicitly told
  to use a disposable worktree.

### Wave 3: Minimal Local Depone Team Loop

Goal: coordinate local lanes using existing primitives before adding live model
adapters.

Actions:

- Add a small `depone team` or `depone team-local` command only after the
  underlying receipts are stable.
- Sequence `team-dry-run`, `team-launch-preflight`, `team-worktree-prep`,
  `team-shell-lane-launch`, `evidence-next`, and `team-ledger`.
- Stop after one lane command per lane.
- Emit `team-run-ledger.json`.

Acceptance:

- No live model is launched.
- The loop stops on the first blocked lane.
- Every passed lane has a receipt, evidence directory, touched files, and a
  passing `evidence-next` verdict.

### Wave 4: Coding Adapter Launch Receipts

Goal: add real coding adapter seams without pretending capability detection is
execution.

Actions:

- Use the landed Codex capability readiness receipt from PR #55 as the
  precondition.
- Add an explicit Codex launch receipt only after capability detection passes.
- Keep command argv allowlisted and sandbox/approval policy recorded.
- Do not read secrets, private auth files, or token-bearing config.

Acceptance:

- Missing binary, unsupported policy, dirty repo, unobservable instruction files,
  or failed version probe block before launch.
- A launched adapter writes a transcript and runner receipt that can be consumed
  by `evidence-run` or Team Ledger.
- The first adapter PR is Codex-only; Claude Code and OpenCode are separate PRs.

### Wave 5: Cloud Adapter Receipt

Goal: observe cloud-first work without owning cloud provisioning.

Actions:

- Add a provider-neutral cloud run artifact producer.
- Start with saved JSON or manually exported provider facts.
- Bind external run id, repo, base/head commits, PR URL, logs/check summaries,
  and evidence hash.
- Keep runtime isolation attestation explicitly false unless the provider gives
  a verifiable attestation.

Acceptance:

- Cloud lane artifacts validate locally.
- Team Ledger blocks passed cloud lanes without matching evidence hash.
- No provider SDK dependency is introduced in the first slice.

### Wave 6: A3 Signing And Attestation Ergonomics

Goal: make signed evidence easy to verify without overclaiming keyless identity.

Actions:

- Keep the existing operator-key signing path.
- Add a friendlier verify command or documented `attest verify` alias only if it
  reduces operator friction.
- Add committed revalidation output for `docs/evidence-run-signing/`.
- Probe cosign/keyless feasibility separately.

Acceptance:

- Verified signed bundles pass.
- Tampered manifest, observer capture, DSSE payload, or signature metadata
  blocks.
- Unsigned evidence remains honest and does not claim A3.

### Wave 7: Bounded Loop

Goal: allow repeated `advance` with a hard budget and chain validation.

Actions:

- Add `loop` over repeated `advance`.
- Require `--max-steps`.
- Validate `capture-manifest.prev_capture_hash` before every step.
- Emit `loop-ledger.json`.

Acceptance:

- Missing intermediate steps block.
- A blocked `next` stops before execution.
- Resume cannot skip, overwrite, or reorder prior artifacts.

### Wave 8: Benchmark Harness

Goal: measure whether Depone governance helps real work.

Actions:

- Create a small local task corpus with direct and governed runs.
- Track correctness, command count, elapsed time, touched files, review findings,
  blocked recovery, and artifact completeness.
- Keep LLM review advisory and deterministic checks authoritative.

Acceptance:

- At least six task classes have re-runnable artifacts before any public
  superiority claim.
- Reports separate deterministic pass/fail from advisory review.
- Public claims remain blocked below the declared sample threshold.

## GitFlow Rules

- Start every new PR branch from `origin/main`.
- Keep one PR to one wave slice.
- Use draft PRs until unit tests, CLI self-tests, `check_contract.py --tier
  changed`, and `scripts/dwm.py doctor` have fresh passing output.
- Commit only source, tests, docs, and intentionally committed revalidatable
  artifacts.
- Do not stage ignored `out/` repair copies.
- Do not use `git reset --hard`, force push, branch deletion, or stale PR merge
  without explicit maintainer approval.
- Merge only when the committed artifacts revalidate from a clean checkout.

## Immediate Next Action

Start the next implementation PR from fresh `origin/main` and pick exactly one
slice:

- Preferred evidence/team fan-in slice: Wave 2, `team-merge-attempt`.
- Preferred adapter slice: Wave 4, Codex-only launch receipt.

Recommended Wave 2 preflight:

```bash
git fetch -q origin
git switch --create codex/team-merge-attempt origin/main
PYTHONDONTWRITEBYTECODE=1 python3 -m depone team-pr-artifact --self-test
PYTHONDONTWRITEBYTECODE=1 python3 -m depone team-ledger --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dwm.py doctor
```

Run the stale PR inventory separately; do not mix it into the Wave 2
implementation PR.
