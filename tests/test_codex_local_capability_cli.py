from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depone.__main__ as depone_main


class CodexLocalCapabilityCliTests(unittest.TestCase):
    def test_self_test_exits_zero(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "depone", "codex-local-capability", "--self-test"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("codex-local-capability --self-test: pass", completed.stdout)

    def test_cli_writes_blocked_receipt_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            out = root / "capability.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "codex-local-capability",
                    "--repo",
                    str(root),
                    "--codex-binary",
                    "definitely-missing-codex-for-test",
                    "--instruction-file",
                    "AGENTS.md",
                    "--out",
                    str(out),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            receipt = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"], "blocked")
        self.assertEqual(receipt["decision"], "blocked")
        self.assertFalse(receipt["readiness"]["version_probe"]["executed"])

    def test_cli_writes_pass_receipt_json_for_fake_codex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
            (root / "AGENTS.md").write_text("# contract\n", encoding="utf-8")
            fake_codex = root / "codex"
            fake_codex.write_text("#!/bin/sh\nprintf 'codex 0.cli\\n'\n", encoding="utf-8")
            fake_codex.chmod(0o755)
            subprocess.run(["git", "add", "AGENTS.md", "codex"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)
            out = base / "capability.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "codex-local-capability",
                    "--repo",
                    str(root),
                    "--codex-binary",
                    str(fake_codex),
                    "--instruction-file",
                    "AGENTS.md",
                    "--out",
                    str(out),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            receipt = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"], "pass")
        self.assertEqual(receipt["decision"], "pass")
        self.assertEqual(receipt["adapter"]["version"], "codex 0.cli")
        self.assertEqual(receipt["readiness"]["version_probe"]["argv"], ["codex", "--version"])
        self.assertEqual(receipt["readiness"]["version_probe"]["exit_code"], 0)
        self.assertEqual(receipt["readiness"]["version_probe"]["sanitized_version_text"], "codex 0.cli")

    def test_main_dispatches_codex_local_capability(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(sys, "argv", ["depone", "codex-local-capability", "--self-test"]):
            with patch.object(depone_main.codex_local_capability, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "codex-local-capability")


if __name__ == "__main__":
    unittest.main()
