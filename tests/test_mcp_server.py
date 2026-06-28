from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from depone._resources import resource_path, resource_text
from depone.agent_fabric.evidence_substrate import (
    DIGEST_MODE_CANONICAL_JSON,
    build_evidence_bundle,
)
from depone.mcp.server import (
    LATEST_PROTOCOL_VERSION,
    handle_line,
    handle_message,
)


def _result_text(response: dict[str, Any]) -> dict[str, Any]:
    result = response["result"]
    return json.loads(result["content"][0]["text"])


class McpServerTest(unittest.TestCase):
    def test_initialize_handshake(self) -> None:
        response = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": LATEST_PROTOCOL_VERSION},
            }
        )
        self.assertIsNotNone(response)
        result = response["result"]
        self.assertEqual(result["protocolVersion"], LATEST_PROTOCOL_VERSION)
        self.assertEqual(result["serverInfo"]["name"], "depone")
        self.assertIn("version", result["serverInfo"])
        self.assertEqual(result["capabilities"], {"tools": {}})

    def test_tools_list_schema(self) -> None:
        response = handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )
        self.assertIsNotNone(response)
        tools = response["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertEqual(
            names,
            {
                "depone_evidence_ingest",
                "depone_evidence_substrate",
                "depone_verify",
            },
        )
        for tool in tools:
            schema = tool["inputSchema"]
            self.assertEqual(schema["type"], "object")
            self.assertIsInstance(schema["properties"], dict)
            self.assertIsInstance(schema["required"], list)

    def test_evidence_ingest_pass_and_blocked(self) -> None:
        capture = json.loads(
            resource_text(
                "fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json"
            )
        )
        bundle = build_evidence_bundle(capture)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "capture-manifest.json"
            observer_path = root / "observer-capture.json"
            tampered_path = root / "tampered.json"
            manifest_path.write_text(json.dumps(capture), encoding="utf-8")
            observer_path.write_text(
                json.dumps(capture["observer_capture"]),
                encoding="utf-8",
            )
            tampered_path.write_text('{"tampered": true}\n', encoding="utf-8")
            with resource_path(
                "fixtures/agent_fabric/reference_adapter_shell.json"
            ) as source_path:
                base_arguments = {
                    "payload": bundle["dsse_envelope"],
                    "artifact_paths": {
                        "source_fixture": str(source_path),
                        "depone-capture-manifest": str(manifest_path),
                        "observer_capture": str(observer_path),
                    },
                    "artifact_digest_modes": {
                        "source_fixture": DIGEST_MODE_CANONICAL_JSON,
                        "depone-capture-manifest": DIGEST_MODE_CANONICAL_JSON,
                        "observer_capture": DIGEST_MODE_CANONICAL_JSON,
                    },
                    "otel_spans": bundle["otel_spans"],
                }
                pass_response = handle_message(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "depone_evidence_ingest",
                            "arguments": base_arguments,
                        },
                    }
                )
                self.assertIsNotNone(pass_response)
                self.assertFalse(pass_response["result"]["isError"])
                self.assertEqual(_result_text(pass_response)["decision"], "pass")

                tampered_arguments = dict(base_arguments)
                tampered_paths = dict(base_arguments["artifact_paths"])
                tampered_paths["source_fixture"] = str(tampered_path)
                tampered_arguments["artifact_paths"] = tampered_paths
                blocked_response = handle_message(
                    {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {
                            "name": "depone_evidence_ingest",
                            "arguments": tampered_arguments,
                        },
                    }
                )
                self.assertIsNotNone(blocked_response)
                self.assertFalse(blocked_response["result"]["isError"])
                self.assertEqual(_result_text(blocked_response)["decision"], "blocked")

    def test_malformed_and_unknown_method_return_errors(self) -> None:
        malformed = handle_line("{bad json")
        self.assertIsNotNone(malformed)
        self.assertEqual(malformed["error"]["code"], -32700)

        unknown = handle_message(
            {"jsonrpc": "2.0", "id": 5, "method": "depone/nope"}
        )
        self.assertIsNotNone(unknown)
        self.assertEqual(unknown["error"]["code"], -32601)

        after_error = handle_message(
            {"jsonrpc": "2.0", "id": 6, "method": "tools/list"}
        )
        self.assertIsNotNone(after_error)
        self.assertIn("tools", after_error["result"])


if __name__ == "__main__":
    unittest.main()
