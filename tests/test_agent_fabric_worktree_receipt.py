from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.team_ledger import build_sample_team_ledger, build_team_ledger_verdict
from depone.agent_fabric.worktree_receipt import build_worktree_lane_receipt


class AgentFabricWorktreeReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _init_repo(self) -> tuple[Path, str, str]:
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "r@x.invalid"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "receipt-test"], cwd=repo, check=True)
        (repo / "sample.txt").write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "add", "sample.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        (repo / "sample.txt").write_text("after\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "change", "-q"], cwd=repo, check=True)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        return repo, base, head

    def _write_evidence_next(self, evidence_dir: Path) -> None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "evidence-next-verdict.json").write_text(
            json.dumps(
                {
                    "command": "evidence-next",
                    "schema_version": "1.0",
                    "decision": "continue",
                    "blocking_reasons": [],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_build_receipt_extracts_changed_files_from_base_to_head(self) -> None:
        repo, base, head = self._init_repo()

        receipt = build_worktree_lane_receipt(
            worktree=repo,
            base_commit=base,
            evidence_dir=Path("lane-evidence"),
            commands=[{"command": "python3 -m unittest", "exit_code": 0}],
        )

        self.assertEqual(receipt["kind"], "depone-worktree-lane-receipt")
        self.assertEqual(receipt["base_commit"], base)
        self.assertEqual(receipt["head_commit"], head)
        self.assertEqual(receipt["changed_files"], ["sample.txt"])
        self.assertFalse(receipt["dirty"])
        self.assertEqual(receipt["boundary"]["executes_commands"], False)

    def test_cli_writes_worktree_receipt_json(self) -> None:
        repo, base, head = self._init_repo()
        out = self.root / "receipt.json"

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "worktree-lane-receipt",
                "--worktree",
                str(repo),
                "--base-commit",
                base,
                "--evidence-dir",
                "lane-evidence",
                "--command-receipt",
                '{"command":"python3 -m unittest","exit_code":0}',
                "--out",
                str(out),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        stdout = json.loads(completed.stdout)
        receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(stdout["command"], "worktree-lane-receipt")
        self.assertEqual(stdout["head_commit"], head)
        self.assertEqual(receipt["changed_files"], ["sample.txt"])

    def test_clean_worktree_receipt_allows_passed_lane(self) -> None:
        repo, base, head = self._init_repo()
        evidence_dir = self.root / "lane-evidence"
        self._write_evidence_next(evidence_dir)
        receipt = build_worktree_lane_receipt(
            worktree=repo,
            base_commit=base,
            evidence_dir=Path("lane-evidence"),
            commands=[],
        )
        (evidence_dir / "worktree-receipt.json").write_text(
            json.dumps(receipt, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["start_commit"] = base
        ledger["lanes"][0]["end_commit"] = head
        ledger["lanes"][0]["touched_files"] = ["sample.txt"]
        ledger["lanes"][0]["evidence_next_verdict"] = "lane-evidence/evidence-next-verdict.json"
        ledger["lanes"][0]["worktree_receipt"] = "lane-evidence/worktree-receipt.json"

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(
            verdict["lane_results"][0]["worktree_receipt"]["head_commit"],
            head,
        )

    def test_dirty_worktree_receipt_blocks_passed_lane(self) -> None:
        receipt_dir = self.root / "lane-evidence"
        self._write_evidence_next(receipt_dir)
        receipt_path = receipt_dir / "worktree-receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "kind": "depone-worktree-lane-receipt",
                    "schema_version": "0.1",
                    "worktree": "repo",
                    "branch": "codex/worktree-lane-receipt",
                    "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "head_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "dirty": True,
                    "dirty_files": ["sample.txt"],
                    "changed_files": ["sample.txt"],
                    "evidence_dir": "lane-evidence",
                    "command_receipts": [],
                    "boundary": {"executes_commands": False, "launches_agents": False},
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["evidence_next_verdict"] = "lane-evidence/evidence-next-verdict.json"
        ledger["lanes"][0]["worktree_receipt"] = "lane-evidence/worktree-receipt.json"
        ledger["lanes"][0]["touched_files"] = ["sample.txt"]

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_DIRTY",
            {error["code"] for error in verdict["errors"]},
        )

    def test_worktree_receipt_path_traversal_blocks_lane(self) -> None:
        self._write_evidence_next(self.root / "lane-evidence")
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["evidence_next_verdict"] = "lane-evidence/evidence-next-verdict.json"
        ledger["lanes"][0]["worktree_receipt"] = "../receipt.json"

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_WORKTREE_RECEIPT_PATH_INVALID",
            {error["code"] for error in verdict["errors"]},
        )

    def test_invalid_touched_files_with_worktree_receipt_blocks_without_crash(self) -> None:
        receipt_dir = self.root / "lane-evidence"
        self._write_evidence_next(receipt_dir)
        receipt_path = receipt_dir / "worktree-receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "kind": "depone-worktree-lane-receipt",
                    "schema_version": "0.1",
                    "worktree": "repo",
                    "branch": "codex/worktree-lane-receipt",
                    "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "head_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "dirty": False,
                    "dirty_files": [],
                    "changed_files": ["sample.txt"],
                    "evidence_dir": "lane-evidence",
                    "command_receipts": [],
                    "boundary": {"executes_commands": False, "launches_agents": False},
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["evidence_next_verdict"] = "lane-evidence/evidence-next-verdict.json"
        ledger["lanes"][0]["worktree_receipt"] = "lane-evidence/worktree-receipt.json"
        ledger["lanes"][0]["touched_files"] = [["sample.txt"]]

        verdict = build_team_ledger_verdict(ledger, base_dir=self.root)

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "ERR_TEAM_LEDGER_TOUCHED_FILES_INVALID",
            {error["code"] for error in verdict["errors"]},
        )

    def test_missing_worktree_repo_blocks_receipt_producer(self) -> None:
        missing = self.root / "missing"

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "worktree-lane-receipt",
                "--worktree",
                str(missing),
                "--base-commit",
                "HEAD~1",
                "--evidence-dir",
                "lane-evidence",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 3)
        self.assertEqual(
            json.loads(completed.stdout)["error"]["code"],
            "ERR_WORKTREE_RECEIPT_REPO_MISSING",
        )


if __name__ == "__main__":
    unittest.main()
