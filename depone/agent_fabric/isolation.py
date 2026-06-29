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
import stat
from pathlib import Path
from typing import Any

ISOLATION_MODEL = "uid-boundary-unwritable-observer-dir"


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

    print("depone agent_fabric isolation --self-test: pass")


if __name__ == "__main__":
    _self_test()
