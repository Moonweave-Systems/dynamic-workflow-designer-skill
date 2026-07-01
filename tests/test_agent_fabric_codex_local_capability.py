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
        self.assertEqual(
            receipt["readiness"]["version_probe"],
            {
                "executed": False,
                "argv": ["codex", "--version"],
                "exit_code": None,
                "timed_out": False,
                "stdout_present": False,
                "stderr_present": False,
                "sanitized_version_text": None,
                "unexpected_output": False,
                "error": "binary_not_found",
            },
        )
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
        self.assertEqual(
            receipt["readiness"]["version_probe"],
            {
                "executed": True,
                "argv": ["codex", "--version"],
                "exit_code": 0,
                "timed_out": False,
                "stdout_present": True,
                "stderr_present": False,
                "sanitized_version_text": "codex 0.test",
                "unexpected_output": False,
                "error": None,
            },
        )
        self.assertEqual(receipt["repo"]["dirty"], False)
        self.assertEqual(receipt["instruction_files"][0]["present"], True)
        self.assertEqual(validate_codex_local_capability(receipt), [])

    def test_version_probe_nonzero_exit_blocks_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
            fake_codex = root / "codex"
            fake_codex.write_text(
                "#!/bin/sh\nprintf 'nope\\n' >&2\nexit 7\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            subprocess.run(["git", "add", "codex"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)

            with patch("shutil.which", return_value=fake_codex.as_posix()):
                receipt = build_codex_local_capability(repo=root)

        probe = receipt["readiness"]["version_probe"]
        self.assertEqual(receipt["decision"], "blocked")
        self.assertIn("codex version probe failed", receipt["blocked_reasons"])
        self.assertEqual(probe["exit_code"], 7)
        self.assertTrue(probe["stderr_present"])
        self.assertIsNone(probe["sanitized_version_text"])
        self.assertEqual(validate_codex_local_capability(receipt), [])

    def test_version_probe_timeout_blocks_without_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
            fake_codex = root / "codex"
            fake_codex.write_text("#!/bin/sh\nsleep 2\n", encoding="utf-8")
            fake_codex.chmod(0o755)
            subprocess.run(["git", "add", "codex"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)

            with patch("shutil.which", return_value=fake_codex.as_posix()):
                receipt = build_codex_local_capability(
                    repo=root,
                    version_timeout_seconds=0.01,
                )

        probe = receipt["readiness"]["version_probe"]
        self.assertEqual(receipt["decision"], "blocked")
        self.assertIn("codex version probe timed out", receipt["blocked_reasons"])
        self.assertTrue(probe["timed_out"])
        self.assertIsNone(probe["exit_code"])
        self.assertIsNone(probe["sanitized_version_text"])
        self.assertEqual(validate_codex_local_capability(receipt), [])

    def test_version_probe_unexpected_output_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
            fake_codex = root / "codex"
            fake_codex.write_text("#!/bin/sh\nprintf 'unexpected-marker\\nextra\\n'\n", encoding="utf-8")
            fake_codex.chmod(0o755)
            subprocess.run(["git", "add", "codex"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)

            with patch("shutil.which", return_value=fake_codex.as_posix()):
                receipt = build_codex_local_capability(repo=root)

        probe = receipt["readiness"]["version_probe"]
        self.assertEqual(receipt["decision"], "blocked")
        self.assertIn("codex version probe returned unexpected output", receipt["blocked_reasons"])
        self.assertTrue(probe["unexpected_output"])
        self.assertIsNone(probe["sanitized_version_text"])
        self.assertNotIn("unexpected-marker", json.dumps(receipt))
        self.assertEqual(validate_codex_local_capability(receipt), [])

    def test_instruction_file_outside_repo_boundary_blocks_without_hashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
            fake_codex = root / "codex"
            fake_codex.write_text("#!/bin/sh\nprintf 'codex 0.test\\n'\n", encoding="utf-8")
            fake_codex.chmod(0o755)
            subprocess.run(["git", "add", "codex"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)

            with patch("shutil.which", return_value=fake_codex.as_posix()):
                receipt = build_codex_local_capability(
                    repo=root,
                    instruction_files=[Path("../outside.md")],
                )

        self.assertEqual(receipt["decision"], "blocked")
        self.assertIn("instruction file path outside repo boundary", receipt["blocked_reasons"])
        self.assertEqual(receipt["instruction_files"][0]["sha256"], None)
        self.assertEqual(
            receipt["instruction_files"][0]["blocked_reason"],
            "instruction file must be repo-relative",
        )
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
            "readiness": {
                "version_probe": {
                    "executed": True,
                    "argv": ["codex", "--version"],
                    "exit_code": 0,
                    "timed_out": False,
                    "stdout_present": True,
                    "stderr_present": False,
                    "sanitized_version_text": "codex 0.test",
                    "unexpected_output": False,
                    "error": None,
                },
            },
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

    def test_invalid_receipt_validation_requires_readiness(self) -> None:
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
            "agent_contract_hash": "same",
            "agent_contract": {"agent_contract_hash": "same"},
        }

        self.assertIn("readiness must be an object", validate_codex_local_capability(receipt))

    def test_invalid_receipt_validation_reports_malformed_version_probe(self) -> None:
        receipt = {
            "kind": CODEX_LOCAL_CAPABILITY_KIND,
            "schema_version": "0.1",
            "decision": "pass",
            "blocked_reasons": [],
            "readiness": {
                "version_probe": {
                    "executed": "yes",
                    "argv": ["/home/user/.codex/bin/codex", "--version"],
                    "exit_code": "0",
                    "timed_out": "no",
                    "stdout_present": "yes",
                    "stderr_present": "no",
                    "sanitized_version_text": "unexpected-marker\ncodex 0.test",
                    "unexpected_output": "no",
                },
            },
            "boundary": {
                "launches_live_model": False,
                "executes_coding_task": False,
                "captures_capability_only": True,
                "raises_assurance": False,
            },
            "agent_contract_hash": "same",
            "agent_contract": {"agent_contract_hash": "same"},
        }

        errors = validate_codex_local_capability(receipt)

        self.assertIn("readiness.version_probe.executed must be boolean", errors)
        self.assertIn("readiness.version_probe.argv must be sanitized codex --version", errors)
        self.assertIn("readiness.version_probe.exit_code must be int or null", errors)
        self.assertIn("readiness.version_probe.sanitized_version_text is invalid", errors)

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
