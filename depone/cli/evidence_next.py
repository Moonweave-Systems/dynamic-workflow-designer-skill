from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from depone.agent_fabric.capture_bridge import ASSURANCE_A2, validate_capture_manifest
from depone.agent_fabric.evidence_substrate import (
    DIGEST_MODE_CANONICAL_JSON,
    ingest_external_evidence,
    validate_statement_for_capture,
)
from depone.agent_fabric.paired_run import validate_runner_receipt
from depone.cli._response import EXIT_FAILED, emit_error, emit_result

REQUIRED_ARTIFACTS = (
    "capture-manifest.json",
    "observer-capture.json",
    "evidence-bundle.json",
)


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    evidence_dir = Path(str(getattr(args, "evidence_dir", "") or ""))
    if not str(evidence_dir):
        emit_error(
            args,
            code="ERR_EVIDENCE_NEXT_INPUT_REQUIRED",
            message="--evidence-dir is required",
        )
    try:
        source_fixture_arg = str(getattr(args, "source_fixture", "") or "")
        decision = evaluate_evidence_dir(
            evidence_dir,
            source_fixture=Path(source_fixture_arg) if source_fixture_arg else None,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit_error(
            args,
            code="ERR_EVIDENCE_NEXT_LOAD_FAILED",
            message=str(exc),
        )

    out_arg = str(getattr(args, "out", "") or "")
    if out_arg:
        out_path = Path(out_arg)
        decision["out"] = str(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(decision, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    emit_result(
        args,
        decision,
        human=[
            f"Evidence next decision: {decision['decision']}",
            f"Next action: {decision['next_action']}",
            f"Assurance: {decision.get('assurance')}",
        ],
    )
    if decision["decision"] == "blocked":
        sys.exit(EXIT_FAILED)


def evaluate_evidence_dir(
    evidence_dir: Path,
    *,
    source_fixture: Path | None = None,
) -> dict[str, Any]:
    """Re-validate an evidence-run directory and recommend the next safe action."""

    root = evidence_dir.resolve(strict=False)
    missing = [
        name for name in REQUIRED_ARTIFACTS if not (root / name).is_file()
    ]
    capture = _read_optional_json_object(root / "capture-manifest.json") or {}
    bundle = _read_optional_json_object(root / "evidence-bundle.json") or {}
    runner_receipt = _read_optional_json_object(root / "runner-receipt.json")
    recorded_ingest = _read_optional_json_object(root / "ingest-verdict.json")

    capture_errors = validate_capture_manifest(capture) if capture else []
    runner_errors = (
        validate_runner_receipt(runner_receipt)
        if isinstance(runner_receipt, dict)
        else []
    )
    statement = bundle.get("statement") if isinstance(bundle.get("statement"), dict) else {}
    statement_errors = validate_statement_for_capture(
        statement,
        capture,
        runner_receipt=runner_receipt if isinstance(runner_receipt, dict) else None,
    )

    artifact_paths = {
        "depone-capture-manifest": str(root / "capture-manifest.json"),
        "source_fixture": _source_fixture_path(capture, source_fixture),
        "observer_capture": str(root / "observer-capture.json"),
    }
    artifact_digest_modes = {
        "depone-capture-manifest": DIGEST_MODE_CANONICAL_JSON,
        "source_fixture": DIGEST_MODE_CANONICAL_JSON,
        "observer_capture": DIGEST_MODE_CANONICAL_JSON,
    }
    if (root / "runner-receipt.json").is_file():
        artifact_paths["runner_receipt"] = str(root / "runner-receipt.json")
        artifact_digest_modes["runner_receipt"] = DIGEST_MODE_CANONICAL_JSON

    if "capture-manifest.json" in missing or "evidence-bundle.json" in missing:
        ingest = {
            "decision": "blocked",
            "reasons": [f"missing required artifact: {name}" for name in missing],
            "subject_results": [],
            "verified_subject_count": 0,
        }
    else:
        envelope = (
            bundle.get("dsse_envelope")
            if isinstance(bundle.get("dsse_envelope"), dict)
            else {}
        )
        ingest = ingest_external_evidence(
            envelope,
            artifact_paths,
            artifact_digest_modes=artifact_digest_modes,
            otel_spans=bundle.get("otel_spans"),
        )

    blocking_reasons = _blocking_reasons(
        missing=missing,
        capture_errors=capture_errors,
        runner_errors=runner_errors,
        statement_errors=statement_errors,
        ingest_decision=str(ingest.get("decision", "blocked")),
    )
    decision = "blocked" if blocking_reasons else "continue"
    next_action = (
        "repair_evidence_artifacts"
        if decision == "blocked"
        else "run_next_evidence_slice"
    )
    subject_results = ingest.get("subject_results", [])
    verified_subject_count = ingest.get("verified_subject_count", 0)
    return {
        "command": "evidence-next",
        "schema_version": "1.0",
        "evidence_dir": str(root),
        "decision": decision,
        "next_action": next_action,
        "assurance": capture.get("assurance"),
        "capture": {
            "path": str(root / "capture-manifest.json"),
            "errors": capture_errors,
        },
        "runner_receipt": {
            "path": str(root / "runner-receipt.json")
            if (root / "runner-receipt.json").is_file()
            else None,
            "errors": runner_errors,
        },
        "evidence_bundle": {
            "path": str(root / "evidence-bundle.json"),
            "statement_errors": statement_errors,
        },
        "evidence_ingest": {
            "decision": ingest.get("decision"),
            "reasons": ingest.get("reasons", []),
            "subject_results": subject_results,
            "verified_subject_count": verified_subject_count,
        },
        "recorded_ingest": {
            "path": str(root / "ingest-verdict.json")
            if (root / "ingest-verdict.json").is_file()
            else None,
            "decision": recorded_ingest.get("decision")
            if isinstance(recorded_ingest, dict)
            else None,
        },
        "verified_artifacts": {
            "subject_count": len(subject_results)
            if isinstance(subject_results, list)
            else 0,
            "verified_subject_count": verified_subject_count,
        },
        "boundary": {
            "privilege_isolated": capture.get("assurance") == ASSURANCE_A2
            and isinstance(capture.get("isolation"), dict)
            and capture.get("isolation", {}).get("boundary") is True,
            "isolation": capture.get("isolation"),
        },
        "blocking_reasons": blocking_reasons,
        "automation_boundary": {
            "executes_next_action": False,
            "requires_operator_or_loop_to_execute": True,
        },
    }


def _blocking_reasons(
    *,
    missing: list[str],
    capture_errors: list[str],
    runner_errors: list[str],
    statement_errors: list[str],
    ingest_decision: str,
) -> list[str]:
    reasons: list[str] = []
    for name in missing:
        reasons.append(f"missing required artifact: {name}")
    if capture_errors:
        reasons.append("capture-manifest.json failed validation")
    if runner_errors:
        reasons.append("runner-receipt.json failed validation")
    if statement_errors:
        reasons.append("evidence-bundle.json statement failed validation")
    if ingest_decision != "pass":
        reasons.append(f"evidence ingest decision is {ingest_decision}")
    return reasons


def _source_fixture_path(capture: dict[str, Any], source_fixture: Path | None) -> str:
    if source_fixture is not None:
        return str(source_fixture)
    # evidence-run bundles commit the full fixture into the manifest, but the
    # portable statement subjects the source fixture separately. Keep the current
    # reference fixture as the default for committed dogfood artifacts; callers
    # can pass --source-fixture for other captures.
    if isinstance(capture.get("fixture"), dict):
        return "depone/fixtures/agent_fabric/reference_adapter_shell.json"
    return ""


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _read_optional_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return _read_json_object(path)


def _self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "evidence"
        root.mkdir()
        source = Path("docs/depone-run-receipt-frontdoor")
        for name in (
            "capture-manifest.json",
            "observer-capture.json",
            "runner-receipt.json",
            "evidence-bundle.json",
            "ingest-verdict.json",
        ):
            (root / name).write_text(
                (source / name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        decision = evaluate_evidence_dir(root)
        if decision["decision"] != "continue":
            raise AssertionError(f"expected continue, got {decision}")
