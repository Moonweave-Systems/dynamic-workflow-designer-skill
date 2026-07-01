"""depone codex-local-capability - detect local Codex adapter readiness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from depone.agent_fabric.codex_local_capability import (
    _self_test,
    build_codex_local_capability,
    write_codex_local_capability,
)
from depone.cli._response import EXIT_INCONCLUSIVE, emit_result, exit_code_for_decision


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        print("depone codex-local-capability --self-test: pass")
        return

    receipt = build_codex_local_capability(
        repo=Path(str(getattr(args, "repo", "") or ".")),
        codex_binary=str(getattr(args, "codex_binary", "") or "codex"),
        sandbox_mode=str(getattr(args, "sandbox_mode", "") or "workspace-write"),
        approval_policy=str(getattr(args, "approval_policy", "") or "on-request"),
        version_timeout_seconds=float(getattr(args, "version_timeout_seconds", 10) or 10),
        instruction_files=[Path(value) for value in getattr(args, "instruction_file", [])],
    )
    out_arg = str(getattr(args, "out", "") or "codex-local-capability.json")
    write_codex_local_capability(Path(out_arg), receipt)
    emit_result(
        args,
        {
            "command": "codex-local-capability",
            "decision": receipt["decision"],
            "blocked_reasons": receipt["blocked_reasons"],
            "out": out_arg,
        },
        human=[
            f"Codex local capability decision: {receipt['decision']}",
            f"  Receipt: {out_arg}",
        ],
    )
    if receipt["decision"] == "blocked":
        sys.exit(EXIT_INCONCLUSIVE)
    sys.exit(exit_code_for_decision(str(receipt["decision"])))
