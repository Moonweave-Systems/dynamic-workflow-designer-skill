from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.team_merge_attempt import (
    TEAM_MERGE_ATTEMPT_KIND,
    TEAM_MERGE_ATTEMPT_SCHEMA_VERSION,
    build_team_merge_attempt_receipt,
    validate_team_merge_attempt_receipt,
)


class AgentFabricTeamMergeAttemptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self._git("init")
        self._git("config", "user.email", "depone@example.invalid")
        self._git("config", "user.name", "Depone Tests")
        (self.repo / "shared.txt").write_text("base\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "base")
        self.common = self._rev("HEAD")

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if check and completed.returncode != 0:
            self.fail(completed.stderr or completed.stdout)
        return completed

    def _rev(self, rev: str) -> str:
        return self._git("rev-parse", rev).stdout.strip()

    def _branch_with_file(self, branch: str, path: str, content: str) -> str:
        self._git("checkout", "-B", branch, self.common)
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self._git("add", path)
        self._git("commit", "-m", f"{branch} change")
        return self._rev("HEAD")

    def _branch_with_shared_content(self, branch: str, content: str) -> str:
        self._git("checkout", "-B", branch, self.common)
        (self.repo / "shared.txt").write_text(content, encoding="utf-8")
        self._git("add", "shared.txt")
        self._git("commit", "-m", f"{branch} conflict")
        return self._rev("HEAD")

    def test_clean_merge_attempt_passes_in_disposable_worktree(self) -> None:
        base = self._branch_with_file("base-lane", "base-only.txt", "base lane\n")
        head = self._branch_with_file("head-lane", "head-only.txt", "head lane\n")

        receipt = build_team_merge_attempt_receipt(repo=self.repo, base=base, heads=[head], captured_at="2026-07-01T00:00:00Z")

        self.assertEqual(receipt["kind"], TEAM_MERGE_ATTEMPT_KIND)
        self.assertEqual(receipt["schema_version"], TEAM_MERGE_ATTEMPT_SCHEMA_VERSION)
        self.assertEqual(receipt["decision"], "pass")
        self.assertEqual(receipt["base_commit"], base)
        self.assertEqual(receipt["head_commits"], [head])
        self.assertIn("head-only.txt", receipt["merged_files"])
        self.assertEqual(receipt["conflict_files"], [])
        self.assertTrue(receipt["cleanup"]["attempt_worktree_removed"])
        self.assertEqual(validate_team_merge_attempt_receipt(receipt), [])
        self.assertFalse(Path(str(receipt["attempt_worktree"])).exists())
        self.assertFalse(receipt["boundary"]["approves_merge"])
        self.assertFalse(receipt["boundary"]["raises_assurance"])

    def test_conflicting_merge_attempt_blocks_with_conflict_files(self) -> None:
        base = self._branch_with_shared_content("base-lane", "base lane\n")
        head = self._branch_with_shared_content("head-lane", "head lane\n")

        receipt = build_team_merge_attempt_receipt(repo=self.repo, base=base, heads=[head], captured_at="2026-07-01T00:00:00Z")

        self.assertEqual(receipt["decision"], "blocked")
        self.assertNotEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["conflict_files"], ["shared.txt"])
        self.assertIn("ERR_TEAM_MERGE_ATTEMPT_CONFLICT", {error["code"] for error in receipt["errors"]})
        self.assertTrue(receipt["cleanup"]["attempt_worktree_removed"])

    def test_dirty_target_worktree_blocks_without_disposable_mode(self) -> None:
        base = self._branch_with_file("base-lane", "base-only.txt", "base lane\n")
        head = self._branch_with_file("head-lane", "head-only.txt", "head lane\n")
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")

        receipt = build_team_merge_attempt_receipt(
            repo=self.repo,
            base=base,
            heads=[head],
            disposable=False,
            captured_at="2026-07-01T00:00:00Z",
        )

        self.assertEqual(receipt["decision"], "blocked")
        self.assertTrue(receipt["dirty_target_refused"])
        self.assertIn("ERR_TEAM_MERGE_ATTEMPT_DIRTY_TARGET", {error["code"] for error in receipt["errors"]})

    def test_in_place_attempt_restores_original_checkout(self) -> None:
        base = self._branch_with_file("base-lane", "base-only.txt", "base lane\n")
        head = self._branch_with_file("head-lane", "head-only.txt", "head lane\n")
        self._git("checkout", "head-lane")

        receipt = build_team_merge_attempt_receipt(
            repo=self.repo,
            base=base,
            heads=[head],
            disposable=False,
            captured_at="2026-07-01T00:00:00Z",
        )

        self.assertEqual(receipt["decision"], "pass")
        self.assertFalse(receipt["cleanup"]["attempt_worktree_removed"])
        self.assertTrue(receipt["cleanup"]["attempt_worktree_restored"])
        self.assertEqual(self._git("branch", "--show-current").stdout.strip(), "head-lane")
        self.assertEqual(validate_team_merge_attempt_receipt(receipt), [])

    def test_missing_base_commit_blocks(self) -> None:
        head = self._branch_with_file("head-lane", "head-only.txt", "head lane\n")

        receipt = build_team_merge_attempt_receipt(repo=self.repo, base="missing", heads=[head], captured_at="2026-07-01T00:00:00Z")

        self.assertEqual(receipt["decision"], "blocked")
        self.assertIn("ERR_TEAM_MERGE_ATTEMPT_BASE_MISSING", {error["code"] for error in receipt["errors"]})

    def test_receipt_validation_rejects_missing_cleanup_state(self) -> None:
        receipt = {
            "kind": TEAM_MERGE_ATTEMPT_KIND,
            "schema_version": TEAM_MERGE_ATTEMPT_SCHEMA_VERSION,
            "decision": "pass",
            "base_commit": "a" * 40,
            "head_commits": ["b" * 40],
            "attempt_worktree": "/tmp/depone-merge-attempt",
            "dirty_target_refused": False,
            "exit_code": 0,
            "merged_files": ["depone/agent_fabric/team_ledger.py"],
            "conflict_files": [],
            "captured_at": "2026-07-01T00:00:00Z",
            "source_command": ["git", "merge", "--no-commit"],
            "errors": [],
            "boundary": {
                "executes_git_merge_attempt": True,
                "launches_agents": False,
                "calls_live_models": False,
                "approves_merge": False,
                "raises_assurance": False,
            },
        }

        self.assertIn(
            "ERR_TEAM_MERGE_ATTEMPT_CLEANUP_INVALID",
            {error["code"] for error in validate_team_merge_attempt_receipt(receipt)},
        )

    def test_pass_receipt_requires_removed_or_restored_attempt_worktree(self) -> None:
        receipt = {
            "kind": TEAM_MERGE_ATTEMPT_KIND,
            "schema_version": TEAM_MERGE_ATTEMPT_SCHEMA_VERSION,
            "decision": "pass",
            "base_commit": "a" * 40,
            "head_commits": ["b" * 40],
            "attempt_worktree": "/tmp/depone-merge-attempt",
            "dirty_target_refused": False,
            "exit_code": 0,
            "merged_files": ["depone/agent_fabric/team_ledger.py"],
            "conflict_files": [],
            "cleanup": {"attempt_worktree_removed": False},
            "captured_at": "2026-07-01T00:00:00Z",
            "source_command": ["git", "merge", "--no-commit"],
            "errors": [],
            "boundary": {
                "executes_git_merge_attempt": True,
                "launches_agents": False,
                "calls_live_models": False,
                "approves_merge": False,
                "raises_assurance": False,
            },
        }

        self.assertIn(
            "ERR_TEAM_MERGE_ATTEMPT_CLEANUP_INVALID",
            {error["code"] for error in validate_team_merge_attempt_receipt(receipt)},
        )


if __name__ == "__main__":
    unittest.main()
