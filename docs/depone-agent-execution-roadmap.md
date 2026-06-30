# Depone Agent Execution Roadmap

Status: agent-facing planning document.
Date: 2026-06-30.
Baseline: PR #37 merged `depone advance`, a re-validating one-step gate over
`next` plus one `evidence-run` continuation.

Read this before starting the next implementation wave. This is not a new
capability claim and it does not supersede
`docs/v125-direction-check-roadmap.md`. Treat V125 as the product-direction
source of truth; this document is the agent-facing execution plan that turns
that direction into small, reviewable implementation waves. If the two disagree,
fix this document or V125 before coding.

## 1. Current Position

Depone now has the first real pieces of an evidence-first agent loop:

- `run` / `evidence-run` captures observer-owned evidence for a runner sandbox.
- `--runner-user` can bind an A2 uid boundary to an observer-launched runner
  receipt.
- `next` / `evidence-next` revalidates the committed artifact directory before
  recommending continuation.
- `advance` revalidates with `next`, runs exactly one continuation when
  unblocked, writes `advance-decision.json`, and stops.
- `docs/depone-advance-one-step/` contains re-validatable machine artifacts for
  that one-step continuation.

The honest state: Depone is not yet a full scheduler, coding agent, or team
runtime. It is a narrow control/evidence plane that can prove one isolated
runner step and one continuation. That is the right base. The next work should
make this loop durable and useful, not add more source-only control layers.

## 2. External Direction Check

The market direction is clear enough to guide the next work:

- Coding agents are moving toward background sessions, pull requests, isolated
  development environments, hooks, persistent instructions, and custom agents.
  Depone should benchmark against that shape, not against chat-only coding.
- OpenAI Codex documents sandboxing as the boundary that allows autonomous local
  action without unrestricted machine access; approval policy decides when the
  agent must stop before crossing that boundary.
- GitHub Copilot cloud agent runs in an ephemeral GitHub Actions development
  environment, can build/test/validate changes there, and uses setup steps to
  make that environment deterministic before work begins.
- Anthropic's agent guidance says to start simple, add agentic complexity only
  when measured value justifies it, and prefer transparent planning/tool
  interfaces. Its multi-agent research system shows parallel subagents help
  breadth-first research, but also warns that most coding tasks are less
  parallelizable and that multi-agent systems burn many more tokens.
- Claude Code and Copilot now expose project memory/instructions, hooks, custom
  agents, and tool/control surfaces. These are runtime ergonomics Depone should
  interoperate with or audit, not blindly duplicate.
- Supply-chain standards already define the trust vocabulary Depone needs:
  in-toto attestations, DSSE/Sigstore signing, SLSA provenance levels, and
  OpenTelemetry-style traces.

Implication: Depone should become the neutral "prove what happened and advance
only from verified artifacts" layer for local and cloud coding agents. It should
not try to out-UI Codex, Claude Code, Copilot, OMX, or LazyCodex. It should make
their runs auditable, restartable, comparable, and harder to overclaim.

## 3. Product Thesis

Depone's durable role is:

> A local-first, stdlib-only control plane that launches or observes agent
> execution inside explicit boundaries, records machine-verifiable evidence,
> refuses stale or untrusted continuation, and advances work one proven step at
> a time.

This means the product should feel like:

- `depone run`: capture one runner step.
- `depone next`: decide whether the evidence can continue.
- `depone advance`: run one safe continuation.
- future `depone loop`: bounded sequence of `advance`, never an unchecked agent.
- future `depone team`: multiple lane receipts under one leader ledger, only
  where the task shape proves parallelism is valuable.
- future `depone attest`: sign and verify evidence bundles.
- future `depone bench`: compare task outcomes across direct vs governed runs.

The core UX should be a small command surface with strong artifacts, not another
profile taxonomy.

## 4. Non-Goals

- Do not build an unrestricted autonomous agent launcher.
- Do not make `danger-full-access` the normal execution model.
- Do not add a new role/profile/fabric layer unless it improves capture,
  validation, isolation, signing, or measured task outcome.
- Do not claim productivity, quality, or agent superiority without a benchmark
  corpus and re-runnable artifacts.
