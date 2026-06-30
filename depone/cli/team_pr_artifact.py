"""depone team-pr-artifact — build and validate Team Ledger PR artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from depone.agent_fabric.team_ledger import (
    TEAM_LEDGER_PR_ARTIFACT_KIND,
    TEAM_LEDGER_SCHEMA_VERSION,
)
from depone.cli._response import EXIT_FAILED, emit_error, emit_result

PASSING_CHECK_STATUSES = frozenset({"pass", "success"})
PASSING_MERGE_STATES = frozenset({"CLEAN", "HAS_HOOKS"})
VALID_PR_STATES = frozenset({"OPEN", "MERGED", "CLOSED"})
FAILED_CONCLUSIONS = frozenset(
    {"ACTION_REQUIRED", "CANCELLED", "FAILURE", "STARTUP_FAILURE", "TIMED_OUT"}
)
PASSING_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})
PENDING_STATUSES = frozenset({"EXPECTED", "IN_PROGRESS", "PENDING", "QUEUED", "REQUESTED", "WAITING"})


class TeamPrArtifactError(ValueError):
    """Structured team-pr-artifact error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        print("depone team-pr-artifact --self-test: pass")
        return

    try:
        if getattr(args, "artifact", ""):
            artifact = _read_json_object(Path(str(args.artifact)))
        else:
            artifact = _build_artifact_from_args(args)

        errors = validate_team_pr_artifact(
            artifact,
            expected_head_sha=_optional_arg(args, "expected_head_sha"),
            expected_base_sha=_optional_arg(args, "expected_base_sha"),
            expected_pr_url=_optional_arg(args, "expected_pr_url"),
        )
    except (OSError, json.JSONDecodeError, TeamPrArtifactError, subprocess.SubprocessError) as exc:
        code = exc.code if isinstance(exc, TeamPrArtifactError) else "ERR_TEAM_PR_ARTIFACT_FAILED"
        emit_error(args, code=code, message=str(exc))

    out_arg = str(getattr(args, "out", "") or "")
    if out_arg and not errors:
        out_path = Path(out_arg)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    decision = "pass" if not errors else "blocked"
    emit_result(
        args,
        {
            "command": "team-pr-artifact",
            "decision": decision,
            "error_count": len(errors),
            "pr_number": artifact.get("pr_number"),
            "pr_url": artifact.get("pr_url"),
            "head_sha": artifact.get("head_sha"),
            **({"out": out_arg} if out_arg and not errors else {}),
            **({"errors": errors} if errors else {}),
        },
        human=[
            f"Team PR artifact decision: {decision}",
            f"  PR: {artifact.get('pr_url')}",
            f"  Errors: {len(errors)}",
            *( [f"Team PR artifact written to {out_arg}"] if out_arg and not errors else [] ),
        ],
    )
    if errors:
        sys.exit(EXIT_FAILED)


def _build_artifact_from_args(args: argparse.Namespace) -> dict[str, Any]:
    source_command: list[str]
    if _optional_arg(args, "live_gh"):
        repo = _optional_arg(args, "repo")
        pr_number = _optional_arg(args, "pr_number")
        if not repo or not pr_number:
            raise TeamPrArtifactError(
                "ERR_TEAM_PR_ARTIFACT_GH_ARGS_REQUIRED",
                "--live-gh requires --repo and --pr-number",
            )
        source_command = [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repo,
            "--json",
            "number,url,state,mergeStateStatus,baseRefOid,headRefOid,statusCheckRollup",
        ]
        completed = subprocess.run(source_command, capture_output=True, text=True, check=False, timeout=30)
        if completed.returncode != 0:
            raise TeamPrArtifactError(
                "ERR_TEAM_PR_ARTIFACT_GH_FAILED",
                f"gh pr view failed with exit {completed.returncode}: {completed.stderr.strip()}",
            )
        raw = json.loads(completed.stdout)
    else:
        input_arg = _optional_arg(args, "input")
        if not input_arg:
            raise TeamPrArtifactError(
                "ERR_TEAM_PR_ARTIFACT_INPUT_REQUIRED",
                "provide --input saved JSON, --artifact, or --live-gh",
            )
        raw = _read_json_object(Path(input_arg))
        source_command = ["saved-json", input_arg]

    return build_team_pr_artifact(
        raw,
        repo=_optional_arg(args, "repo"),
        captured_at=_optional_arg(args, "captured_at"),
        source_command=source_command,
    )


