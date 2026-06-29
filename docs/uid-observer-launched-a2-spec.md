# Observer-Launched UID A2 Spec

Task id: `server-next-rung`

Slice: `uid-observer-launched-a2`

Status: implementation-ready spec

Date: 2026-06-29

## Decision

Depone should keep the original uid A2 artifact valid, but add a stronger uid
path where the observer launches the runner user itself. This closes the main
trust residual in `--runner-uid`: the operator no longer supplies a bare uid as
the reason for A2. Instead, `evidence-run` records a launch receipt from
`sudo -u <runner-user> bash -lc ...`, captures the uid observed inside that same
shell, and only then probes the observer-owned output directory.

This is still A2, not A3. It proves a host uid boundary and an unwritable
observer directory from observer-produced facts; it does not add cryptographic
signing or remote attestation.

## Trust Model

The stronger uid model is:

```text
uid-boundary-observer-launched-unwritable-observer-dir
```

Required facts:

- The observer process launches the runner command as `--runner-user`.
- The runner command receipt records the configured user uid and the uid observed
  inside the same launched shell.
- The observed runner uid differs from the observer uid.
- The observer-owned output directory is not writable by the runner uid.
- The committed capture manifest re-validates with
  `validate_capture_manifest(...) == []`.

Fail-closed cases:

- `--runner-user` and `--runner-command` are not provided together.
- `sudo` is unavailable.
- The launched shell fails, omits the uid marker, or reports a uid mismatch.
- The observer directory is writable by the runner.
- The isolation object omits `observer_launched: true`.

## Implementation Boundary

This slice stays intentionally small:

- Add a new uid isolation model while preserving legacy
  `uid-boundary-unwritable-observer-dir` artifact compatibility.
- Add `evidence-run --runner-user ... --runner-command ...`.
- Record `observer_capture.runner_uid_launch`.
- Add tests for the new isolation model, fail-closed launch requirement, and uid
  launch receipt parsing.
- Commit real machine artifacts under `docs/uid-observer-launched-a2/`.

## Independent Re-Validation

```bash
python3 - <<'PY'
import json
from depone.agent_fabric.capture_bridge import validate_capture_manifest, _sha256_json
from depone.agent_fabric.isolation import verify_isolation_boundary

m = json.load(open("docs/uid-observer-launched-a2/capture-manifest.json"))
errs = validate_capture_manifest(m)
iso = m.get("isolation", {})
launch = m.get("observer_capture", {}).get("runner_uid_launch", {})
print("assurance        :", m.get("assurance"))
print("validate errors  :", errs)
print("isolation_hash OK:", m.get("isolation_hash") == _sha256_json(iso))
print("observer_hash OK :", m.get("observer_capture_hash") == _sha256_json(m.get("observer_capture")))
print("boundary reverify:", verify_isolation_boundary(iso).get("boundary"))
print("model            :", iso.get("model"))
print("observer launched:", iso.get("observer_launched"))
print("launch observed  :", launch.get("observed_uid"), "as", launch.get("user"))
print("MERGE_OK:", (
    m.get("assurance") == "A2-isolated-observed"
    and errs == []
    and verify_isolation_boundary(iso).get("boundary") is True
    and iso.get("model") == "uid-boundary-observer-launched-unwritable-observer-dir"
    and iso.get("observer_launched") is True
    and launch.get("observed_uid") == iso.get("runner_uid")
    and iso.get("runner_uid") != iso.get("observer_uid")
))
PY
```

Expected successful output must include `MERGE_OK: True`.

## Honest Residuals

This strengthens uid A2 by binding the runner uid to an observer launch receipt.
It does not make the bundle cryptographically unforgeable; signing remains an A3
follow-on. The legacy `--runner-uid` path remains available for existing
artifacts and externally attested captures, but new host-uid evidence should use
`--runner-user` and `--runner-command`.

The observer-launched uid path intentionally records the exact invocation. The
current implementation runs the operator-supplied command through
`sudo -u <runner-user> bash -lc ...`; therefore the runner user's shell
environment and shell startup behavior are part of the observed run. This does
not weaken the uid boundary check, but it means the receipt is host/shell
specific rather than a hermetic execution transcript.
