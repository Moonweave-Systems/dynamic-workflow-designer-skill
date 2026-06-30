from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depone.__main__ as depone_main
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


if __name__ == "__main__":
    unittest.main()
