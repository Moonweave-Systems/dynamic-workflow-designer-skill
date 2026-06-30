"""depone team-launch-preflight - validate planned team lanes without launching workers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from depone.agent_fabric.team_launch_preflight import (
    _self_test as team_launch_preflight_self_test,
    build_team_launch_preflight,
)
from depone.cli._response import emit_error, emit_result, exit_code_for_decision


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        team_launch_preflight_self_test()
        print("depone team-launch-preflight --self-test: pass")
        return

    team_dry_run_arg = str(getattr(args, "team_dry_run", "") or "")
    if not team_dry_run_arg:
        emit_error(
            args,
            code="ERR_TEAM_LAUNCH_PREFLIGHT_DRY_RUN_REQUIRED",
            message="--team-dry-run is required",
        )
    team_dry_run_path = Path(team_dry_run_arg)
    try:
        team_dry_run = _read_json_object(team_dry_run_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit_error(
            args,
            code="ERR_TEAM_LAUNCH_PREFLIGHT_READ_FAILED",
            message=str(exc),
            path=team_dry_run_path,
        )

    adapter_availability = None
    adapter_availability_arg = str(getattr(args, "adapter_availability", "") or "")
    if adapter_availability_arg:
        adapter_availability_path = Path(adapter_availability_arg)
        try:
            adapter_availability = _read_json_object(adapter_availability_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            emit_error(
                args,
                code="ERR_TEAM_LAUNCH_PREFLIGHT_ADAPTER_AVAILABILITY_READ_FAILED",
                message=str(exc),
                path=adapter_availability_path,
            )

    base_commit = str(getattr(args, "base_commit", "") or team_dry_run.get("base_commit", ""))
    preflight = build_team_launch_preflight(
        team_dry_run,
        repo_root=Path(str(getattr(args, "repo", "") or ".")),
        base_commit=base_commit,
        launch_intent=str(getattr(args, "launch_intent", "") or "plan-only"),
        adapter_availability=adapter_availability,
    )

    out_arg = str(getattr(args, "out", "") or "")
    out_path = Path(out_arg) if out_arg else None
    if out_path is not None:
        _write_json(out_path, preflight)

    team_ledger_arg = str(getattr(args, "team_ledger_out", "") or "")
    team_ledger_path = Path(team_ledger_arg) if team_ledger_arg else None
    if team_ledger_path is not None:
        team_ledger = team_dry_run.get("team_ledger")
        if not isinstance(team_ledger, dict):
            emit_error(
                args,
                code="ERR_TEAM_LAUNCH_PREFLIGHT_TEAM_LEDGER_MISSING",
                message="team dry-run artifact must include team_ledger to write --team-ledger-out",
            )
        _write_json(team_ledger_path, team_ledger)

    files: dict[str, str] = {}
    if out_path is not None:
        files["team_launch_preflight"] = out_path.as_posix()
    if team_ledger_path is not None:
        files["team_ledger"] = team_ledger_path.as_posix()

    emit_result(
        args,
        {
            "command": "team-launch-preflight",
            "kind": preflight["kind"],
            "decision": preflight["decision"],
            "lane_count": preflight["lane_count"],
            "error_count": len(preflight["errors"]),
            "files": files,
            "boundary": preflight["boundary"],
        },
        human=[
            f"Team launch preflight decision: {preflight['decision']}",
            f"  Lanes: {preflight['lane_count']}",
            f"  Errors: {len(preflight['errors'])}",
            "  Boundary: does not launch agents, create worktrees, or execute commands",
        ],
    )
    sys.exit(exit_code_for_decision(str(preflight["decision"])))


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON input must be an object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
