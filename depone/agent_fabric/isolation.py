"""Privilege-boundary verification for A2 isolated-observer capture.

A1 evidence is observer-owned but same-uid: the runner could in principle write
the observer's output, so the chain caps at A1. A2 requires a real boundary the
runner cannot cross. This module is the gate that keeps A2 honest: it verifies,
from facts the observer can attest on an isolated host, that the runner ran under
a different OS uid than the observer and that the observer's output directory is
not writable by the runner. On a same-uid host (e.g. WSL1) the boundary cannot
hold, so the verifier returns ``boundary: False`` and capture stays A1.

The verifier is pure and environment-independent (testable by simulation); the
probe gathers the real facts and only runs meaningfully on an isolated POSIX
host.
"""

from __future__ import annotations

import os
import json
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

ISOLATION_MODEL = "uid-boundary-unwritable-observer-dir"
CONTAINER_ISOLATION_MODEL = "container-boundary-unwritable-observer-dir"


def verify_isolation_boundary(facts: Any) -> dict[str, Any]:
    """Decide whether the supplied facts establish a real privilege boundary.

    Fail-closed: ``boundary`` is True only when both uids are known and differ
    AND the observer directory is proven not writable by the runner. Any unknown
    fact keeps the boundary False, so a missing or partial attestation can never
    be upgraded to A2.
    """

    reasons: list[str] = []
    if not isinstance(facts, dict):
        return {
            "model": ISOLATION_MODEL,
            "boundary": False,
            "runner_uid": None,
            "observer_uid": None,
            "observer_dir_writable_by_runner": None,
            "reasons": ["isolation facts must be an object"],
        }

    model = facts.get("model", ISOLATION_MODEL)
    if model == CONTAINER_ISOLATION_MODEL:
        return _verify_container_isolation_boundary(facts)
    if model != ISOLATION_MODEL:
        return {
            "model": model if isinstance(model, str) else None,
            "boundary": False,
            "runner_uid": None,
            "observer_uid": None,
            "observer_dir_writable_by_runner": None,
            "reasons": ["unknown isolation model"],
        }

    runner_uid = facts.get("runner_uid")
    observer_uid = facts.get("observer_uid")
    writable = facts.get("observer_dir_writable_by_runner")
    boundary = True

    if not isinstance(runner_uid, int) or not isinstance(observer_uid, int):
        boundary = False
        reasons.append("runner_uid and observer_uid must both be known integers")
    elif runner_uid == observer_uid:
        boundary = False
        reasons.append("runner and observer share the same uid (no privilege boundary)")

    if writable is not False:
        boundary = False
        reasons.append("observer dir must be proven not writable by the runner")

    return {
        "model": ISOLATION_MODEL,
        "boundary": boundary,
        "runner_uid": runner_uid if isinstance(runner_uid, int) else None,
        "observer_uid": observer_uid if isinstance(observer_uid, int) else None,
        "observer_dir_writable_by_runner": writable if isinstance(writable, bool) else None,
        "reasons": reasons,
    }


