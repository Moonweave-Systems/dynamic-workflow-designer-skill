# Depone Cloud/Team Control Plane

Status: V130 follow-up direction note and Team Ledger v0 merge-receipt slice.
Date: 2026-06-30.
Source context: `.omx/context/cloud-team-control-20260630T043433Z.md`.

## Position

Depone should be the neutral control and evidence layer over increasingly
cloud-first coding agents and small agent teams while keeping Depone's own
trust anchor local-first and stdlib-only. Codex, Claude Code, GitHub
Copilot, Cursor, OpenCode, OMX, LazyCodex-style teams, shell runners, and future
Depone-native lanes are adapter surfaces. Depone's job is to record what they
claimed, what artifacts they produced, what deterministic checks passed, and
whether the next step is allowed from verified evidence.

The first implementation slices are deliberately small: Team Ledger v0 validates
a leader ledger over lane records, passed lanes must point at a machine
`evidence-next` verdict that revalidated their evidence directory, and
overlapping passed lanes must point at a passing merge receipt before fan-in can
pass. It does not schedule work, launch cloud agents, merge pull requests,
provision containers, sign evidence, or replace a team runtime.

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
- runner and team adapter kind (`codex`, `claude-code`, `github-copilot`,
  `omx`, `lazycodex`, `opencode`, `depone-native`, `shell`, `external`, or
  a later explicitly modeled adapter),
- start and end commits,
- evidence directory and `evidence-next` verdict for passed lanes,
- optional touched files and a top-level merge receipt when passed lanes overlap,
- optional PR URL,
- verification state (`pass` or `blocked`),
- blocked reason for blocked lanes.

Fan-in passes only when every lane is either:

1. `pass` with an existing evidence directory and an `evidence-next` verdict
   whose `decision` is `continue` and `blocking_reasons` is empty; or
2. `blocked` with an explicit reason.

A lane with prose only cannot pass. Missing evidence, missing or blocked
`evidence-next` verdicts, overlapping passed-lane touched files without a
passing merge receipt, unknown environment kind, unknown adapter kind, duplicate
lane ids, or a blocked lane without a reason blocks the ledger.

## Team Ledger v0 schema sketch

```json
{
  "kind": "depone-team-ledger",
  "schema_version": "0.1",
  "leader_objective": "ship one reviewed control-plane slice",
  "leader_id": "leader-fixed",
  "start_commit": "abc123",
  "stop_rule": "stop after deterministic verification",
  "merge_receipt": "out/team/team-merge-receipt.json",
  "lanes": [
    {
      "lane_id": "worker-1",
      "objective": "implement the ledger validator",
      "env_kind": "local",
      "runner_adapter_kind": "codex",
      "team_adapter_kind": "omx",
      "start_commit": "abc123",
      "end_commit": "def456",
      "evidence_dir": "out/team/worker-1",
      "evidence_next_verdict": "out/team/worker-1/evidence-next-verdict.json",
      "worktree_receipt": "out/team/worker-1/worktree-receipt.json",
      "touched_files": ["depone/agent_fabric/team_ledger.py"],
      "pr_url": "https://github.com/example/repo/pull/123",
      "pr_artifact": "out/team/worker-1/pr-artifact.json",
      "verification_state": "pass",
      "verification_artifacts": ["unit-tests", "contract"]
    },
    {
      "lane_id": "worker-2",
      "objective": "run a cloud adapter lane",
      "env_kind": "cloud",
      "runner_adapter_kind": "codex",
      "team_adapter_kind": "external",
      "start_commit": "abc123",
      "end_commit": "abc123",
      "evidence_dir": "out/team/worker-2",
      "verification_state": "blocked",
      "blocked_reason": "required cloud setup secret unavailable"
    }
  ]
}
```

When a local lane includes `worktree_receipt`, it points at a machine JSON
receipt captured from read-only git state. The receipt is optional, but once
present it must match the lane `start_commit`, `end_commit`, `evidence_dir`, and
`touched_files`. Dirty receipts fail closed for passed-lane fan-in:

```json
{
  "kind": "depone-worktree-lane-receipt",
  "schema_version": "0.1",
  "worktree": "/tmp/depone-worker-1",
  "branch": "codex/lane-docs",
  "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "head_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "dirty": false,
  "dirty_files": [],
  "changed_files": ["depone/agent_fabric/team_ledger.py"],
  "evidence_dir": "out/team/worker-1",
  "command_receipts": [
    {"command": "python3 -m unittest", "exit_code": 0}
  ],
  "boundary": {
    "executes_commands": false,
    "launches_agents": false,
    "mutates_worktree": false,
    "git_read_only": true
  }
}
```

When `merge_receipt` is required, it points at a machine JSON receipt:

```json
{
  "command": "team-ledger-merge-receipt",
  "schema_version": "1.0",
  "decision": "pass",
  "lanes": ["worker-1", "worker-2"],
  "files": ["depone/agent_fabric/team_ledger.py"],
  "conflict_events": []
}
```

Passed lanes must include non-empty `touched_files` so the ledger can decide
whether a merge receipt is required. Omitted or empty `touched_files` fails
closed instead of treating the lane as non-overlapping.

When a lane includes `pr_artifact`, it points at a local JSON artifact captured
from a PR surface rather than trusting the `pr_url` as prose. The artifact is
optional, but once present it must validate and its `head_sha` must match the
lane `end_commit`:

```json
{
  "kind": "depone-team-ledger-pr-artifact",
  "schema_version": "0.1",
  "provider": "github",
  "pr_number": 123,
  "pr_url": "https://github.com/example/repo/pull/123",
  "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "head_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "state": "OPEN",
  "merge_state_status": "CLEAN",
  "check_summary": {
    "status": "pass",
    "total_count": 3,
    "failed_count": 0,
    "pending_count": 0
  },
  "stale": false,
  "captured_at": "2026-06-30T06:30:00Z"
}
```

Validate with:

```bash
python3 -m depone team-ledger-merge-receipt --lane worker-1 --lane worker-2 --file depone/agent_fabric/team_ledger.py --out out/team/team-merge-receipt.json --json
python3 -m depone worktree-lane-receipt --worktree ./worker-1 --base-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa --evidence-dir out/team/worker-1 --out out/team/worker-1/worktree-receipt.json --json
python3 -m depone team-ledger --ledger team-ledger.json --out team-ledger-verdict.json
python3 -m depone team-ledger --self-test
```

## Non-goals for this slice

- No PR #38 merge or modification.
- No Docker A2C implementation.
- No signing or Sigstore/keyless work.
- No cloud runner, GitHub App, or full scheduler.
- No automatic git merge, conflict resolution, or worktree orchestration.
- No claim that a worktree receipt proves cloud execution, identity, or runtime
  isolation; it only binds local git facts for a lane.
- No claim that Team Ledger v0 proves adapter correctness beyond the recorded
  deterministic facts.

## Next slices

The current follow-up order is tracked in `docs/depone-next-work-plan.md`.

1. Optional PR artifact checks for Team Ledger lanes are implemented.
2. Local worktree lane receipts are the current slice.
3. Only after those artifacts are useful, consider a minimal `depone team`
   command that coordinates lanes under explicit budgets and stop rules.
