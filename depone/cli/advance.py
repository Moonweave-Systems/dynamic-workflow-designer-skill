from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from depone._resources import resource_text
from depone.cli._response import EXIT_FAILED, EXIT_INTERNAL, emit_error, emit_result
from depone.cli.evidence_next import evaluate_evidence_dir
from depone.cli.evidence_run import run_evidence_loop


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    evidence_dir_arg = str(getattr(args, "evidence_dir", "") or "")
    if not evidence_dir_arg:
        emit_error(
            args,
            code="ERR_ADVANCE_INPUT_REQUIRED",
            message="--evidence-dir is required",
        )

    try:
        artifact = advance_once(args)
    except (OSError, json.JSONDecodeError, ValueError, NotADirectoryError) as exc:
        emit_error(
            args,
            code="ERR_ADVANCE_FAILED",
            message=str(exc),
            exit_code=EXIT_FAILED,
        )
    except Exception as exc:
        emit_error(
            args,
            code="ERR_ADVANCE_INTERNAL",
            message=str(exc),
            exit_code=EXIT_INTERNAL,
        )

    emit_result(
        args,
        artifact,
        human=[
            f"Advance decision: {artifact['decision']}",
            f"Advance action: {artifact['action']}",
            f"Advance artifact: {artifact['out']}",
        ],
    )
    if artifact["decision"] != "pass":
        sys.exit(EXIT_FAILED)


def advance_once(args: argparse.Namespace) -> dict[str, Any]:
    """Gate a single evidence-run continuation on a fresh evidence-next verdict."""

    previous_dir = Path(str(getattr(args, "evidence_dir", "") or ""))
    source_fixture_arg = str(getattr(args, "source_fixture", "") or "")
    source_fixture = Path(source_fixture_arg) if source_fixture_arg else None
    next_decision = evaluate_evidence_dir(previous_dir, source_fixture=source_fixture)
    artifact = _base_artifact(args, previous_dir, next_decision)

    blockers = next_decision.get("blocking_reasons", [])
    if not isinstance(blockers, list):
        blockers = ["evidence-next blocking_reasons is malformed"]
    if next_decision.get("decision") != "continue" or blockers:
        artifact.update(
            {
                "decision": "blocked",
                "action": "refuse_continuation",
                "reason": "evidence-next did not return continue with zero blockers",
                "continuation": None,
                "automation_boundary": {
                    "executed_continuation_count": 0,
                    "max_continuations": 1,
                    "full_scheduler": False,
                },
            }
        )
        _write_artifact(args, artifact)
        return artifact

    continuation = run_evidence_loop(args)
    artifact.update(
        {
            "decision": "pass" if continuation.get("decision") == "pass" else "blocked",
            "action": "ran_one_evidence_run_continuation",
            "reason": "continuation completed" if continuation.get("decision") == "pass" else "continuation did not pass",
            "continuation": {
                "command": continuation.get("command"),
                "decision": continuation.get("decision"),
                "out": continuation.get("out"),
                "observe": continuation.get("observe"),
                "evidence_ingest": continuation.get("evidence_ingest"),
                "verify": continuation.get("verify"),
                "boundary": continuation.get("boundary"),
            },
            "automation_boundary": {
                "executed_continuation_count": 1,
                "max_continuations": 1,
                "full_scheduler": False,
            },
        }
    )
    _write_artifact(args, artifact)
    return artifact


def _base_artifact(
    args: argparse.Namespace,
    previous_dir: Path,
    next_decision: dict[str, Any],
) -> dict[str, Any]:
    return {
        "command": "advance",
        "schema_version": "1.0",
        "previous_evidence_dir": str(previous_dir),
        "next_gate": {
            "command": next_decision.get("command"),
            "decision": next_decision.get("decision"),
            "next_action": next_decision.get("next_action"),
            "blocking_reasons": next_decision.get("blocking_reasons", []),
            "assurance": next_decision.get("assurance"),
            "verified_artifacts": next_decision.get("verified_artifacts"),
        },
        "requested_continuation": {
            "runner_sandbox": str(getattr(args, "runner_sandbox", "") or ""),
            "source_fixture": str(getattr(args, "source_fixture", "") or ""),
            "out": str(getattr(args, "out", "") or ""),
            "verification_command": list(getattr(args, "verification_command", []) or []),
        },
        "out": "",
    }


def _artifact_path(args: argparse.Namespace) -> Path:
    advance_out = str(getattr(args, "advance_out", "") or "")
    if advance_out:
        return Path(advance_out)
    out_dir = Path(str(getattr(args, "out", "evidence-run") or "evidence-run"))
    return out_dir / "advance-decision.json"


def _write_artifact(args: argparse.Namespace, artifact: dict[str, Any]) -> None:
    path = _artifact_path(args)
    artifact["out"] = str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _self_test() -> None:
    import subprocess

    def run_git(repo: Path, argv: list[str]) -> None:
        completed = subprocess.run(
            ["git", *argv],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr.strip() or completed.stdout.strip())

    with tempfile.TemporaryDirectory(prefix="depone-advance-") as temp_dir:
        root = Path(temp_dir)
        source_fixture = root / "reference_adapter_shell.json"
        source_fixture.write_text(
            resource_text("fixtures/agent_fabric/reference_adapter_shell.json"),
            encoding="utf-8",
        )
        runner = root / "runner-sandbox"
        runner.mkdir()
        run_git(runner, ["init"])
        run_git(runner, ["config", "user.email", "observer@example.invalid"])
        run_git(runner, ["config", "user.name", "Observer Test"])
        (runner / "sample.txt").write_text("before\n", encoding="utf-8")
        run_git(runner, ["add", "sample.txt"])
        run_git(runner, ["commit", "-m", "seed"])
        (runner / "sample.txt").write_text("after\n", encoding="utf-8")

        repo_root = Path(__file__).resolve().parents[2]
        args = argparse.Namespace(
            evidence_dir=str(repo_root / "docs" / "depone-run-receipt-frontdoor"),
            runner_sandbox=str(runner),
            source_fixture=str(source_fixture),
            out=str(root / "continuation"),
            advance_out=str(root / "advance-decision.json"),
            allow_touched_file=["sample.txt"],
            verify_plan=str(repo_root / "fixtures" / "v105-verify-wedge" / "plan.json"),
            verify_evidence=str(repo_root / "fixtures" / "v105-verify-wedge" / "evidence" / "good"),
            verify_adapter="generic",
            operator_view_out="",
            timeout_seconds=120,
            runner_uid=None,
            runner_user="",
            runner_command="",
            runner_container_id="",
            runner_container_image="",
            runner_container_command="",
            runner_container_hold_seconds=600,
            sign_private_key="",
            sign_key_id="",
            sign_public_key="",
            verification_command=[
                sys.executable,
                "-c",
                "from pathlib import Path; assert Path('sample.txt').exists()",
            ],
            json=False,
        )
        artifact = advance_once(args)
        if artifact["decision"] != "pass":
            raise AssertionError(f"expected advance pass: {artifact}")
        if artifact["automation_boundary"]["executed_continuation_count"] != 1:
            raise AssertionError("advance must execute exactly one continuation")
        if not Path(str(artifact["out"])).is_file():
            raise AssertionError("expected advance decision artifact")
    print("depone advance --self-test: pass")
