from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depone.__main__ as depone_main
from depone.agent_fabric.capture_bridge import _sha256_json
from depone.agent_fabric.evidence_substrate import build_evidence_bundle
from depone.cli.evidence_next import evaluate_evidence_dir


FIXTURE_ROOT = Path("docs/depone-run-receipt-frontdoor")


class EvidenceNextTests(unittest.TestCase):
    def test_valid_committed_evidence_dir_recommends_continue(self) -> None:
        decision = evaluate_evidence_dir(FIXTURE_ROOT)

        self.assertEqual(decision["command"], "evidence-next")
        self.assertEqual(decision["decision"], "continue")
        self.assertEqual(decision["next_action"], "run_next_evidence_slice")
        self.assertEqual(decision["assurance"], "A2-isolated-observed")
        self.assertEqual(decision["capture"]["errors"], [])
        self.assertEqual(decision["runner_receipt"]["errors"], [])
        self.assertEqual(decision["evidence_bundle"]["statement_errors"], [])
        self.assertEqual(decision["evidence_ingest"]["decision"], "pass")
        self.assertEqual(decision["blocking_reasons"], [])
        self.assertTrue(decision["boundary"]["privilege_isolated"])
        self.assertEqual(decision["verified_artifacts"]["verified_subject_count"], 4)
        self.assertEqual(decision["recorded_ingest"]["decision"], "pass")
        self.assertEqual(decision["verify"]["summary_decision"], "skipped")
        self.assertEqual(decision["verify"]["errors"], [])

    def test_digest_mismatch_blocks_instead_of_trusting_recorded_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "evidence"
            shutil.copytree(FIXTURE_ROOT, root)
            manifest_path = root / "capture-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["allowed_touched_files"] = ["tampered.txt"]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            decision = evaluate_evidence_dir(root)

        self.assertEqual(decision["decision"], "blocked")
        self.assertEqual(decision["next_action"], "repair_evidence_artifacts")
        self.assertIn("capture-manifest.json failed validation", decision["blocking_reasons"])
        self.assertIn("evidence ingest decision is blocked", decision["blocking_reasons"])
        self.assertEqual(decision["recorded_ingest"]["decision"], "pass")

    def test_missing_artifact_blocks_with_machine_readable_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "evidence"
            shutil.copytree(FIXTURE_ROOT, root)
            (root / "evidence-bundle.json").unlink()

            decision = evaluate_evidence_dir(root)

        self.assertEqual(decision["decision"], "blocked")
        self.assertEqual(decision["next_action"], "repair_evidence_artifacts")
        self.assertIn(
            "missing required artifact: evidence-bundle.json",
            decision["blocking_reasons"],
        )

    def test_verify_failure_blocks_even_when_artifact_hashes_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "evidence"
            shutil.copytree(FIXTURE_ROOT, root)
            summary_path = root / "evidence-run-summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["verify"]["decision"] = "blocked"
            summary_path.write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            decision = evaluate_evidence_dir(root)

        self.assertEqual(decision["decision"], "blocked")
        self.assertEqual(decision["evidence_ingest"]["decision"], "pass")
        self.assertIn(
            "evidence-run summary verify decision is blocked",
            decision["blocking_reasons"],
        )

    def test_embedded_source_fixture_revalidates_without_default_fixture_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "evidence"
            shutil.copytree(FIXTURE_ROOT, root)
            manifest_path = root / "capture-manifest.json"
            receipt = json.loads((root / "runner-receipt.json").read_text(encoding="utf-8"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            fixture = dict(manifest["fixture"])
            invocation = dict(fixture["invocation"])
            invocation["instructions"] = "Use a non-default embedded fixture."
            fixture["invocation"] = invocation
            fixture_hash = _sha256_json(fixture)
            manifest["fixture"] = fixture
            manifest["source_fixture_hash"] = fixture_hash
            observer_capture = dict(manifest["observer_capture"])
            observer_capture["source_fixture_hash"] = fixture_hash
            manifest["observer_capture"] = observer_capture
            manifest["observer_capture_hash"] = _sha256_json(observer_capture)
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (root / "observer-capture.json").write_text(
                json.dumps(observer_capture, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            bundle = build_evidence_bundle(manifest, runner_receipt=receipt)
            (root / "evidence-bundle.json").write_text(
                json.dumps(bundle, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            decision = evaluate_evidence_dir(root)

        self.assertEqual(decision["decision"], "continue")
        self.assertEqual(decision["evidence_ingest"]["decision"], "pass")

    def test_cli_next_alias_dispatches_to_evidence_next(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(
            sys,
            "argv",
            ["depone", "next", "--evidence-dir", str(FIXTURE_ROOT), "--json"],
        ):
            with patch.object(depone_main.evidence_next, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "next")
        self.assertEqual(getattr(seen[0], "evidence_dir"), str(FIXTURE_ROOT))
        self.assertTrue(getattr(seen[0], "json"))

    def test_cli_requires_evidence_dir(self) -> None:
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["depone", "next", "--json"]):
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as raised:
                    depone_main.main()

        self.assertEqual(raised.exception.code, 3)


if __name__ == "__main__":
    unittest.main()
