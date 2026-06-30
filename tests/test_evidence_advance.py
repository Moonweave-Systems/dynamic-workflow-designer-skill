from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depone.__main__ as depone_main
from depone.agent_fabric.capture_bridge import validate_capture_manifest
from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.evidence_substrate import verify_capture_chain
from depone.agent_fabric.paired_run import validate_runner_receipt
from depone.cli import advance
from depone.cli.evidence_next import evaluate_evidence_dir


class EvidenceAdvanceTests(unittest.TestCase):
    def _args(self, root: Path) -> argparse.Namespace:
        return argparse.Namespace(
            evidence_dir=str(root / "previous"),
            runner_sandbox=str(root / "runner"),
            source_fixture=str(root / "source.json"),
            out=str(root / "continuation"),
            advance_out=str(root / "advance-decision.json"),
            allow_touched_file=[],
            verify_plan="",
            verify_evidence="",
            verify_adapter="generic",
            operator_view_out="",
            timeout_seconds=120,
            runner_uid=None,
            runner_user="",
            runner_command="",
            runner_container_id="",
            runner_container_image="",
            runner_container_command="",
            runner_container_hold_seconds=600,
            sign_private_key="",
            sign_key_id="",
            sign_public_key="",
            previous_source_fixture="",
            verification_command=[sys.executable, "-m", "unittest"],
            json=True,
        )

    def _write_previous_manifest(self, root: Path) -> dict[str, object]:
        previous = root / "previous"
        previous.mkdir(exist_ok=True)
        previous_manifest: dict[str, object] = {
            "kind": "agent-fabric-capture-manifest",
            "prev_capture_hash": None,
        }
        (previous / "capture-manifest.json").write_text(
            json.dumps(previous_manifest) + "\n",
            encoding="utf-8",
        )
        return previous_manifest

    def test_advance_revalidates_previous_evidence_dir_before_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self._args(root)
            args.previous_source_fixture = str(root / "previous-source.json")
            previous_manifest = self._write_previous_manifest(root)
            calls = []

            def fake_evaluate(path: Path, *, source_fixture: Path | None = None) -> dict[str, object]:
                calls.append((path, source_fixture))
                return {
                    "command": "evidence-next",
                    "decision": "continue",
                    "next_action": "run_next_evidence_slice",
                    "blocking_reasons": [],
                }

            with patch.object(advance, "evaluate_evidence_dir", side_effect=fake_evaluate):
                with patch.object(
                    advance,
                    "run_evidence_loop",
                    return_value={"command": "evidence-run", "decision": "pass", "out": str(root / "continuation")},
                ):
                    artifact = advance.advance_once(args)

        self.assertEqual(calls, [(Path(args.evidence_dir), Path(args.previous_source_fixture))])
        self.assertEqual(artifact["decision"], "pass")
        self.assertEqual(artifact["next_gate"]["decision"], "continue")
        self.assertEqual(artifact["previous_source_fixture"], args.previous_source_fixture)
        self.assertEqual(getattr(args, "prev_capture_hash"), canonical_hash(previous_manifest))

    def test_advance_refuses_when_next_decision_is_not_continue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self._args(root)
            with patch.object(
                advance,
                "evaluate_evidence_dir",
                return_value={"decision": "blocked", "blocking_reasons": ["tampered"]},
            ):
                with patch.object(advance, "run_evidence_loop") as run_loop:
                    artifact = advance.advance_once(args)

        self.assertEqual(artifact["decision"], "blocked")
        self.assertEqual(artifact["action"], "refuse_continuation")
        self.assertEqual(artifact["executed_continuations"], 0)
        self.assertEqual(artifact["automation_boundary"]["executed_continuation_count"], 0)
        run_loop.assert_not_called()

    def test_advance_refuses_when_continue_has_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self._args(root)
            with patch.object(
                advance,
                "evaluate_evidence_dir",
                return_value={"decision": "continue", "blocking_reasons": ["stale verify"]},
            ):
                with patch.object(advance, "run_evidence_loop") as run_loop:
                    artifact = advance.advance_once(args)

        self.assertEqual(artifact["decision"], "blocked")
        self.assertEqual(artifact["action"], "refuse_continuation")
        run_loop.assert_not_called()

    def test_advance_runs_exactly_one_existing_evidence_run_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self._args(root)
            previous_manifest = self._write_previous_manifest(root)
            with patch.object(
                advance,
                "evaluate_evidence_dir",
                return_value={"decision": "continue", "blocking_reasons": []},
            ):
                with patch.object(
                    advance,
                    "run_evidence_loop",
                    return_value={"command": "evidence-run", "decision": "pass", "out": str(root / "continuation")},
                ) as run_loop:
                    artifact = advance.advance_once(args)

        run_loop.assert_called_once_with(args)
        self.assertEqual(getattr(args, "prev_capture_hash"), canonical_hash(previous_manifest))
        self.assertEqual(
            getattr(args, "previous_capture_path"),
            str(Path(args.evidence_dir) / "capture-manifest.json"),
        )
        self.assertEqual(artifact["executed_continuations"], 1)
        self.assertEqual(artifact["automation_boundary"]["executed_continuation_count"], 1)
        self.assertFalse(artifact["automation_boundary"]["full_scheduler"])

    def test_advance_writes_machine_readable_decision_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self._args(root)
            self._write_previous_manifest(root)
            with patch.object(
                advance,
                "evaluate_evidence_dir",
                return_value={"command": "evidence-next", "decision": "continue", "blocking_reasons": []},
            ):
                with patch.object(
                    advance,
                    "run_evidence_loop",
                    return_value={"command": "evidence-run", "decision": "pass", "out": str(root / "continuation")},
                ):
                    artifact = advance.advance_once(args)

            payload = json.loads(Path(args.advance_out).read_text(encoding="utf-8"))

        self.assertEqual(payload, artifact)
        self.assertEqual(payload["command"], "advance")
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["decision"], "pass")
        self.assertEqual(payload["previous_evidence_dir"], str(root / "previous"))
        self.assertEqual(payload["continuation"]["decision"], "pass")
        self.assertEqual(payload["executed_continuations"], 1)
        self.assertEqual(payload["out"], str(root / "advance-decision.json"))

    def test_cli_advance_dispatches_to_advance(self) -> None:
        seen = []
        argv = [
            "depone",
            "advance",
            "--evidence-dir",
            "/tmp/previous",
            "--runner-sandbox",
            "/tmp/runner",
            "--source-fixture",
            "/tmp/source.json",
            "--out",
            "/tmp/continuation",
            "--advance-out",
            "/tmp/advance.json",
            "--json",
            "--",
            sys.executable,
            "-m",
            "unittest",
        ]

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(sys, "argv", argv):
            with patch.object(depone_main.advance, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        args = seen[0]
        self.assertEqual(getattr(args, "command"), "advance")
        self.assertEqual(getattr(args, "evidence_dir"), "/tmp/previous")
        self.assertEqual(getattr(args, "advance_out"), "/tmp/advance.json")
        self.assertEqual(getattr(args, "verification_command"), ["--", sys.executable, "-m", "unittest"])

    def test_cli_requires_evidence_dir_before_running(self) -> None:
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["depone", "advance", "--json"]):
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as raised:
                    depone_main.main()

        self.assertEqual(raised.exception.code, 3)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["error"]["code"], "ERR_ADVANCE_INPUT_REQUIRED")

    def test_cli_reports_continuation_input_errors_as_usage(self) -> None:
        cases = [
            (
                "verification_command",
                ["--"],
                "verification command is required after --",
            ),
            ("runner_sandbox", "", "--runner-sandbox is required"),
            ("source_fixture", "", "--source-fixture is required"),
            ("verify_plan", "plan.json", "--verify-plan and --verify-evidence"),
            ("sign_private_key", "key.pem", "--sign-private-key and --sign-key-id"),
            ("sign_public_key", "pub.pem", "--sign-public-key requires"),
        ]

        for attr, value, message in cases:
            with self.subTest(attr=attr):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    args = self._args(root)
                    setattr(args, attr, value)
                    stdout = io.StringIO()

                    with patch.object(
                        advance,
                        "evaluate_evidence_dir",
                        return_value={"decision": "continue", "blocking_reasons": []},
                    ):
                        with contextlib.redirect_stdout(stdout):
                            with self.assertRaises(SystemExit) as raised:
                                advance.run(args)

                self.assertEqual(raised.exception.code, 3)
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["error"]["code"], "ERR_ADVANCE_INPUT_INVALID")
                self.assertIn(message, payload["error"]["message"])

    def test_committed_advance_artifacts_revalidate(self) -> None:
        root = Path("docs/depone-advance-one-step")
        evidence_dir = root / "evidence-run-next"
        advance_payload = json.loads(
            (root / "advance-decision.json").read_text(encoding="utf-8")
        )
        manifest = json.loads(
            (evidence_dir / "capture-manifest.json").read_text(encoding="utf-8")
        )
        receipt = json.loads(
            (evidence_dir / "runner-receipt.json").read_text(encoding="utf-8")
        )
        previous_manifest = json.loads(
            Path("docs/depone-run-receipt-frontdoor/capture-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        next_decision = evaluate_evidence_dir(
            evidence_dir,
            previous_capture=Path("docs/depone-run-receipt-frontdoor/capture-manifest.json"),
        )
        chain_verdict = verify_capture_chain([previous_manifest, manifest])

        self.assertEqual(advance_payload["decision"], "pass")
        self.assertEqual(advance_payload["executed_continuations"], 1)
        self.assertFalse(advance_payload["automation_boundary"]["full_scheduler"])
        self.assertEqual(validate_capture_manifest(manifest), [])
        self.assertEqual(validate_runner_receipt(receipt), [])
        self.assertEqual(
            manifest["prev_capture_hash"],
            canonical_hash(previous_manifest),
        )
        self.assertEqual(chain_verdict["decision"], "pass")
        self.assertNotIn("chain", advance_payload)
        self.assertNotIn("prev_capture_hash", advance_payload)
        self.assertEqual(next_decision["decision"], "continue")
        self.assertEqual(next_decision["blocking_reasons"], [])
        self.assertEqual(next_decision["assurance"], "A2-isolated-observed")
        self.assertTrue(next_decision["boundary"]["privilege_isolated"])


if __name__ == "__main__":
    unittest.main()
