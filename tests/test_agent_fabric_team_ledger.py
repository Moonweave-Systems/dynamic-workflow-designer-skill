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

    def _write_evidence_next_verdict(
        self,
        relative_path: str = "lane-evidence/evidence-next-verdict.json",
        *,
        decision: str = "continue",
        blocking_reasons: list[str] | None = None,
    ) -> str:
        verdict_path = self.root / relative_path
        verdict_path.parent.mkdir(parents=True, exist_ok=True)
        verdict_path.write_text(
            json.dumps(
                {
                    "command": "evidence-next",
                    "schema_version": "1.0",
                    "decision": decision,
                    "blocking_reasons": blocking_reasons or [],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return relative_path

    def _ledger_with_evidence_next(self) -> dict[str, object]:
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["evidence_next_verdict"] = self._write_evidence_next_verdict()
        return ledger

    def test_valid_ledger_passes(self) -> None:
        ledger = self._ledger_with_evidence_next()

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["kind"], "depone-team-ledger-verdict")
        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["passed_lane_count"], 1)
        self.assertFalse(verdict["boundary"]["executes_commands"])
        self.assertFalse(verdict["boundary"]["raises_assurance"])

    def test_missing_evidence_dir_blocks_passed_lane(self) -> None:
        ledger = build_sample_team_ledger("missing-evidence")
        ledger["lanes"][0]["evidence_next_verdict"] = "missing-evidence/evidence-next-verdict.json"

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_EVIDENCE_DIR_MISSING",
            {error["code"] for error in verdict["errors"]},
        )

    def test_invalid_environment_kind_blocks(self) -> None:
        ledger = self._ledger_with_evidence_next()
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


    def test_invalid_adapter_and_verification_choices_block(self) -> None:
        for field, value in (
            ("runner_adapter_kind", "unknown-runner"),
            ("team_adapter_kind", "unknown-team"),
            ("verification_state", "pending"),
        ):
            with self.subTest(field=field):
                ledger = self._ledger_with_evidence_next()
                ledger["lanes"][0][field] = value

                verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

                self.assertEqual(verdict["decision"], "blocked")
                self.assertIn(
                    "ERR_TEAM_LEDGER_CHOICE_INVALID",
                    {error["code"] for error in verdict["errors"]},
                )

    def test_empty_lanes_and_duplicate_lane_ids_block(self) -> None:
        empty = self._ledger_with_evidence_next()
        empty["lanes"] = []

        empty_verdict = build_team_ledger_verdict(empty, base_dir=self.root)

        self.assertEqual(empty_verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_LANES_REQUIRED",
            {error["code"] for error in empty_verdict["errors"]},
        )

        duplicate = self._ledger_with_evidence_next()
        duplicate["lanes"].append(dict(duplicate["lanes"][0]))

        duplicate_verdict = build_team_ledger_verdict(duplicate, base_dir=self.root)

        self.assertEqual(duplicate_verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_LANE_ID_DUPLICATE",
            {error["code"] for error in duplicate_verdict["errors"]},
        )

    def test_whitespace_blocked_reason_blocks(self) -> None:
        ledger = build_sample_team_ledger("missing-evidence")
        ledger["lanes"][0]["verification_state"] = "blocked"
        ledger["lanes"][0]["blocked_reason"] = "   "

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_BLOCKED_REASON_REQUIRED",
            {error["code"] for error in verdict["errors"]},
        )

    def test_cli_base_dir_resolves_relative_evidence_dir(self) -> None:
        ledger_root = self.root / "ledger"
        evidence_root = self.root / "evidence-root"
        ledger_root.mkdir()
        (evidence_root / "lane-evidence").mkdir(parents=True)
        ledger = build_sample_team_ledger("lane-evidence")
        verdict_path = evidence_root / "lane-evidence" / "evidence-next-verdict.json"
        verdict_path.write_text(
            json.dumps(
                {
                    "command": "evidence-next",
                    "schema_version": "1.0",
                    "decision": "continue",
                    "blocking_reasons": [],
                }
            ),
            encoding="utf-8",
        )
        ledger["lanes"][0]["evidence_next_verdict"] = "lane-evidence/evidence-next-verdict.json"
        ledger_path = ledger_root / "team-ledger.json"
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "team-ledger",
                "--ledger",
                str(ledger_path),
                "--base-dir",
                str(evidence_root),
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], "pass")

    def test_cli_writes_verdict(self) -> None:
        ledger = self._ledger_with_evidence_next()
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
        ledger = self._ledger_with_evidence_next()
        ledger["lanes"].append(dict(ledger["lanes"][0]))

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_LANE_ID_DUPLICATE",
            {error["code"] for error in verdict["errors"]},
        )

    def test_empty_or_non_list_lanes_block(self) -> None:
        ledger = self._ledger_with_evidence_next()
        ledger["lanes"] = []
        empty_verdict = build_team_ledger_verdict(ledger, base_dir=self.root)
        ledger["lanes"] = "lane-a"
        non_list_verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(empty_verdict["decision"], "blocked")
        self.assertEqual(non_list_verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_LANES_REQUIRED",
            {error["code"] for error in empty_verdict["errors"]},
        )
        self.assertIn(
            "ERR_TEAM_LEDGER_LANES_REQUIRED",
            {error["code"] for error in non_list_verdict["errors"]},
        )

    def test_cli_writes_json_verdict(self) -> None:
        ledger = self._ledger_with_evidence_next()
        second = dict(ledger["lanes"][0])
        second["lane_id"] = "lane-tests"
        ledger["lanes"].append(second)
        ledger_path = self.root / "team-ledger.json"
        out_path = self.root / "team-ledger-verdict.json"
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

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

    def test_passed_lane_without_evidence_next_verdict_blocks(self) -> None:
        ledger = build_sample_team_ledger("lane-evidence")

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_REQUIRED",
            {error["code"] for error in verdict["errors"]},
        )

    def test_blocked_evidence_next_verdict_blocks_passed_lane(self) -> None:
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["evidence_next_verdict"] = self._write_evidence_next_verdict(
            decision="blocked",
            blocking_reasons=["tampered capture manifest"],
        )

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_EVIDENCE_NEXT_NOT_CONTINUE",
            {error["code"] for error in verdict["errors"]},
        )


if __name__ == "__main__":
    unittest.main()
