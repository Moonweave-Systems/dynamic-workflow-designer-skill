from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.team_shell_lane_launch import (
    TEAM_SHELL_LANE_LAUNCH_KIND,
    TeamShellLaneLaunchError,
    run_shell_lane_command,
)


class AgentFabricTeamShellLaneLaunchTests(unittest.TestCase):
    def test_allowlisted_argv_command_writes_receipt_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = run_shell_lane_command(
                allowlist={
                    "commands": [
                        {
                            "id": "hello",
                            "argv": [sys.executable, "-c", "print('hello shell lane')"],
                        }
                    ]
                },
                command_id="hello",
                cwd=root,
                transcript_path=root / "transcript.json",
                timeout_seconds=30,
            )

            self.assertEqual(receipt["kind"], TEAM_SHELL_LANE_LAUNCH_KIND)
            self.assertEqual(receipt["decision"], "pass")
            self.assertEqual(receipt["exit_code"], 0)
            self.assertEqual(receipt["argv"][1:], ["-c", "print('hello shell lane')"])
            self.assertIn("stdout_sha256", receipt)
            self.assertIn("stderr_sha256", receipt)
            self.assertTrue(Path(str(receipt["transcript_path"])).exists())
            self.assertFalse(receipt["boundary"]["uses_shell"])
            self.assertTrue(receipt["boundary"]["uses_argv_allowlist"])
            self.assertFalse(receipt["boundary"]["allows_arbitrary_shell_string"])
            self.assertFalse(receipt["boundary"]["raises_assurance"])
            transcript = json.loads(Path(str(receipt["transcript_path"])).read_text(encoding="utf-8"))
            self.assertEqual(transcript["stdout_text"], "hello shell lane\n")

    def test_unknown_command_id_is_blocked_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(TeamShellLaneLaunchError) as raised:
                run_shell_lane_command(
                    allowlist={"commands": [{"id": "known", "argv": [sys.executable, "--version"]}]},
                    command_id="missing",
                    cwd=Path(tmp),
                    transcript_path=Path(tmp) / "transcript.json",
                )

            self.assertEqual(raised.exception.code, "ERR_TEAM_SHELL_LANE_COMMAND_NOT_ALLOWED")
            self.assertFalse((Path(tmp) / "transcript.json").exists())

    def test_agent_executables_are_blocked_even_when_allowlisted(self) -> None:
        for executable in ("codex", "claude", "claude-code", "opencode"):
            with self.subTest(executable=executable):
                with tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaises(TeamShellLaneLaunchError) as raised:
                        run_shell_lane_command(
                            allowlist={
                                "commands": [
                                    {
                                        "id": "agent",
                                        "argv": [executable, "--version"],
                                    }
                                ]
                            },
                            command_id="agent",
                            cwd=Path(tmp),
                            transcript_path=Path(tmp) / "transcript.json",
                        )

                    self.assertEqual(
                        raised.exception.code,
                        "ERR_TEAM_SHELL_LANE_AGENT_EXECUTABLE_BLOCKED",
                    )
                    self.assertFalse((Path(tmp) / "transcript.json").exists())


if __name__ == "__main__":
    unittest.main()
