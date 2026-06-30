"""depone team-ledger — validate Team Ledger v0 fan-in evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depone.agent_fabric.team_ledger import (
    _self_test as team_ledger_self_test,
    build_team_ledger_verdict,
    read_team_ledger,
)
from depone.cli._response import EXIT_FAILED, emit_error, emit_result


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        team_ledger_self_test()
        print("depone team-ledger --self-test: pass")
        return

    ledger_arg = str(getattr(args, "ledger", "") or "")
    if not ledger_arg:
        emit_error(
            args,
            code="ERR_TEAM_LEDGER_INPUT_REQUIRED",
            message="--ledger is required",
        )
    ledger_path = Path(ledger_arg)
    try:
        ledger = read_team_ledger(ledger_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit_error(
            args,
            code="ERR_TEAM_LEDGER_READ_FAILED",
            message=str(exc),
            path=ledger_path,
        )

    base_arg = str(getattr(args, "base_dir", "") or "")
    base_dir = Path(base_arg) if base_arg else ledger_path.parent
    verdict = build_team_ledger_verdict(ledger, base_dir=base_dir)
    out_arg = str(getattr(args, "out", "") or "")
    if out_arg:
        out_path = Path(out_arg)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(verdict, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    emit_result(
        args,
        {
            "command": "team-ledger",
            "decision": verdict["decision"],
            "lane_count": verdict["lane_count"],
            "passed_lane_count": verdict["passed_lane_count"],
            "blocked_lane_count": verdict["blocked_lane_count"],
            "error_count": len(verdict["errors"]),
            **({"out": out_arg} if out_arg else {}),
        },
        human=[
            f"Team ledger decision: {verdict['decision']}",
            f"  Lanes: {verdict['lane_count']}",
            f"  Errors: {len(verdict['errors'])}",
            *( [f"Team ledger verdict written to {out_arg}"] if out_arg else [] ),
        ],
    )
    if verdict["decision"] == "blocked":
        sys.exit(EXIT_FAILED)

