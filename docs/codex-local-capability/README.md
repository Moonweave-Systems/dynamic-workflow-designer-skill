# Codex Local Capability

This directory contains a committed capability-only fixture for
`python3 -m depone codex-local-capability`.

The command detects local Codex adapter readiness without launching a live model
or executing a coding task. It records Codex binary lookup, version output when
available, git repo facts, requested sandbox and approval policy, instruction
file hashes, `agent_contract_hash`, and boundary flags.

Regenerate the committed fixture:

```bash
python3 -m depone codex-local-capability \
  --repo . \
  --codex-binary definitely-missing-codex-for-committed-fixture \
  --instruction-file AGENTS.md \
  --instruction-file CLAUDE.md \
  --out docs/codex-local-capability/capability.json \
  --json
```

The committed `capability.json` fixture intentionally uses a missing binary, so
it must return `decision: blocked`. A blocked receipt is accepted here because
the detector is proving fail-closed behavior, not launch success.

A committed `pass-capability.json` may be added only when the capture can be
proved from capability-only facts: `codex --version`, a clean git worktree,
supported sandbox and approval values, and observable instruction file hashes.
Do not create a pass fixture by reading auth state, environment secrets, Codex
configuration contents, or private token files. If the pass fixture cannot be
made stable and revalidatable from committed facts, leave it absent and keep the
blocked fixture as the committed evidence.

`scripts/check_contract.py --tier changed` validates every committed JSON
fixture in this directory. The contract re-runs the capability validator, checks
the safety boundary flags, rejects secret/auth fragments, confirms the requested
runtime values, and recomputes instruction-file hashes. The default
`capability.json` fixture must remain a missing-binary `decision: blocked`
receipt; an optional `pass-capability.json` still proves only local capability
and not a live model launch.

Honest boundary: these fixtures do not launch a Codex model session, do not call
live models, do not execute a coding task, do not schedule a team, do not prove
a2/container isolation, and do not raise assurance.
Contract wording: this capability evidence does not launch a Codex model session; does not execute a coding task; does not prove a2/container isolation; and does not raise assurance.