def build_team_pr_artifact(
    raw: dict[str, Any],
    *,
    repo: str | None = None,
    captured_at: str | None = None,
    source_command: list[str] | None = None,
) -> dict[str, Any]:
    """Normalize saved GitHub PR JSON into a Team Ledger PR artifact."""

    if raw.get("kind") == TEAM_LEDGER_PR_ARTIFACT_KIND:
        return dict(raw)

    pr_number = raw.get("number", raw.get("pr_number"))
    if isinstance(pr_number, str) and pr_number.isdecimal():
        pr_number = int(pr_number)
    artifact = {
        "kind": TEAM_LEDGER_PR_ARTIFACT_KIND,
        "schema_version": TEAM_LEDGER_SCHEMA_VERSION,
        "provider": "github",
        "repo": repo or _read_repo(raw),
        "pr_number": pr_number,
        "pr_url": _read_first_string(raw, "url", "pr_url"),
        "base_sha": _read_first_string(raw, "baseRefOid", "base_sha", "base_sha"),
        "head_sha": _read_first_string(raw, "headRefOid", "head_sha", "head_sha"),
        "state": str(raw.get("state", "")).upper(),
        "merge_state_status": str(raw.get("mergeStateStatus", raw.get("merge_state_status", ""))).upper(),
        "check_summary": _build_check_summary(raw),
        "stale": bool(raw.get("stale", False)),
        "captured_at": captured_at or _read_first_string(raw, "captured_at", "capturedAt"),
        "source_command": source_command or raw.get("source_command") or ["saved-json"],
    }
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
    if artifact.get("kind") != TEAM_LEDGER_PR_ARTIFACT_KIND:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", f"kind must be {TEAM_LEDGER_PR_ARTIFACT_KIND}"))
    if artifact.get("schema_version") != TEAM_LEDGER_SCHEMA_VERSION:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", f"schema_version must be {TEAM_LEDGER_SCHEMA_VERSION}"))
    if artifact.get("provider") != "github":
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", "provider must be github"))
    if not isinstance(artifact.get("repo"), str) or not artifact.get("repo", "").strip():
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", "repo must be a non-empty string"))
    if not isinstance(artifact.get("pr_number"), int) or artifact.get("pr_number", 0) <= 0:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", "pr_number must be a positive integer"))
    for field in ("pr_url", "base_sha", "head_sha", "merge_state_status"):
        if not isinstance(artifact.get(field), str) or not artifact.get(field, "").strip():
            errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", f"{field} must be a non-empty string"))
    if artifact.get("state") not in VALID_PR_STATES:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", "state must be OPEN, MERGED, or CLOSED"))
    if artifact.get("merge_state_status") not in PASSING_MERGE_STATES:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_NOT_MERGEABLE", "merge_state_status must be CLEAN or HAS_HOOKS"))
    if artifact.get("stale") is not False:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_STALE", "stale must be false"))
    _validate_captured_at(artifact.get("captured_at"), errors)
    _validate_source_command(artifact.get("source_command"), errors)
    _validate_check_summary(artifact.get("check_summary"), errors)
    if expected_head_sha and artifact.get("head_sha") != expected_head_sha:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_HEAD_SHA_MISMATCH", "head_sha does not match expected head SHA"))
    if expected_base_sha and artifact.get("base_sha") != expected_base_sha:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_BASE_SHA_MISMATCH", "base_sha does not match expected base SHA"))
    if expected_pr_url and artifact.get("pr_url") != expected_pr_url:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_PR_URL_MISMATCH", "pr_url does not match expected PR URL"))
    return errors


