"""depone team-worktree-prep — prepare local lane worktrees without agents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from depone.agent_fabric.team_worktree_prep import (
    TeamWorktreePrepError,
    _self_test,
    build_team_worktree_prep,
)
from depone.cli._response import emit_error, emit_result


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        print("depone team-worktree-prep --self-test: pass")
        return

    preflight_arg = str(getattr(args, "team_launch_preflight", "") or "")
    if not preflight_arg:
        emit_error(
            args,
            code="ERR_TEAM_WORKTREE_PREP_PREFLIGHT_REQUIRED",
            message="--team-launch-preflight is required",
        )
    preflight_path = Path(preflight_arg)
    try:
        preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        emit_error(
            args,
            code="ERR_TEAM_WORKTREE_PREP_PREFLIGHT_READ_FAILED",
            message=str(exc),
            path=preflight_path,
        )
    if not isinstance(preflight, dict):
        emit_error(
            args,
            code="ERR_TEAM_WORKTREE_PREP_PREFLIGHT_INVALID",
            message="--team-launch-preflight must point to a JSON object",
            path=preflight_path,
        )

    try:
        receipt = build_team_worktree_prep(
            preflight,
            repo_root=Path(str(getattr(args, "repo", "") or ".")),
            worktree_root=Path(str(getattr(args, "worktree_root", "") or ".")),
            create_worktree=bool(getattr(args, "create_worktree", False)),
        )
    except TeamWorktreePrepError as exc:
        emit_error(args, code=exc.code, message=exc.message)

    out_arg = str(getattr(args, "out", "") or "")
    if out_arg:
        out_path = Path(out_arg)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    emit_result(
        args,
        {
            "command": "team-worktree-prep",
            "decision": receipt["decision"],
            "lane_count": receipt["lane_count"],
            "created_lane_count": sum(
                1 for lane in receipt["lanes"] if isinstance(lane, dict) and lane.get("action") == "created"
            ),
            "selected_lane_count": sum(
                1 for lane in receipt["lanes"] if isinstance(lane, dict) and lane.get("action") == "selected"
            ),
            "error_count": len(receipt["errors"]),
            **({"out": out_arg} if out_arg else {}),
        },
        human=[
            f"Team worktree prep decision: {receipt['decision']}",
            f"  Lanes: {receipt['lane_count']}",
            f"  Errors: {len(receipt['errors'])}",
            *( [f"Team worktree prep written to {out_arg}"] if out_arg else [] ),
        ],
    )
