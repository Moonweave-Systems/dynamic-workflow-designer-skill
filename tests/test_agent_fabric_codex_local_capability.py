from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from depone.agent_fabric.codex_local_capability import (
    CODEX_LOCAL_CAPABILITY_KIND,
    build_codex_local_capability,
    validate_codex_local_capability,
)


class CodexLocalCapabilityTests(unittest.TestCase):
    def test_missing_codex_binary_blocks_without_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            with patch("shutil.which", return_value=None):
                receipt = build_codex_local_capability(
                    repo=root,
                    codex_binary="codex",
                    sandbox_mode="workspace-write",
                    approval_policy="on-request",
                    instruction_files=[],
                )

        self.assertEqual(receipt["kind"], CODEX_LOCAL_CAPABILITY_KIND)
        self.assertEqual(receipt["decision"], "blocked")
        self.assertIn("codex binary not found", receipt["blocked_reasons"])
        self.assertFalse(receipt["boundary"]["launches_live_model"])
        self.assertFalse(receipt["boundary"]["executes_coding_task"])
        self.assertFalse(receipt["boundary"]["raises_assurance"])
        self.assertEqual(validate_codex_local_capability(receipt), [])

    def test_pass_receipt_records_version_repo_and_instruction_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
            (root / "AGENTS.md").write_text("# contract\n", encoding="utf-8")
            fake_codex = root / "codex"
            fake_codex.write_text("#!/bin/sh\nprintf 'codex 0.test\\n'\n", encoding="utf-8")
            fake_codex.chmod(0o755)
            subprocess.run(["git", "add", "AGENTS.md", "codex"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)

            with patch("shutil.which", return_value=fake_codex.as_posix()):
                receipt = build_codex_local_capability(
                    repo=root,
                    codex_binary="codex",
                    sandbox_mode="workspace-write",
                    approval_policy="on-request",
                    instruction_files=[Path("AGENTS.md")],
                )

        self.assertEqual(receipt["decision"], "pass")
        self.assertEqual(receipt["adapter"]["version"], "codex 0.test")
        self.assertEqual(receipt["repo"]["dirty"], False)
        self.assertEqual(receipt["instruction_files"][0]["present"], True)
        self.assertEqual(validate_codex_local_capability(receipt), [])

    def test_dirty_repo_blocks_even_when_codex_binary_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
            (root / "tracked.txt").write_text("before\n", encoding="utf-8")
            fake_codex = root / "codex"
            fake_codex.write_text("#!/bin/sh\nprintf 'codex 0.test\\n'\n", encoding="utf-8")
            fake_codex.chmod(0o755)
            subprocess.run(["git", "add", "tracked.txt", "codex"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)
            (root / "tracked.txt").write_text("after\n", encoding="utf-8")

            with patch("shutil.which", return_value=fake_codex.as_posix()):
                receipt = build_codex_local_capability(repo=root)

        self.assertEqual(receipt["decision"], "blocked")
        self.assertIn("repo working tree is dirty", receipt["blocked_reasons"])
        self.assertEqual(validate_codex_local_capability(receipt), [])

    def test_invalid_receipt_validation_reports_hash_mismatch(self) -> None:
        receipt = {
            "kind": CODEX_LOCAL_CAPABILITY_KIND,
            "schema_version": "0.1",
            "decision": "pass",
            "blocked_reasons": [],
            "boundary": {
                "launches_live_model": False,
                "executes_coding_task": False,
                "captures_capability_only": True,
                "raises_assurance": False,
            },
            "agent_contract_hash": "wrong",
            "agent_contract": {"agent_contract_hash": "right"},
        }

        self.assertIn("agent_contract_hash mismatch", validate_codex_local_capability(receipt))

    def test_write_receipt_round_trips_json(self) -> None:
        from depone.agent_fabric.codex_local_capability import write_codex_local_capability

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            with patch("shutil.which", return_value=None):
                receipt = build_codex_local_capability(repo=root)
            out = root / "capability.json"
            write_codex_local_capability(out, receipt)

            loaded = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(loaded["kind"], CODEX_LOCAL_CAPABILITY_KIND)
        self.assertEqual(loaded["decision"], "blocked")


if __name__ == "__main__":
    unittest.main()
