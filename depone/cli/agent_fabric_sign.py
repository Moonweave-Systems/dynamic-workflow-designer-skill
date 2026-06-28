from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from depone.agent_fabric.sign import DsseSigningError, sign_dsse_envelope
from depone.agent_fabric.sign import _self_test as sign_self_test

SIGNING_STATUS = "signed-ed25519-operator-key"


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        sign_self_test()
        return

    bundle_path = str(getattr(args, "bundle", "") or "")
    private_key_path = str(getattr(args, "private_key", "") or "")
    key_id = str(getattr(args, "key_id", "") or "")
    out_path = str(getattr(args, "out", "") or "")
    if not bundle_path or not private_key_path or not key_id or not out_path:
        print(
            "Usage: depone agent-fabric-sign --bundle <bundle.json> "
            "--private-key <pem> --key-id <label> --out <signed-bundle.json>",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        bundle = _read_json(Path(bundle_path))
        envelope = bundle.get("dsse_envelope")
        if not isinstance(envelope, dict):
            raise DsseSigningError("ERR_DSSE_SIGN_FAILED", "bundle missing dsse_envelope")
        signed_bundle = dict(bundle)
        signed_bundle["dsse_envelope"] = sign_dsse_envelope(
            envelope,
            private_key_path,
            key_id=key_id,
        )
        signed_bundle["signing_status"] = SIGNING_STATUS
        signed_bundle["signature_boundary"] = {
            "scheme": "DSSE-Ed25519-openssl-cli",
            "operator_key": True,
            "public_verifiable": True,
            "keyless_identity": False,
            "transparency_logged": False,
            "note": (
                "Trust is rooted in the operator-held key and distributed public "
                "key; this is not Fulcio keyless identity or Rekor logging."
            ),
        }
        out_abs = Path(out_path).expanduser().resolve(strict=False)
        out_abs.parent.mkdir(parents=True, exist_ok=True)
        out_abs.write_text(
            json.dumps(signed_bundle, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except DsseSigningError as exc:
        print(json.dumps({"error": exc.to_record()}, sort_keys=True), file=sys.stderr)
        sys.exit(1)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "error": {
                        "code": "ERR_DSSE_SIGN_FAILED",
                        "message": str(exc),
                    }
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Signed evidence bundle written to {out_path}")
    print(f"  Signing status: {signed_bundle['signing_status']}")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value
