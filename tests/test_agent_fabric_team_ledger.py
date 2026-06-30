from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.team_ledger import (
    build_sample_team_ledger,
    build_team_ledger_verdict,
)


class AgentFabricTeamLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "lane-evidence").mkdir()

    def test_valid_ledger_passes(self) -> None:
        ledger = build_sample_team_ledger("lane-evidence")

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["kind"], "depone-team-ledger-verdict")
        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["passed_lane_count"], 1)
        self.assertFalse(verdict["boundary"]["executes_commands"])
        self.assertFalse(verdict["boundary"]["raises_assurance"])

    def test_missing_evidence_dir_blocks_passed_lane(self) -> None:
        ledger = build_sample_team_ledger("missing-evidence")

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_EVIDENCE_DIR_MISSING",
            {error["code"] for error in verdict["errors"]},
        )

    def test_invalid_environment_kind_blocks(self) -> None:
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["env_kind"] = "bare-metal"

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_CHOICE_INVALID",
            {error["code"] for error in verdict["errors"]},
        )

    def test_blocked_lane_requires_explicit_reason(self) -> None:
        ledger = build_sample_team_ledger("missing-evidence")
        ledger["lanes"][0]["verification_state"] = "blocked"

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_BLOCKED_REASON_REQUIRED",
            {error["code"] for error in verdict["errors"]},
        )

    def test_blocked_lane_with_reason_fans_in_as_explicit_block(self) -> None:
        ledger = build_sample_team_ledger("missing-evidence")
        ledger["lanes"][0]["verification_state"] = "blocked"
        ledger["lanes"][0]["blocked_reason"] = "lane hit a merge conflict"

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked-explicit")
        self.assertEqual(verdict["blocked_lane_count"], 1)
        self.assertEqual(verdict["errors"], [])

    def test_duplicate_lane_ids_block(self) -> None:
        ledger = build_sample_team_ledger("lane-evidence")
        second = dict(ledger["lanes"][0])
        ledger["lanes"].append(second)

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_LANE_ID_DUPLICATE",
            {error["code"] for error in verdict["errors"]},
        )

    def test_cli_self_test_and_validate(self) -> None:
        ledger = build_sample_team_ledger("lane-evidence")
        ledger_path = self.root / "team-ledger.json"
        verdict_path = self.root / "team-ledger-verdict.json"
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-ledger",
                "--ledger",
                str(ledger_path),
                "--out",
                str(verdict_path),
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["decision"], "pass")
        self.assertEqual(verdict["decision"], "pass")

    def test_duplicate_lane_ids_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self._ledger(root)
            ledger["lanes"][1]["lane_id"] = "lane-a"
            verdict = validate_team_ledger(ledger, base_dir=root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn("duplicate lane_id", "\n".join(verdict["errors"]))

    def test_empty_or_non_list_lanes_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self._ledger(root)
            ledger["lanes"] = []
            empty_verdict = validate_team_ledger(ledger, base_dir=root)
            ledger["lanes"] = "lane-a"
            non_list_verdict = validate_team_ledger(ledger, base_dir=root)

        self.assertEqual(empty_verdict["decision"], "blocked")
        self.assertEqual(non_list_verdict["decision"], "blocked")
        self.assertIn("at least one lane", "\n".join(empty_verdict["errors"]))
        self.assertIn("lanes must be a list", "\n".join(non_list_verdict["errors"]))

    def test_cli_writes_json_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self._ledger(root)
            ledger_path = root / "team-ledger.json"
            out_path = root / "team-ledger-verdict.json"
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

            import subprocess
            import sys

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "team-ledger",
                    "--ledger",
                    str(ledger_path),
                    "--out",
                    str(out_path),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            stdout = json.loads(completed.stdout)
            verdict = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(stdout["decision"], "pass")
        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["lane_count"], 2)


if __name__ == "__main__":
    unittest.main()
