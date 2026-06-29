from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depone._resources import resource_text
from depone.agent_fabric.evidence_substrate import build_evidence_bundle
from depone.agent_fabric.sign import (
    _generate_ed25519_keypair,
    openssl_path,
    verify_signed_bundle,
)
from depone.cli.evidence_run import _maybe_write_signed_bundle, run_evidence_loop


def _run_git(repo: Path, args: list[str]) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip() or result.stdout.strip())


class EvidenceRunSigningTests(unittest.TestCase):
    def test_evidence_run_writes_verifiable_signed_bundle(self) -> None:
        if openssl_path() is None:
            self.skipTest("openssl executable is not on PATH")

        with tempfile.TemporaryDirectory(prefix="depone-evidence-run-signing-") as temp_text:
            root = Path(temp_text)
            runner = root / "runner-sandbox"
            runner.mkdir()
            _run_git(runner, ["init"])
            _run_git(runner, ["config", "user.email", "observer@example.invalid"])
            _run_git(runner, ["config", "user.name", "Observer Test"])
            (runner / "sample.txt").write_text("before\n", encoding="utf-8")
            _run_git(runner, ["add", "sample.txt"])
            _run_git(runner, ["commit", "-m", "seed"])
            (runner / "sample.txt").write_text("after\n", encoding="utf-8")

            source_fixture = root / "reference_adapter_shell.json"
            source_fixture.write_text(
                resource_text("fixtures/agent_fabric/reference_adapter_shell.json"),
                encoding="utf-8",
            )
            private_key, public_key = _generate_ed25519_keypair(root)
            args = argparse.Namespace(
                runner_sandbox=str(runner),
                source_fixture=str(source_fixture),
                out=str(root / "evidence-run"),
                allow_touched_file=["sample.txt"],
                verify_plan="",
                verify_evidence="",
                verify_adapter="generic",
                operator_view_out="",
                timeout_seconds=120,
                runner_uid=None,
                runner_container_id="",
                runner_container_image="",
                runner_container_command="",
                runner_container_hold_seconds=600,
                sign_private_key=str(private_key),
                sign_key_id="operator-test-key",
                sign_public_key=str(public_key),
                verification_command=[
                    sys.executable,
                    "-c",
                    "from pathlib import Path; assert Path('sample.txt').exists()",
                ],
                json=False,
            )

            payload = run_evidence_loop(args)
            signed_path = root / "evidence-run" / "signed-evidence-bundle.json"
            signed_bundle = json.loads(signed_path.read_text(encoding="utf-8"))
            self.assertTrue(verify_signed_bundle(signed_bundle, str(public_key)))

            self.assertEqual(
                payload["signed_evidence_bundle"]["signing_status"],
                "signed-ed25519-operator-key",
            )
            self.assertIs(payload["signed_evidence_bundle"]["verified"], True)

    def test_signed_bundle_is_not_written_when_public_key_verify_fails(self) -> None:
        if openssl_path() is None:
            self.skipTest("openssl executable is not on PATH")

        with tempfile.TemporaryDirectory(prefix="depone-evidence-run-signing-") as temp_text:
            root = Path(temp_text)
            private_key, _public_key = _generate_ed25519_keypair(root)
            wrong_dir = root / "wrong"
            wrong_dir.mkdir()
            _wrong_private, wrong_public = _generate_ed25519_keypair(wrong_dir)
            capture = json.loads(
                resource_text(
                    "fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json"
                )
            )
            bundle = build_evidence_bundle(capture)

            with self.assertRaises(ValueError):
                _maybe_write_signed_bundle(
                    root,
                    bundle,
                    private_key_path=str(private_key),
                    key_id="operator-test-key",
                    public_key_path=str(wrong_public),
                )

            self.assertFalse((root / "signed-evidence-bundle.json").exists())


if __name__ == "__main__":
    unittest.main()
