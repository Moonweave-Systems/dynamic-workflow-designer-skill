"""depone team-pr-artifact — build and validate Team Ledger PR artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from depone.agent_fabric.team_pr_artifact import (
    TeamPrArtifactError,
    build_team_pr_artifact,
    read_json_object,
    validate_team_pr_artifact,
    write_team_pr_artifact,
)
from depone.agent_fabric.team_pr_artifact import _self_test as _artifact_self_test
from depone.cli._response import EXIT_FAILED, emit_error, emit_result


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        print("depone team-pr-artifact --self-test: pass")
        return

    try:
        if getattr(args, "artifact", ""):
            artifact = read_json_object(Path(str(args.artifact)))
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
        write_team_pr_artifact(artifact, Path(out_arg))

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
            *([f"Team PR artifact written to {out_arg}"] if out_arg and not errors else []),
        ],
    )
    if errors:
        sys.exit(EXIT_FAILED)


def _build_artifact_from_args(args: argparse.Namespace) -> dict[str, Any]:
    source_command: list[str]
    if bool(getattr(args, "live_gh", False)):
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
        raw = read_json_object(Path(input_arg))
        source_command = ["saved-json", input_arg]

    return build_team_pr_artifact(
        raw,
        expected_head_sha=_optional_arg(args, "expected_head_sha"),
        repo=_optional_arg(args, "repo"),
        captured_at=_optional_arg(args, "captured_at"),
        source_command=source_command,
        strict=False,
    )


def _optional_arg(args: argparse.Namespace, name: str) -> str | None:
    value = getattr(args, name, None)
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _self_test() -> None:
    _artifact_self_test()
