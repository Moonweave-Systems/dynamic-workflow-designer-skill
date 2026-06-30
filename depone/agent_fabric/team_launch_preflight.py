"""Non-executing preflight for planned Depone native team launches."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.team_dry_run import TEAM_DRY_RUN_KIND, TEAM_DRY_RUN_SCHEMA_VERSION

TEAM_LAUNCH_PREFLIGHT_KIND = "depone-team-launch-preflight"
TEAM_LAUNCH_PREFLIGHT_SCHEMA_VERSION = "0.1"
VALID_LAUNCH_INTENTS = frozenset({"plan-only", "launch-ready"})


def build_team_launch_preflight(
    team_dry_run: dict[str, object],
    *,
    repo_root: Path,
    base_commit: str,
    launch_intent: str = "plan-only",
    adapter_availability: dict[str, object] | None = None,
) -> dict[str, object]:
    """Return a fail-closed, non-executing preflight for a team dry-run artifact."""

    errors: list[dict[str, str]] = []
    if not isinstance(team_dry_run, dict):
        team_dry_run = {}
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_DRY_RUN_INVALID",
                "team_dry_run must be an object",
            )
        )

    if launch_intent not in VALID_LAUNCH_INTENTS:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_LAUNCH_INTENT_INVALID",
                "launch_intent must be plan-only or launch-ready",
            )
        )

    dry_run_base_commit = team_dry_run.get("base_commit")
    if not isinstance(base_commit, str) or not base_commit.strip():
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_BASE_COMMIT_REQUIRED",
                "base_commit must be a non-empty string",
            )
        )
    elif dry_run_base_commit != base_commit:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_BASE_COMMIT_MISMATCH",
                "base_commit must match the team dry-run artifact",
            )
        )

    errors.extend(_validate_team_dry_run_input(team_dry_run))
    lanes = _lane_preflights(team_dry_run, adapter_availability, launch_intent, errors)
    errors.extend(_validate_next_commands(team_dry_run, lanes))

    payload: dict[str, object] = {
        "kind": TEAM_LAUNCH_PREFLIGHT_KIND,
        "schema_version": TEAM_LAUNCH_PREFLIGHT_SCHEMA_VERSION,
        "decision": "blocked" if errors else "pass",
        "launch_intent": launch_intent,
        "repo_root": repo_root.as_posix(),
        "base_commit": base_commit,
        "leader_objective": team_dry_run.get("leader_objective"),
        "lane_count": len(lanes),
        "lanes": lanes,
        "adapter_availability": adapter_availability or {},
        "errors": errors,
        "source_hashes": {"team_dry_run": canonical_hash(team_dry_run)},
        "boundary": {
            "launches_agents": False,
            "creates_worktrees": False,
            "executes_commands": False,
            "mutates_worktree": False,
            "calls_live_models": False,
            "raises_assurance": False,
        },
    }
    payload_errors = validate_team_launch_preflight(payload)
    if payload_errors:
        payload["decision"] = "blocked"
        payload["errors"] = [*errors, *payload_errors]
    return payload


def validate_team_launch_preflight(payload: dict[str, object]) -> list[dict[str, str]]:
    """Return structured validation errors for a team launch preflight payload."""

    errors: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return [
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_PAYLOAD_INVALID",
                "payload must be an object",
            )
        ]
    if payload.get("kind") != TEAM_LAUNCH_PREFLIGHT_KIND:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_KIND_INVALID",
                f"kind must be {TEAM_LAUNCH_PREFLIGHT_KIND}",
            )
        )
    if payload.get("schema_version") != TEAM_LAUNCH_PREFLIGHT_SCHEMA_VERSION:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_SCHEMA_VERSION_INVALID",
                f"schema_version must be {TEAM_LAUNCH_PREFLIGHT_SCHEMA_VERSION}",
            )
        )
    if payload.get("launch_intent") not in VALID_LAUNCH_INTENTS:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_LAUNCH_INTENT_INVALID",
                "launch_intent must be plan-only or launch-ready",
            )
        )
    if payload.get("decision") not in {"pass", "blocked"}:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_DECISION_INVALID",
                "decision must be pass or blocked",
            )
        )
    raw_errors = payload.get("errors")
    if not isinstance(raw_errors, list) or not all(isinstance(error, dict) for error in raw_errors):
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_ERRORS_INVALID",
                "errors must be a list of objects",
            )
        )
    elif payload.get("decision") == "pass" and raw_errors:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_DECISION_INVALID",
                "passing preflight must not include errors",
            )
        )
    lanes = payload.get("lanes")
    if not isinstance(lanes, list):
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_LANES_INVALID",
                "lanes must be a list",
            )
        )
    boundary = payload.get("boundary")
    if not isinstance(boundary, dict):
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_BOUNDARY_INVALID",
                "boundary must be an object",
            )
        )
    else:
        for key in (
            "launches_agents",
            "creates_worktrees",
            "executes_commands",
            "mutates_worktree",
            "calls_live_models",
            "raises_assurance",
        ):
            if boundary.get(key) is not False:
                errors.append(
                    _error(
                        "ERR_TEAM_LAUNCH_PREFLIGHT_BOUNDARY_INVALID",
                        f"boundary.{key} must be false",
                    )
                )
    return errors


def _validate_team_dry_run_input(team_dry_run: dict[str, object]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if team_dry_run.get("kind") != TEAM_DRY_RUN_KIND:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_DRY_RUN_KIND_INVALID",
                f"team dry-run kind must be {TEAM_DRY_RUN_KIND}",
            )
        )
    if team_dry_run.get("schema_version") != TEAM_DRY_RUN_SCHEMA_VERSION:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_DRY_RUN_SCHEMA_VERSION_INVALID",
                f"team dry-run schema_version must be {TEAM_DRY_RUN_SCHEMA_VERSION}",
            )
        )
    lanes = team_dry_run.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_LANES_INVALID",
                "team dry-run lanes must be a non-empty list",
            )
        )
    boundary = team_dry_run.get("boundary")
    if not isinstance(boundary, dict):
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_DRY_RUN_BOUNDARY_INVALID",
                "team dry-run boundary must be an object",
            )
        )
    else:
        for key in ("launches_agents", "executes_commands", "mutates_worktree", "raises_assurance"):
            if boundary.get(key) is not False:
                errors.append(
                    _error(
                        "ERR_TEAM_LAUNCH_PREFLIGHT_DRY_RUN_BOUNDARY_INVALID",
                        f"team dry-run boundary.{key} must be false",
                    )
                )
    return errors


def _lane_preflights(
    team_dry_run: dict[str, object],
    adapter_availability: dict[str, object] | None,
    launch_intent: str,
    errors: list[dict[str, str]],
) -> list[dict[str, object]]:
    raw_lanes = team_dry_run.get("lanes")
    if not isinstance(raw_lanes, list):
        return []
    ledger_adapters = _ledger_adapters(team_dry_run)
    lanes: list[dict[str, object]] = []
    seen_lane_ids: set[str] = set()
    for index, raw_lane in enumerate(raw_lanes):
        if not isinstance(raw_lane, dict):
            errors.append(
                _error(
                    "ERR_TEAM_LAUNCH_PREFLIGHT_LANE_INVALID",
                    f"lanes[{index}] must be an object",
                )
            )
            continue
        lane_id = _non_empty_string(raw_lane.get("lane_id"))
        if lane_id is None:
            lane_id = f"lane-{index + 1}"
        if lane_id in seen_lane_ids:
            errors.append(
                _error(
                    "ERR_TEAM_LAUNCH_PREFLIGHT_LANE_ID_DUPLICATE",
                    "lane_id must be unique",
                    lane_id=lane_id,
                )
            )
        seen_lane_ids.add(lane_id)
        planned_worktree = _non_empty_string(raw_lane.get("planned_worktree"))
        if planned_worktree is None or not _is_relative_safe_path(planned_worktree):
            errors.append(
                _error(
                    "ERR_TEAM_LAUNCH_PREFLIGHT_PLANNED_WORKTREE_INVALID",
                    "planned_worktree must be a repo-relative path without traversal",
                    lane_id=lane_id,
                )
            )
        evidence_dir = _non_empty_string(raw_lane.get("evidence_dir"))
        if evidence_dir is None or not _is_relative_safe_path(evidence_dir):
            errors.append(
                _error(
                    "ERR_TEAM_LAUNCH_PREFLIGHT_LANE_EVIDENCE_PATH_REQUIRED",
                    "lane evidence_dir must be a repo-relative path",
                    lane_id=lane_id,
                )
            )
        adapter = ledger_adapters.get(lane_id, "codex")
        adapter_record = _adapter_record(adapter_availability, adapter)
        availability_required = launch_intent == "launch-ready" or raw_lane.get("availability_required") is True
        if launch_intent == "launch-ready" and adapter_availability is None:
            errors.append(
                _error(
                    "ERR_TEAM_LAUNCH_PREFLIGHT_ADAPTER_AVAILABILITY_REQUIRED",
                    "launch-ready preflight requires adapter_availability",
                    lane_id=lane_id,
                )
            )
        elif availability_required and not _adapter_is_available(adapter_record):
            errors.append(
                _error(
                    "ERR_TEAM_LAUNCH_PREFLIGHT_ADAPTER_UNAVAILABLE",
                    f"adapter {adapter} is not available for launch-ready preflight",
                    lane_id=lane_id,
                )
            )
        lanes.append(
            {
                "lane_id": lane_id,
                "planned_worktree": planned_worktree,
                "evidence_dir": evidence_dir,
                "runner_adapter_kind": adapter,
                "availability_required": availability_required,
                "adapter_available": _adapter_is_available(adapter_record),
                "boundary": {
                    "launches_agents": False,
                    "creates_worktrees": False,
                    "executes_commands": False,
                },
            }
        )
    return lanes


def _validate_next_commands(
    team_dry_run: dict[str, object],
    lanes: list[dict[str, object]],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    expected_lane_ids = {lane["lane_id"] for lane in lanes if isinstance(lane.get("lane_id"), str)}
    raw_next_commands = team_dry_run.get("next_commands")
    if not isinstance(raw_next_commands, list):
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_NEXT_COMMANDS_INVALID",
                "next_commands must be a list",
            )
        )
        return errors
    command_lane_ids: set[str] = set()
    for index, raw in enumerate(raw_next_commands):
        if not isinstance(raw, dict):
            errors.append(
                _error(
                    "ERR_TEAM_LAUNCH_PREFLIGHT_NEXT_COMMANDS_INVALID",
                    f"next_commands[{index}] must be an object",
                )
            )
            continue
        lane_id = _non_empty_string(raw.get("lane_id"))
        if lane_id is None:
            errors.append(
                _error(
                    "ERR_TEAM_LAUNCH_PREFLIGHT_NEXT_COMMANDS_INVALID",
                    f"next_commands[{index}].lane_id must be a non-empty string",
                )
            )
            continue
        command_lane_ids.add(lane_id)
    missing = sorted(str(lane_id) for lane_id in expected_lane_ids - command_lane_ids)
    extra = sorted(command_lane_ids - {str(lane_id) for lane_id in expected_lane_ids})
    if missing or extra:
        errors.append(
            _error(
                "ERR_TEAM_LAUNCH_PREFLIGHT_NEXT_COMMANDS_INCOMPLETE",
                "next_commands lane ids must exactly match dry-run lanes",
            )
        )
    return errors


def _ledger_adapters(team_dry_run: dict[str, object]) -> dict[str, str]:
    team_ledger = team_dry_run.get("team_ledger")
    if not isinstance(team_ledger, dict):
        return {}
    lanes = team_ledger.get("lanes")
    if not isinstance(lanes, list):
        return {}
    adapters: dict[str, str] = {}
    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        lane_id = _non_empty_string(lane.get("lane_id"))
        adapter = _non_empty_string(lane.get("runner_adapter_kind"))
        if lane_id is not None and adapter is not None:
            adapters[lane_id] = adapter
    return adapters


def _adapter_record(
    adapter_availability: dict[str, object] | None,
    adapter: str,
) -> dict[str, object] | None:
    if adapter_availability is None:
        return None
    raw = adapter_availability.get(adapter)
    return raw if isinstance(raw, dict) else None


def _adapter_is_available(record: dict[str, object] | None) -> bool:
    return bool(record and record.get("available") is True)


def _non_empty_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _is_relative_safe_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def _error(code: str, message: str, *, lane_id: str | None = None) -> dict[str, str]:
    error = {"code": code, "message": message}
    if lane_id is not None:
        error["lane_id"] = lane_id
    return error


def _self_test() -> None:
    dry_run = {
        "kind": TEAM_DRY_RUN_KIND,
        "schema_version": TEAM_DRY_RUN_SCHEMA_VERSION,
        "leader_objective": "Plan without launching workers",
        "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "lanes": [
            {
                "lane_id": "lane-1",
                "objective": "Run tests",
                "planned_worktree": "out/team-dry-run/worktrees/lane-1",
                "evidence_dir": "lane-1",
            }
        ],
        "team_ledger": {
            "lanes": [{"lane_id": "lane-1", "runner_adapter_kind": "codex"}],
        },
        "next_commands": [{"lane_id": "lane-1", "commands": []}],
        "boundary": {
            "launches_agents": False,
            "executes_commands": False,
            "mutates_worktree": False,
            "raises_assurance": False,
        },
    }
    preflight = build_team_launch_preflight(
        dry_run,
        repo_root=Path("."),
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        launch_intent="plan-only",
        adapter_availability={"codex": {"available": False, "source": "self-test"}},
    )
    if preflight["decision"] != "pass":
        raise AssertionError("plan-only preflight should pass without launching")
    if preflight["boundary"]["launches_agents"] is not False:
        raise AssertionError("preflight must not launch agents")
    blocked = build_team_launch_preflight(
        dry_run,
        repo_root=Path("."),
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        launch_intent="launch-ready",
        adapter_availability={"codex": {"available": False, "source": "self-test"}},
    )
    if blocked["decision"] != "blocked":
        raise AssertionError("launch-ready preflight should block unavailable adapters")
