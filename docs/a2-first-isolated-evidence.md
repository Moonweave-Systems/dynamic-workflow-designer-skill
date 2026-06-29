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

The runner-side repo mutation was seeded under `/srv/depone/sandbox` by running
the git work as `deponerun`:

```text
1002
```

That printed uid matched `id -u deponerun`, so `--runner-uid 1002` reflected the
uid that actually performed the runner work.

## Evidence-run boundary

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

The nested observer output directories were also tightened to mode `0700`:

```text
/home/ubuntu/observer-owned ubuntu 700
/home/ubuntu/observer-owned/evidence-run ubuntu 700
/home/ubuntu/observer-owned/evidence-run/observer-owned ubuntu 700
```

## Capture note

An initial attempt returned `A1-local-observed` because `evidence-run` probes the
nested output path `/home/ubuntu/observer-owned/evidence-run/observer-owned`.
That nested directory had been auto-created as mode `775`, causing Depone to
fail closed and record `observer_dir_writable_by_runner: true` even though the
top-level observer directory was mode `700`.

After setting the nested evidence-run directories to mode `700`, the same
observer capture emitted:

```json
{
  "observer_assurance": "A2-isolated-observed",
  "privilege_isolated": true
}
```

The `evidence-run` command still exited with status `2` because the optional
final Depone verify stage was not provided and the aggregate `decision` remained
`inconclusive`. The A2 boundary claim itself was emitted by the tool and recorded
in `boundary`.
