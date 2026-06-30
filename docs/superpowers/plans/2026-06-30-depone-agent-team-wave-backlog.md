# Depone Agent Team Wave Backlog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended), superpowers:executing-plans, OMX `$team`, or an equivalent supervised multi-lane workflow to implement one wave at a time. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the post-PR #53 state into a large-unit execution backlog for agents, so Depone can move from capability receipts toward bounded local launches, PR evidence, team fan-in, cloud observation, signing, and benchmark evidence without overclaiming.

**Architecture:** Keep Depone as the evidence and control plane, not the coding model. Every wave produces one reviewable PR with machine-verifiable JSON artifacts, deterministic validators, focused tests, and explicit stop conditions. Runners such as Codex, Claude Code, OpenCode, OMX, LazyCodex, shell, or cloud agents remain adapters until Depone has receipts proving what happened.

**Tech Stack:** Python standard library only, existing `depone.agent_fabric` modules, existing CLI registration in `depone/__main__.py`, `unittest`, `git`/`gh`/adapter CLIs through subprocess only when the wave authorizes them, committed docs fixtures under `docs/`, and `scripts/check_contract.py --tier changed`.

---

## Current Baseline

Main currently has these useful rungs:

- A2 uid/container evidence exists as committed revalidatable artifacts.
- Evidence bundles, DSSE/in-toto shape, OTel span shape, and key-based signing examples exist.
- `run`, `next`, and `advance` form a one-step continuation gate.
- Team dry-run, launch preflight, worktree prep, shell lane launch, cloud lane artifact validation, and merge receipt surfaces exist.
- PR #53 added `codex-local-capability`, a capability-only detector that writes a blocked/pass receipt without launching a Codex model session or coding task.

The honest missing layer is not more prose. The next missing layer is a chain of receipts:

```text
capability receipt -> launch receipt -> worktree/evidence receipt -> verifier receipt -> PR/check receipt -> ledger verdict -> optional signature -> benchmark result
```

## Global Execution Rules

- Execute one wave per PR unless the wave explicitly says it may split.
- Do not launch live model sessions in a wave whose boundary says capability-only, fixture-only, or observed-only.
- Do not raise A2/A3/A4 assurance unless the committed artifact can be independently revalidated.
- Do not add third-party Python dependencies.
- Do not read secrets, tokens, or private config to make a capability pass.
- Do not force push, reset, delete branches, delete worktrees, or merge PRs unless the active packet explicitly authorizes that operation.
- Use TDD for code slices: write a failing test, run it, implement the smallest passing code, rerun.
- Commit machine artifacts only when they are part of the claim and validated by code.
- Keep Markdown explanatory. JSON, hashes, transcripts, receipts, and validators are the truth.

## Standard Verification Bundle

Run the focused tests for the wave, then this baseline before claiming a PR is ready:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dwm.py doctor
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_release_text.py .
git diff --check
```

If a wave changes README, also run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_readme_quality.py README.md
```

## Wave 1: Codex Capability Pass And Environment Readiness

**Purpose:** Extend `codex-local-capability` from a blocked-safe fixture to a stronger readiness receipt when the environment can prove it, while staying capability-only.

**Role mix:**

- `explorer`: inspect current Codex binary, version command, repo state, and instruction files without reading secrets.
- `worker`: add readiness fields and tests.
- `verifier`: revalidate blocked and pass fixtures.
- `reviewer`: check overclaim language and secret/auth leakage risk.

**Files:**

- Modify: `depone/agent_fabric/codex_local_capability.py`
- Modify: `depone/cli/codex_local_capability.py`
- Modify: `tests/test_agent_fabric_codex_local_capability.py`
- Modify: `tests/test_codex_local_capability_cli.py`
- Modify: `docs/codex-local-capability/README.md`
- Optional create: `docs/codex-local-capability/pass-capability.json`
- Modify: `scripts/check_contract.py`

**Task list:**

- [ ] Add tests for `pass` capability when a fake Codex binary exists, repo is clean, sandbox/approval values are supported, and instruction hashes are observable.
- [ ] Add tests for blocked capability when version probing times out, returns nonzero, or writes unexpected output.
- [ ] Add a receipt field such as `probe` or `readiness` that records whether `codex --version` was executed, its exit code, timeout status, and sanitized version text.
- [ ] Ensure the receipt never records auth tokens, environment variables, config file contents, or home-directory secret paths.
- [ ] Generate a committed pass fixture only if the server can prove readiness without interactive auth or secret inspection. If not, keep the blocked fixture and document the residual.
- [ ] Add contract checks that validate every committed capability fixture and recompute instruction hashes.
- [ ] Update command reference text to say this is still not a live model launch.

