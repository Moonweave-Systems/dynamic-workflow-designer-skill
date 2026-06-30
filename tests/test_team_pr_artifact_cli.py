from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depone.__main__ as depone_main


class TeamPrArtifactCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _saved_pr_json(self) -> dict[str, object]:
        return {
            "number": 42,
            "url": "https://github.com/Moonweave-Systems/Depone/pull/42",
            "state": "OPEN",
            "mergeStateStatus": "CLEAN",
            "baseRefOid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "headRefOid": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "repository": {"nameWithOwner": "Moonweave-Systems/Depone"},
            "statusCheckRollup": [
                {"name": "contract", "conclusion": "SUCCESS", "status": "COMPLETED"},
                {"name": "unit", "conclusion": "SUCCESS", "status": "COMPLETED"},
            ],
        }

    def _write_saved_pr_json(self, payload: dict[str, object] | None = None) -> Path:
        path = self.root / "gh-pr-view.json"
        path.write_text(json.dumps(payload or self._saved_pr_json()), encoding="utf-8")
        return path

    def test_self_test_exits_zero(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "depone", "team-pr-artifact", "--self-test"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("team-pr-artifact --self-test: pass", completed.stdout)

    def test_saved_json_input_writes_artifact_without_network(self) -> None:
        input_path = self._write_saved_pr_json()
        out_path = self.root / "pr-artifact.json"

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-pr-artifact",
                "--input",
                str(input_path),
                "--captured-at",
                "2026-06-30T15:30:00Z",
                "--expected-head-sha",
                "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "--out",
                str(out_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = json.loads(completed.stdout)
        self.assertEqual(stdout["command"], "team-pr-artifact")
        self.assertEqual(stdout["decision"], "pass")
        self.assertEqual(stdout["error_count"], 0)
        artifact = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(artifact["kind"], "depone-team-ledger-pr-artifact")
        self.assertEqual(artifact["schema_version"], "0.1")
        self.assertEqual(artifact["provider"], "github")
        self.assertEqual(artifact["repo"], "Moonweave-Systems/Depone")
        self.assertEqual(artifact["pr_number"], 42)
        self.assertEqual(artifact["check_summary"]["status"], "pass")
        self.assertEqual(artifact["check_summary"]["failed_count"], 0)
        self.assertEqual(artifact["check_summary"]["pending_count"], 0)
        self.assertEqual(artifact["source_command"], ["saved-json", str(input_path)])

    def test_existing_artifact_validation_blocks_head_mismatch(self) -> None:
        artifact = {
            "kind": "depone-team-ledger-pr-artifact",
            "schema_version": "0.1",
            "provider": "github",
            "repo": "Moonweave-Systems/Depone",
            "pr_number": 42,
            "pr_url": "https://github.com/Moonweave-Systems/Depone/pull/42",
            "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "head_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "state": "OPEN",
            "merge_state_status": "CLEAN",
            "check_summary": {
                "status": "pass",
                "total_count": 1,
                "failed_count": 0,
                "pending_count": 0,
            },
            "stale": False,
            "captured_at": "2026-06-30T15:30:00Z",
            "source_command": ["saved-json", "fixture"],
        }
        artifact_path = self.root / "pr-artifact.json"
        artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-pr-artifact",
                "--artifact",
                str(artifact_path),
                "--expected-head-sha",
                "cccccccccccccccccccccccccccccccccccccccc",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        stdout = json.loads(completed.stdout)
        self.assertEqual(stdout["decision"], "blocked")
        self.assertEqual(
            stdout["errors"][0]["code"],
            "ERR_TEAM_PR_ARTIFACT_HEAD_SHA_MISMATCH",
        )

    def test_saved_json_with_pending_check_blocks(self) -> None:
        payload = self._saved_pr_json()
        payload["statusCheckRollup"] = [
            {"name": "contract", "conclusion": None, "status": "IN_PROGRESS"}
        ]
        input_path = self._write_saved_pr_json(payload)

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-pr-artifact",
                "--input",
                str(input_path),
                "--captured-at",
                "2026-06-30T15:30:00Z",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        stdout = json.loads(completed.stdout)
        self.assertEqual(stdout["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_PR_ARTIFACT_CHECKS_NOT_PASSING",
            {error["code"] for error in stdout["errors"]},
        )

    def test_main_dispatches_team_pr_artifact_command(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(sys, "argv", ["depone", "team-pr-artifact", "--self-test"]):
            with patch.object(depone_main.team_pr_artifact, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "team-pr-artifact")
        self.assertTrue(getattr(seen[0], "self_test"))


if __name__ == "__main__":
    unittest.main()
