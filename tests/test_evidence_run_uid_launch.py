from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from depone._resources import resource_text
from depone.cli.evidence_run import _launch_runner_user, run_evidence_loop


def _run_git(repo: Path, args: list[str]) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip() or result.stdout.strip())


class EvidenceRunUidLaunchTests(unittest.TestCase):
    def test_launch_runner_user_records_uid_and_receipt(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> object:
            if command == ["id", "-u", "deponerun"]:
                return type(
                    "Completed",
                    (),
                    {"returncode": 0, "stdout": "1001\n", "stderr": ""},
                )()
            if command[:4] == ["sudo", "-u", "deponerun", "bash"]:
                return type(
                    "Completed",
                    (),
                    {
                        "returncode": 0,
                        "stdout": "__DEPONE_RUNNER_UID=1001\nrunner-ok\n",
                        "stderr": "",
                    },
                )()
            raise AssertionError(f"unexpected command: {command}")

        with patch("depone.cli.evidence_run.shutil.which", return_value="sudo"):
            with patch("depone.cli.evidence_run.subprocess.run", side_effect=fake_run):
                receipt = _launch_runner_user(
                    Path("/srv/depone/sandbox"),
                    user="deponerun",
                    shell_command="printf runner-ok",
                )

        self.assertEqual(receipt["user"], "deponerun")
        self.assertEqual(receipt["uid"], 1001)
        self.assertEqual(receipt["observed_uid"], 1001)
        self.assertEqual(receipt["command"], "printf runner-ok")
        self.assertEqual(receipt["cwd"], "/srv/depone/sandbox")
        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["stdout"], "runner-ok\n")

    def test_launch_runner_user_fails_closed_when_command_fails(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> object:
            if command == ["id", "-u", "deponerun"]:
                return type(
                    "Completed",
                    (),
                    {"returncode": 0, "stdout": "1001\n", "stderr": ""},
                )()
            return type(
                "Completed",
                (),
                {"returncode": 17, "stdout": "", "stderr": "runner failed\n"},
            )()

        with patch("depone.cli.evidence_run.shutil.which", return_value="sudo"):
            with patch("depone.cli.evidence_run.subprocess.run", side_effect=fake_run):
                with self.assertRaises(ValueError):
                    _launch_runner_user(
                        Path("/srv/depone/sandbox"),
                        user="deponerun",
                        shell_command="exit 17",
                    )

    def test_evidence_run_uses_observer_launched_uid_receipt_for_a2(self) -> None:
        with tempfile.TemporaryDirectory(prefix="depone-uid-launch-") as temp_text:
            root = Path(temp_text)
            runner = root / "runner-sandbox"
            runner.mkdir()
            _run_git(runner, ["init"])
            _run_git(runner, ["config", "user.email", "observer@example.invalid"])
            _run_git(runner, ["config", "user.name", "Observer Test"])
            (runner / "sample.txt").write_text("before\n", encoding="utf-8")
            _run_git(runner, ["add", "sample.txt"])
            _run_git(runner, ["commit", "-m", "seed"])
            (runner / "sample.txt").write_text("after\n", encoding="utf-8")

            source_fixture = root / "reference_adapter_shell.json"
            source_fixture.write_text(
                resource_text("fixtures/agent_fabric/reference_adapter_shell.json"),
                encoding="utf-8",
            )
            launch_receipt = {
                "runtime": "posix-sudo",
                "user": "deponerun",
                "uid": 4242,
                "observed_uid": 4242,
                "command": "printf after",
                "cwd": str(runner),
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "invocation": ["sudo", "-u", "deponerun", "bash", "-lc", "printf after"],
            }
            args = argparse.Namespace(
                runner_sandbox=str(runner),
                source_fixture=str(source_fixture),
                out=str(root / "evidence-run"),
                allow_touched_file=["sample.txt"],
                verify_plan="",
                verify_evidence="",
                verify_adapter="generic",
                operator_view_out="",
                timeout_seconds=120,
                runner_uid=None,
                runner_user="deponerun",
                runner_command="printf after",
                runner_container_id="",
                runner_container_image="",
                runner_container_command="",
                runner_container_hold_seconds=600,
                verification_command=[
                    sys.executable,
                    "-c",
                    "from pathlib import Path; assert Path('sample.txt').exists()",
                ],
                json=False,
            )

            with patch(
                "depone.cli.evidence_run._launch_runner_user",
                return_value=launch_receipt,
            ):
                payload = run_evidence_loop(args)

            manifest = json.loads(
                (root / "evidence-run" / "capture-manifest.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(payload["boundary"]["observer_assurance"], "A2-isolated-observed")
        self.assertTrue(payload["boundary"]["privilege_isolated"])
        self.assertEqual(
            manifest["isolation"]["model"],
            "uid-boundary-observer-launched-unwritable-observer-dir",
        )
        self.assertIs(manifest["isolation"]["observer_launched"], True)
        self.assertEqual(manifest["isolation"]["runner_uid"], 4242)
        self.assertEqual(
            manifest["observer_capture"]["runner_uid_launch"],
            launch_receipt,
        )


if __name__ == "__main__":
    unittest.main()
