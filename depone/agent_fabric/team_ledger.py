"""Team Ledger v0 validation for Depone-observed team lanes.

This module records and validates evidence about externally-run team lanes. It
is deliberately non-executing: it does not launch agents, inspect cloud state,
or raise assurance. It only checks that a leader ledger and lane receipts have
honest, present evidence before fan-in.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.team_merge_attempt import (
    TEAM_MERGE_ATTEMPT_KIND,
    validate_team_merge_attempt_receipt,
)
from depone.agent_fabric.worktree_receipt import (
    WORKTREE_LANE_RECEIPT_KIND,
    WORKTREE_LANE_RECEIPT_SCHEMA_VERSION,
)

TEAM_LEDGER_KIND = "depone-team-ledger"
TEAM_LEDGER_SCHEMA_VERSION = "0.1"
TEAM_LEDGER_VERDICT_KIND = "depone-team-ledger-verdict"
TEAM_LEDGER_PR_ARTIFACT_KIND = "depone-team-ledger-pr-artifact"
TEAM_LEDGER_CLOUD_ARTIFACT_KIND = "depone-team-ledger-cloud-artifact"
TEAM_LEDGER_MERGE_ATTEMPT_KIND = TEAM_MERGE_ATTEMPT_KIND
TEAM_LEDGER_SUBJECT_COMMIT_SEMANTICS = "observed_subject_commit"
VALID_ENV_KINDS = frozenset({"local", "container", "cloud"})
VALID_ADAPTER_KINDS = frozenset(
    {
        "codex",
        "claude-code",
        "opencode",
        "omx",
        "lazycodex",
        "github-copilot",
        "depone-native",
        "shell",
        "external",
    }
)
VALID_LANE_VERIFICATION_STATES = frozenset({"pass", "blocked"})
VALID_PASSING_PR_MERGE_STATES = frozenset({"CLEAN", "HAS_HOOKS"})


class TeamLedgerError(ValueError):
    """Structured Team Ledger v0 validation error."""

    def __init__(self, code: str, message: str, *, lane_id: str | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.lane_id = lane_id

    def to_record(self) -> dict[str, str]:
        record = {"code": self.code, "message": self.message}
        if self.lane_id is not None:
            record["lane_id"] = self.lane_id
        return record


def build_team_ledger_verdict(
    ledger: dict[str, Any], *, base_dir: Path | None = None
) -> dict[str, Any]:
    """Return a fail-closed validation verdict for a Team Ledger v0 object."""

    root = base_dir or Path.cwd()
    errors: list[dict[str, str]] = []
    lane_results: list[dict[str, Any]] = []

    _validate_ledger_header(ledger, errors)
    lanes = ledger.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_LANES_REQUIRED",
                "message": "lanes must be a non-empty list",
            }
        )
        lanes = []
    commit_scope = _validate_commit_scope(ledger, errors)

    seen_lane_ids: set[str] = set()
    for index, raw_lane in enumerate(lanes):
        if not isinstance(raw_lane, dict):
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_LANE_INVALID",
                    "message": f"lanes[{index}] must be an object",
                }
            )
            continue
        lane_result = _validate_lane(raw_lane, root, seen_lane_ids)
        lane_results.append(lane_result)
        errors.extend(lane_result["errors"])

    overlapping_touched_files = _find_overlapping_touched_files(lane_results)
    merge_receipt = _validate_merge_receipt(
        ledger.get("merge_receipt"),
        root,
        errors,
        required=bool(overlapping_touched_files),
        overlapping_touched_files=overlapping_touched_files,
    )

    blocked = sum(1 for lane in lane_results if lane["decision"] != "pass")
    passed = len(lane_results) - blocked
    if errors:
        decision = "blocked"
    elif any(lane["verification_state"] == "blocked" for lane in lane_results):
        decision = "blocked-explicit"
    else:
        decision = "pass"

    verdict = {
        "kind": TEAM_LEDGER_VERDICT_KIND,
        "schema_version": TEAM_LEDGER_SCHEMA_VERSION,
        "decision": decision,
        "leader_objective": ledger.get("leader_objective"),
        "lane_count": len(lane_results),
        "passed_lane_count": passed,
        "blocked_lane_count": blocked,
        "lane_results": lane_results,
        "overlapping_touched_files": overlapping_touched_files,
        "merge_receipt": merge_receipt,
        "errors": errors,
        "source_hashes": {"team_ledger": canonical_hash(ledger)},
        "boundary": {
            "executes_commands": False,
            "launches_agents": False,
            "calls_live_models": False,
            "inspects_cloud_runtime": False,
            "raises_assurance": False,
            "approves_merge": False,
        },
    }
    if commit_scope is not None:
        verdict["commit_scope"] = commit_scope
    return verdict


def validate_team_ledger(
    ledger: dict[str, Any], *, base_dir: Path | None = None
) -> list[dict[str, str]]:
    """Return validation errors for a Team Ledger v0 object."""

    return list(build_team_ledger_verdict(ledger, base_dir=base_dir)["errors"])


def build_team_ledger_merge_receipt(
    *,
    lanes: list[str],
    files: list[str],
    conflict_events: list[Any] | None = None,
    decision: str = "pass",
) -> dict[str, Any]:
    """Return a deterministic Team Ledger merge receipt JSON object."""

    normalized_lanes = _normalize_merge_receipt_lanes(lanes)
    normalized_files = _normalize_repo_relative_files(files)
    if decision not in {"pass", "blocked"}:
        raise TeamLedgerError(
            "ERR_TEAM_LEDGER_MERGE_RECEIPT_DECISION_INVALID",
            "decision must be pass or blocked",
        )
    if conflict_events is not None and not isinstance(conflict_events, list):
        raise TeamLedgerError(
            "ERR_TEAM_LEDGER_MERGE_RECEIPT_CONFLICT_EVENTS_INVALID",
            "conflict_events must be a list",
        )
    return {
        "command": "team-ledger-merge-receipt",
        "schema_version": "1.0",
        "decision": decision,
        "lanes": normalized_lanes,
        "files": normalized_files,
        "conflict_events": conflict_events or [],
    }


def _validate_ledger_header(
    ledger: dict[str, Any], errors: list[dict[str, str]]
) -> None:
    if ledger.get("kind") != TEAM_LEDGER_KIND:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_KIND_INVALID",
                "message": f"kind must be {TEAM_LEDGER_KIND}",
            }
        )
    if ledger.get("schema_version") != TEAM_LEDGER_SCHEMA_VERSION:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_SCHEMA_VERSION_INVALID",
                "message": f"schema_version must be {TEAM_LEDGER_SCHEMA_VERSION}",
            }
        )
    _require_non_empty_string(ledger, "leader_objective", errors)
    _require_non_empty_string(ledger, "leader_id", errors)
    _require_non_empty_string(ledger, "start_commit", errors)
    _require_non_empty_string(ledger, "stop_rule", errors)


def _validate_commit_scope(
    ledger: dict[str, Any],
    errors: list[dict[str, str]],
) -> dict[str, Any] | None:
    raw = ledger.get("commit_scope")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_COMMIT_SCOPE_INVALID",
                "message": "commit_scope must be an object when present",
            }
        )
        return {
            "end_commit_semantics": None,
            "subject_commit": None,
            "allowed_post_subject_paths": [],
        }

    semantics = raw.get("end_commit_semantics")
    if semantics != TEAM_LEDGER_SUBJECT_COMMIT_SEMANTICS:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_COMMIT_SCOPE_INVALID",
                "message": (
                    "commit_scope end_commit_semantics must be "
                    f"{TEAM_LEDGER_SUBJECT_COMMIT_SEMANTICS}"
                ),
            }
        )

    subject_commit = raw.get("subject_commit")
    if not isinstance(subject_commit, str) or not subject_commit.strip():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_COMMIT_SCOPE_INVALID",
                "message": "commit_scope subject_commit must be a non-empty string",
            }
        )
        subject_commit = None

    ledger_end_commit = ledger.get("end_commit")
    if (
        isinstance(subject_commit, str)
        and isinstance(ledger_end_commit, str)
        and ledger_end_commit
        and subject_commit != ledger_end_commit
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_COMMIT_SCOPE_SUBJECT_MISMATCH",
                "message": "commit_scope subject_commit must match ledger end_commit",
            }
        )

    allowed_paths = _validate_commit_scope_paths(
        raw.get("allowed_post_subject_paths"), errors
    )
    rationale = raw.get("rationale")
    if rationale is not None and not isinstance(rationale, str):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_COMMIT_SCOPE_INVALID",
                "message": "commit_scope rationale must be a string when present",
            }
        )
        rationale = None

    summary = {
        "end_commit_semantics": semantics if isinstance(semantics, str) else None,
        "subject_commit": subject_commit,
        "allowed_post_subject_paths": allowed_paths,
    }
    if isinstance(rationale, str) and rationale:
        summary["rationale"] = rationale
    return summary


def _validate_commit_scope_paths(
    value: Any,
    errors: list[dict[str, str]],
) -> list[str]:
    if not isinstance(value, list) or not value:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_COMMIT_SCOPE_PATHS_INVALID",
                "message": "commit_scope allowed_post_subject_paths must be a non-empty list",
            }
        )
        return []

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_COMMIT_SCOPE_PATHS_INVALID",
                    "message": "commit_scope allowed_post_subject_paths entries must be non-empty strings",
                }
            )
            continue
        path = PurePosixPath(item)
        if path.is_absolute() or ".." in path.parts:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_COMMIT_SCOPE_PATHS_INVALID",
                    "message": "commit_scope allowed_post_subject_paths entries must stay repo-relative",
                }
            )
            continue
        normalized.append(path.as_posix())
    return sorted(set(normalized))


def _validate_lane(
    lane: dict[str, Any],
    base_dir: Path,
    seen_lane_ids: set[str],
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    lane_id = lane.get("lane_id") if isinstance(lane.get("lane_id"), str) else ""
    lane_error_id = lane_id or "<missing>"

    _require_non_empty_string(lane, "lane_id", errors, lane_id=lane_error_id)
    if lane_id:
        if lane_id in seen_lane_ids:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_LANE_ID_DUPLICATE",
                    "message": "lane_id must be unique",
                    "lane_id": lane_id,
                }
            )
        seen_lane_ids.add(lane_id)

    _require_non_empty_string(lane, "objective", errors, lane_id=lane_error_id)
    _require_non_empty_string(lane, "start_commit", errors, lane_id=lane_error_id)
    _require_non_empty_string(lane, "end_commit", errors, lane_id=lane_error_id)
    _require_non_empty_string(lane, "evidence_dir", errors, lane_id=lane_error_id)

    _validate_choice(lane, "env_kind", VALID_ENV_KINDS, errors, lane_id=lane_error_id)
    _validate_choice(
        lane,
        "runner_adapter_kind",
        VALID_ADAPTER_KINDS,
        errors,
        lane_id=lane_error_id,
    )
    _validate_choice(
        lane,
        "team_adapter_kind",
        VALID_ADAPTER_KINDS,
        errors,
        lane_id=lane_error_id,
    )
    state = _validate_choice(
        lane,
        "verification_state",
        VALID_LANE_VERIFICATION_STATES,
        errors,
        lane_id=lane_error_id,
    )

    evidence_dir = lane.get("evidence_dir")
    evidence_dir_exists = False
    if isinstance(evidence_dir, str) and evidence_dir:
        evidence_path = (base_dir / evidence_dir).resolve(strict=False)
        evidence_dir_exists = evidence_path.is_dir()
        if state == "pass" and not evidence_dir_exists:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_EVIDENCE_DIR_MISSING",
                    "message": "passed lane evidence_dir must exist",
                    "lane_id": lane_error_id,
                }
            )

    evidence_next_verdict = lane.get("evidence_next_verdict")
    evidence_next_summary = _validate_evidence_next_verdict(
        evidence_next_verdict,
        base_dir,
        errors,
        lane_id=lane_error_id,
        required=state == "pass",
    )

    blocked_reason = lane.get("blocked_reason")
    if state == "blocked" and (
        not isinstance(blocked_reason, str) or not blocked_reason.strip()
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_BLOCKED_REASON_REQUIRED",
                "message": "blocked lane must include a non-empty blocked_reason",
                "lane_id": lane_error_id,
            }
        )

    verification_artifacts = lane.get("verification_artifacts", [])
    if verification_artifacts is None:
        verification_artifacts = []
    if not isinstance(verification_artifacts, list) or not all(
        isinstance(item, str) and item for item in verification_artifacts
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_VERIFICATION_ARTIFACTS_INVALID",
                "message": "verification_artifacts must be a list of non-empty strings",
                "lane_id": lane_error_id,
            }
        )
        verification_artifacts = []

    pr_url = lane.get("pr_url")
    if pr_url is not None and not isinstance(pr_url, str):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_URL_INVALID",
                "message": "pr_url must be a string when present",
                "lane_id": lane_error_id,
            }
        )

    pr_artifact_summary = _validate_pr_artifact(
        lane.get("pr_artifact"),
        lane,
        base_dir,
        errors,
        lane_id=lane_error_id,
    )
    cloud_artifact_summary = _validate_cloud_artifact(
        lane.get("cloud_artifact"),
        lane,
        base_dir,
        errors,
        lane_id=lane_error_id,
        required=state == "pass" and lane.get("env_kind") == "cloud",
    )
    worktree_receipt_summary = _validate_worktree_receipt(
        lane.get("worktree_receipt"),
        lane,
        base_dir,
        errors,
        lane_id=lane_error_id,
        required=state == "pass",
    )

    touched_files = _validate_touched_files(
        lane.get("touched_files"), errors, lane_id=lane_error_id
    )
    if state == "pass" and not touched_files:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_TOUCHED_FILES_REQUIRED",
                "message": "passed lane must include at least one touched_files entry",
                "lane_id": lane_error_id,
            }
        )

    return {
        "lane_id": lane_error_id,
        "env_kind": lane.get("env_kind"),
        "runner_adapter_kind": lane.get("runner_adapter_kind"),
        "team_adapter_kind": lane.get("team_adapter_kind"),
        "verification_state": state,
        "decision": "blocked" if errors or state == "blocked" else "pass",
        "start_commit": lane.get("start_commit"),
        "end_commit": lane.get("end_commit"),
        "evidence_dir": evidence_dir,
        "evidence_dir_exists": evidence_dir_exists,
        "evidence_next_verdict": evidence_next_verdict,
        "evidence_next": evidence_next_summary,
        "pr_artifact": pr_artifact_summary,
        "cloud_artifact": cloud_artifact_summary,
        "worktree_receipt": worktree_receipt_summary,
        "verification_artifact_count": len(verification_artifacts),
        "touched_files": touched_files,
        "touched_file_count": len(touched_files),
        "errors": errors,
    }


def _require_non_empty_string(
    value: dict[str, Any],
    field: str,
    errors: list[dict[str, str]],
    *,
    lane_id: str | None = None,
) -> None:
    if not isinstance(value.get(field), str) or not str(value.get(field)).strip():
        record = {
            "code": "ERR_TEAM_LEDGER_REQUIRED_FIELD_MISSING",
            "message": f"{field} must be a non-empty string",
        }
        if lane_id is not None:
            record["lane_id"] = lane_id
        errors.append(record)


def _validate_choice(
    value: dict[str, Any],
    field: str,
    valid: frozenset[str],
    errors: list[dict[str, str]],
    *,
    lane_id: str,
) -> str | None:
    raw = value.get(field)
    if isinstance(raw, str) and raw in valid:
        return raw
    errors.append(
        {
            "code": "ERR_TEAM_LEDGER_CHOICE_INVALID",
            "message": f"{field} must be one of {sorted(valid)}",
            "lane_id": lane_id,
        }
    )
    return raw if isinstance(raw, str) else None


def _validate_evidence_next_verdict(
    evidence_next_verdict: Any,
    base_dir: Path,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
    required: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": evidence_next_verdict
        if isinstance(evidence_next_verdict, str)
        else None,
        "decision": None,
        "blocking_reason_count": None,
    }
    if not isinstance(evidence_next_verdict, str) or not evidence_next_verdict.strip():
        if required:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_REQUIRED",
                    "message": "passed lane must include evidence_next_verdict",
                    "lane_id": lane_id,
                }
            )
        return summary

    verdict_path = Path(evidence_next_verdict)
    if verdict_path.is_absolute():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_PATH_INVALID",
                "message": "evidence_next_verdict must be relative to the ledger base directory",
                "lane_id": lane_id,
            }
        )
        return summary

    resolved = (base_dir / verdict_path).resolve(strict=False)
    base_resolved = base_dir.resolve(strict=False)
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_PATH_INVALID",
                "message": "evidence_next_verdict must stay under the ledger base directory",
                "lane_id": lane_id,
            }
        )
        return summary

    if not resolved.is_file():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_MISSING",
                "message": "evidence_next_verdict file must exist",
                "lane_id": lane_id,
            }
        )
        return summary

    try:
        verdict = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_INVALID",
                "message": f"evidence_next_verdict must be readable JSON: {exc}",
                "lane_id": lane_id,
            }
        )
        return summary
    if not isinstance(verdict, dict):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_INVALID",
                "message": "evidence_next_verdict root must be an object",
                "lane_id": lane_id,
            }
        )
        return summary

    blocking_reasons = verdict.get("blocking_reasons", [])
    if not isinstance(blocking_reasons, list):
        blocking_reasons = []
    summary["decision"] = verdict.get("decision")
    summary["blocking_reason_count"] = len(blocking_reasons)
    if verdict.get("command") != "evidence-next":
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_INVALID",
                "message": "evidence_next_verdict command must be evidence-next",
                "lane_id": lane_id,
            }
        )
    if verdict.get("decision") != "continue" or blocking_reasons:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_NOT_CONTINUE",
                "message": "evidence_next_verdict must have decision=continue and no blocking_reasons",
                "lane_id": lane_id,
            }
        )
    return summary


def _validate_pr_artifact(
    pr_artifact: Any,
    lane: dict[str, Any],
    base_dir: Path,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": pr_artifact if isinstance(pr_artifact, str) else None,
        "pr_url": None,
        "head_sha": None,
        "base_sha": None,
        "state": None,
        "merge_state_status": None,
        "check_status": None,
        "failed_count": None,
        "pending_count": None,
    }
    if pr_artifact is None:
        return summary
    if not isinstance(pr_artifact, str) or not pr_artifact.strip():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_PATH_INVALID",
                "message": "pr_artifact must be a relative JSON path when present",
                "lane_id": lane_id,
            }
        )
        return summary

    artifact_path = Path(pr_artifact)
    if artifact_path.is_absolute():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_PATH_INVALID",
                "message": "pr_artifact must be relative to the ledger base directory",
                "lane_id": lane_id,
            }
        )
        return summary

    resolved = (base_dir / artifact_path).resolve(strict=False)
    base_resolved = base_dir.resolve(strict=False)
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_PATH_INVALID",
                "message": "pr_artifact must stay under the ledger base directory",
                "lane_id": lane_id,
            }
        )
        return summary

    if not resolved.is_file():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_MISSING",
                "message": "pr_artifact file must exist",
                "lane_id": lane_id,
            }
        )
        return summary

    try:
        artifact = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                "message": f"pr_artifact must be readable JSON: {exc}",
                "lane_id": lane_id,
            }
        )
        return summary
    if not isinstance(artifact, dict):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                "message": "pr_artifact root must be an object",
                "lane_id": lane_id,
            }
        )
        return summary

    summary["pr_url"] = artifact.get("pr_url")
    summary["head_sha"] = artifact.get("head_sha")
    summary["base_sha"] = artifact.get("base_sha")
    summary["state"] = artifact.get("state")
    summary["merge_state_status"] = artifact.get("merge_state_status")
    summary["stale"] = artifact.get("stale")

    if artifact.get("kind") != TEAM_LEDGER_PR_ARTIFACT_KIND:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                "message": f"pr_artifact kind must be {TEAM_LEDGER_PR_ARTIFACT_KIND}",
                "lane_id": lane_id,
            }
        )
    if artifact.get("schema_version") != TEAM_LEDGER_SCHEMA_VERSION:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                "message": f"pr_artifact schema_version must be {TEAM_LEDGER_SCHEMA_VERSION}",
                "lane_id": lane_id,
            }
        )
    if (
        not isinstance(artifact.get("pr_number"), int)
        or artifact.get("pr_number", 0) <= 0
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                "message": "pr_artifact pr_number must be a positive integer",
                "lane_id": lane_id,
            }
        )

    _validate_pr_artifact_string_field(artifact, "pr_url", errors, lane_id=lane_id)
    _validate_pr_artifact_string_field(artifact, "base_sha", errors, lane_id=lane_id)
    _validate_pr_artifact_string_field(artifact, "head_sha", errors, lane_id=lane_id)
    _validate_pr_artifact_string_field(
        artifact, "merge_state_status", errors, lane_id=lane_id
    )
    _validate_pr_artifact_captured_at(
        artifact.get("captured_at"), errors, lane_id=lane_id
    )
    if artifact.get("stale") is not False:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_STALE",
                "message": "pr_artifact stale must be false",
                "lane_id": lane_id,
            }
        )
    merge_state_status = artifact.get("merge_state_status")
    if (
        not isinstance(merge_state_status, str)
        or merge_state_status.upper() not in VALID_PASSING_PR_MERGE_STATES
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_NOT_MERGEABLE",
                "message": "pr_artifact merge_state_status must be CLEAN or HAS_HOOKS",
                "lane_id": lane_id,
            }
        )

    state = artifact.get("state")
    if not isinstance(state, str) or state.upper() not in {"OPEN", "MERGED", "CLOSED"}:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                "message": "pr_artifact state must be OPEN, MERGED, or CLOSED",
                "lane_id": lane_id,
            }
        )

    lane_pr_url = lane.get("pr_url")
    artifact_pr_url = artifact.get("pr_url")
    if (
        isinstance(lane_pr_url, str)
        and lane_pr_url
        and isinstance(artifact_pr_url, str)
        and artifact_pr_url
        and artifact_pr_url != lane_pr_url
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_PR_URL_MISMATCH",
                "message": "pr_artifact pr_url must match lane pr_url",
                "lane_id": lane_id,
            }
        )

    lane_end_commit = lane.get("end_commit")
    head_sha = artifact.get("head_sha")
    if (
        isinstance(lane_end_commit, str)
        and lane_end_commit
        and isinstance(head_sha, str)
    ):
        if head_sha != lane_end_commit:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_HEAD_SHA_MISMATCH",
                    "message": "pr_artifact head_sha must match lane end_commit",
                    "lane_id": lane_id,
                }
            )

    check_summary = artifact.get("check_summary")
    if not isinstance(check_summary, dict):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                "message": "pr_artifact check_summary must be an object",
                "lane_id": lane_id,
            }
        )
        return summary

    check_status = check_summary.get("status")
    failed_count = check_summary.get("failed_count")
    pending_count = check_summary.get("pending_count")
    total_count = check_summary.get("total_count")
    summary["check_status"] = check_status
    summary["failed_count"] = failed_count
    summary["pending_count"] = pending_count
    if not isinstance(check_status, str) or check_status.lower() not in {
        "pass",
        "success",
    }:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_CHECKS_NOT_PASSING",
                "message": "pr_artifact check_summary status must be pass or success",
                "lane_id": lane_id,
            }
        )
    for field, raw_count in (
        ("total_count", total_count),
        ("failed_count", failed_count),
        ("pending_count", pending_count),
    ):
        if not isinstance(raw_count, int) or raw_count < 0:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                    "message": f"pr_artifact check_summary {field} must be a non-negative integer",
                    "lane_id": lane_id,
                }
            )
    if failed_count != 0 or pending_count != 0:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_CHECKS_NOT_PASSING",
                "message": "pr_artifact check_summary must have zero failed and pending checks",
                "lane_id": lane_id,
            }
        )
    return summary


def _validate_pr_artifact_string_field(
    artifact: dict[str, Any],
    field: str,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
) -> None:
    if not isinstance(artifact.get(field), str) or not str(artifact.get(field)).strip():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                "message": f"pr_artifact {field} must be a non-empty string",
                "lane_id": lane_id,
            }
        )


def _validate_pr_artifact_captured_at(
    value: Any,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                "message": "pr_artifact captured_at must be a non-empty ISO timestamp",
                "lane_id": lane_id,
            }
        )
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_ARTIFACT_INVALID",
                "message": "pr_artifact captured_at must be parseable as an ISO timestamp",
                "lane_id": lane_id,
            }
        )


def _validate_cloud_artifact(
    cloud_artifact: Any,
    lane: dict[str, Any],
    base_dir: Path,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
    required: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": cloud_artifact if isinstance(cloud_artifact, str) else None,
        "provider": None,
        "adapter_kind": None,
        "external_run_id": None,
        "repo": None,
        "base_sha": None,
        "head_sha": None,
        "pr_url": None,
        "evidence_hash": None,
        "observed_external_facts_only": None,
        "attests_runtime_isolation": None,
    }
    if cloud_artifact is None:
        if required:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_REQUIRED",
                    "message": "passed cloud lane must include cloud_artifact",
                    "lane_id": lane_id,
                }
            )
        return summary
    if not isinstance(cloud_artifact, str) or not cloud_artifact.strip():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_PATH_INVALID",
                "message": "cloud_artifact must be a relative JSON path when present",
                "lane_id": lane_id,
            }
        )
        return summary

    artifact_path = Path(cloud_artifact)
    if artifact_path.is_absolute():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_PATH_INVALID",
                "message": "cloud_artifact must be relative to the ledger base directory",
                "lane_id": lane_id,
            }
        )
        return summary

    resolved = (base_dir / artifact_path).resolve(strict=False)
    base_resolved = base_dir.resolve(strict=False)
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_PATH_INVALID",
                "message": "cloud_artifact must stay under the ledger base directory",
                "lane_id": lane_id,
            }
        )
        return summary

    if not resolved.is_file():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_MISSING",
                "message": "cloud_artifact file must exist",
                "lane_id": lane_id,
            }
        )
        return summary

    try:
        artifact = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_INVALID",
                "message": f"cloud_artifact must be readable JSON: {exc}",
                "lane_id": lane_id,
            }
        )
        return summary
    if not isinstance(artifact, dict):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_INVALID",
                "message": "cloud_artifact root must be an object",
                "lane_id": lane_id,
            }
        )
        return summary

    for field in (
        "provider",
        "adapter_kind",
        "external_run_id",
        "repo",
        "base_sha",
        "head_sha",
        "evidence_hash",
    ):
        summary[field] = artifact.get(field)
    summary["pr_url"] = artifact.get("pr_url")

    if artifact.get("kind") != TEAM_LEDGER_CLOUD_ARTIFACT_KIND:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_INVALID",
                "message": f"cloud_artifact kind must be {TEAM_LEDGER_CLOUD_ARTIFACT_KIND}",
                "lane_id": lane_id,
            }
        )
    if artifact.get("schema_version") != TEAM_LEDGER_SCHEMA_VERSION:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_INVALID",
                "message": f"cloud_artifact schema_version must be {TEAM_LEDGER_SCHEMA_VERSION}",
                "lane_id": lane_id,
            }
        )

    for field in (
        "provider",
        "external_run_id",
        "repo",
        "base_sha",
        "head_sha",
        "evidence_hash",
    ):
        _validate_cloud_artifact_string_field(artifact, field, errors, lane_id=lane_id)
    _validate_cloud_artifact_captured_at(
        artifact.get("captured_at"), errors, lane_id=lane_id
    )

    adapter_kind = artifact.get("adapter_kind")
    if not isinstance(adapter_kind, str) or adapter_kind not in VALID_ADAPTER_KINDS:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_INVALID",
                "message": "cloud_artifact adapter_kind must be a known adapter kind",
                "lane_id": lane_id,
            }
        )
    lane_runner_adapter_kind = lane.get("runner_adapter_kind")
    if (
        isinstance(lane_runner_adapter_kind, str)
        and lane_runner_adapter_kind
        and isinstance(adapter_kind, str)
        and adapter_kind != lane_runner_adapter_kind
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_ADAPTER_KIND_MISMATCH",
                "message": "cloud_artifact adapter_kind must match lane runner_adapter_kind",
                "lane_id": lane_id,
            }
        )

    evidence_hash = artifact.get("evidence_hash")
    if isinstance(evidence_hash, str) and (
        len(evidence_hash) != 64
        or any(char not in "0123456789abcdef" for char in evidence_hash)
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_INVALID",
                "message": "cloud_artifact evidence_hash must be lowercase sha256 hex",
                "lane_id": lane_id,
            }
        )
    elif isinstance(evidence_hash, str):
        evidence_next_path = lane.get("evidence_next_verdict")
        if isinstance(evidence_next_path, str) and evidence_next_path:
            resolved_evidence_next = (base_dir / evidence_next_path).resolve(
                strict=False
            )
            base_resolved = base_dir.resolve(strict=False)
            try:
                resolved_evidence_next.relative_to(base_resolved)
            except ValueError:
                resolved_evidence_next = None
            if resolved_evidence_next is not None and resolved_evidence_next.is_file():
                actual_hash = hashlib.sha256(
                    resolved_evidence_next.read_bytes()
                ).hexdigest()
                if evidence_hash != actual_hash:
                    errors.append(
                        {
                            "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_EVIDENCE_HASH_MISMATCH",
                            "message": "cloud_artifact evidence_hash must match evidence_next_verdict sha256",
                            "lane_id": lane_id,
                        }
                    )

    boundary = artifact.get("boundary")
    if isinstance(boundary, dict):
        summary["observed_external_facts_only"] = boundary.get(
            "observed_external_facts_only"
        )
        summary["attests_runtime_isolation"] = boundary.get("attests_runtime_isolation")
    if (
        not isinstance(boundary, dict)
        or boundary.get("observed_external_facts_only") is not True
        or boundary.get("attests_runtime_isolation") is not False
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_BOUNDARY_INVALID",
                "message": (
                    "cloud_artifact boundary must record observed_external_facts_only=true "
                    "and attests_runtime_isolation=false"
                ),
                "lane_id": lane_id,
            }
        )

    lane_start_commit = lane.get("start_commit")
    base_sha = artifact.get("base_sha")
    if (
        isinstance(lane_start_commit, str)
        and lane_start_commit
        and isinstance(base_sha, str)
    ):
        if base_sha != lane_start_commit:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_BASE_SHA_MISMATCH",
                    "message": "cloud_artifact base_sha must match lane start_commit",
                    "lane_id": lane_id,
                }
            )

    lane_end_commit = lane.get("end_commit")
    head_sha = artifact.get("head_sha")
    if (
        isinstance(lane_end_commit, str)
        and lane_end_commit
        and isinstance(head_sha, str)
    ):
        if head_sha != lane_end_commit:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_HEAD_SHA_MISMATCH",
                    "message": "cloud_artifact head_sha must match lane end_commit",
                    "lane_id": lane_id,
                }
            )

    lane_pr_url = lane.get("pr_url")
    artifact_pr_url = artifact.get("pr_url")
    if (
        isinstance(lane_pr_url, str)
        and lane_pr_url
        and isinstance(artifact_pr_url, str)
        and artifact_pr_url
        and artifact_pr_url != lane_pr_url
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_PR_URL_MISMATCH",
                "message": "cloud_artifact pr_url must match lane pr_url",
                "lane_id": lane_id,
            }
        )
    elif artifact_pr_url is not None and not isinstance(artifact_pr_url, str):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_INVALID",
                "message": "cloud_artifact pr_url must be a string when present",
                "lane_id": lane_id,
            }
        )

    return summary


def _validate_cloud_artifact_string_field(
    artifact: dict[str, Any],
    field: str,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
) -> None:
    if not isinstance(artifact.get(field), str) or not str(artifact.get(field)).strip():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_INVALID",
                "message": f"cloud_artifact {field} must be a non-empty string",
                "lane_id": lane_id,
            }
        )


def _validate_cloud_artifact_captured_at(
    value: Any,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_INVALID",
                "message": "cloud_artifact captured_at must be a non-empty ISO timestamp",
                "lane_id": lane_id,
            }
        )
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_CLOUD_ARTIFACT_INVALID",
                "message": "cloud_artifact captured_at must be parseable as an ISO timestamp",
                "lane_id": lane_id,
            }
        )


def _validate_worktree_receipt(
    worktree_receipt: Any,
    lane: dict[str, Any],
    base_dir: Path,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
    required: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": worktree_receipt if isinstance(worktree_receipt, str) else None,
        "branch": None,
        "base_commit": None,
        "head_commit": None,
        "dirty": None,
        "dirty_file_count": None,
        "changed_files": [],
    }
    if worktree_receipt is None:
        return summary
    if not isinstance(worktree_receipt, str) or not worktree_receipt.strip():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_PATH_INVALID",
                "message": "worktree_receipt must be a relative JSON path when present",
                "lane_id": lane_id,
            }
        )
        return summary

    receipt_path = Path(worktree_receipt)
    if receipt_path.is_absolute():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_PATH_INVALID",
                "message": "worktree_receipt must be relative to the ledger base directory",
                "lane_id": lane_id,
            }
        )
        return summary

    resolved = (base_dir / receipt_path).resolve(strict=False)
    base_resolved = base_dir.resolve(strict=False)
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_PATH_INVALID",
                "message": "worktree_receipt must stay under the ledger base directory",
                "lane_id": lane_id,
            }
        )
        return summary

    if not resolved.is_file():
        if not required:
            return summary
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_MISSING",
                "message": "worktree_receipt file must exist",
                "lane_id": lane_id,
            }
        )
        return summary

    try:
        receipt = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                "message": f"worktree_receipt must be readable JSON: {exc}",
                "lane_id": lane_id,
            }
        )
        return summary
    if not isinstance(receipt, dict):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                "message": "worktree_receipt root must be an object",
                "lane_id": lane_id,
            }
        )
        return summary

    summary["branch"] = receipt.get("branch")
    summary["base_commit"] = receipt.get("base_commit")
    summary["head_commit"] = receipt.get("head_commit")
    summary["dirty"] = receipt.get("dirty")
    dirty_files = receipt.get("dirty_files")
    if isinstance(dirty_files, list):
        summary["dirty_file_count"] = len(dirty_files)

    if receipt.get("kind") != WORKTREE_LANE_RECEIPT_KIND:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                "message": f"worktree_receipt kind must be {WORKTREE_LANE_RECEIPT_KIND}",
                "lane_id": lane_id,
            }
        )
    if receipt.get("schema_version") != WORKTREE_LANE_RECEIPT_SCHEMA_VERSION:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                "message": (
                    "worktree_receipt schema_version must be "
                    f"{WORKTREE_LANE_RECEIPT_SCHEMA_VERSION}"
                ),
                "lane_id": lane_id,
            }
        )

    for field in ("worktree", "branch", "base_commit", "head_commit", "evidence_dir"):
        if (
            not isinstance(receipt.get(field), str)
            or not str(receipt.get(field)).strip()
        ):
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                    "message": f"worktree_receipt {field} must be a non-empty string",
                    "lane_id": lane_id,
                }
            )

    if receipt.get("dirty") is True:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_DIRTY",
                "message": "worktree_receipt dirty must be false for passed lane fan-in",
                "lane_id": lane_id,
            }
        )
    elif receipt.get("dirty") is not False:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                "message": "worktree_receipt dirty must be a boolean",
                "lane_id": lane_id,
            }
        )

    changed_files = _validate_worktree_receipt_files(
        receipt.get("changed_files"),
        errors,
        lane_id=lane_id,
        field="changed_files",
    )
    _validate_worktree_receipt_files(
        dirty_files,
        errors,
        lane_id=lane_id,
        field="dirty_files",
        allow_empty=True,
    )
    summary["changed_files"] = changed_files

    command_receipts = receipt.get("command_receipts")
    if not isinstance(command_receipts, list) or not all(
        isinstance(item, dict) for item in command_receipts
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                "message": "worktree_receipt command_receipts must be a list of objects",
                "lane_id": lane_id,
            }
        )

    boundary = receipt.get("boundary")
    if not isinstance(boundary, dict) or boundary.get("launches_agents") is not False:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                "message": "worktree_receipt boundary must record launches_agents=false",
                "lane_id": lane_id,
            }
        )

    if isinstance(lane.get("start_commit"), str) and receipt.get(
        "base_commit"
    ) != lane.get("start_commit"):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_BASE_COMMIT_MISMATCH",
                "message": "worktree_receipt base_commit must match lane start_commit",
                "lane_id": lane_id,
            }
        )
    if isinstance(lane.get("end_commit"), str) and receipt.get(
        "head_commit"
    ) != lane.get("end_commit"):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_HEAD_COMMIT_MISMATCH",
                "message": "worktree_receipt head_commit must match lane end_commit",
                "lane_id": lane_id,
            }
        )
    if isinstance(lane.get("evidence_dir"), str) and receipt.get(
        "evidence_dir"
    ) != lane.get("evidence_dir"):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_EVIDENCE_DIR_MISMATCH",
                "message": "worktree_receipt evidence_dir must match lane evidence_dir",
                "lane_id": lane_id,
            }
        )

    lane_touched_files = lane.get("touched_files")
    if (
        isinstance(lane_touched_files, list)
        and all(isinstance(item, str) for item in lane_touched_files)
        and changed_files
    ):
        normalized_touched = {
            PurePosixPath(item).as_posix() for item in lane_touched_files
        }
        changed_set = set(changed_files)
        extra_touched = sorted(normalized_touched - changed_set)
        if extra_touched:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_TOUCHED_FILES_MISMATCH",
                    "message": "worktree_receipt changed_files must cover lane touched_files",
                    "lane_id": lane_id,
                }
            )
        if required:
            under_reported = sorted(changed_set - normalized_touched)
            if under_reported:
                errors.append(
                    {
                        "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_TOUCHED_FILES_UNDERREPORTED",
                        "message": "passed lane touched_files must equal worktree_receipt changed_files",
                        "lane_id": lane_id,
                    }
                )
    return summary


def _validate_worktree_receipt_files(
    value: Any,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
    field: str,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                "message": f"worktree_receipt {field} must be a list of repo-relative paths",
                "lane_id": lane_id,
            }
        )
        return []
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                    "message": f"worktree_receipt {field} entries must be non-empty strings",
                    "lane_id": lane_id,
                }
            )
            continue
        path = PurePosixPath(item)
        if path.is_absolute() or ".." in path.parts:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_INVALID",
                    "message": f"worktree_receipt {field} entries must stay repo-relative",
                    "lane_id": lane_id,
                }
            )
            continue
        normalized.append(path.as_posix())
    return sorted(set(normalized))


def _validate_touched_files(
    touched_files: Any,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
) -> list[str]:
    if touched_files is None:
        return []
    if not isinstance(touched_files, list):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_TOUCHED_FILES_INVALID",
                "message": "touched_files must be a list of repo-relative file paths",
                "lane_id": lane_id,
            }
        )
        return []

    normalized: list[str] = []
    for value in touched_files:
        if not isinstance(value, str) or not value.strip():
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_TOUCHED_FILES_INVALID",
                    "message": "touched_files entries must be non-empty strings",
                    "lane_id": lane_id,
                }
            )
            continue
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_TOUCHED_FILES_INVALID",
                    "message": "touched_files entries must stay repo-relative",
                    "lane_id": lane_id,
                }
            )
            continue
        normalized.append(path.as_posix())
    return sorted(set(normalized))


def _normalize_merge_receipt_lanes(lanes: list[str]) -> list[str]:
    if not isinstance(lanes, list) or not lanes:
        raise TeamLedgerError(
            "ERR_TEAM_LEDGER_MERGE_RECEIPT_LANES_INVALID",
            "lanes must be a non-empty list of lane ids",
        )
    normalized: list[str] = []
    for lane in lanes:
        if not isinstance(lane, str) or not lane.strip():
            raise TeamLedgerError(
                "ERR_TEAM_LEDGER_MERGE_RECEIPT_LANES_INVALID",
                "lanes must contain non-empty lane ids",
            )
        normalized.append(lane.strip())
    return sorted(set(normalized))


def _normalize_repo_relative_files(files: list[str]) -> list[str]:
    if not isinstance(files, list) or not files:
        raise TeamLedgerError(
            "ERR_TEAM_LEDGER_MERGE_RECEIPT_FILES_INVALID",
            "files must be a non-empty list of repo-relative paths",
        )
    normalized: list[str] = []
    for value in files:
        if not isinstance(value, str) or not value.strip():
            raise TeamLedgerError(
                "ERR_TEAM_LEDGER_MERGE_RECEIPT_FILES_INVALID",
                "files must contain non-empty repo-relative paths",
            )
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise TeamLedgerError(
                "ERR_TEAM_LEDGER_MERGE_RECEIPT_FILES_INVALID",
                "files must stay repo-relative",
            )
        normalized.append(path.as_posix())
    return sorted(set(normalized))


def _observed_overlap_files(lane: dict[str, Any]) -> list[Any]:
    receipt = lane.get("worktree_receipt")
    if isinstance(receipt, dict):
        changed_files = receipt.get("changed_files")
        if changed_files:
            return list(changed_files)
    return lane.get("touched_files", [])


def _find_overlapping_touched_files(
    lane_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    owners_by_file: dict[str, list[dict[str, str]]] = {}
    for lane in lane_results:
        if lane["decision"] != "pass":
            continue
        lane_id = str(lane["lane_id"])
        end_commit = lane.get("end_commit")
        owner = {"lane_id": lane_id}
        if isinstance(end_commit, str) and end_commit:
            owner["end_commit"] = end_commit
        for touched_file in _observed_overlap_files(lane):
            owners_by_file.setdefault(str(touched_file), []).append(owner)

    overlaps: list[dict[str, Any]] = []
    for touched_file, owners in sorted(owners_by_file.items()):
        unique_lane_ids = sorted({owner["lane_id"] for owner in owners})
        if len(unique_lane_ids) > 1:
            lane_commits = sorted(
                {
                    owner["end_commit"]
                    for owner in owners
                    if owner["lane_id"] in unique_lane_ids and "end_commit" in owner
                }
            )
            overlap: dict[str, Any] = {
                "path": touched_file,
                "lane_ids": unique_lane_ids,
            }
            if lane_commits:
                overlap["lane_end_commits"] = lane_commits
            overlaps.append(overlap)
    return overlaps


def _validate_merge_receipt(
    merge_receipt: Any,
    base_dir: Path,
    errors: list[dict[str, str]],
    *,
    required: bool,
    overlapping_touched_files: list[dict[str, Any]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": merge_receipt if isinstance(merge_receipt, str) else None,
        "required": required,
        "decision": None,
        "overlap_count": len(overlapping_touched_files),
    }
    if not isinstance(merge_receipt, str) or not merge_receipt.strip():
        if required:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_REQUIRED",
                    "message": "overlapping passed lanes must include merge_receipt",
                }
            )
        return summary

    receipt_path = Path(merge_receipt)
    if receipt_path.is_absolute():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_PATH_INVALID",
                "message": "merge_receipt must be relative to the ledger base directory",
            }
        )
        return summary

    resolved = (base_dir / receipt_path).resolve(strict=False)
    base_resolved = base_dir.resolve(strict=False)
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_PATH_INVALID",
                "message": "merge_receipt must stay under the ledger base directory",
            }
        )
        return summary

    if not resolved.is_file():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_MISSING",
                "message": "merge_receipt file must exist",
            }
        )
        return summary

    try:
        receipt = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
                "message": f"merge_receipt must be readable JSON: {exc}",
            }
        )
        return summary
    if not isinstance(receipt, dict):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
                "message": "merge_receipt root must be an object",
            }
        )
        return summary

    summary["decision"] = receipt.get("decision")
    summary["kind"] = receipt.get("kind") or receipt.get("command")
    required_files = {str(item["path"]) for item in overlapping_touched_files}
    required_lanes = {
        lane_id
        for item in overlapping_touched_files
        for lane_id in item.get("lane_ids", [])
        if isinstance(lane_id, str)
    }

    if receipt.get("kind") == TEAM_LEDGER_MERGE_ATTEMPT_KIND:
        _validate_team_merge_attempt_receipt(receipt, overlapping_touched_files, errors)
        return summary

    if receipt.get("command") != "team-ledger-merge-receipt":
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
                "message": (
                    "merge_receipt command must be team-ledger-merge-receipt or "
                    f"kind must be {TEAM_MERGE_ATTEMPT_KIND}"
                ),
            }
        )
    if receipt.get("decision") != "pass":
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_NOT_PASS",
                "message": "merge_receipt must have decision=pass",
            }
        )
    if not isinstance(receipt.get("conflict_events", []), list):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
                "message": "merge_receipt conflict_events must be a list",
            }
        )
    receipt_files = receipt.get("files")
    receipt_lanes = receipt.get("lanes")
    if not _is_string_list(receipt_files) or not _is_string_list(receipt_lanes):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
                "message": "merge_receipt files and lanes must be lists of non-empty strings",
            }
        )
        return summary

    if not required_files.issubset(set(receipt_files)) or not required_lanes.issubset(
        set(receipt_lanes)
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_COVERAGE_MISSING",
                "message": "merge_receipt must cover every overlapping file and lane id",
            }
        )
    return summary


def _validate_team_merge_attempt_receipt(
    receipt: dict[str, Any],
    overlapping_touched_files: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> None:
    producer_errors = validate_team_merge_attempt_receipt(receipt)
    errors.extend(
        {
            "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
            "message": f"team-merge-attempt invalid: {error['code']}: {error['message']}",
        }
        for error in producer_errors
    )
    if receipt.get("schema_version") != TEAM_LEDGER_SCHEMA_VERSION:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
                "message": f"team-merge-attempt schema_version must be {TEAM_LEDGER_SCHEMA_VERSION}",
            }
        )
    if receipt.get("decision") != "pass":
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_NOT_PASS",
                "message": "merge_receipt must have decision=pass",
            }
        )
    if receipt.get("exit_code") != 0:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_NOT_PASS",
                "message": "team-merge-attempt merge_receipt exit_code must be 0",
            }
        )
    if receipt.get("dirty_target_refused") is not False:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
                "message": "team-merge-attempt dirty_target_refused must be false",
            }
        )

    cleanup = receipt.get("cleanup")
    if (
        not isinstance(cleanup, dict)
        or cleanup.get("attempt_worktree_removed") is not True
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
                "message": "team-merge-attempt cleanup.attempt_worktree_removed must be true",
            }
        )

    conflict_files = receipt.get("conflict_files")
    if not isinstance(conflict_files, list):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
                "message": "team-merge-attempt conflict_files must be a list",
            }
        )
    elif conflict_files:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_CONFLICTS_PRESENT",
                "message": "team-merge-attempt merge_receipt must not contain conflict_files",
            }
        )

    merged_files = receipt.get("merged_files")
    head_commits = receipt.get("head_commits")
    if not _is_string_list(merged_files) or not _is_string_list(head_commits):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_INVALID",
                "message": "team-merge-attempt merged_files and head_commits must be lists of non-empty strings",
            }
        )
        return

    required_files = {str(item["path"]) for item in overlapping_touched_files}
    required_commits = {
        commit
        for item in overlapping_touched_files
        for commit in item.get("lane_end_commits", [])
        if isinstance(commit, str)
    }
    if not required_files.issubset(set(merged_files)) or not required_commits.issubset(
        set(head_commits)
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_MERGE_RECEIPT_COVERAGE_MISSING",
                "message": (
                    "team-merge-attempt merge_receipt must cover every overlapping "
                    "file and lane end_commit"
                ),
            }
        )


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and item for item in value
    )


def build_sample_team_ledger(evidence_dir: str) -> dict[str, Any]:
    """Return a minimal valid Team Ledger v0 object for tests and examples."""

    return {
        "kind": TEAM_LEDGER_KIND,
        "schema_version": TEAM_LEDGER_SCHEMA_VERSION,
        "leader_objective": "Validate a small team fan-in before integration",
        "leader_id": "leader-fixed",
        "start_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "end_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "stop_rule": "fan-in only after every lane passes or is explicitly blocked",
        "lanes": [
            {
                "lane_id": "lane-docs",
                "objective": "Document the control plane direction",
                "env_kind": "local",
                "runner_adapter_kind": "codex",
                "team_adapter_kind": "omx",
                "start_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "end_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "evidence_dir": evidence_dir,
                "pr_url": "",
                "verification_state": "pass",
                "verification_artifacts": ["unittest"],
                "touched_files": ["docs/depone-cloud-team-control.md"],
            }
        ],
    }


def _self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as temp_text:
        root = Path(temp_text)
        evidence = root / "lane-evidence"
        evidence.mkdir()
        evidence_next = evidence / "evidence-next-verdict.json"
        evidence_next.write_text(
            json.dumps(
                {
                    "command": "evidence-next",
                    "schema_version": "1.0",
                    "decision": "continue",
                    "blocking_reasons": [],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["evidence_next_verdict"] = (
            "lane-evidence/evidence-next-verdict.json"
        )
        verdict = build_team_ledger_verdict(ledger, base_dir=root)
        if verdict["decision"] != "pass":
            raise AssertionError("valid ledger must pass")

        pr_artifact = evidence / "pr-artifact.json"
        pr_artifact.write_text(
            json.dumps(
                {
                    "kind": TEAM_LEDGER_PR_ARTIFACT_KIND,
                    "schema_version": TEAM_LEDGER_SCHEMA_VERSION,
                    "provider": "github",
                    "pr_number": 42,
                    "pr_url": "https://github.com/Moonweave-Systems/Depone/pull/42",
                    "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "head_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "state": "OPEN",
                    "merge_state_status": "CLEAN",
                    "check_summary": {
                        "status": "pass",
                        "total_count": 0,
                        "failed_count": 0,
                        "pending_count": 0,
                    },
                    "stale": False,
                    "captured_at": "2026-06-30T06:30:00Z",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        with_pr = build_sample_team_ledger("lane-evidence")
        with_pr["lanes"][0]["evidence_next_verdict"] = (
            "lane-evidence/evidence-next-verdict.json"
        )
        with_pr["lanes"][0]["pr_url"] = (
            "https://github.com/Moonweave-Systems/Depone/pull/42"
        )
        with_pr["lanes"][0]["pr_artifact"] = "lane-evidence/pr-artifact.json"
        with_pr_verdict = build_team_ledger_verdict(with_pr, base_dir=root)
        if with_pr_verdict["decision"] != "pass":
            raise AssertionError("matching PR artifact must pass")

        bad_pr = build_sample_team_ledger("lane-evidence")
        bad_pr["lanes"][0]["evidence_next_verdict"] = (
            "lane-evidence/evidence-next-verdict.json"
        )
        bad_pr["lanes"][0]["pr_artifact"] = "lane-evidence/missing-pr-artifact.json"
        bad_pr_verdict = build_team_ledger_verdict(bad_pr, base_dir=root)
        if bad_pr_verdict["decision"] != "blocked":
            raise AssertionError("missing PR artifact must block")

        cloud_artifact = evidence / "cloud-artifact.json"
        cloud_artifact.write_text(
            json.dumps(
                {
                    "kind": TEAM_LEDGER_CLOUD_ARTIFACT_KIND,
                    "schema_version": TEAM_LEDGER_SCHEMA_VERSION,
                    "provider": "codex-cloud",
                    "adapter_kind": "codex",
                    "external_run_id": "codex-cloud-run-42",
                    "repo": "Moonweave-Systems/Depone",
                    "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "head_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "pr_url": "https://github.com/Moonweave-Systems/Depone/pull/42",
                    "evidence_hash": hashlib.sha256(
                        evidence_next.read_bytes()
                    ).hexdigest(),
                    "captured_at": "2026-06-30T07:30:00Z",
                    "boundary": {
                        "observed_external_facts_only": True,
                        "attests_runtime_isolation": False,
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        cloud_lane = build_sample_team_ledger("lane-evidence")
        cloud_lane["lanes"][0]["env_kind"] = "cloud"
        cloud_lane["lanes"][0]["team_adapter_kind"] = "external"
        cloud_lane["lanes"][0]["evidence_next_verdict"] = (
            "lane-evidence/evidence-next-verdict.json"
        )
        cloud_lane["lanes"][0]["cloud_artifact"] = "lane-evidence/cloud-artifact.json"
        cloud_verdict = build_team_ledger_verdict(cloud_lane, base_dir=root)
        if cloud_verdict["decision"] != "pass":
            raise AssertionError("passed cloud lane with matching artifact must pass")

        missing_cloud = build_sample_team_ledger("lane-evidence")
        missing_cloud["lanes"][0]["env_kind"] = "cloud"
        missing_cloud["lanes"][0]["evidence_next_verdict"] = (
            "lane-evidence/evidence-next-verdict.json"
        )
        missing_cloud_verdict = build_team_ledger_verdict(missing_cloud, base_dir=root)
        if missing_cloud_verdict["decision"] != "blocked":
            raise AssertionError("passed cloud lane without cloud artifact must block")

        second_evidence = root / "lane-evidence-2"
        second_evidence.mkdir()
        second_evidence_next = second_evidence / "evidence-next-verdict.json"
        second_evidence_next.write_text(
            evidence_next.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        receipt = root / "team-merge-receipt.json"
        receipt.write_text(
            json.dumps(
                build_team_ledger_merge_receipt(
                    lanes=["lane-docs", "lane-tests"],
                    files=["depone/agent_fabric/team_ledger.py"],
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        merged = build_sample_team_ledger("lane-evidence")
        merged["merge_receipt"] = "team-merge-receipt.json"
        merged["lanes"][0]["evidence_next_verdict"] = (
            "lane-evidence/evidence-next-verdict.json"
        )
        merged["lanes"][0]["touched_files"] = ["depone/agent_fabric/team_ledger.py"]
        second_lane = dict(merged["lanes"][0])
        second_lane["lane_id"] = "lane-tests"
        second_lane["evidence_dir"] = "lane-evidence-2"
        second_lane["evidence_next_verdict"] = (
            "lane-evidence-2/evidence-next-verdict.json"
        )
        merged["lanes"].append(second_lane)
        merged_verdict = build_team_ledger_verdict(merged, base_dir=root)
        if merged_verdict["decision"] != "pass":
            raise AssertionError(
                "overlapping passed lanes with a passing merge receipt must pass"
            )

        missing = build_sample_team_ledger("missing")
        missing["lanes"][0]["evidence_next_verdict"] = (
            "missing/evidence-next-verdict.json"
        )
        missing_verdict = build_team_ledger_verdict(missing, base_dir=root)
        if missing_verdict["decision"] != "blocked":
            raise AssertionError("passed lane with missing evidence must block")

        blocked = build_sample_team_ledger("missing")
        blocked["lanes"][0]["verification_state"] = "blocked"
        blocked["lanes"][0]["blocked_reason"] = "lane waiting on peer merge"
        blocked_verdict = build_team_ledger_verdict(blocked, base_dir=root)
        if blocked_verdict["decision"] != "blocked-explicit":
            raise AssertionError(
                "explicitly blocked lane must fan in as blocked-explicit"
            )

        invalid = build_sample_team_ledger("lane-evidence")
        invalid["lanes"][0]["env_kind"] = "bare-metal"
        invalid_verdict = build_team_ledger_verdict(invalid, base_dir=root)
        if invalid_verdict["decision"] != "blocked":
            raise AssertionError("invalid env kind must block")


def read_team_ledger(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Team Ledger root must be an object: {path}")
    return value
