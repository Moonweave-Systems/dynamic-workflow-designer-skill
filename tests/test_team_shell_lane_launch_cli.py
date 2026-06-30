from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depone.__main__ as depone_main


class TeamShellLaneLaunchCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_self_test_exits_zero(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "depone", "team-shell-lane-launch", "--self-test"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("team-shell-lane-launch --self-test: pass", completed.stdout)

    def test_cli_runs_allowlisted_argv_and_writes_receipt(self) -> None:
        allowlist = self.root / "allowlist.json"
        receipt_path = self.root / "receipt.json"
        transcript_path = self.root / "transcript.json"
        allowlist.write_text(
            json.dumps(
                {
                    "commands": [
                        {
                            "id": "fixture-echo",
                            "argv": [sys.executable, "-c", "print('fixture ok')"],
                        }
                    ]
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-shell-lane-launch",
                "--allowlist",
                str(allowlist),
                "--command-id",
                "fixture-echo",
                "--cwd",
                str(self.root),
                "--out",
                str(receipt_path),
                "--transcript",
                str(transcript_path),
                "--agent-role-id",
                "worker",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = json.loads(completed.stdout)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        self.assertEqual(stdout["command"], "team-shell-lane-launch")
        self.assertEqual(stdout["decision"], "pass")
        self.assertEqual(receipt["boundary"]["uses_shell"], False)
        self.assertEqual(receipt["agent_contract_hash"], receipt["agent_contract"]["agent_contract_hash"])
        self.assertEqual(receipt["agent_contract"]["role_id"], "worker")
        self.assertEqual(receipt["boundary"]["uses_argv_allowlist"], True)
        self.assertEqual(receipt["boundary"]["allows_arbitrary_shell_string"], False)
        self.assertEqual(transcript["stdout_text"], "fixture ok\n")

    def test_main_dispatches_team_shell_lane_launch_command(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(sys, "argv", ["depone", "team-shell-lane-launch", "--self-test"]):
            with patch.object(depone_main.team_shell_lane_launch, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "team-shell-lane-launch")
        self.assertTrue(getattr(seen[0], "self_test"))

    def test_cli_blocks_role_not_bound_by_contract(self) -> None:
        allowlist = self.root / "allowlist.json"
        receipt_path = self.root / "receipt.json"
        transcript_path = self.root / "transcript.json"
        allowlist.write_text(
            json.dumps(
                {
                    "commands": [
                        {
                            "id": "fixture-echo",
                            "argv": [sys.executable, "-c", "print('should not run')"],
                        }
                    ]
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-shell-lane-launch",
                "--allowlist",
                str(allowlist),
                "--command-id",
                "fixture-echo",
                "--cwd",
                str(self.root),
                "--out",
                str(receipt_path),
                "--transcript",
                str(transcript_path),
                "--agent-role-id",
                "operator",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("ERR_TEAM_SHELL_LANE_AGENT_ROLE_INVALID", completed.stdout)
        self.assertFalse(receipt_path.exists())
        self.assertFalse(transcript_path.exists())


if __name__ == "__main__":
    unittest.main()