**Acceptance evidence:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_codex_local_capability tests.test_codex_local_capability_cli -v
PYTHONDONTWRITEBYTECODE=1 python3 -m depone codex-local-capability --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
```

**Stop conditions:**

- Stop if proving pass requires interactive login, reading credentials, or assuming auth.
- Stop if the local binary is absent and the only possible output is another blocked fixture.
- Stop if a proposed field implies live model readiness when only version probing was observed.

## Wave 2: Codex Local Launch Receipt For One Bounded Packet

**Purpose:** Launch one bounded Codex local packet only after capability passes, then write a launch receipt with transcript, changed files, and verification commands. This is the first real local coding adapter slice.

**Role mix:**

- `planner`: define the smallest packet shape and launch boundary.
- `worker`: implement core launch receipt and CLI.
- `test-engineer`: add fake Codex subprocess fixtures and dirty-worktree tests.
- `verifier`: prove launch receipt validates from committed artifacts.
- `reviewer`: look for arbitrary prompt/shell injection, auth leakage, and assurance overclaim.

**Files:**

- Create: `depone/agent_fabric/codex_local_launch.py`
- Create: `depone/cli/codex_local_launch.py`
- Modify: `depone/__main__.py`
- Create: `tests/test_agent_fabric_codex_local_launch.py`
- Create: `tests/test_codex_local_launch_cli.py`
- Create: `docs/codex-local-launch/README.md`
- Create: `docs/codex-local-launch/launch-receipt.json`
- Create: `docs/codex-local-launch/transcript.json`
- Modify: `docs/command-reference.md`
- Modify: `scripts/check_contract.py`

**Task list:**

- [ ] Define an input packet schema with objective, allowed paths, verification commands, sandbox mode, approval policy, and stop rules.
- [ ] Add a core builder that refuses unless a capability receipt validates and has `decision: pass`.
- [ ] Execute Codex only through argv list subprocess calls, never through shell strings.
- [ ] Capture stdout, stderr, exit code, timeout status, transcript path/hash, git head before/after, dirty state, and changed files.
- [ ] Require verification commands to be explicit argv arrays and run them only after the adapter exits.
- [ ] Emit `decision: pass`, `fail`, or `blocked` from machine facts, not model text.
- [ ] Commit a fake-Codex fixture first. A live Codex fixture is allowed only when the packet is harmless, bounded, and independently revalidatable.
- [ ] Keep assurance at local observed receipt level; do not claim A2 unless the runner boundary is separately proven.

**Acceptance evidence:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_codex_local_launch tests.test_codex_local_launch_cli -v
PYTHONDONTWRITEBYTECODE=1 python3 -m depone codex-local-launch --self-test
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import json
from depone.agent_fabric.codex_local_launch import validate_codex_local_launch
m = json.load(open("docs/codex-local-launch/launch-receipt.json"))
print("validate errors:", validate_codex_local_launch(m))
PY
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
```

**Stop conditions:**

- Stop if the adapter would need unrestricted filesystem access.
- Stop if changed files cannot be bounded to the packet.
- Stop if verification commands are model-generated strings instead of declared argv arrays.

## Wave 3: Worktree And Evidence Binding For Local Lanes

**Purpose:** Bind a local lane's worktree receipt, launch receipt, evidence directory, touched files, and `evidence-next` verdict into Team Ledger.

**Role mix:**

- `explorer`: map existing `team_ledger`, `worktree_receipt`, and `team-shell-lane-launch` validator patterns.
- `worker`: extend ledger lane schema.
- `test-engineer`: add conflict and mismatch tests.
- `verifier`: revalidate docs artifacts and ledger verdict.

**Files:**

- Modify: `depone/agent_fabric/team_ledger.py`
- Modify: `depone/cli/agent_fabric_team_ledger.py`
- Modify: `tests/test_agent_fabric_team_ledger.py`
- Modify: `docs/worktree-lane-receipt/README.md`
- Modify or create: `docs/local-lane-fanin/README.md`
- Create: `docs/local-lane-fanin/team-ledger.json`
- Create: `docs/local-lane-fanin/team-ledger-verdict.json`
- Modify: `scripts/check_contract.py`

**Task list:**

