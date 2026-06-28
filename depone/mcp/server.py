"""Stdlib-only MCP stdio server for Depone evidence tools."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import depone
from depone._resources import resource_path, resource_text
from depone.agent_fabric.evidence_substrate import (
    DIGEST_MODE_CANONICAL_JSON,
    build_evidence_bundle,
    ingest_external_evidence,
)
from depone.core.plan_schema import load_plan
from depone.verify.adapters import resolve
from depone.verify.engine import run_verification

JSONRPC_VERSION = "2.0"
LATEST_PROTOCOL_VERSION = "2025-11-25"
COMPATIBLE_PROTOCOL_VERSIONS = frozenset(
    {
        LATEST_PROTOCOL_VERSION,
        "2025-06-18",
        "2025-03-26",
        "2024-11-05",
    }
)

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _json_schema_object(
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _any_object(description: str) -> dict[str, Any]:
    return {"type": "object", "description": description}


def _string_map(description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "additionalProperties": {"type": "string"},
    }


def _tool_result(value: Any) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(value, sort_keys=True, ensure_ascii=False),
            }
        ],
        "isError": False,
    }


def _tool_failure(message: str) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {"decision": "blocked", "error": message},
                    sort_keys=True,
                    ensure_ascii=False,
                ),
            }
        ],
        "isError": True,
    }


def _require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _optional_object(value: Any, name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    return _require_object(value, name)


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _string_dict(value: Any, name: str) -> dict[str, str]:
    raw = _require_object(value, name)
    result: dict[str, str] = {}
    for key, item in raw.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"{name} must map strings to strings")
        result[key] = item
    return result


def depone_evidence_ingest(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = _require_object(arguments.get("payload"), "payload")
    artifact_paths = _string_dict(arguments.get("artifact_paths", {}), "artifact_paths")
    artifact_digest_modes = _optional_object(
        arguments.get("artifact_digest_modes"),
        "artifact_digest_modes",
    )
    if artifact_digest_modes is not None:
        artifact_digest_modes = _string_dict(
            artifact_digest_modes,
            "artifact_digest_modes",
        )
    otel_spans = arguments.get("otel_spans")
    if otel_spans is not None and not isinstance(otel_spans, list):
        raise ValueError("otel_spans must be an array when supplied")
    verdict = ingest_external_evidence(
        payload,
        artifact_paths,
        artifact_digest_modes=artifact_digest_modes,
        otel_spans=otel_spans,
    )
    return _tool_result(verdict)


def depone_evidence_substrate(arguments: dict[str, Any]) -> dict[str, Any]:
    capture_manifest = _require_object(
        arguments.get("capture_manifest"),
        "capture_manifest",
    )
    runner_receipt = _optional_object(arguments.get("runner_receipt"), "runner_receipt")
    bundle = build_evidence_bundle(capture_manifest, runner_receipt=runner_receipt)
    return _tool_result(bundle)


def depone_verify(arguments: dict[str, Any]) -> dict[str, Any]:
    plan_path = _require_string(arguments.get("plan_path"), "plan_path")
    evidence_dir = _require_string(arguments.get("evidence_dir"), "evidence_dir")
    adapter = arguments.get("adapter", "generic")
    adapter_name = _require_string(adapter, "adapter")
    plan = load_plan(plan_path)
    adapter_mod = importlib.import_module(resolve(adapter_name))
    evidence = adapter_mod.read_evidence(evidence_dir)
    report = run_verification(plan, evidence, framework=adapter_name)
    return _tool_result(asdict(report))


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "depone_evidence_ingest": {
        "description": (
            "Ingest an external in-toto Statement or DSSE envelope as untrusted "
            "evidence and return Depone's pass/inconclusive/blocked verdict."
        ),
        "inputSchema": _json_schema_object(
            {
                "payload": _any_object("in-toto Statement or DSSE envelope"),
                "artifact_paths": _string_map("Subject name to local artifact path"),
                "artifact_digest_modes": _string_map(
                    "Optional subject name to digest mode"
                ),
                "otel_spans": {
                    "type": "array",
                    "description": "Optional OTel span objects to validate",
                    "items": {"type": "object"},
                },
            },
            ["payload", "artifact_paths"],
        ),
        "handler": depone_evidence_ingest,
    },
    "depone_evidence_substrate": {
        "description": (
            "Emit the in-toto/DSSE plus OTel evidence bundle from a capture "
            "manifest."
        ),
        "inputSchema": _json_schema_object(
            {
                "capture_manifest": _any_object("Depone Agent Fabric capture manifest"),
                "runner_receipt": _any_object("Optional V126 runner receipt"),
            },
            ["capture_manifest"],
        ),
        "handler": depone_evidence_substrate,
    },
    "depone_verify": {
        "description": "Verify an execution-evidence directory against a Depone plan.",
        "inputSchema": _json_schema_object(
            {
                "plan_path": {"type": "string", "description": "Path to plan.json"},
                "evidence_dir": {
                    "type": "string",
                    "description": "Path to execution evidence directory",
                },
                "adapter": {
                    "type": "string",
                    "description": "Evidence adapter name",
                    "default": "generic",
                },
            },
            ["plan_path", "evidence_dir"],
        ),
        "handler": depone_verify,
    },
}


def list_tools() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for name, item in sorted(TOOL_REGISTRY.items()):
        tools.append(
            {
                "name": name,
                "description": item["description"],
                "inputSchema": item["inputSchema"],
            }
        )
    return tools


def _server_protocol_version(params: Any) -> str:
    if isinstance(params, dict):
        requested = params.get("protocolVersion")
        if requested in COMPATIBLE_PROTOCOL_VERSIONS:
            return str(requested)
    return LATEST_PROTOCOL_VERSION


def _result_response(message_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": message_id, "result": result}


def _error_response(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": message_id,
        "error": {"code": code, "message": message},
    }


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return _error_response(None, -32600, "Invalid Request")
    message_id = message.get("id")
    method = message.get("method")
    if not isinstance(method, str):
        return _error_response(message_id, -32600, "Invalid Request")
    params = message.get("params", {})
    if "id" not in message and method.startswith("notifications/"):
        return None

    try:
        if method == "initialize":
            return _result_response(
                message_id,
                {
                    "protocolVersion": _server_protocol_version(params),
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "depone",
                        "version": depone.__version__,
                    },
                },
            )
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return _result_response(message_id, {"tools": list_tools()})
        if method == "tools/call":
            result = _handle_tools_call(params)
            return _result_response(message_id, result)
        return _error_response(message_id, -32601, f"Method not found: {method}")
    except ValueError as exc:
        return _error_response(message_id, -32602, str(exc))
    except Exception as exc:
        print(f"depone mcp internal error: {exc}", file=sys.stderr)
        return _error_response(message_id, -32603, "Internal error")


def _handle_tools_call(params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ValueError("tools/call params must be an object")
    name = params.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("tools/call params.name must be a non-empty string")
    arguments = params.get("arguments", {})
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("tools/call params.arguments must be an object")
    item = TOOL_REGISTRY.get(name)
    if item is None:
        return _tool_failure(f"unknown tool: {name}")
    handler: ToolHandler = item["handler"]
    try:
        return handler(arguments)
    except Exception as exc:
        return _tool_failure(str(exc))


def serve_stdio() -> None:
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            response = _error_response(None, -32700, f"Parse error: {exc.msg}")
        else:
            response = handle_message(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


def _self_test() -> None:
    init = handle_message(
        {
            "jsonrpc": JSONRPC_VERSION,
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": LATEST_PROTOCOL_VERSION},
        }
    )
    if not init or init.get("result", {}).get("serverInfo", {}).get("name") != "depone":
        raise AssertionError("initialize response must include Depone serverInfo")
    tools = handle_message({"jsonrpc": JSONRPC_VERSION, "id": 2, "method": "tools/list"})
    tool_names = {
        tool.get("name")
        for tool in tools.get("result", {}).get("tools", [])
        if isinstance(tool, dict)
    }
    expected = {
        "depone_evidence_ingest",
        "depone_evidence_substrate",
        "depone_verify",
    }
    if tool_names != expected:
        raise AssertionError(f"unexpected MCP tool set: {sorted(tool_names)}")
    capture = json.loads(
        resource_text("fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json")
    )
    bundle = build_evidence_bundle(capture)
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        manifest_path = root / "capture-manifest.json"
        observer_path = root / "observer-capture.json"
        manifest_path.write_text(json.dumps(capture), encoding="utf-8")
        observer_path.write_text(
            json.dumps(capture["observer_capture"]),
            encoding="utf-8",
        )
        with resource_path(
            "fixtures/agent_fabric/reference_adapter_shell.json"
        ) as source:
            response = handle_message(
                {
                    "jsonrpc": JSONRPC_VERSION,
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "depone_evidence_ingest",
                        "arguments": {
                            "payload": bundle["dsse_envelope"],
                            "artifact_paths": {
                                "source_fixture": str(source),
                                "depone-capture-manifest": str(manifest_path),
                                "observer_capture": str(observer_path),
                            },
                            "artifact_digest_modes": {
                                "source_fixture": DIGEST_MODE_CANONICAL_JSON,
                                "depone-capture-manifest": DIGEST_MODE_CANONICAL_JSON,
                                "observer_capture": DIGEST_MODE_CANONICAL_JSON,
                            },
                            "otel_spans": bundle["otel_spans"],
                        },
                    },
                }
            )
    if response is None:
        raise AssertionError("tools/call must return a response")
    result = response.get("result", {})
    verdict = json.loads(result["content"][0]["text"])
    if result.get("isError") or verdict.get("decision") != "pass":
        raise AssertionError("evidence ingest self-test must pass")
    malformed = handle_line("{bad json")
    if not malformed or malformed.get("error", {}).get("code") != -32700:
        raise AssertionError("malformed input must return parse error")
    unknown = handle_message({"jsonrpc": JSONRPC_VERSION, "id": 4, "method": "missing"})
    if not unknown or unknown.get("error", {}).get("code") != -32601:
        raise AssertionError("unknown method must return method-not-found")
    print("depone mcp --self-test: pass")


def handle_line(line: str) -> dict[str, Any] | None:
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        return _error_response(None, -32700, f"Parse error: {exc.msg}")
    return handle_message(message)


def run(args: argparse.Namespace) -> None:
    if args.self_test:
        _self_test()
        return
    serve_stdio()
