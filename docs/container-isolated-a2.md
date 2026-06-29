# Container-Isolated A2 Evidence

Task id: `server-next-rung`

Slice: `container-isolated-a2`

Date: 2026-06-29

## Summary

Depone produced an `A2-isolated-observed` capture from an observer-launched
Docker runner container. The runner container wrote the sandbox change through
`/srv/depone/sandbox:/work`; the observer output directory was not mounted into
the container. The committed manifest records both the Docker launch receipt in
`observer_capture.runner_container_launch` and the Docker-inspected isolation
facts in `isolation.container`.

The machine artifacts are committed under `docs/container-isolated-a2/`:

- `capture-manifest.json`
- `evidence-run-summary.json`

These JSON artifacts are the source of truth. The manifest can be independently
re-validated with:

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

## Honest Residuals

This is still A2, not A3. It is unsigned content-addressed evidence and does not
prove keyless identity, transparency-log inclusion, remote attestation, or that
Depone will launch every future runner itself. It records an observer-launched,
Docker-inspected container fact set and validates it against the existing A2
manifest rules.