- [ ] Add optional lane fields for `codex_launch_receipt`, `worktree_receipt`, and `evidence_next_verdict`.
- [ ] Require lane `end_commit` to match receipt head facts when those fields are present.
- [ ] Require changed files in the worktree receipt to match or cover lane touched files.
- [ ] Require a passing or blocked-explicit `evidence-next` verdict before the lane can fan in.
- [ ] Block when launch receipt, worktree receipt, and ledger lane facts contradict each other.
- [ ] Add a committed fixture where a lane passes from revalidatable local artifacts.

**Acceptance evidence:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_team_ledger -v
PYTHONDONTWRITEBYTECODE=1 python3 -m depone team-ledger --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
```

**Stop conditions:**

- Stop if fan-in would rely on lane prose or chat summaries.
- Stop if the validator cannot prove which commit and files the lane produced.

## Wave 4: PR And Check Artifact Evidence

**Purpose:** Make PR/check status first-class evidence that Team Ledger can validate locally from JSON, without requiring live GitHub access during review.

**Role mix:**

- `explorer`: inspect current GitHub CLI output shape and existing ledger fields.
- `worker`: implement PR artifact producer and validator.
- `verifier`: test committed PR artifacts with no network.
- `reviewer`: check stale SHA and check-status failure cases.

**Files:**

- Create: `depone/agent_fabric/pr_artifact.py`
- Create: `depone/cli/pr_artifact.py`
- Modify: `depone/__main__.py`
- Modify: `depone/agent_fabric/team_ledger.py`
- Create: `tests/test_agent_fabric_pr_artifact.py`
- Modify: `tests/test_agent_fabric_team_ledger.py`
- Create: `docs/pr-artifact/README.md`
- Create: `docs/pr-artifact/pr-artifact.json`
- Modify: `docs/command-reference.md`
- Modify: `scripts/check_contract.py`

**Task list:**

- [ ] Define a PR artifact schema with provider, repo, PR number, URL, state, base SHA, head SHA, mergeability, check rollup, captured time, and source command.
- [ ] Add a producer that can consume `gh pr view --json ...` output and normalize it into deterministic JSON.
- [ ] Add a validator that runs without network and blocks on missing head SHA, failed checks, stale base/head mismatch, or malformed state.
- [ ] Let Team Ledger reference a PR artifact and require artifact head SHA to match lane `end_commit` when present.
- [ ] Commit a small fixture from a non-sensitive PR or synthetic `gh` output.

**Acceptance evidence:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_pr_artifact tests.test_agent_fabric_team_ledger -v
PYTHONDONTWRITEBYTECODE=1 python3 -m depone pr-artifact --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
```

**Stop conditions:**

- Stop if GitHub auth is unavailable and no committed fixture can be validated.
- Stop if the producer would need to read secrets or mutate PR state.
- Stop if failed or pending checks are treated as pass.

## Wave 5: Reviewer And Verifier Receipts

**Purpose:** Separate deterministic verification from advisory review so a lane can prove tests passed and also record review findings without treating LLM review as authority.

**Role mix:**

- `test-engineer`: design verifier receipt fields.
- `worker`: implement receipt producer and validator.
- `reviewer`: define findings-only review artifact shape.
- `verifier`: prove both receipts can be consumed by Team Ledger.

**Files:**

- Create: `depone/agent_fabric/lane_verification_receipt.py`
- Create: `depone/agent_fabric/lane_review_receipt.py`
- Create: `depone/cli/lane_verification_receipt.py`
- Create: `depone/cli/lane_review_receipt.py`
- Modify: `depone/__main__.py`
- Modify: `depone/agent_fabric/team_ledger.py`
- Create: `tests/test_lane_verification_receipt.py`
- Create: `tests/test_lane_review_receipt.py`
- Modify: `tests/test_agent_fabric_team_ledger.py`
- Create: `docs/lane-verification-receipt/README.md`
- Create: `docs/lane-review-receipt/README.md`
- Modify: `scripts/check_contract.py`

**Task list:**

- [ ] Add a verifier receipt schema for command argv, cwd, exit code, stdout/stderr hashes, elapsed time, and pass/fail decision.
- [ ] Add a review receipt schema for findings, severity, file references, reviewer role, and unresolved/open-question state.
- [ ] Require verifier receipt pass before a lane can be marked complete.
- [ ] Allow review receipt to block when it contains unresolved high-severity findings.
- [ ] Record review as advisory unless a deterministic verification or human policy promotes it to a gate.

