# Team Worktree Prep Evidence

This directory contains the first machine artifact for Wave 2 local worktree
preparation.

The artifact was generated with:

```bash
python3 -m depone team-worktree-prep \
  --team-launch-preflight docs/team-launch-preflight/team-launch-preflight.json \
  --repo . \
  --worktree-root /tmp/depone-team-worktree-prep-fixture \
  --create-worktree \
  --out docs/team-worktree-prep/team-worktree-prep.json \
  --json
```

`team-worktree-prep` consumes a passing `team-launch-preflight.json`, resolves
each planned worktree under `--worktree-root`, and writes
`team-worktree-prep.json`. It may run `git worktree add --detach` only when
`--create-worktree` is present.

Boundary:

- it may create or select local git worktrees;
- it does not launch agents;
- it does not execute lane commands;
- it does not call live models;
- it does not delete worktrees;
- it does not raise assurance;
- it does not prove task completion.

Independent re-validation:

```bash
python3 - <<'PY'
import json
from depone.agent_fabric.team_worktree_prep import validate_team_worktree_prep
m=json.load(open("docs/team-worktree-prep/team-worktree-prep.json"))
print("worktree prep decision:", m.get("decision"))
print("validate errors:", validate_team_worktree_prep(m))
print("boundary:", m.get("boundary"))
PY
```

Expected output:

```text
worktree prep decision: pass
validate errors: []
boundary: {'calls_live_models': False, 'create_worktree_requested': True, 'deletes_worktrees': False, 'executes_lane_commands': False, 'launches_agents': False, 'raises_assurance': False, 'runs_git_worktree_add': True}
```

Honest residual: the committed artifact records host paths from the capture
machine. A fresh clone can revalidate the JSON schema and boundary fields, but
it should re-run the command to recreate local worktrees on that host.
