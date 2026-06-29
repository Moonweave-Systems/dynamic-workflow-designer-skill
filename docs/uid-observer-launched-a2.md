# Observer-Launched UID A2 Evidence

Task id: `server-next-rung`

Slice: `uid-observer-launched-a2`

Date: 2026-06-29

## Summary

Depone produced an `A2-isolated-observed` capture where the observer launched
the runner work as `deponerun` through the new `--runner-user` /
`--runner-command` path. The machine artifacts are committed under
`docs/uid-observer-launched-a2/`:

- `capture-manifest.json`
- `evidence-run-summary.json`

The JSON artifacts are the source of truth. The manifest records:

- `observer_capture.runner_uid_launch`: the observer-side `sudo -u deponerun`
  launch receipt, including the uid observed inside the launched shell.
- `isolation.model`: `uid-boundary-observer-launched-unwritable-observer-dir`.
- `isolation.observer_launched`: `true`.
- `isolation.runner_uid`: `1002`.
- `isolation.observer_uid`: `1001`.
- `isolation.observer_dir_writable_by_runner`: `false`.

Re-validate the committed artifact with the command in
`docs/uid-observer-launched-a2-spec.md`.

## Honest Residuals

This is a stronger uid-based A2 capture than the legacy bare `--runner-uid`
path, because the observer launched the runner and recorded the launch receipt.
It is still unsigned A2 evidence, not A3 signing or remote attestation.

The launch receipt is host/shell specific: `evidence-run` currently invokes the
runner command through `sudo -u <runner-user> bash -lc ...`, so the runner
user's shell environment is part of the observed execution.