def _verify_container_isolation_boundary(facts: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    runner_uid = facts.get("runner_uid")
    observer_uid = facts.get("observer_uid")
    writable = facts.get("observer_dir_writable_by_runner")
    container = facts.get("container")
    container = container if isinstance(container, dict) else {}

    boundary = True
    if not isinstance(observer_uid, int):
        boundary = False
        reasons.append("observer_uid must be a known integer")
    if not isinstance(runner_uid, int):
        boundary = False
        reasons.append("runner_uid must be a known integer")
    if writable is not False:
        boundary = False
        reasons.append("observer dir must be proven not writable by the runner")
    if container.get("runtime") != "docker":
        boundary = False
        reasons.append("container runtime must be docker")
    if container.get("observer_launched") is not True:
        boundary = False
        reasons.append("container must be observer-launched")
    if not isinstance(container.get("container_id"), str) or not container.get(
        "container_id"
    ):
        boundary = False
        reasons.append("container_id must be known")
    if container.get("running") is not True:
        boundary = False
        reasons.append("container must be running when inspected")
    if container.get("observer_dir_mounted_rw") is not False:
        boundary = False
        reasons.append("observer dir must not be mounted writable in the container")
    mounts = container.get("mounts")
    if not isinstance(mounts, list):
        boundary = False
        reasons.append("container mounts must be recorded as a list")

    return {
        "model": CONTAINER_ISOLATION_MODEL,
        "boundary": boundary,
        "runner_uid": runner_uid if isinstance(runner_uid, int) else None,
        "observer_uid": observer_uid if isinstance(observer_uid, int) else None,
        "observer_dir_writable_by_runner": writable if isinstance(writable, bool) else None,
        "container": {
            "runtime": container.get("runtime") if container.get("runtime") == "docker" else None,
            "container_id": (
                container.get("container_id")
                if isinstance(container.get("container_id"), str)
                else None
            ),
            "image": container.get("image") if isinstance(container.get("image"), str) else None,
            "observer_launched": (
                container.get("observer_launched")
                if isinstance(container.get("observer_launched"), bool)
                else None
            ),
            "running": (
                container.get("running") if isinstance(container.get("running"), bool) else None
            ),
            "observer_dir_mounted_rw": (
                container.get("observer_dir_mounted_rw")
                if isinstance(container.get("observer_dir_mounted_rw"), bool)
                else None
            ),
            "mounts": mounts if isinstance(mounts, list) else None,
        },
        "reasons": reasons,
    }


def probe_isolation_facts(
    observer_dir: Path, *, runner_uid: int | None
) -> dict[str, Any]:
    """Gather isolation facts on a real host (server-side).

    The observer process records its own uid and whether its output directory is
    writable by a *different* uid (foreign ownership or group/other write bits).
    ``runner_uid`` comes from the runner receipt. On a platform without POSIX
    uids the facts are unknown, which fails closed to A1 via the verifier.
    """

    facts: dict[str, Any] = {"runner_uid": runner_uid}
    getuid = getattr(os, "getuid", None)
    if getuid is None:
        facts["observer_uid"] = None
        facts["observer_dir_writable_by_runner"] = None
        return facts

    observer_uid = getuid()
    facts["observer_uid"] = observer_uid
    try:
        st = os.stat(observer_dir)
    except OSError:
        facts["observer_dir_writable_by_runner"] = None
        return facts

    foreign_owner = st.st_uid != observer_uid
    group_or_other_writable = bool(st.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
    facts["observer_dir_writable_by_runner"] = bool(
        foreign_owner or group_or_other_writable
    )
    return facts


def probe_container_isolation_facts(
    observer_dir: Path, *, container_id: str, observer_launched: bool = False
) -> dict[str, Any]:
    """Gather Docker container isolation facts from the host observer."""

    facts: dict[str, Any] = {
        "model": CONTAINER_ISOLATION_MODEL,
        "runner_uid": None,
        "container": {
            "runtime": "docker",
            "container_id": container_id,
            "image": None,
            "observer_launched": observer_launched,
            "running": None,
            "observer_dir_mounted_rw": None,
            "mounts": None,
        },
    }
    getuid = getattr(os, "getuid", None)
    facts["observer_uid"] = getuid() if getuid is not None else None

    docker = shutil.which("docker")
    if docker is None:
        facts["observer_dir_writable_by_runner"] = None
        return facts
    result = subprocess.run(
        [docker, "inspect", container_id],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        facts["observer_dir_writable_by_runner"] = None
        return facts
    try:
        inspected = json.loads(result.stdout)
    except json.JSONDecodeError:
        facts["observer_dir_writable_by_runner"] = None
        return facts
    if not isinstance(inspected, list) or not inspected or not isinstance(inspected[0], dict):
        facts["observer_dir_writable_by_runner"] = None
        return facts

    record = inspected[0]
    container = _container_facts_from_docker_inspect(record, observer_dir)
    container["observer_launched"] = observer_launched
    facts["runner_uid"] = _runner_uid_from_docker_user(record)
    facts["container"] = container
    facts["observer_dir_writable_by_runner"] = container["observer_dir_mounted_rw"]
    return facts


def _container_facts_from_docker_inspect(
    record: dict[str, Any], observer_dir: Path
) -> dict[str, Any]:
    mounts = _mount_facts(record.get("Mounts"))
    mounted_rw = any(
        mount.get("rw") is True
        and _paths_overlap(Path(str(mount.get("source", ""))), observer_dir)
        for mount in mounts
    )
    state = record.get("State")
    config = record.get("Config")
    return {
        "runtime": "docker",
        "container_id": record.get("Id") if isinstance(record.get("Id"), str) else None,
        "image": (
            config.get("Image")
            if isinstance(config, dict) and isinstance(config.get("Image"), str)
            else record.get("Image")
            if isinstance(record.get("Image"), str)
            else None
        ),
        "observer_launched": False,
        "running": state.get("Running") if isinstance(state, dict) else None,
        "observer_dir_mounted_rw": mounted_rw,
        "mounts": mounts,
    }


def _mount_facts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    mounts: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        source = item.get("Source")
        destination = item.get("Destination")
        mounts.append(
            {
                "source": source if isinstance(source, str) else "",
                "destination": destination if isinstance(destination, str) else "",
                "rw": bool(item.get("RW")),
            }
        )
    return mounts


def _paths_overlap(source: Path, observer_dir: Path) -> bool:
    if not str(source):
        return False
    source_path = source.expanduser().resolve(strict=False)
    observer_path = observer_dir.expanduser().resolve(strict=False)
    return _is_relative_to(observer_path, source_path) or _is_relative_to(
        source_path, observer_path
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _runner_uid_from_docker_user(record: dict[str, Any]) -> int | None:
    config = record.get("Config")
    user = config.get("User") if isinstance(config, dict) else None
    if user in (None, ""):
        return 0
    if not isinstance(user, str):
        return None
    uid_text = user.split(":", 1)[0]
    if uid_text.isdigit():
        return int(uid_text)
    return None


def _self_test() -> None:
    isolated = verify_isolation_boundary(
        {
            "runner_uid": 1001,
            "observer_uid": 1002,
            "observer_dir_writable_by_runner": False,
        }
    )
    if isolated["boundary"] is not True:
        raise AssertionError(f"different uid + unwritable dir must hold: {isolated}")
    print("  [PASS] different uid + unwritable observer dir -> boundary")

    same_uid = verify_isolation_boundary(
        {
            "runner_uid": 1001,
            "observer_uid": 1001,
            "observer_dir_writable_by_runner": False,
        }
    )
    if same_uid["boundary"] is not False:
        raise AssertionError("same uid must not establish a boundary")
    print("  [PASS] same uid -> no boundary")

    writable = verify_isolation_boundary(
        {
            "runner_uid": 1001,
            "observer_uid": 1002,
            "observer_dir_writable_by_runner": True,
        }
    )
    if writable["boundary"] is not False:
        raise AssertionError("writable observer dir must not establish a boundary")
    print("  [PASS] writable observer dir -> no boundary")

    missing = verify_isolation_boundary({"runner_uid": 1001})
    if missing["boundary"] is not False:
        raise AssertionError("missing facts must fail closed")
    print("  [PASS] missing/unknown facts -> fail closed")

    if verify_isolation_boundary(None)["boundary"] is not False:
        raise AssertionError("non-object facts must fail closed")
    print("  [PASS] non-object facts -> fail closed")

    unknown_model = verify_isolation_boundary(
        {
            "model": "unknown-model",
            "runner_uid": 1001,
            "observer_uid": 1002,
            "observer_dir_writable_by_runner": False,
        }
    )
    if unknown_model["boundary"] is not False:
        raise AssertionError("unknown isolation models must fail closed")
    print("  [PASS] unknown isolation model -> fail closed")

    container_isolated = verify_isolation_boundary(
        {
            "model": CONTAINER_ISOLATION_MODEL,
            "runner_uid": 0,
            "observer_uid": 1001,
            "observer_dir_writable_by_runner": False,
            "container": {
                "runtime": "docker",
                "container_id": "abc123",
                "image": "alpine:3.20",
                "observer_launched": True,
                "running": True,
                "observer_dir_mounted_rw": False,
                "mounts": [],
            },
        }
    )
    if container_isolated["boundary"] is not True:
        raise AssertionError(f"container facts must establish A2: {container_isolated}")
    print("  [PASS] docker container + unwritable observer dir -> boundary")

    container_rw = verify_isolation_boundary(
        {
            "model": CONTAINER_ISOLATION_MODEL,
            "runner_uid": 0,
            "observer_uid": 1001,
            "observer_dir_writable_by_runner": True,
            "container": {
                "runtime": "docker",
                "container_id": "abc123",
                "image": "alpine:3.20",
                "observer_launched": True,
                "running": True,
                "observer_dir_mounted_rw": True,
                "mounts": [{"destination": "/observer", "rw": True}],
            },
        }
    )
    if container_rw["boundary"] is not False:
        raise AssertionError("writable observer mount must fail closed")
    print("  [PASS] writable observer mount -> no boundary")

    print("depone agent_fabric isolation --self-test: pass")


if __name__ == "__main__":
    _self_test()
