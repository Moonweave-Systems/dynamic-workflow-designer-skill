# Team Local Run Ledger

This directory contains the first machine artifact for
`python3 -m depone team-local`.

`team-local` is a minimal local team loop over existing fail-closed primitives:
`team-dry-run`, `team-launch-preflight`, `team-worktree-prep`, one allowlisted
`team-shell-lane-launch` per lane, `evidence-next`, and `team-ledger`. It writes
`team-run-ledger.json` as the fan-in record.

Regenerate the committed fixture with:

```bash
python3 -m depone team-local \
  --plan docs/team-local/team-plan.json \
  --allowlist docs/team-local/allowlist.json \
  --repo . \
  --worktree-root /tmp/depone-team-local-fixture \
  --base-commit c48aa8b8b50f093798e849c82f9e592d7345661d \
  --out-dir docs/team-local \
  --create-worktree \
  --execute-lanes \
  --json
```

The fixture is intentionally blocked. The shell lane runs only the explicit argv
allowlist command, then `evidence-next` blocks because the lane directory is not
a full evidence-run capture. That is the honest boundary for this first slice:
local team sequencing exists, but passed lane completion still requires a real
evidence bundle.

Independent re-validation:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from depone.agent_fabric.team_local import validate_team_local_run_ledger
m=json.load(open("docs/team-local/team-run-ledger.json"))
print("team-local decision:", m.get("decision"))
print("validate errors:", validate_team_local_run_ledger(m, base_dir=Path(".")))
print("boundary:", m.get("boundary"))
PY
```

Expected output:

```text
team-local decision: blocked
validate errors: []
boundary: {'approves_merge': False, 'calls_live_models': False, 'creates_worktrees': True, 'executes_allowlisted_shell_commands': True, 'executes_unlisted_shell_commands': False, 'launches_agents': False, 'raises_assurance': False}
```

Honest boundary: this command may create or select local git worktrees and run
allowlisted shell argv commands. It does not launch live models, Codex, Claude,
OpenCode, coding-agent sessions, or a team scheduler. It does not execute
unlisted shell commands, approve merges, prove A2/container isolation, or raise
assurance.

Contract wording: does not execute unlisted shell commands; does not raise assurance.
