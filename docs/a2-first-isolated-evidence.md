# Depone A2 First Isolated Evidence

Task id: `a2-first-isolated-evidence`

Profile: `server-isolation-setup`

Role: `observer-orchestrator`

Date: 2026-06-29

## Summary

Depone produced its first genuine `A2-isolated-observed` capture on an isolated
Ubuntu server. The runner work executed as OS user `deponerun` with uid `1002`,
while the observer ran as uid `1001`. The observer output directory was owned by
the observer and not writable by the runner.

The machine artifacts are committed under
`docs/a2-first-isolated-evidence/`:

- `capture-manifest.json`
- `evidence-run-summary.json`

These JSON artifacts are the source of truth for the A2 claim. The manifest can
be re-validated with:

```bash
python3 - <<'PY'
import json
from depone.agent_fabric.capture_bridge import validate_capture_manifest
m=json.load(open("docs/a2-first-isolated-evidence/capture-manifest.json"))
print("assurance:", m.get("assurance"))
print("validate errors:", validate_capture_manifest(m))
PY
```

The runner-side repo mutation was seeded under `/srv/depone/sandbox` by running
the git work as `deponerun`:

```text
1002
```

That printed uid matched `id -u deponerun`, so `--runner-uid 1002` reflected the
uid that actually performed the runner work.

## Evidence-run boundary

The boundary below is recorded in
`docs/a2-first-isolated-evidence/evidence-run-summary.json`.

```json
{
  "isolation": {
    "boundary": true,
    "model": "uid-boundary-unwritable-observer-dir",
    "observer_dir_writable_by_runner": false,
    "observer_uid": 1001,
    "reasons": [],
    "runner_uid": 1002
  },
  "note": "A2 isolated observed: runner ran under a different uid and could not write the observer output.",
  "observer_assurance": "A2-isolated-observed",
  "privilege_isolated": true
}
```

## Host facts

```text
$ stat -c '%U %a' "$HOME/observer-owned"
ubuntu 700

$ id -u deponerun
1002

$ id -u
1001
```

The runner could not write the observer-owned output directory:

```text
$ sudo -u deponerun bash -lc 'test -w /home/ubuntu/observer-owned && echo writable || echo not-writable'
not-writable
```

The evidence-run command on main commit `792c054` hardened its nested observer
directories to mode `0700` without manual chmod:

```text
/home/ubuntu/observer-owned ubuntu 700
/home/ubuntu/observer-owned/evidence-run ubuntu 700
/home/ubuntu/observer-owned/evidence-run/observer-owned ubuntu 700
```

## Capture note

The `evidence-run` command still exited with status `2` because the optional
final Depone verify stage was not provided and the aggregate `decision` remained
`inconclusive`. The A2 boundary claim itself was emitted by the tool and recorded
in the committed `boundary` object.