**Acceptance evidence:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_lane_verification_receipt tests.test_lane_review_receipt tests.test_agent_fabric_team_ledger -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
```

**Stop conditions:**

- Stop if a reviewer receipt can pass a lane without deterministic verification.
- Stop if file references are free-form text with no repo-relative path validation.

## Wave 6: Minimal Depone Native Team Command

**Purpose:** Add the first Depone-native team orchestrator command over local lanes, but keep it bounded: prepare plan, require capability, launch one lane or a small declared set, collect receipts, run ledger, stop.

**Role mix:**

- `planner`: packetizes the team plan and lane ownership.
- `worker`: implements the command.
- `verifier`: validates artifacts and ledger verdicts.
- `reviewer`: audits concurrency, shared-file conflict, and cleanup behavior.

**Files:**

- Create: `depone/agent_fabric/team_run.py`
- Create: `depone/cli/team_run.py`
- Modify: `depone/__main__.py`
- Create: `tests/test_agent_fabric_team_run.py`
- Create: `tests/test_team_run_cli.py`
- Create: `docs/team-run/README.md`
- Create: `docs/team-run/team-run-receipt.json`
- Modify: `docs/command-reference.md`
- Modify: `scripts/check_contract.py`

**Task list:**

- [ ] Accept a team plan JSON with objective, lanes, adapters, allowed paths, verification commands, budgets, and stop rules.
- [ ] Refuse unless every lane has a passing capability receipt.
- [ ] Launch only adapters explicitly supported by previous waves.
- [ ] Write per-lane launch receipts, verification receipts, and a final Team Ledger verdict.
- [ ] Stop after the declared budget or after the first unresolved blocker.
- [ ] Do not auto-merge, auto-delete branches, or mutate remote PRs.

**Acceptance evidence:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_team_run tests.test_team_run_cli -v
PYTHONDONTWRITEBYTECODE=1 python3 -m depone team-run --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
```

**Stop conditions:**

- Stop if a lane would need a runner adapter without a capability and launch receipt.
- Stop if two lanes touch the same file and no merge receipt exists.
- Stop if the command would become an unchecked loop rather than bounded orchestration.

## Wave 7: Observed Cloud Lane Artifacts

**Purpose:** Represent cloud-run work honestly before Depone owns any cloud workspace lifecycle.

**Role mix:**

- `docs_researcher` or `researcher`: verify provider artifact fields from official docs before implementing provider-specific text.
- `worker`: implement provider-neutral observed cloud artifact validation.
- `verifier`: validate fixture-only artifacts.
- `reviewer`: check residuals around provider isolation claims.

**Files:**

- Modify: `depone/agent_fabric/cloud_lane_artifact.py`
- Modify: `depone/agent_fabric/team_ledger.py`
- Create or modify: `tests/test_cloud_lane_artifact.py`
- Modify: `docs/cloud-lane-artifact/README.md`
- Create: `docs/cloud-lane-artifact/github-copilot-cloud-example.json`
- Create: `docs/cloud-lane-artifact/codex-cloud-example.json`
- Modify: `scripts/check_contract.py`

**Task list:**

- [ ] Add provider-neutral fields for external run id, provider, adapter kind, repo, base/head SHA, PR URL, checks, logs hash, captured time, and evidence hash.
- [ ] Add provider residual fields that explicitly say runtime isolation is observed or unproven.
- [ ] Validate fixtures without network.
- [ ] Make Team Ledger block when cloud artifact SHA or evidence hash disagrees with the lane.
- [ ] Keep provider-specific docs as references, not executable claims.

