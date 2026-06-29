from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from depone._resources import resource_text
from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.evidence_substrate import verify_capture_chain
from depone.cli._response import EXIT_FAILED, emit_error, emit_json


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    capture_paths = list(getattr(args, "capture", []) or [])
    if not capture_paths:
        emit_error(
            args,
            code="ERR_EVIDENCE_CHAIN_CAPTURE_REQUIRED",
            message="provide at least one --capture path",
        )

    try:
        manifests = [_read_json(Path(str(path))) for path in capture_paths]
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        emit_error(
            args,
            code="ERR_EVIDENCE_CHAIN_READ_CAPTURE",
            message=str(exc),
        )

    verdict = verify_capture_chain(manifests)
    out_path = Path(str(getattr(args, "out", "evidence-chain-verdict.json")))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if getattr(args, "json", False):
        emit_json(verdict)
    else:
        print(f"Evidence chain decision: {verdict['decision']}")
        print(f"Evidence chain verdict written to {out_path}")

    if str(verdict.get("decision")) == "blocked":
        sys.exit(EXIT_FAILED)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _self_test() -> None:
    capture = json.loads(
        resource_text(
            "fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json"
        )
    )
    step0 = deepcopy(capture)
    step0["prev_capture_hash"] = None
    step1 = deepcopy(capture)
    step1["prev_capture_hash"] = canonical_hash(step0)
    step2 = deepcopy(capture)
    step2["prev_capture_hash"] = canonical_hash(step1)
    chain = [step0, step1, step2]

    if verify_capture_chain(chain)["decision"] != "pass":
        raise AssertionError("intact three-step chain must pass")
    if verify_capture_chain([])["decision"] != "inconclusive":
        raise AssertionError("empty chain must be inconclusive")
    if verify_capture_chain([step0, step2])["decision"] != "blocked":
        raise AssertionError("dropped intermediate step must be blocked")

    tampered = deepcopy(chain)
    tampered[1]["allowed_touched_files"] = ["smuggled.py"]
    if verify_capture_chain(tampered)["decision"] != "blocked":
        raise AssertionError("tampered predecessor must be blocked")

    print("depone agent-fabric-evidence-chain --self-test: pass")
