from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.team_ledger import validate_team_ledger


class AgentFabricTeamLedgerTests(unittest.TestCase):
    def _ledger(self, root: Path) -> dict[str, object]:
        evidence_dir = root / "lane-a-evidence"
        evidence_dir.mkdir()
        return {
            "kind": "depone-team-ledger",
            "schema_version": "0.1",
            "objective": "audit a small team run",
            "leader": "leader-fixed",
            "lanes": [
                {
                    "lane_id": "lane-a",
                    "role": "executor",
                    "environment_kind": "local",
                    "adapter_kind": "omx",
                    "start_commit": "1111111",
                    "end_commit": "2222222",
                    "evidence_dir": "lane-a-evidence",
                    "pr_url": "https://github.com/example/repo/pull/1",
                    "verification_state": "pass",
                    "next_decision": "pass",
                },
                {
                    "lane_id": "lane-b",
                    "role": "reviewer",
                    "environment_kind": "cloud",
                    "adapter_kind": "codex",
                    "start_commit": "1111111",
                    "end_commit": "1111111",
                    "verification_state": "blocked",
                    "blocked_reason": "no lane changes to verify",
                },
            ],
        }

    def test_valid_ledger_allows_pass_and_explicit_blocked_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            verdict = validate_team_ledger(self._ledger(root), base_dir=root)

        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["passed_lanes"], 1)
        self.assertEqual(verdict["blocked_lanes"], 1)
        self.assertEqual(verdict["errors"], [])

    def test_pass_lane_with_missing_evidence_dir_blocks_fan_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self._ledger(root)
            ledger["lanes"][0]["evidence_dir"] = "missing-evidence"
            verdict = validate_team_ledger(ledger, base_dir=root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn("evidence_dir does not exist", "\n".join(verdict["errors"]))

    def test_invalid_environment_or_adapter_kind_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self._ledger(root)
            ledger["lanes"][0]["environment_kind"] = "bare-metal"
            ledger["lanes"][1]["adapter_kind"] = "unknown-agent"
            verdict = validate_team_ledger(ledger, base_dir=root)

        self.assertEqual(verdict["decision"], "blocked")
        joined = "\n".join(verdict["errors"])
        self.assertIn("environment_kind", joined)
        self.assertIn("adapter_kind", joined)

    def test_blocked_lane_requires_explicit_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = json.loads(json.dumps(self._ledger(root)))
            del ledger["lanes"][1]["blocked_reason"]
            verdict = validate_team_ledger(ledger, base_dir=root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn("blocked_reason", "\n".join(verdict["errors"]))


if __name__ == "__main__":
    unittest.main()