**Acceptance evidence:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_cloud_lane_artifact tests.test_agent_fabric_team_ledger -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
```

**Stop conditions:**

- Stop if the artifact implies Depone attests provider runtime isolation.
- Stop if the implementation requires provider SDK dependencies.
- Stop if network-only validation is required for the committed fixture.

## Wave 8: A3 Signing And Verification Bundle

**Purpose:** Make evidence bundles tamper-evident with a committed verifier path, starting with the existing key-based path and adding keyless only when identity is actually available.

**Role mix:**

- `security reviewer`: inspect signing boundaries and key material handling.
- `worker`: wire signing into evidence bundle outputs.
- `verifier`: prove committed signed fixtures validate.
- `reviewer`: check that unsigned evidence does not raise assurance.

**Files:**

- Modify: `depone/cli/agent_fabric_sign.py`
- Modify: `depone/cli/agent_fabric_seal.py`
- Modify: relevant evidence bundle modules under `depone/agent_fabric/`
- Create or modify: `tests/test_agent_fabric_signing.py`
- Create: `docs/evidence-bundle-signing/README.md`
- Create: `docs/evidence-bundle-signing/signed-bundle.json`
- Modify: `scripts/check_contract.py`

**Task list:**

- [ ] Add a verifier command or helper that proves a committed signed bundle validates from public verification material.
- [ ] Ensure unsigned bundles stay at their current assurance level.
- [ ] Record signer identity, key id or certificate facts, signed subject digest, and verification result.
- [ ] Add keyless Sigstore/cosign only if OIDC identity is present and the command can verify without hidden state.
- [ ] Document the residual when keyless is unavailable.

**Acceptance evidence:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_fabric_signing -v
PYTHONDONTWRITEBYTECODE=1 python3 -m depone agent-fabric-verify-signature --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
```

**Stop conditions:**

- Stop if private keys would be committed or logged.
- Stop if verification depends on undeclared local key material.
- Stop if signature presence raises assurance without successful verification.

## Wave 9: Small Benchmark Corpus And A4 Gate

**Purpose:** Start measuring whether governed agent work is actually useful, using a small local corpus before public benchmark claims.

**Role mix:**

- `planner`: define corpus tasks and scoring rules.
- `worker`: implement corpus runner/recorder.
- `verifier`: validate attempts and scoring artifacts.
- `reviewer`: check public-claim overreach.

**Files:**

- Create: `depone/agent_fabric/agent_benchmark_corpus.py`
- Create: `depone/cli/agent_benchmark_corpus.py`
- Modify: `depone/__main__.py`
- Create: `tests/test_agent_benchmark_corpus.py`
- Create: `docs/agent-benchmark-corpus/README.md`
- Create: `docs/agent-benchmark-corpus/tasks.json`
- Create: `docs/agent-benchmark-corpus/results.json`
- Modify: `docs/command-reference.md`
- Modify: `scripts/check_contract.py`

**Task list:**

- [ ] Define a local corpus with documentation update, single-file bug fix, multi-file CLI change, artifact regeneration, review-only no-change, and merge finalization tasks.
- [ ] Record direct run and governed run attempts separately.
- [ ] Score correctness from deterministic tests and artifact validation only.
- [ ] Track risk reduction, traceability, recovery, and changed-file scope as secondary measures.
- [ ] Keep public claims blocked until the corpus is stable and results are reproducible.

**Acceptance evidence:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_benchmark_corpus -v
PYTHONDONTWRITEBYTECODE=1 python3 -m depone agent-benchmark-corpus --self-test
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_contract.py --tier changed
```

**Stop conditions:**

- Stop if tasks require hidden tests or external services.
- Stop if scoring uses subjective model preference as the main correctness signal.
- Stop if results are used for public superiority claims before A4 criteria are met.

## Recommended Next Execution Order

1. Wave 1 if the current server can prove a Codex capability pass without secrets; otherwise skip to Wave 2 with fake-Codex fixtures only.
2. Wave 2 because launch receipts are the missing seam between capability detection and useful agent work.
3. Wave 3 because Team Ledger must consume real local lane artifacts before a native team command exists.
4. Wave 4 because PR/check evidence is the normal output shape for cloud and background coding agents.
5. Wave 5 because verifier/reviewer separation prevents review prose from becoming false authority.
6. Wave 6 because only then is a native team command grounded enough to launch bounded lanes.
7. Wave 7 because cloud should be observed before it is owned.
8. Wave 8 because signed evidence is worth signing after the evidence flow is useful.
9. Wave 9 because benchmarks should measure the system after it can run a real bounded loop.

## GitFlow For Agents

- Create one branch per wave, for example `codex/codex-local-launch-receipt`.
- Keep the PR draft until focused tests, self-tests, `check_contract.py --tier changed`, `dwm.py doctor`, release text, and `git diff --check` pass.
- Include independent fixture revalidation output in the PR body.
- Merge only when local verification and PR state are clean.
- After merge, switch back to `main`, pull fast-forward, and confirm the committed artifact exists on main.

## Handoff Summary

The next agent should not ask for the whole roadmap again. It should choose the first feasible wave, state the capability boundary, implement one PR, verify from committed artifacts, and stop. If it cannot prove a stronger rung, it should commit a blocked-safe artifact or report the exact blocker instead of escalating a claim.