- Do not treat LLM review as a pass/fail authority over deterministic tests.
- Do not require a single external runtime. Codex, Claude Code, GitHub Copilot,
  OMX, LazyCodex, OpenCode, shell, and future runners are adapters.

## 5. Benchmark Targets

Benchmark capabilities, not brands. The comparison matrix should track whether a
system can do each item and whether Depone can independently verify it.

| Target surface | What to benchmark | Depone response |
| --- | --- | --- |
| Codex local/cloud | sandbox modes, approvals, subagents, worktrees, hooks, PR workflow | record sandbox facts, command receipts, changed files, tests, reviewer verdicts |
| GitHub Copilot cloud agent | ephemeral Actions environment, setup steps, background PR sessions | validate environment recipe, capture PR artifacts, compare setup determinism |
| Claude Code | `CLAUDE.md`, hooks, subagents, memory, long-running sessions | verify loaded instructions, hook receipts, subagent outputs, memory-derived context |
| OMX / LazyCodex-style local teams | leader/worker queues, tmux sessions, stop/resume, parallel waves | bind worker claims to mailbox/task state, receipts, commits, tests, and shutdown state |
| SWE-bench style coding tasks | issue-to-patch correctness under hidden/held-out tests | create a small local corpus first, then map to public benchmarks later |
| SLSA / in-toto / Sigstore | provenance, signatures, transparency logs, isolated builders | map evidence bundles to attestations; keep assurance honest when unsigned |
| OpenTelemetry | traces for model/tool/agent steps | emit portable spans with stable operation and tool names |

First benchmark corpus should be local and small:

1. Documentation-only update.
2. Single-file bug fix with unit test.
3. Multi-file CLI behavior change.
4. Artifact regeneration / validation task.
5. Review-only no-change task.
6. Merge/PR finalization task.

Each task must have a direct run and a governed run. The governed run only wins
when artifacts show equal or better correctness with clearer traceability,
smaller risk, or easier recovery.

## 6. Architecture Direction

### 6.1 Assurance Ladder

Keep the ladder explicit:

- A0: claims only, no independent observer.
- A1: local observed evidence, same uid possible.
- A2: isolated observed evidence, runner cannot write observer-owned output.
- A2C: container/namespace observed evidence, host observer plus container
  runner facts.
- A3: signed evidence bundle, verified with key-based or keyless provenance.
- A4: audited multi-run benchmark evidence with held-out tests and public
  reproducibility.

Do not raise assurance because a command name sounds stronger. Raise assurance
only when the manifest contains re-verifiable facts and validation returns no
errors.

### 6.2 Execution Loop

The next durable loop should be:

1. Prepare runner sandbox from a clean git state.
2. Launch runner or observe external runner.
3. Capture observer-owned artifacts.
4. Build evidence bundle.
5. Validate bundle and runner receipt.
6. Run deterministic verification.
7. Run advisory review only after deterministic checks.
8. Emit `next` decision.
9. Run at most one `advance`.
10. Append a chain link and stop or repeat under an explicit loop budget.

Every loop iteration must write:

- `capture-manifest.json`
- `observer-capture.json`
- `runner-receipt.json` when Depone launches the runner
- `runner-transcript.json`
- `evidence-bundle.json`
- `ingest-verdict.json`
- `verify-report.json` when deterministic verification is configured
- `evidence-run-summary.json`
- `advance-decision.json` when `advance` is used
- optional `signed-evidence-bundle.json`
- optional `chain.json` as an index over the canonical
  `capture-manifest.prev_capture_hash` links, not a second chain source of
  truth

### 6.3 Team Model

Do not start with a large team runtime. Build a small evidence model first:

- A leader ledger records objective, lanes, budgets, and stop rules.
- Each lane produces an ordinary runner receipt and evidence directory.
- Fan-in requires every lane to pass `next` or be explicitly marked blocked.
- The leader cannot summarize a lane as complete unless its artifacts validate.
- Cross-lane merge conflicts are evidence events, not chat messages.

This lets Depone audit OMX/LazyCodex-style teams before it owns a team runtime.

### 6.4 Isolation Model

