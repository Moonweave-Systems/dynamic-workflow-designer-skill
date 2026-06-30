"""Stdlib-only GitHub PR artifact producer for Team Ledger lanes.

The artifact is non-executing evidence: this module does not call GitHub,
launch agents, approve merges, or raise assurance. It normalizes a saved PR JSON
object into the Team Ledger PR artifact shape and validates that the artifact is
safe to fan in.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from depone.agent_fabric.team_ledger import (
    TEAM_LEDGER_PR_ARTIFACT_KIND,
    TEAM_LEDGER_SCHEMA_VERSION,
)

TEAM_PR_ARTIFACT_KIND = TEAM_LEDGER_PR_ARTIFACT_KIND
TEAM_PR_ARTIFACT_SCHEMA_VERSION = TEAM_LEDGER_SCHEMA_VERSION
TEAM_PR_ARTIFACT_PROVIDER = "github"
VALID_PASSING_PR_MERGE_STATES = frozenset({"CLEAN", "HAS_HOOKS"})
VALID_PR_STATES = frozenset({"OPEN", "MERGED", "CLOSED"})
PASSING_CHECK_STATUSES = frozenset({"pass", "success"})
PASSING_CHECK_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})
FAILED_CHECK_CONCLUSIONS = frozenset(
    {"ACTION_REQUIRED", "CANCELLED", "FAILURE", "FAILED", "STARTUP_FAILURE", "TIMED_OUT"}
)
PENDING_CHECK_STATES = frozenset({"EXPECTED", "IN_PROGRESS", "PENDING", "QUEUED", "REQUESTED", "WAITING"})


class TeamPrArtifactError(ValueError):
    """Structured Team PR artifact producer error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message

    def to_record(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def build_team_pr_artifact(
    pr: dict[str, Any],
    *,
    expected_head_sha: str | None = None,
    captured_at: str | None = None,
    repo: str | None = None,
    source_command: list[str] | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    """Normalize saved GitHub PR JSON into a deterministic Team Ledger artifact."""

    if not isinstance(pr, dict):
        raise TeamPrArtifactError("ERR_TEAM_PR_ARTIFACT_INPUT_INVALID", "PR input must be an object")

    if pr.get("kind") == TEAM_PR_ARTIFACT_KIND:
        artifact = dict(pr)
        errors = validate_team_pr_artifact(artifact, expected_head_sha=expected_head_sha)
        if errors and strict:
            first = errors[0]
            raise TeamPrArtifactError(first["code"], first["message"])
        return artifact

    pr_number = _first_present(pr, "pr_number", "number")
    if isinstance(pr_number, str) and pr_number.isdecimal():
        pr_number = int(pr_number)
    pr_url = _first_present(pr, "pr_url", "url")
    base_sha = _first_present(pr, "base_sha", "baseRefOid") or _nested_first_present(
        pr, "baseRef", ("oid", "targetOid")
    )
    head_sha = _first_present(pr, "head_sha", "headRefOid") or _nested_first_present(
        pr, "headRef", ("oid", "targetOid")
    )
    state = _first_present(pr, "state")
    merge_state_status = _first_present(pr, "merge_state_status", "mergeStateStatus")
    captured_at_text = captured_at or _first_present(pr, "captured_at", "capturedAt") or _utc_now()
    stale = _first_present(pr, "stale")
    if stale is None:
        stale = bool(expected_head_sha and isinstance(head_sha, str) and head_sha != expected_head_sha)

    artifact = {
        "kind": TEAM_PR_ARTIFACT_KIND,
        "schema_version": TEAM_PR_ARTIFACT_SCHEMA_VERSION,
        "provider": TEAM_PR_ARTIFACT_PROVIDER,
        "repo": repo or _read_repo(pr) or _repo_from_github_url(pr_url),
        "pr_number": pr_number,
        "pr_url": pr_url,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "state": str(state).upper() if isinstance(state, str) else state,
        "merge_state_status": (
            str(merge_state_status).upper() if isinstance(merge_state_status, str) else merge_state_status
        ),
        "check_summary": _normalize_check_summary(pr),
        "stale": stale,
        "captured_at": captured_at_text,
        "source_command": source_command or _normalize_source_command(pr.get("source_command")),
        "boundary": {
            "observed_external_facts_only": True,
            "executes_commands": False,
            "launches_agents": False,
            "calls_live_models": False,
            "approves_merge": False,
            "raises_assurance": False,
        },
    }
    errors = validate_team_pr_artifact(artifact, expected_head_sha=expected_head_sha)
    if errors and strict:
        first = errors[0]
        raise TeamPrArtifactError(first["code"], first["message"])
    return artifact


def validate_team_pr_artifact(
    artifact: dict[str, Any],
    *,
    expected_head_sha: str | None = None,
    expected_base_sha: str | None = None,
    expected_pr_url: str | None = None,
) -> list[dict[str, str]]:
    """Return fail-closed validation errors for a Team Ledger PR artifact."""

    errors: list[dict[str, str]] = []
    if not isinstance(artifact, dict):
        return [
            {
                "code": "ERR_TEAM_PR_ARTIFACT_INVALID",
                "message": "artifact root must be an object",
            }
        ]

    if artifact.get("kind") != TEAM_PR_ARTIFACT_KIND:
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", f"kind must be {TEAM_PR_ARTIFACT_KIND}"))
    if artifact.get("schema_version") != TEAM_PR_ARTIFACT_SCHEMA_VERSION:
        errors.append(
            _error(
                "ERR_TEAM_PR_ARTIFACT_INVALID",
                f"schema_version must be {TEAM_PR_ARTIFACT_SCHEMA_VERSION}",
            )
        )
    if artifact.get("provider") != TEAM_PR_ARTIFACT_PROVIDER:
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", "provider must be github"))
    if not isinstance(artifact.get("repo"), str) or not str(artifact.get("repo")).strip():
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", "repo must be a non-empty string"))
    if not isinstance(artifact.get("pr_number"), int) or artifact.get("pr_number", 0) <= 0:
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", "pr_number must be a positive integer"))

    pr_url = artifact.get("pr_url")
    if not isinstance(pr_url, str) or not pr_url.strip() or not _is_github_pull_url(pr_url):
        errors.append(
            _error("ERR_TEAM_PR_ARTIFACT_URL_INVALID", "pr_url must be an https GitHub pull request URL")
        )
    elif expected_pr_url is not None and pr_url != expected_pr_url:
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_PR_URL_MISMATCH", "pr_url must match expected_pr_url"))

    _validate_sha(artifact, "base_sha", errors)
    _validate_sha(artifact, "head_sha", errors)
    _validate_iso_timestamp(artifact.get("captured_at"), errors)
    _validate_source_command(artifact.get("source_command"), errors)

    head_sha = artifact.get("head_sha")
    if expected_head_sha is not None and isinstance(head_sha, str) and head_sha != expected_head_sha:
        errors.append(
            _error("ERR_TEAM_PR_ARTIFACT_HEAD_SHA_MISMATCH", "head_sha must match expected_head_sha")
        )
    base_sha = artifact.get("base_sha")
    if expected_base_sha is not None and isinstance(base_sha, str) and base_sha != expected_base_sha:
        errors.append(
            _error("ERR_TEAM_PR_ARTIFACT_BASE_SHA_MISMATCH", "base_sha must match expected_base_sha")
        )

    if artifact.get("stale") is not False:
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_STALE", "stale must be false"))

    state = artifact.get("state")
    if not isinstance(state, str) or state.upper() not in VALID_PR_STATES:
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_STATE_INVALID", "state must be OPEN, MERGED, or CLOSED"))

    merge_state_status = artifact.get("merge_state_status")
    if (
        not isinstance(merge_state_status, str)
        or merge_state_status.upper() not in VALID_PASSING_PR_MERGE_STATES
    ):
        errors.append(
            _error("ERR_TEAM_PR_ARTIFACT_NOT_MERGEABLE", "merge_state_status must be CLEAN or HAS_HOOKS")
        )

    _validate_check_summary(artifact.get("check_summary"), errors)
    _validate_boundary(artifact.get("boundary"), errors)
    return errors


def write_team_pr_artifact(artifact: dict[str, Any], out_path: Path) -> None:
    """Validate and write a deterministic JSON artifact with a trailing newline."""

    errors = validate_team_pr_artifact(artifact)
    if errors:
        first = errors[0]
        raise TeamPrArtifactError(first["code"], first["message"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON object or raise a structured artifact error."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TeamPrArtifactError("ERR_TEAM_PR_ARTIFACT_INPUT_INVALID", f"input must be readable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise TeamPrArtifactError("ERR_TEAM_PR_ARTIFACT_INPUT_INVALID", "input root must be an object")
    return value


def _normalize_check_summary(pr: dict[str, Any]) -> dict[str, int | str | None]:
    raw_summary = pr.get("check_summary")
    if isinstance(raw_summary, dict):
        return {
            "status": raw_summary.get("status"),
            "total_count": raw_summary.get("total_count"),
            "failed_count": raw_summary.get("failed_count"),
            "pending_count": raw_summary.get("pending_count"),
        }

    raw_rollup = pr.get("statusCheckRollup") or pr.get("status_check_rollup")
    if isinstance(raw_rollup, dict):
        contexts = raw_rollup.get("contexts")
        if isinstance(contexts, dict):
            raw_rollup = contexts.get("nodes")
        elif isinstance(contexts, list):
            raw_rollup = contexts
        elif isinstance(raw_rollup.get("nodes"), list):
            raw_rollup = raw_rollup.get("nodes")

    if not isinstance(raw_rollup, list):
        return {"status": "blocked", "total_count": 0, "failed_count": 0, "pending_count": 1}

    failed_count = 0
    pending_count = 0
    for item in raw_rollup:
        if not isinstance(item, dict):
            pending_count += 1
            continue
        conclusion = _upper_or_empty(item.get("conclusion"))
        status = _upper_or_empty(item.get("status"))
        state = _upper_or_empty(item.get("state"))
        if conclusion in FAILED_CHECK_CONCLUSIONS or state in {"FAILURE", "ERROR"}:
            failed_count += 1
            continue
        if conclusion in PASSING_CHECK_CONCLUSIONS or status in {"COMPLETED", "SUCCESS"} or state in {"SUCCESS", "PASS"}:
            continue
        if status in PENDING_CHECK_STATES or state in PENDING_CHECK_STATES or not conclusion:
            pending_count += 1
            continue
        failed_count += 1
    return {
        "status": "pass" if failed_count == 0 and pending_count == 0 else "blocked",
        "total_count": len(raw_rollup),
        "failed_count": failed_count,
        "pending_count": pending_count,
    }


def _first_present(value: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return None


def _nested_first_present(value: dict[str, Any], key: str, nested_keys: tuple[str, ...]) -> Any:
    nested = value.get(key)
    if not isinstance(nested, dict):
        return None
    return _first_present(nested, *nested_keys)


def _read_repo(raw: dict[str, Any]) -> str:
    repository = raw.get("repository")
    if isinstance(repository, dict):
        name = repository.get("nameWithOwner") or repository.get("name_with_owner")
        if isinstance(name, str):
            return name
    repo = raw.get("repo")
    return repo if isinstance(repo, str) else ""


def _repo_from_github_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parsed = urlparse(value)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc.lower() == "github.com" and len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return ""


def _normalize_source_command(value: Any) -> list[str]:
    if isinstance(value, list) and value and all(isinstance(item, str) and item for item in value):
        return list(value)
    return ["saved-json"]


def _validate_sha(value: dict[str, Any], field: str, errors: list[dict[str, str]]) -> None:
    raw = value.get(field)
    if not isinstance(raw, str) or not raw.strip():
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", f"{field} must be a non-empty string"))
        return
    if len(raw) != 40 or any(character not in "0123456789abcdefABCDEF" for character in raw):
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", f"{field} must be a 40-character hex SHA"))


def _validate_iso_timestamp(value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", "captured_at must be a non-empty ISO timestamp"))
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", "captured_at must be parseable as an ISO timestamp"))


def _validate_source_command(value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", "source_command must be a non-empty list of strings"))


def _validate_check_summary(value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, dict):
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", "check_summary must be an object"))
        return
    check_status = value.get("status")
    failed_count = value.get("failed_count")
    pending_count = value.get("pending_count")
    total_count = value.get("total_count")
    if not isinstance(check_status, str) or check_status.lower() not in PASSING_CHECK_STATUSES:
        errors.append(
            _error("ERR_TEAM_PR_ARTIFACT_CHECKS_NOT_PASSING", "check_summary status must be pass or success")
        )
    for field, raw_count in (
        ("total_count", total_count),
        ("failed_count", failed_count),
        ("pending_count", pending_count),
    ):
        if not isinstance(raw_count, int) or raw_count < 0:
            errors.append(
                _error("ERR_TEAM_PR_ARTIFACT_INVALID", f"check_summary {field} must be a non-negative integer")
            )
    if failed_count != 0 or pending_count != 0:
        errors.append(
            _error(
                "ERR_TEAM_PR_ARTIFACT_CHECKS_NOT_PASSING",
                "check_summary must have zero failed and pending checks",
            )
        )


def _validate_boundary(value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, dict):
        errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", "boundary must be an object"))
        return
    for field in (
        "observed_external_facts_only",
        "executes_commands",
        "launches_agents",
        "calls_live_models",
        "approves_merge",
        "raises_assurance",
    ):
        if field not in value:
            errors.append(_error("ERR_TEAM_PR_ARTIFACT_INVALID", f"boundary {field} is required"))
    for field in ("executes_commands", "launches_agents", "calls_live_models", "approves_merge", "raises_assurance"):
        if value.get(field) is not False:
            errors.append(_error("ERR_TEAM_PR_ARTIFACT_BOUNDARY_INVALID", f"boundary {field} must be false"))
    if value.get("observed_external_facts_only") is not True:
        errors.append(
            _error("ERR_TEAM_PR_ARTIFACT_BOUNDARY_INVALID", "boundary observed_external_facts_only must be true")
        )


def _is_github_pull_url(value: str) -> bool:
    parsed = urlparse(value)
    parts = [part for part in parsed.path.split("/") if part]
    return (
        parsed.scheme == "https"
        and parsed.netloc.lower() == "github.com"
        and len(parts) == 4
        and parts[2] == "pull"
        and parts[3].isdigit()
    )


def _upper_or_empty(value: Any) -> str:
    return value.upper() if isinstance(value, str) else ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _self_test() -> None:
    import tempfile

    source = {
        "number": 42,
        "url": "https://github.com/Moonweave-Systems/Depone/pull/42",
        "baseRefOid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "headRefOid": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "state": "OPEN",
        "mergeStateStatus": "CLEAN",
        "repository": {"nameWithOwner": "Moonweave-Systems/Depone"},
        "statusCheckRollup": [{"name": "contract", "conclusion": "SUCCESS", "status": "COMPLETED"}],
    }
    artifact = build_team_pr_artifact(
        source,
        expected_head_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        captured_at="2026-06-30T15:00:00Z",
        source_command=["saved-json", "self-test"],
    )
    if validate_team_pr_artifact(artifact, expected_head_sha=source["headRefOid"]):
        raise AssertionError("valid team PR artifact must pass")
    bad = dict(artifact)
    bad["head_sha"] = "cccccccccccccccccccccccccccccccccccccccc"
    mismatch = validate_team_pr_artifact(
        bad,
        expected_head_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )
    if not any(error["code"] == "ERR_TEAM_PR_ARTIFACT_HEAD_SHA_MISMATCH" for error in mismatch):
        raise AssertionError("expected head SHA mismatch")
    with tempfile.TemporaryDirectory() as temp_text:
        out = Path(temp_text) / "pr-artifact.json"
        write_team_pr_artifact(artifact, out)
        if read_json_object(out)["kind"] != TEAM_PR_ARTIFACT_KIND:
            raise AssertionError("written artifact must be readable JSON")
