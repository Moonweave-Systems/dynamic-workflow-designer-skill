from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.team_shell_lane_launch import (
    TEAM_SHELL_LANE_LAUNCH_KIND,
    TeamShellLaneLaunchError,
    _canonical_hash,
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
            self.assertIsInstance(receipt["agent_contract_hash"], str)
            self.assertEqual(receipt["agent_contract_hash"], receipt["agent_contract"]["resolved_contract_hash"])
            self.assertEqual(receipt["agent_contract"]["role_id"], "operator")
            self.assertEqual(
                receipt["agent_contract"]["contract_path"],
                "packaging/depone-agent-operating-contract.json",
            )
            self.assertTrue(Path(str(receipt["transcript_path"])).exists())
            self.assertFalse(receipt["boundary"]["uses_shell"])
            self.assertTrue(receipt["boundary"]["uses_argv_allowlist"])
            self.assertFalse(receipt["boundary"]["allows_arbitrary_shell_string"])
            self.assertFalse(receipt["boundary"]["raises_assurance"])
            transcript = json.loads(Path(str(receipt["transcript_path"])).read_text(encoding="utf-8"))
            self.assertEqual(transcript["stdout_text"], "hello shell lane\n")

    def test_agent_contract_hash_binds_common_contract_and_v22_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = {
                "contract_id": "test-contract",
                "contract_version": "0.1.0",
                "clauses": [
                    {
                        "id": "common.fail_closed",
                        "level": "must",
                        "validation_note": "reject malformed contract bindings",
                    }
                ],
            }
            role = {
                "id": "worker",
                "purpose": "test worker",
                "allowed_tools": ["read"],
                "output_schema": "worker-result-v1",
                "evidence_obligations": ["files", "commands", "tests"],
                "trust_boundary": "untrusted until reviewed",
            }
            contract_path = root / "contract.json"
            registry_path = root / "roles.json"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            registry_path.write_text(json.dumps({"roles": [role]}), encoding="utf-8")

            receipt = run_shell_lane_command(
                allowlist={
                    "commands": [
                        {
                            "id": "hello",
                            "argv": [sys.executable, "-c", "print('contract hash')"],
                        }
                    ]
                },
                command_id="hello",
                cwd=root,
                transcript_path=root / "transcript.json",
                timeout_seconds=30,
                agent_role_id="worker",
                agent_contract_path=contract_path,
                role_registry_path=registry_path,
            )

            resolved = {"common_contract": contract, "v22_role": role}
            self.assertEqual(receipt["agent_contract_hash"], _canonical_hash(resolved))
            self.assertEqual(receipt["agent_contract"]["common_contract_hash"], _canonical_hash(contract))
            self.assertEqual(receipt["agent_contract"]["role_hash"], _canonical_hash(role))
            self.assertEqual(receipt["agent_contract"]["clause_ids"], ["common.fail_closed"])

    def test_invalid_agent_contract_is_blocked_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract_path = root / "contract.json"
            registry_path = root / "roles.json"
            contract_path.write_text(json.dumps({"contract_id": "missing clauses"}), encoding="utf-8")
            registry_path.write_text(
                json.dumps(
                    {
                        "roles": [
                            {
                                "id": "worker",
                                "purpose": "test worker",
                                "allowed_tools": ["read"],
                                "output_schema": "worker-result-v1",
                                "evidence_obligations": ["files", "commands", "tests"],
                                "trust_boundary": "untrusted until reviewed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(TeamShellLaneLaunchError) as raised:
                run_shell_lane_command(
                    allowlist={"commands": [{"id": "hello", "argv": [sys.executable, "--version"]}]},
                    command_id="hello",
                    cwd=root,
                    transcript_path=root / "transcript.json",
                    agent_role_id="worker",
                    agent_contract_path=contract_path,
                    role_registry_path=registry_path,
                )

            self.assertEqual(raised.exception.code, "ERR_TEAM_SHELL_LANE_AGENT_CONTRACT_INVALID")
            self.assertFalse((root / "transcript.json").exists())

    def test_unknown_agent_role_is_blocked_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract_path = root / "contract.json"
            registry_path = root / "roles.json"
            contract_path.write_text(
                json.dumps(
                    {
                        "contract_id": "test-contract",
                        "contract_version": "0.1.0",
                        "clauses": [
                            {
                                "id": "common.fail_closed",
                                "level": "must",
                                "validation_note": "reject malformed contract bindings",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            registry_path.write_text(
                json.dumps(
                    {
                        "roles": [
                            {
                                "id": "operator",
                                "purpose": "test operator",
                                "allowed_tools": ["read"],
                                "output_schema": "operator-result-v1",
                                "evidence_obligations": ["files", "commands", "tests"],
                                "trust_boundary": "operator cannot bypass gates",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(TeamShellLaneLaunchError) as raised:
                run_shell_lane_command(
                    allowlist={"commands": [{"id": "hello", "argv": [sys.executable, "--version"]}]},
                    command_id="hello",
                    cwd=root,
                    transcript_path=root / "transcript.json",
                    agent_role_id="worker",
                    agent_contract_path=contract_path,
                    role_registry_path=registry_path,
                )

            self.assertEqual(raised.exception.code, "ERR_TEAM_SHELL_LANE_AGENT_ROLE_INVALID")
            self.assertFalse((root / "transcript.json").exists())

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