Next isolation work should be in this order:

1. Keep the observer-launched uid path stable.
2. Add container/namespace facts when Docker or Podman is available.
3. Record image id, container id, mount mode, network mode, user id inside the
   container, and observer output writability from inside the container.
4. Require artifact revalidation before claiming container A2C.
5. Only then consider VM/firecracker-style isolation.

### 6.5 Signing Model

A3 should not depend on keyless availability at first:

1. Keep existing stdlib key-based signing path working.
2. Add a verifier command that proves a committed signed bundle validates.
3. Add cosign/keyless only when OIDC identity is actually available.
4. If keyless is unavailable, say so in artifacts and stay at key-based A3 or
   unsigned A2.

## 7. Implementation Waves

### Wave 1: Harden Revalidation And Dogfood

Goal: close the current V125 "Now" gap while making `run -> next -> advance`
boring, re-runnable, and easy for agents to use.

Deliverables:

- Harden V128 ingest for external in-toto/DSSE statements and OTel span bundles
  as untrusted inputs: verify subject digests against present artifacts and
  return `inconclusive` or `blocked` on mismatch or missing artifacts.
- Add a single command, helper, or documented unittest path that revalidates
  `docs/depone-advance-one-step/` end to end.
- Wire the existing V129 continuity seam into the one-step path: use
  `capture-manifest.prev_capture_hash` plus `evidence-chain`, not a parallel
  chain field on `advance-decision.json`.
- Run one more installed-`depone` dogfood loop only after the revalidation path
  is deterministic, and commit real artifacts if the capability claim depends
  on them.
- Add a concise agent runbook for local isolated execution.

Acceptance:

- `python3 -m unittest tests.test_evidence_advance tests.test_evidence_next -v`
  passes.
- `python3 scripts/check_contract.py --tier changed` passes.
- The committed one-step artifacts still revalidate to `continue []`, and any
  chain check uses the canonical capture-manifest link.
- V128 external ingest behavior is covered by self-test or unittest cases for
  present, missing, and digest-mismatched artifacts.

### Wave 2: Container A2C

Goal: strengthen A2 from uid-only to container/namespace-observed evidence when
the host supports Docker or Podman.

Deliverables:

- Probe container facts fail-closed.
- Launch runner in a container with a read-only or controlled mount for source
  and a host-owned observer output outside the container write path.
- Record container facts in `isolation`.
- Commit real A2C artifacts only if the host actually proves the boundary.

Acceptance:

- Same-uid/no-container paths stay A1 or A2 uid only.
- Container claim validates independently from committed artifacts.
- No `--runner-container-*` value is trusted unless Depone launched or verified
  it.

### Wave 3: A3 Signing

Goal: make evidence bundles cryptographically verifiable without raising claims
when signatures are absent or unverifiable.

Deliverables:

- Sign `evidence-bundle.json` with the existing key-based path.
- Add `depone attest verify` or extend existing verify-signature ergonomics.
- Commit a signed test artifact with public key and verifier output.
- Add keyless/cosign feasibility probe, but do not require it.

Acceptance:

- Signature verification returns true for committed artifact.
- Tampering manifest, observer capture, or signature metadata blocks.
- Unsigned bundles remain honest and do not claim A3.

### Wave 4: Bounded Loop

Goal: turn `advance` into a budgeted loop without becoming an unchecked agent.

Deliverables:

- Add `loop` over repeated `advance` with `--max-steps`, `--stop-on-blocked`,
  and chain validation.
- Emit `loop-ledger.json`.
- Support resume from the last valid chain head.

Acceptance:

- Missing intermediate step blocks.
- A blocked `next` stops before execution.
- Resume cannot skip or overwrite prior artifacts.

### Wave 5: Team Evidence Ledger

Goal: audit multi-lane agent/team work without owning all execution.

Deliverables:

- Define `team-ledger.json` with objective, lanes, worker receipts, fan-in
  rules, and conflict state.
- Add ingestion for external worker evidence directories.
- Add a leader fan-in command that refuses incomplete or invalid lanes.

Acceptance:

