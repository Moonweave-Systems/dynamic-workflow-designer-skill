# Depone Cloud/Team Control Plane

Status: architecture direction plus first Team Ledger v0 slice.  
Date: 2026-06-30.

This document extends `docs/v125-direction-check-roadmap.md` and
`docs/depone-agent-execution-roadmap.md`. Those documents remain the product
source of truth: Depone is a non-executing design and evidence plane, not a
replacement coding agent, cloud runner, or scheduler.

## Position

Depone should be the neutral control and evidence layer over increasingly
cloud-first coding agents and small agent teams while keeping Depone's own
trust anchor local-first and stdlib-only. Codex, Claude Code, GitHub
Copilot, Cursor, OpenCode, OMX, LazyCodex-style teams, shell runners, and future
Depone-native lanes are adapter surfaces. Depone's job is to record what they
claimed, what artifacts they produced, what deterministic checks passed, and
whether the next step is allowed from verified evidence.

The first implementation slice is deliberately small: Team Ledger v0 validates a
leader ledger over lane records. It does not schedule work, launch cloud agents,
merge pull requests, provision containers, sign evidence, or replace a team
runtime.

## External direction to interoperate with

These surfaces are moving toward background/cloud work, PR-oriented output,
custom setup, hooks, permissions, and team ergonomics:

- OpenAI Codex cloud can run delegated tasks in the background using a cloud
  environment; Codex cloud environments describe container checkout, setup
  scripts, and internet access settings. See
  <https://developers.openai.com/codex/cloud> and
  <https://developers.openai.com/codex/cloud/environments>.
- GitHub Copilot cloud agent sessions are started and managed from GitHub
  surfaces, with customization paths for cloud-agent environments, hooks,
  secrets, firewalls, and agent settings. See
  <https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/start-copilot-sessions>.
- Claude Code exposes local/team ergonomics such as hooks, subagents, and
  permission-oriented control surfaces. See
  <https://code.claude.com/docs/en/hooks>.
- Cursor Cloud Agents run agent work in the cloud for continuous coding
  assistance and expose a run-based API. See
  <https://cursor.com/docs/cloud-agent> and
  <https://cursor.com/docs/cloud-agent/api/endpoints>.

Depone should not overclaim superiority over these systems. It should make their
runs auditable and restartable by binding adapter facts to source hashes,
receipts, evidence directories, and deterministic verification.

## Architecture boundaries

### External team adapters

External adapters are systems Depone observes or audits without owning their
execution loop. Examples include Codex cloud tasks, GitHub Copilot cloud agent,
Claude Code subagents, Cursor Cloud Agents, OpenCode, shell scripts, and
OMX/LazyCodex-style local teams.

Depone records adapter kind, environment kind, commits, evidence directories,
verification state, and PR URLs when present. Adapter-specific UX remains outside
Depone.

### Depone-native future team runtime

A future `depone team` may coordinate multiple lanes, but only after the evidence
model is boring and useful. The near-term invariant is simpler: every lane must
produce verifiable artifacts or be explicitly blocked. The leader cannot convert
chat summaries into completed evidence.

### Cloud runner

A cloud runner would provision or observe remote/cloud execution. This slice does
not implement one. Cloud is only a value for `environment_kind` in the ledger, so
an externally produced cloud lane can be represented honestly.

### Local fallback

Local fallback remains first-class and is the default trust anchor for Depone
itself. A lane can be `local` with an adapter such as `omx`, `codex`,
`claude-code`, `opencode`, or `shell`. Local lanes still need an evidence
directory when they claim `pass`.

### Evidence ledger and fan-in

Team Ledger v0 is a fan-in gate. A ledger records:

- leader objective, optional leader/budget/stop-rule metadata,
- lanes with environment kind (`local`, `container`, or `cloud`),
- adapter kind (`codex`, `claude-code`, `cursor`, `github-copilot`, `omx`,
  `lazycodex`, `opencode`, `depone-native`, `shell`, or `other`),
- start and end commits,
- evidence directory for passed lanes,
- optional PR URL,
- verification state (`pass` or `blocked`),
- blocked reason for blocked lanes.

Fan-in passes only when every lane is either:

1. `pass` with an existing evidence directory; or
2. `blocked` with an explicit reason.

A lane with prose only cannot pass. Missing evidence, unknown environment kind,
unknown adapter kind, duplicate lane ids, or a blocked lane without a reason
blocks the ledger.

## Team Ledger v0 schema sketch

```json
{
  "kind": "depone-team-ledger",
  "schema_version": "0.1",
  "objective": "ship one reviewed control-plane slice",
  "leader": "leader-fixed",
  "budget": "one small branch",
  "stop_rule": "stop after deterministic verification",
  "lanes": [
    {
      "lane_id": "worker-1",
      "role": "executor",
      "environment_kind": "local",
      "adapter_kind": "omx",
      "start_commit": "abc123",
      "end_commit": "def456",
      "evidence_dir": "out/team/worker-1",
      "pr_url": "https://github.com/example/repo/pull/123",
      "verification_state": "pass",
      "next_decision": "pass"
    },
    {
      "lane_id": "worker-2",
      "environment_kind": "cloud",
      "adapter_kind": "codex",
      "start_commit": "abc123",
      "end_commit": "abc123",
      "verification_state": "blocked",
      "blocked_reason": "required cloud setup secret unavailable"
    }
  ]
}
```

Validate with:

```bash
python3 -m depone team-ledger --ledger team-ledger.json --out team-ledger-verdict.json
python3 -m depone team-ledger --self-test
```

## Non-goals for this slice

- No PR #38 merge or modification.
- No Docker A2C implementation.
- No signing or Sigstore/keyless work.
- No cloud runner, GitHub App, or full scheduler.
- No claim that Team Ledger v0 proves adapter correctness beyond the recorded
  deterministic facts.

## Next slices

1. Add ingestion for external worker evidence directories and `evidence-next`
   verdicts, so a pass lane requires more than directory presence.
2. Record conflict events when lanes touch overlapping files, then require a
   merge receipt before fan-in can pass.
3. Add optional PR artifact checks for cloud adapters.
4. Only after the ledger is useful, consider a minimal `depone team` command that
   coordinates lanes under explicit budgets and stop rules.
