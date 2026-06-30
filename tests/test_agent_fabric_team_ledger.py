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
        self.assertFalse(verdict["errors"])

    def test_cli_writes_verdict(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