def _build_check_summary(raw: dict[str, Any]) -> dict[str, Any]:
    existing = raw.get("check_summary")
    if isinstance(existing, dict):
        return dict(existing)

    rollup = raw.get("statusCheckRollup") or raw.get("status_check_rollup")
    checks = _flatten_rollup(rollup)
    if not checks:
        return {"status": "blocked", "total_count": 0, "failed_count": 0, "pending_count": 1}

    failed_count = 0
    pending_count = 0
    for check in checks:
        conclusion = _upper_string(check.get("conclusion"))
        status = _upper_string(check.get("status"))
        state = _upper_string(check.get("state"))
        if conclusion in FAILED_CONCLUSIONS or state in {"FAILURE", "ERROR"}:
            failed_count += 1
        elif conclusion in PASSING_CONCLUSIONS or status in {"COMPLETED", "SUCCESS"} or state in {"SUCCESS", "PASS"}:
            continue
        elif status in PENDING_STATUSES or state in PENDING_STATUSES or not conclusion:
            pending_count += 1
        else:
            failed_count += 1
    return {
        "status": "pass" if failed_count == 0 and pending_count == 0 else "blocked",
        "total_count": len(checks),
        "failed_count": failed_count,
        "pending_count": pending_count,
    }


def _flatten_rollup(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        nodes = value.get("nodes")
        if isinstance(nodes, list):
            return [item for item in nodes if isinstance(item, dict)]
        contexts = value.get("contexts")
        if isinstance(contexts, dict) and isinstance(contexts.get("nodes"), list):
            return [item for item in contexts["nodes"] if isinstance(item, dict)]
        if isinstance(contexts, list):
            return [item for item in contexts if isinstance(item, dict)]
    return []


def _validate_check_summary(value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, dict):
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", "check_summary must be an object"))
        return
    status = value.get("status")
    if not isinstance(status, str) or status.lower() not in PASSING_CHECK_STATUSES:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_CHECKS_NOT_PASSING", "check_summary status must be pass or success"))
    for field in ("total_count", "failed_count", "pending_count"):
        if not isinstance(value.get(field), int) or value.get(field) < 0:
            errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", f"check_summary {field} must be a non-negative integer"))
    if value.get("failed_count") != 0 or value.get("pending_count") != 0:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_CHECKS_NOT_PASSING", "check_summary must have zero failed and pending checks"))


def _validate_captured_at(value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", "captured_at must be a non-empty ISO timestamp"))
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", "captured_at must be parseable as an ISO timestamp"))


def _validate_source_command(value: Any, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        errors.append(_err("ERR_TEAM_PR_ARTIFACT_INVALID", "source_command must be a non-empty list of strings"))


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TeamPrArtifactError("ERR_TEAM_PR_ARTIFACT_INPUT_INVALID", "input JSON root must be an object")
    return value


def _read_repo(raw: dict[str, Any]) -> str:
    repository = raw.get("repository")
    if isinstance(repository, dict):
        name = repository.get("nameWithOwner") or repository.get("name_with_owner")
        if isinstance(name, str):
            return name
    return str(raw.get("repo", ""))


def _read_first_string(raw: dict[str, Any], *names: str) -> str:
    for name in names:
        value = raw.get(name)
        if isinstance(value, str):
            return value
    return ""


def _optional_arg(args: argparse.Namespace, name: str) -> str | None:
    value = getattr(args, name, None)
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _upper_string(value: Any) -> str:
    return str(value).upper() if value is not None else ""


def _err(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _self_test() -> None:
    saved = {
        "number": 42,
        "url": "https://github.com/Moonweave-Systems/Depone/pull/42",
        "state": "OPEN",
        "mergeStateStatus": "CLEAN",
        "baseRefOid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "headRefOid": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "repository": {"nameWithOwner": "Moonweave-Systems/Depone"},
        "statusCheckRollup": [{"name": "contract", "conclusion": "SUCCESS", "status": "COMPLETED"}],
    }
    artifact = build_team_pr_artifact(
        saved,
        captured_at="2026-06-30T15:30:00Z",
        source_command=["saved-json", "self-test"],
    )
    errors = validate_team_pr_artifact(
        artifact,
        expected_head_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )
    if errors:
        raise AssertionError(errors)
    bad = dict(artifact)
    bad["head_sha"] = "cccccccccccccccccccccccccccccccccccccccc"
    mismatch = validate_team_pr_artifact(
        bad,
        expected_head_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )
    if not any(error["code"] == "ERR_TEAM_PR_ARTIFACT_HEAD_SHA_MISMATCH" for error in mismatch):
        raise AssertionError("expected head SHA mismatch")


