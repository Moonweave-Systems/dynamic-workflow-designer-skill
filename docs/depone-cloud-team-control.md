# Depone Cloud And Team Control Plane

Date: 2026-06-30.
Status: follow-up direction note plus Team Ledger v0 slice.

Depone's near-term role is a **cloud-first, local-fallback evidence and control
plane** over coding agents and team runtimes. It should observe and validate
runs from Codex, Claude Code, OpenCode, GitHub Copilot-style cloud agents,
OMX/LazyCodex-style local teams, shell adapters, and future Depone-native teams.
It should not replace their coding UX or claim to be a full scheduler yet.

## Position

The current roadmap keeps Depone as a non-executing control/evidence plane:
artifacts and source hashes are the source of truth, deterministic verification
is authoritative, and LLM review remains advisory. The next team direction is to
bind each worker lane to durable evidence before a leader can summarize fan-in.

Cloud agent products increasingly converge on the same operating shape:
background work, isolated development environments, deterministic setup,
project instructions, hooks or permissions, test/build receipts, and pull
request output. Depone should sit above that shape as the neutral verifier:
record what environment was used, which adapter produced the lane, what commits
bounded it, where the evidence lives, and whether deterministic verification
passed or the lane was explicitly blocked.

## Terms

- **External team adapter**: a runner or team system Depone observes, such as
  Codex, Claude Code, OpenCode, GitHub Copilot-style cloud work, OMX, LazyCodex,
  or shell. The adapter owns execution; Depone owns validation of recorded
  artifacts.
- **Depone-native future team runtime**: a possible later scheduler over the same
  ledger and evidence model. It is not implemented in this slice.
- **Cloud runner**: an execution environment outside the local checkout, usually
  background/ephemeral and PR-oriented. This document only defines how Depone
  records cloud lanes; it does not launch cloud jobs.
- **Local fallback**: the same evidence contract can describe a local worktree,
  tmux team, or shell runner when cloud execution is unavailable or unnecessary.
- **Evidence ledger / fan-in**: the leader record that refuses to call a lane
  complete unless its evidence validates, and treats merge conflicts or blocked
  lanes as evidence events rather than chat-only status.

## Team Ledger v0

Team Ledger v0 is the smallest useful evidence model for audited team fan-in.
It records one leader objective and one or more lane records:

- `leader_objective`, `leader_id`, `start_commit`, optional `end_commit`, and a
  `stop_rule`.
- Lane `lane_id`, `objective`, `env_kind` (`local`, `container`, `cloud`),
  `runner_adapter_kind`, `team_adapter_kind`, `start_commit`, `end_commit`,
  `evidence_dir`, optional `pr_url`, and `verification_state` (`pass` or
  `blocked`).
- Passed lanes must have a present evidence directory. Blocked lanes must have a
  non-empty `blocked_reason`.

The validator emits a verdict:

- `pass`: every lane passed and all required evidence is present.
- `blocked-explicit`: no schema/evidence errors, but one or more lanes are
  explicitly blocked with reasons.
- `blocked`: required fields, allowed values, or passed-lane evidence are
  missing/invalid.

This is intentionally not a scheduler. It does not launch agents, call models,
inspect live cloud state, sign bundles, merge PRs, or raise assurance. It gives
later `depone team`, `depone loop`, or cloud-runner work a stable fan-in seam.

## Boundaries And Deferred Work

This slice does **not** implement Docker A2C, signing, a GitHub App, a cloud
runner, a full scheduler, or PR #38 integration. Those remain downstream work
after the current `run -> next -> advance` evidence chain and the
`capture-manifest.prev_capture_hash` continuity seam stay stable.

The next safe extensions are:

1. Convert real OMX/LazyCodex lane receipts into Team Ledger v0 JSON.
2. Require every passed lane to include an evidence-run directory that `next`
   can revalidate.
3. Record merge conflicts as lane or leader evidence events.
4. Only then add container/cloud runner facts or signing.
