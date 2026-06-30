"""Team Ledger v0 validation for external agent-team evidence.

The ledger is an audit artifact, not a scheduler. It records one leader
objective and a set of lane records from local, container, or cloud agent runs.
Fan-in is conservative: each lane must be either verified as ``pass`` with an
existing evidence directory, or explicitly ``blocked`` with a reason.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

TEAM_LEDGER_KIND = "depone-team-ledger"
TEAM_LEDGER_SCHEMA_VERSION = "0.1"

ENVIRONMENT_KINDS = {"local", "container", "cloud"}
ADAPTER_KINDS = {
    "codex",
    "claude-code",
    "cursor",
    "depone-native",
    "github-copilot",
    "lazycodex",
    "omx",
    "opencode",
    "shell",
    "other",
}
LANE_VERIFICATION_STATES = {"pass", "blocked"}

_REQUIRED_LEDGER_FIELDS = ("objective", "lanes")
_REQUIRED_LANE_FIELDS = (
    "lane_id",
    "environment_kind",
    "adapter_kind",
    "start_commit",
    "end_commit",
    "verification_state",
)
_OPTIONAL_TEXT_FIELDS = ("leader", "budget", "stop_rule", "conflict_state", "pr_url")
_OPTIONAL_LANE_TEXT_FIELDS = ("role", "worker", "pr_url", "next_decision")


def validate_team_ledger(
    ledger: dict[str, Any], *, base_dir: str | Path = "."
) -> dict[str, Any]:
    """Validate a Team Ledger v0 object and return a fan-in verdict."""

    base_path = Path(base_dir)
    errors: list[str] = []
    lane_results: list[dict[str, Any]] = []

    kind = ledger.get("kind")
    if kind not in (None, TEAM_LEDGER_KIND):
        errors.append(f"kind must be {TEAM_LEDGER_KIND!r}")

    schema_version = ledger.get("schema_version")
    if schema_version not in (None, TEAM_LEDGER_SCHEMA_VERSION):
        errors.append(f"schema_version must be {TEAM_LEDGER_SCHEMA_VERSION!r}")

    for field in _REQUIRED_LEDGER_FIELDS:
        if field not in ledger:
            errors.append(f"missing ledger field: {field}")

    objective = ledger.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        errors.append("objective must be a non-empty string")

    for field in _OPTIONAL_TEXT_FIELDS:
        if field in ledger and not _is_optional_text(ledger[field]):
            errors.append(f"{field} must be a string when present")

    lanes = ledger.get("lanes")
    if not isinstance(lanes, list):
        errors.append("lanes must be a list")
        lanes = []
    elif not lanes:
        errors.append("lanes must contain at least one lane")

    seen_lane_ids: set[str] = set()
    passed_lanes = 0
    blocked_lanes = 0
    for index, lane in enumerate(lanes):
        if not isinstance(lane, dict):
            errors.append(f"lanes[{index}] must be an object")
            lane_results.append(
                {
                    "lane_index": index,
                    "lane_id": None,
                    "status": "blocked",
                    "errors": ["lane must be an object"],
                }
            )
            continue

        result = _validate_lane(lane, index=index, base_dir=base_path)
        lane_results.append(result)
        errors.extend(result["errors"])

        lane_id = result.get("lane_id")
        if isinstance(lane_id, str):
            if lane_id in seen_lane_ids:
                errors.append(f"duplicate lane_id: {lane_id}")
                result["errors"].append("duplicate lane_id")
                result["status"] = "blocked"
            seen_lane_ids.add(lane_id)

        if result["status"] == "pass":
            passed_lanes += 1
        elif result.get("verification_state") == "blocked" and not result["errors"]:
            blocked_lanes += 1

    decision = "pass" if not errors else "blocked"
    return {
        "kind": "depone-team-ledger-verdict",
        "schema_version": "0.1",
        "decision": decision,
        "lane_count": len(lane_results),
        "passed_lanes": passed_lanes,
        "blocked_lanes": blocked_lanes,
        "errors": errors,
        "lane_results": lane_results,
    }


def _validate_lane(
    lane: dict[str, Any], *, index: int, base_dir: Path
) -> dict[str, Any]:
    errors: list[str] = []

    for field in _REQUIRED_LANE_FIELDS:
        if field not in lane:
            errors.append(f"lanes[{index}] missing field: {field}")

    lane_id = lane.get("lane_id")
    if not isinstance(lane_id, str) or not lane_id.strip():
        errors.append(f"lanes[{index}].lane_id must be a non-empty string")

    for field in ("start_commit", "end_commit"):
        value = lane.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"lanes[{index}].{field} must be a non-empty string")

    for field in _OPTIONAL_LANE_TEXT_FIELDS:
        if field in lane and not _is_optional_text(lane[field]):
            errors.append(f"lanes[{index}].{field} must be a string when present")

    environment_kind = lane.get("environment_kind")
    if environment_kind not in ENVIRONMENT_KINDS:
        errors.append(
            f"lanes[{index}].environment_kind must be one of "
            f"{sorted(ENVIRONMENT_KINDS)}"
        )

    adapter_kind = lane.get("adapter_kind")
    if adapter_kind not in ADAPTER_KINDS:
        errors.append(
            f"lanes[{index}].adapter_kind must be one of {sorted(ADAPTER_KINDS)}"
        )

    verification_state = lane.get("verification_state")
    if verification_state not in LANE_VERIFICATION_STATES:
        errors.append(
            f"lanes[{index}].verification_state must be one of "
            f"{sorted(LANE_VERIFICATION_STATES)}"
        )

    evidence_dir = lane.get("evidence_dir")
    evidence_dir_status = "not-required"
    if verification_state == "pass":
        if not isinstance(evidence_dir, str) or not evidence_dir.strip():
            errors.append(f"lanes[{index}].evidence_dir is required for pass lanes")
            evidence_dir_status = "missing"
        else:
            path = _resolve_path(base_dir, evidence_dir)
            if not path.is_dir():
                errors.append(f"lanes[{index}].evidence_dir does not exist: {evidence_dir}")
                evidence_dir_status = "missing"
            else:
                evidence_dir_status = "present"
    elif verification_state == "blocked":
        reason = lane.get("blocked_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"lanes[{index}].blocked_reason is required for blocked lanes")

    status = "pass" if not errors and verification_state == "pass" else "blocked"
    return {
        "lane_index": index,
        "lane_id": lane_id if isinstance(lane_id, str) else None,
        "verification_state": verification_state,
        "status": status,
        "evidence_dir_status": evidence_dir_status,
        "errors": errors,
    }


def _resolve_path(base_dir: Path, path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return base_dir / path


def _is_optional_text(value: Any) -> bool:
    return value is None or isinstance(value, str)


def read_team_ledger(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Team ledger JSON root must be an object")
    return value


def _self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="depone-team-ledger-") as temp_dir:
        root = Path(temp_dir)
        evidence_dir = root / "lane-1-evidence"
        evidence_dir.mkdir()
        ledger = {
            "kind": TEAM_LEDGER_KIND,
            "schema_version": TEAM_LEDGER_SCHEMA_VERSION,
            "objective": "verify a two-lane team",
            "leader": "leader-fixed",
            "lanes": [
                {
                    "lane_id": "lane-1",
                    "environment_kind": "local",
                    "adapter_kind": "omx",
                    "start_commit": "abc123",
                    "end_commit": "def456",
                    "evidence_dir": "lane-1-evidence",
                    "verification_state": "pass",
                    "next_decision": "pass",
                },
                {
                    "lane_id": "lane-2",
                    "environment_kind": "cloud",
                    "adapter_kind": "codex",
                    "start_commit": "abc123",
                    "end_commit": "abc123",
                    "verification_state": "blocked",
                    "blocked_reason": "upstream CI unavailable",
                },
            ],
        }

        verdict = validate_team_ledger(ledger, base_dir=root)
        if verdict["decision"] != "pass":
            raise AssertionError(f"valid mixed pass/blocked ledger failed: {verdict}")

        missing_evidence = json.loads(json.dumps(ledger))
        missing_evidence["lanes"][0]["evidence_dir"] = "missing"
        if validate_team_ledger(missing_evidence, base_dir=root)["decision"] != "blocked":
            raise AssertionError("pass lane with missing evidence_dir must block")

        bad_environment = json.loads(json.dumps(ledger))
        bad_environment["lanes"][0]["environment_kind"] = "prod"
        if validate_team_ledger(bad_environment, base_dir=root)["decision"] != "blocked":
            raise AssertionError("invalid environment kind must block")

        bad_blocked = json.loads(json.dumps(ledger))
        del bad_blocked["lanes"][1]["blocked_reason"]
        if validate_team_ledger(bad_blocked, base_dir=root)["decision"] != "blocked":
            raise AssertionError("blocked lane without blocked_reason must block")