- A lane with only prose cannot pass.
- Conflicting touched files block fan-in unless a merge receipt validates.
- Team ledger can represent OMX/LazyCodex-style runs from artifacts.

### Wave 6: Bench Harness

Goal: measure whether Depone governance helps real work.

Deliverables:

- Local task corpus with direct and governed runs.
- Metrics: correctness, time, token/tool count where available, touched files,
  rework count, review findings, recovery quality.
- Report format that refuses direct superiority claims below minimum sample size.

Acceptance:

- At least six local task classes have re-runnable artifacts.
- Public claims remain blocked until the corpus reaches a declared threshold.
- Benchmark report separates deterministic pass/fail from advisory review.

## 8. Agent Operating Rules

For any agent continuing this roadmap:

1. Start from `origin/main`, not a divergent local `main`.
2. Read `AGENTS.md`, mirrored `CLAUDE.md`, this document, V125, and the command
   docs before editing.
3. Pick one wave slice, not an entire wave.
4. Before coding, identify the artifact that will prove the slice.
5. Use stdlib-only Python. External tools are allowed through subprocess only
   when the environment actually has them.
6. Add self-test or unittest coverage before implementation when changing
   behavior.
7. Commit real artifacts when a capability claim depends on machine state.
8. Never merge a PR if the committed artifacts fail revalidation.
9. Never upgrade assurance from operator prose.
10. Stop at destructive, secret-bearing, production, or history-rewrite steps.

## 9. Immediate Next Slice Recommendation

Pick Wave 1 first.

Reason: PR #37 proved the one-step gate works, but V125 still names V128 ingest
hardening and another installed-`depone` dogfood loop as the next actual product
work. Container isolation and signing remain valuable, but the next agent should
first make the existing evidence path revalidate from present artifacts and
canonical manifest-chain facts. That reduces operator friction and gives every
later A2C, A3, loop, or team slice a stronger base.

Suggested PR:

- Branch: `codex/ingest-chain-revalidation`
- Title: `Harden ingest and chain revalidation`
- Scope:
  - Harden external evidence ingest for missing and digest-mismatched artifacts.
  - Wire or document `evidence-chain` validation for the one-step artifact set
    using `capture-manifest.prev_capture_hash`.
  - Add a revalidation helper or unittest for
    `docs/depone-advance-one-step/`.
  - Update `docs/depone-next-frontdoor.md` with the exact command.
- Anti-scope:
  - No scheduler.
  - No Docker.
  - No signing.
  - No new Agent Fabric roles.

Verification:

```bash
python3 -m unittest tests.test_evidence_advance tests.test_evidence_next -v
python3 -m depone advance --self-test
python3 scripts/check_contract.py --tier changed
python3 scripts/dwm.py doctor
```

## 10. Source Index

- OpenAI Codex sandboxing and approval model:
  <https://developers.openai.com/codex/concepts/sandboxing>
- OpenAI Codex documentation index for workflows, subagents, hooks, AGENTS.md,
  and automation surfaces:
  <https://developers.openai.com/codex>
- GitHub Copilot cloud agent environment and setup steps:
  <https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/customize-the-agent-environment>
- GitHub Copilot cloud agent sessions:
  <https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/start-copilot-sessions>
- Anthropic, "Building Effective Agents":
  <https://www.anthropic.com/engineering/building-effective-agents>
- Anthropic, "How we built our multi-agent research system":
  <https://www.anthropic.com/engineering/multi-agent-research-system>
- Claude Code subagents:
  <https://code.claude.com/docs/en/sub-agents>
- Claude Code hooks:
  <https://code.claude.com/docs/en/hooks>
- Claude Code project memory:
  <https://code.claude.com/docs/en/memory>
- SLSA security levels:
  <https://slsa.dev/spec/v1.1/levels>
- SLSA provenance:
  <https://slsa.dev/spec/v1.1/provenance>
- in-toto Attestation Framework:
  <https://github.com/in-toto/attestation>
- Sigstore Cosign signing and attestations:
  <https://docs.sigstore.dev/cosign/signing/signing_with_containers/>
- OpenTelemetry:
  <https://opentelemetry.io/>
- SWE-bench:
  <https://www.swebench.com/>
