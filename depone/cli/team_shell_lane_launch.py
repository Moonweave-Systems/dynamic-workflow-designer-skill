"""depone team-shell-lane-launch - run one allowlisted argv command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from depone.agent_fabric.team_shell_lane_launch import (
    TeamShellLaneLaunchError,
    _self_test,
    load_allowlist,
    run_shell_lane_command,
    write_receipt,
)
from depone.cli._response import emit_error, emit_result, exit_code_for_decision


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        print("depone team-shell-lane-launch --self-test: pass")
        return

    allowlist_arg = str(getattr(args, "allowlist", "") or "")
    if not allowlist_arg:
        emit_error(
            args,
            code="ERR_TEAM_SHELL_LANE_ALLOWLIST_REQUIRED",
            message="--allowlist is required",
        )
    command_id = str(getattr(args, "command_id", "") or "")
    if not command_id:
        emit_error(
            args,
            code="ERR_TEAM_SHELL_LANE_COMMAND_ID_REQUIRED",
            message="--command-id is required",
        )
    out_arg = str(getattr(args, "out", "") or "")
    if not out_arg:
        emit_error(
            args,
            code="ERR_TEAM_SHELL_LANE_OUT_REQUIRED",
            message="--out is required",
        )
    transcript_arg = str(getattr(args, "transcript", "") or "")
    if not transcript_arg:
        emit_error(
            args,
            code="ERR_TEAM_SHELL_LANE_TRANSCRIPT_REQUIRED",
            message="--transcript is required",
        )

    try:
        allowlist = load_allowlist(Path(allowlist_arg))
        receipt = run_shell_lane_command(
            allowlist=allowlist,
            command_id=command_id,
            cwd=Path(str(getattr(args, "cwd", "") or ".")),
            transcript_path=Path(transcript_arg),
            timeout_seconds=int(getattr(args, "timeout_seconds", 120)),
        )
        write_receipt(Path(out_arg), receipt)
    except TeamShellLaneLaunchError as exc:
        emit_error(args, code=exc.code, message=exc.message)

    emit_result(
        args,
        {
            "command": "team-shell-lane-launch",
            "decision": receipt["decision"],
            "command_id": receipt["command_id"],
            "exit_code": receipt["exit_code"],
            "out": out_arg,
            "transcript": transcript_arg,
        },
        human=[
            f"Team shell lane launch decision: {receipt['decision']}",
            f"  Command id: {receipt['command_id']}",
            f"  Exit code: {receipt['exit_code']}",
            f"  Receipt: {out_arg}",
            f"  Transcript: {transcript_arg}",
        ],
    )
    sys.exit(exit_code_for_decision(str(receipt["decision"])))
