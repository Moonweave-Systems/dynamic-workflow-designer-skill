from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depone.__main__ as depone_main


class TeamLaunchPreflightCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_self_test_exits_zero(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "depone", "team-launch-preflight", "--self-test"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("team-launch-preflight --self-test: pass", completed.stdout)

    def test_valid_fixture_emits_json_with_kind_and_writes_outputs(self) -> None:
        preflight_path = self.root / "team-launch-preflight.json"
        ledger_path = self.root / "team-ledger.json"

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-launch-preflight",
                "--team-dry-run",
                "docs/team-dry-run/team-dry-run.json",
                "--repo",
                ".",
                "--out",
                str(preflight_path),
                "--team-ledger-out",
                str(ledger_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = json.loads(completed.stdout)
        self.assertEqual(stdout["command"], "team-launch-preflight")
        self.assertEqual(stdout["kind"], "depone-team-launch-preflight")
        self.assertEqual(stdout["decision"], "pass")
        self.assertFalse(stdout["boundary"]["launches_agents"])
        self.assertTrue(preflight_path.exists())
        self.assertTrue(ledger_path.exists())

    def test_invalid_input_exits_usage_with_structured_error_json(self) -> None:
        missing_path = self.root / "missing-team-dry-run.json"

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-launch-preflight",
                "--team-dry-run",
                str(missing_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 3)
        stdout = json.loads(completed.stdout)
        self.assertEqual(stdout["error"]["code"], "ERR_TEAM_LAUNCH_PREFLIGHT_READ_FAILED")
        self.assertEqual(stdout["error"]["path"], str(missing_path))

    def test_main_dispatches_team_launch_preflight_command(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(sys, "argv", ["depone", "team-launch-preflight", "--self-test"]):
            with patch.object(depone_main.team_launch_preflight, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "team-launch-preflight")
        self.assertTrue(getattr(seen[0], "self_test"))


if __name__ == "__main__":
    unittest.main()
