from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import json
from pathlib import Path

from depone.agent_fabric.capture_bridge import (
    build_capture_manifest,
    validate_capture_manifest,
)
from depone.agent_fabric.paired_run import (
    build_paired_run_report,
    build_observer_capture,
    build_runner_receipt,
    now_utc,
    validate_runner_receipt,
)


class AgentFabricPairedRunTests(unittest.TestCase):
    def test_observer_capture_records_diff_and_command_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            (repo / "task.txt").write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "add", "task.txt"], cwd=repo, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Depone",
                    "-c",
                    "user.email=depone@example.com",
                    "commit",
                    "-m",
                    "seed",
                ],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            (repo / "task.txt").write_text("after\n", encoding="utf-8")

            capture = build_observer_capture(
                repo,
                source_fixture_hash="fixture-hash",
                verification_command=[sys.executable, "--version"],
                log_path=root / "verification.log",
            )

            self.assertEqual(capture["observed_by"], "depone-observer")
            self.assertEqual(capture["touched_files"], ["task.txt"])
            self.assertEqual(capture["test_output"]["status"], "passed")
            self.assertEqual(capture["command_receipts"][0]["exit_code"], 0)

            fixture = json.loads(
                Path("depone/fixtures/agent_fabric/reference_adapter_shell.json").read_text(
                    encoding="utf-8"
                )
            )
            capture["source_fixture_hash"] = ""
            manifest = build_capture_manifest(
                fixture,
                observer_capture=capture,
                allowed_touched_files=["task.txt"],
            )
            self.assertEqual(validate_capture_manifest(manifest), [])

    def test_runner_receipt_requires_transcript_and_valid_arm(self) -> None:
        receipt = build_runner_receipt(
            runner_kind="codex-cli",
            arm="governed",
            task_id="task",
            worktree="worktree",
            invocation=["codex", "run"],
            transcript_path="transcript.log",
            exit_code=0,
            touched_files=["task.txt"],
            started_at=now_utc(),
            ended_at=now_utc(),
        )

        self.assertEqual(validate_runner_receipt(receipt), [])

        receipt["transcript_path"] = ""
        receipt["arm"] = "other"
        errors = validate_runner_receipt(receipt)
        self.assertIn("transcript_path must be a non-empty string", errors)
        self.assertIn("arm must be one of ['direct', 'governed']", errors)

    def test_runner_receipt_rejects_source_hash_mismatch(self) -> None:
        receipt = build_runner_receipt(
            runner_kind="codex-cli",
            arm="governed",
            task_id="task",
            worktree="worktree",
            invocation=["codex", "run"],
            transcript_path="transcript.log",
            exit_code=0,
            touched_files=["task.txt"],
            started_at=now_utc(),
            ended_at=now_utc(),
        )
        receipt["source_hashes"]["receipt"] = "0" * 64

        errors = validate_runner_receipt(receipt)

        self.assertIn("source_hashes.receipt mismatch", errors)

    def test_paired_run_report_blocks_failed_governed_verification(self) -> None:
        direct_runner = build_runner_receipt(
            runner_kind="codex-cli",
            arm="direct",
            task_id="task",
            worktree="direct",
            invocation=["codex", "exec"],
            transcript_path="direct.log",
            exit_code=0,
            touched_files=["result.txt"],
            started_at=now_utc(),
            ended_at=now_utc(),
        )
        governed_runner = build_runner_receipt(
            runner_kind="codex-cli",
            arm="governed",
            task_id="task",
            worktree="governed",
            invocation=["codex", "exec"],
            transcript_path="governed.log",
            exit_code=0,
            touched_files=[],
            started_at=now_utc(),
            ended_at=now_utc(),
        )
        direct_observer = {
            "test_output": {"status": "passed"},
            "touched_files": ["result.txt"],
        }
        governed_observer = {
            "test_output": {"status": "failed"},
            "touched_files": [],
        }

        report = build_paired_run_report(
            task_id="task",
            direct_runner=direct_runner,
            direct_observer=direct_observer,
            governed_runner=governed_runner,
            governed_observer=governed_observer,
        )

        self.assertEqual(report["decision"], "blocked-paired-run-not-ready")
        self.assertEqual(
            report["blockers"][0]["code"],
            "ERR_PAIRED_RUN_VERIFICATION_NOT_PASSED",
        )

        governed_observer["test_output"]["status"] = "passed"
        governed_observer["touched_files"] = ["result.txt"]
        governed_runner = build_runner_receipt(
            runner_kind="codex-cli",
            arm="governed",
            task_id="task",
            worktree="governed",
            invocation=["codex", "exec"],
            transcript_path="governed.log",
            exit_code=0,
            touched_files=["result.txt"],
            started_at=now_utc(),
            ended_at=now_utc(),
        )
        ready = build_paired_run_report(
            task_id="task",
            direct_runner=direct_runner,
            direct_observer=direct_observer,
            governed_runner=governed_runner,
            governed_observer=governed_observer,
        )
        self.assertEqual(ready["decision"], "paired-run-observed")


if __name__ == "__main__":
    unittest.main()
