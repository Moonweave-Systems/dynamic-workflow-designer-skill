# Depone Cloud/Team Control Plane

Status: V130 follow-up direction note and Team Ledger v0 slice.  
Date: 2026-06-30.  
Source context: `.omx/context/cloud-team-control-20260630T043433Z.md`.

## Position

Depone should be a cloud-first, local-fallback control and evidence plane over
coding agents, not a replacement coding UX. The durable job is to record what a
runner or team did, revalidate artifacts before continuation, and keep assurance
claims tied to independently checkable evidence.

This keeps the V125/V129 direction intact:

- Depone remains a non-executing design/verify/control layer unless a bounded
  runner command is explicitly invoked.
- Execution systems such as Codex, GitHub Copilot cloud agent, Claude Code,
  Cursor, OpenCode, OMX, LazyCodex-style teams, shell runners, and future
  Depone-native teams are adapters.
- Deterministic checks, receipts, source hashes, and evidence directories are
  the pass/fail authority. LLM review is advisory.
- Team control starts with a small evidence ledger before any Depone-owned team
  scheduler.

## External surfaces to audit, not duplicate

The current market direction is background work, isolated or configured
development environments, branch/PR output, persistent instructions, hooks,
subagents, and permission boundaries:

- OpenAI Codex cloud threads run in an isolated environment, clone the repo, and
  work on a branch; Codex also exposes permissions profiles and PR-oriented Git
  tools for local/worktree tasks. See OpenAI's Codex prompting, permissions, and
  app feature docs.
- GitHub Copilot cloud agent works on GitHub in a GitHub Actions-powered
  environment, can research/plan/change code on a branch, and can open or
  prepare pull requests. Its setup workflow is `.github/workflows/copilot-setup-steps.yml`.
- Claude Code exposes subagents, hooks, permissions, MCP, skills, and SDK
  sessions. Hooks are deterministic lifecycle commands; subagents have their
  own context and permission behavior.
- Cursor Cloud Agents are another cloud/background coding surface. Depone should
  treat them as an adapter whose artifacts and PRs can be audited.

Depone's role is to make those runs auditable, restartable, comparable, and hard
to overclaim. It should not claim competitive superiority or attempt to out-UI
these tools.

## Control-plane boundaries

Depone should distinguish five concepts that are easy to blur:

1. **External team adapters**: Codex, Claude Code, GitHub Copilot cloud agent,
   Cursor, OMX, LazyCodex-style queues, OpenCode, shell, and similar systems.
   They own coding ergonomics and execution.
2. **Depone-native future team runtime**: a possible future scheduler. It is not
   implemented by this slice and should only be added after ledgers prove useful.
3. **Cloud runner**: a future execution environment for `run`/`advance` style
   steps. This slice records `environment_kind: "cloud"` but does not execute in
   the cloud.
4. **Local fallback**: local/worktree/shell execution that can still produce
   evidence and pass the same validators.
5. **Evidence ledger/fan-in**: a leader-level record that every lane either
   passed with evidence or is explicitly blocked with a reason.

## Team Ledger v0

Team Ledger v0 is the first narrow team-control slice. It is deliberately only a
schema plus validator:

- `kind`: `depone-team-ledger`
- `schema_version`: `1.0`
- `objective`: leader objective for the team run
- `leader`: leader lane/worker identity
- `lanes`: lane records with:
  - `lane_id`
  - `environment_kind`: `local`, `container`, or `cloud`
  - `adapter_kind`: external or Depone-native adapter label
  - `start_commit` and `end_commit`
  - `evidence_dir` for passed lanes
  - optional `pr_url`
  - `verification_state`: `pass` or `blocked`
  - `blocked_reason` for blocked lanes

Fan-in is fail-closed:

- empty or malformed lane lists block;
- duplicate lane IDs block;
- invalid environment or adapter kinds block;
- a `pass` lane without an existing evidence directory blocks;
- a `blocked` lane without an explicit reason blocks;
- any blocked lane keeps the ledger verdict `blocked` until the leader resolves
  or accepts that blocked state as the next planning input.

The ledger does not introduce a parallel evidence chain. Continuity remains the
canonical `capture-manifest.prev_capture_hash` plus `evidence-chain` seam.

## Near-term roadmap fit

This slice supports the roadmap without adding source-only control layers:

1. V128/V129 continuity remains first: keep `run -> next -> advance` artifacts
   revalidatable.
2. Team audit comes next as ledger validation over ordinary lane evidence
   directories.
3. Container A2C, signing, cloud runners, GitHub Apps, and full scheduling stay
   future work until evidence proves the smaller seam.

## Sources checked

- OpenAI Codex prompting: <https://developers.openai.com/codex/prompting>
- OpenAI Codex permissions: <https://developers.openai.com/codex/permissions>
- OpenAI Codex app Git features: <https://developers.openai.com/codex/app/features>
- GitHub Copilot cloud agent overview: <https://docs.github.com/copilot/concepts/agents/cloud-agent/about-cloud-agent>
- GitHub Copilot setup environment: <https://docs.github.com/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment>
- Claude Code subagents: <https://docs.anthropic.com/en/docs/claude-code/sub-agents>
- Claude Code hooks guide: <https://docs.anthropic.com/en/docs/claude-code/hooks-guide>
- Claude Code permissions: <https://code.claude.com/docs/en/permissions>
- Cursor Cloud Agents: <https://cursor.com/docs/cloud-agent>
