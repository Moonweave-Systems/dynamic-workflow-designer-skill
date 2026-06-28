from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from depone.agent_fabric.sign import _self_test as sign_self_test
from depone.agent_fabric.sign import verify_dsse_envelope


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        sign_self_test()
        print("depone agent-fabric-verify-signature --self-test: pass")
        return

    bundle_path = str(getattr(args, "bundle", "") or "")
    public_key_path = str(getattr(args, "public_key", "") or "")
    if not bundle_path or not public_key_path:
        print(
            "Usage: depone agent-fabric-verify-signature --bundle <signed.json> "
            "--public-key <pem>",
            file=sys.stderr,
        )
        sys.exit(1)

    verified = False
    try:
        bundle = _read_json(Path(bundle_path))
        envelope = bundle.get("dsse_envelope")
        if isinstance(envelope, dict):
            verified = verify_dsse_envelope(envelope, public_key_path)
    except Exception:
        verified = False

    print(f"verified: {str(verified).lower()}")
    if not verified:
        sys.exit(1)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value
