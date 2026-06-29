# Container-Isolated A2 Spec

Task id: `server-next-rung`

Slice: `container-isolated-a2`

Status: implementation-ready spec

Date: 2026-06-29

## Decision

The next Depone rung should be container-isolated A2. The first A2 proof showed a
real uid boundary between runner and observer. The next useful step is not a new
agent runtime and not keyless A3; it is a stronger runner boundary that matches
how long-running coding agents are actually operated: runner work happens in an
isolated environment, while observer evidence is produced outside the runner's
write reach.

Docker is available on the target server and a minimal container run was proven:

```text
$ docker run --rm alpine:3.20 sh -c 'id -u; test -f /etc/os-release; echo container-ok'
0
container-ok
```

## Why This Slice

Container isolation is the smallest next step that improves real personal use.
It makes it harder for a coding agent process to modify the evidence that judges
its own run. This aligns with Depone's core rule: agents may execute work, but
artifacts outside the runner's reach are the source of truth.

This slice deliberately does not implement A3 signing, Sigstore, Rekor,
multi-hop delegation, or a full agent launcher. Those are follow-ons.

## Trust Model

Container-isolated A2 is an A2 variant, not a new assurance label. It still emits
`A2-isolated-observed` only when all required facts hold.

Required facts:

- The observer process runs on the host.
- The observer launches the runner container and records the launch receipt in
  the observer capture.
- The observer-owned output directory is outside the runner container's writable
  mounts.
- The observer records container facts from `docker inspect`, not from runner
  self-report.
- The inspected container id is the id returned by the observer-launched Docker
  run, not a free-form operator-supplied id.
- The capture manifest validates with `validate_capture_manifest(...) == []`.

Fail-closed cases:

- Docker is unavailable or the container facts are missing.
- The observer output directory is mounted writable into the runner container.
- The container id is externally supplied rather than observer-launched.
- The supplied container id cannot be inspected by the observer.
- The runner uid inside the container cannot be recorded as a numeric uid.
- The recorded runner and observer boundary cannot be verified from the manifest.
- The capture is only prose and lacks committed machine artifacts.

## Data Shape

`isolation` should preserve the existing A2 fields and add container-specific
facts without breaking old manifests:

```json
{
  "model": "container-boundary-unwritable-observer-dir",
  "boundary": true,
  "runner_uid": 0,
  "observer_uid": 1001,
  "observer_dir_writable_by_runner": false,
  "container": {
    "runtime": "docker",
    "container_id": "...",
    "image": "alpine:3.20",
    "observer_launched": true,
    "running": true,
    "observer_dir_mounted_rw": false,
    "mounts": []
  },
  "reasons": []
}
```

The container subobject is evidence metadata. It must not raise assurance by
itself. The A2 raise still depends on `boundary: true`, an unwritable observer
dir, an observer-launched and Docker-inspected container fact set, and validation
of the committed manifest.

## Implementation Boundary

The first implementation PR should stay small:

- Extend `depone/agent_fabric/isolation.py` with a pure verifier for container
  isolation facts and self-tests for pass/fail cases.
- Add an observer-side Docker probe that runs `docker inspect`, records
  image/running/mount facts, and fails closed if Docker is unavailable or the
  container cannot be inspected.
- Extend `depone/cli/evidence_run.py` only enough to launch a runner container,
  record the launch receipt in the observer capture, call the Docker probe on the
  returned container id, and pass the resulting isolation facts to the existing
  manifest builder. A free-form retained container id may record facts but must
  not raise assurance to A2.
- Preserve the existing uid A2 behavior and manifest compatibility.
- Add a real Docker-backed capture under `docs/container-isolated-a2/` with:
  - `capture-manifest.json`
  - `evidence-run-summary.json`
- Add a short markdown note that points to those JSON artifacts rather than
  retyping the claim as the source of truth.

The implementation must not add Python dependencies. Docker may be used as an
external tool through subprocess or shell invocation.

## Independent Re-Validation

The PR must include a command like:

```bash
python3 - <<'PY'
import json
from depone.agent_fabric.capture_bridge import validate_capture_manifest, _sha256_json
from depone.agent_fabric.isolation import verify_isolation_boundary

m = json.load(open("docs/container-isolated-a2/capture-manifest.json"))
errs = validate_capture_manifest(m)
iso = m.get("isolation", {})
print("assurance        :", m.get("assurance"))
print("validate errors  :", errs)
print("isolation_hash OK:", m.get("isolation_hash") == _sha256_json(iso))
print("boundary reverify:", verify_isolation_boundary(iso).get("boundary"))
print("model            :", iso.get("model"))
print("observer launched:", iso.get("container", {}).get("observer_launched"))
print("MERGE_OK:", (
    m.get("assurance") == "A2-isolated-observed"
    and errs == []
    and verify_isolation_boundary(iso).get("boundary") is True
    and iso.get("model") == "container-boundary-unwritable-observer-dir"
    and iso.get("container", {}).get("observer_launched") is True
))
PY
```

Expected successful output must include:

```text
assurance        : A2-isolated-observed
validate errors  : []
isolation_hash OK: True
boundary reverify: True
model            : container-boundary-unwritable-observer-dir
observer launched: True
MERGE_OK: True
```

## Honest Residuals

This slice records and re-validates a Docker-inspected container boundary from
observer-produced facts and committed artifacts. It does not prove keyless
identity, transparency-log inclusion, remote attestation, or that every future
agent task will be launched by Depone. Closing the uid-based `--runner-uid`
trust residual for the non-container path remains a separate follow-on.
