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

The committed fixture intentionally uses a missing binary, so it must return
`decision: blocked`. A blocked receipt is accepted here because the detector is
proving fail-closed behavior, not launch success.

Honest boundary: this fixture does not launch a Codex model session, does not call live models,
does not execute a coding task, does not schedule a team, does not prove a2/container isolation, and does not raise assurance.
