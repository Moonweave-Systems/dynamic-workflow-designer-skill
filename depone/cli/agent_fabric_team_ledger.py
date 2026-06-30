from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from depone.agent_fabric.team_ledger import read_team_ledger, validate_team_ledger
from depone.cli._response import EXIT_FAILED, emit_error, emit_result


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    ledger_path = Path(str(getattr(args, "ledger", "")))
    if not str(ledger_path):
        emit_error(
            args,
            code="ERR_TEAM_LEDGER_REQUIRED",
            message="--ledger is required",
        )

    try:
        ledger = read_team_ledger(ledger_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit_error(
            args,
            code="ERR_TEAM_LEDGER_READ",
            message=f"cannot read team ledger: {exc}",
            path=ledger_path,
        )

    base_dir = Path(str(getattr(args, "base_dir", "") or ledger_path.parent))
    verdict = validate_team_ledger(ledger, base_dir=base_dir)
    out_path = Path(str(getattr(args, "out", "team-ledger-verdict.json")))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    emit_result(
        args,
        {
            "command": "team-ledger",
            "decision": verdict["decision"],
            "out": str(out_path),
            "lane_count": verdict["lane_count"],
            "passed_lanes": verdict["passed_lanes"],
            "blocked_lanes": verdict["blocked_lanes"],
            "error_count": len(verdict["errors"]),
        },
        human=[
            f"Team ledger decision: {verdict['decision']}",
            f"Team ledger verdict written to {out_path}",
        ],
    )

    if verdict["decision"] == "blocked":
        sys.exit(EXIT_FAILED)


def _self_test() -> None:
    from depone.agent_fabric.team_ledger import _self_test as team_ledger_self_test

    team_ledger_self_test()
    print("depone team-ledger --self-test: pass")
