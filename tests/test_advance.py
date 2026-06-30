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
from depone.cli.advance import advance_once


FIXTURE_ROOT = Path("docs/depone-run-receipt-frontdoor")


class AdvanceTests(unittest.TestCase):
    def test_continue_gate_runs_exactly_one_continuation_and_writes_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "advance.json"
            args = _args(evidence_dir=FIXTURE_ROOT, advance_out=out)
            continuation = {
                "command": "evidence-run",
                "decision": "pass",
                "out": str(Path(tmp) / "next-run"),
                "observe": {"decision": "pass"},
                "evidence_ingest": {"decision": "pass"},
                "verify": {"decision": "pass"},
            }

            with patch("depone.cli.advance.evidence_run.run_evidence_loop", return_value=continuation) as run_loop:
                payload = advance_once(args)

            self.assertEqual(run_loop.call_count, 1)
            self.assertEqual(payload["decision"], "pass")
            self.assertEqual(payload["executed_continuations"], 1)
            self.assertEqual(payload["gate"]["decision"], "continue")
            self.assertEqual(payload["gate"]["blocking_reasons"], [])
            recorded = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(recorded, payload)

    def test_blocked_gate_fails_closed_without_running_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "evidence"
            shutil.copytree(FIXTURE_ROOT, root)
            (root / "evidence-bundle.json").unlink()
            out = Path(tmp) / "advance.json"
            args = _args(evidence_dir=root, advance_out=out)

            with patch("depone.cli.advance.evidence_run.run_evidence_loop") as run_loop:
                payload = advance_once(args)

            run_loop.assert_not_called()
            self.assertEqual(payload["decision"], "blocked")
            self.assertEqual(payload["executed_continuations"], 0)
            self.assertIn("missing required artifact: evidence-bundle.json", payload["gate"]["blocking_reasons"])
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["decision"], "blocked")

    def test_cli_advance_alias_dispatches(self) -> None:
        seen = []

        def fake_run(args: object) -> None:
            seen.append(args)

        with patch.object(
            sys,
            "argv",
            [
                "depone",
                "advance",
                "--evidence-dir",
                str(FIXTURE_ROOT),
                "--advance-out",
                "advance.json",
                "--runner-sandbox",
                ".",
                "--source-fixture",
                "depone/fixtures/agent_fabric/reference_adapter_shell.json",
                "--json",
                "--",
                sys.executable,
                "-c",
                "print('ok')",
            ],
        ):
            with patch.object(depone_main.advance, "run", side_effect=fake_run):
                depone_main.main()

        self.assertEqual(len(seen), 1)
        self.assertEqual(getattr(seen[0], "command"), "advance")
        self.assertEqual(getattr(seen[0], "evidence_dir"), str(FIXTURE_ROOT))
        self.assertEqual(getattr(seen[0], "advance_out"), "advance.json")
        self.assertTrue(getattr(seen[0], "json"))

    def test_cli_blocked_gate_exits_failed_with_single_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "evidence"
            shutil.copytree(FIXTURE_ROOT, root)
            (root / "evidence-bundle.json").unlink()
            out = Path(tmp) / "advance.json"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "depone",
                    "advance",
                    "--evidence-dir",
                    str(root),
                    "--advance-out",
                    str(out),
                    "--runner-sandbox",
                    ".",
                    "--source-fixture",
                    "depone/fixtures/agent_fabric/reference_adapter_shell.json",
                    "--json",
                    "--",
                    sys.executable,
                    "-c",
                    "print('must not run')",
                ],
            ):
                with contextlib.redirect_stdout(stdout):
                    with self.assertRaises(SystemExit) as raised:
                        depone_main.main()

        self.assertEqual(raised.exception.code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["decision"], "blocked")
        self.assertEqual(payload["executed_continuations"], 0)


def _args(*, evidence_dir: Path, advance_out: Path) -> object:
    class Args:
        pass

    args = Args()
    args.evidence_dir = str(evidence_dir)
    args.previous_source_fixture = ""
    args.advance_out = str(advance_out)
    args.runner_sandbox = "."
    args.source_fixture = "depone/fixtures/agent_fabric/reference_adapter_shell.json"
    args.verification_command = [sys.executable, "-c", "print('ok')"]
    return args


if __name__ == "__main__":
    unittest.main()
