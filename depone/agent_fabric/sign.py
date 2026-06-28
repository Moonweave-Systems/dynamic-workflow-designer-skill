"""Ed25519 DSSE signing helpers backed by the openssl CLI.

This is an operator-key signing step. It is public-key verifiable relative to
trust in the distributed public key, but it is not keyless identity, not
Fulcio-backed, and not transparency-logged in Rekor. Sigstore keyless signing
remains deferred.
"""

from __future__ import annotations

import base64
import binascii
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from depone._resources import resource_text
from depone.agent_fabric.evidence_substrate import build_evidence_bundle

ERR_OPENSSL_UNAVAILABLE = "ERR_OPENSSL_UNAVAILABLE"
ERR_DSSE_SIGN_FAILED = "ERR_DSSE_SIGN_FAILED"


class DsseSigningError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_record(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def openssl_error_record() -> dict[str, str]:
    return {
        "code": ERR_OPENSSL_UNAVAILABLE,
        "message": "openssl executable not found on PATH",
    }


def openssl_path() -> str | None:
    return shutil.which("openssl")


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    """Return DSSE v1 Pre-Authentication Encoding bytes."""

    return (
        b"DSSEv1 "
        + str(len(payload_type)).encode("ascii")
        + b" "
        + payload_type.encode("utf-8")
        + b" "
        + str(len(payload)).encode("ascii")
        + b" "
        + payload
    )


def sign_dsse_envelope(
    envelope: dict[str, Any],
    private_key_path: str,
    *,
    key_id: str,
) -> dict[str, Any]:
    """Return a copy of a DSSE envelope signed by an operator-held Ed25519 key."""

    openssl = openssl_path()
    if openssl is None:
        record = openssl_error_record()
        raise DsseSigningError(record["code"], record["message"])
    if not isinstance(key_id, str) or not key_id:
        raise DsseSigningError(ERR_DSSE_SIGN_FAILED, "key_id must be non-empty")
    payload_type, payload = _decode_envelope_payload(envelope)
    pae = dsse_pae(payload_type, payload)

    with tempfile.TemporaryDirectory() as temp_dir:
        pae_path = Path(temp_dir) / "payload.pae"
        sig_path = Path(temp_dir) / "payload.sig"
        pae_path.write_bytes(pae)
        result = subprocess.run(
            [
                openssl,
                "pkeyutl",
                "-sign",
                "-inkey",
                private_key_path,
                "-rawin",
                "-in",
                str(pae_path),
                "-out",
                str(sig_path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0 or not sig_path.exists():
            message = (result.stderr or result.stdout or "openssl signing failed").strip()
            raise DsseSigningError(ERR_DSSE_SIGN_FAILED, message)
        signature = sig_path.read_bytes()

    signed = dict(envelope)
    signed["signatures"] = [
        {
            "keyid": key_id,
            "sig": base64.b64encode(signature).decode("ascii"),
        }
    ]
    return signed


def verify_dsse_envelope(envelope: dict[str, Any], public_key_path: str) -> bool:
    """Verify a DSSE envelope with openssl, returning False on any failure."""

    openssl = openssl_path()
    if openssl is None:
        return False
    try:
        payload_type, payload = _decode_envelope_payload(envelope)
        signatures = envelope.get("signatures")
        if not isinstance(signatures, list) or not signatures:
            return False
        pae = dsse_pae(payload_type, payload)
    except Exception:
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        pae_path = Path(temp_dir) / "payload.pae"
        sig_path = Path(temp_dir) / "payload.sig"
        pae_path.write_bytes(pae)
        for signature_record in signatures:
            try:
                if not isinstance(signature_record, dict):
                    continue
                if signature_record.get("alg") not in (None, "Ed25519"):
                    continue
                sig_text = signature_record.get("sig")
                if not isinstance(sig_text, str):
                    continue
                sig_path.write_bytes(base64.b64decode(sig_text.encode("ascii"), validate=True))
                result = subprocess.run(
                    [
                        openssl,
                        "pkeyutl",
                        "-verify",
                        "-pubin",
                        "-inkey",
                        public_key_path,
                        "-rawin",
                        "-in",
                        str(pae_path),
                        "-sigfile",
                        str(sig_path),
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0:
                    return True
            except Exception:
                continue
    return False


def _decode_envelope_payload(envelope: dict[str, Any]) -> tuple[str, bytes]:
    if not isinstance(envelope, dict):
        raise DsseSigningError(ERR_DSSE_SIGN_FAILED, "DSSE envelope must be an object")
    payload_type = envelope.get("payloadType")
    payload = envelope.get("payload")
    if not isinstance(payload_type, str) or not payload_type:
        raise DsseSigningError(ERR_DSSE_SIGN_FAILED, "payloadType must be non-empty")
    if not isinstance(payload, str):
        raise DsseSigningError(ERR_DSSE_SIGN_FAILED, "payload must be base64 text")
    try:
        return payload_type, base64.b64decode(payload.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise DsseSigningError(ERR_DSSE_SIGN_FAILED, "payload is not valid base64") from exc


def _generate_ed25519_keypair(temp_dir: Path) -> tuple[Path, Path]:
    openssl = openssl_path()
    if openssl is None:
        record = openssl_error_record()
        raise DsseSigningError(record["code"], record["message"])
    private_key = temp_dir / "operator-ed25519.pem"
    public_key = temp_dir / "operator-ed25519.pub.pem"
    for command in (
        [openssl, "genpkey", "-algorithm", "Ed25519", "-out", str(private_key)],
        [openssl, "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
    ):
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "openssl keygen failed").strip()
            raise DsseSigningError(ERR_DSSE_SIGN_FAILED, message)
    return private_key, public_key


def _self_test() -> None:
    if openssl_path() is None:
        if openssl_error_record()["code"] != ERR_OPENSSL_UNAVAILABLE:
            raise AssertionError("missing openssl must return a structured error")
        print("depone agent-fabric-sign --self-test: pass (openssl unavailable)")
        return
    if dsse_pae("x", b"abc") != b"DSSEv1 1 x 3 abc":
        raise AssertionError("DSSE PAE vector mismatch")
    capture = json.loads(
        resource_text("fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json")
    )
    bundle = build_evidence_bundle(capture)
    with tempfile.TemporaryDirectory() as temp_text:
        temp_dir = Path(temp_text)
        private_key, public_key = _generate_ed25519_keypair(temp_dir)
        signed = sign_dsse_envelope(
            bundle["dsse_envelope"],
            str(private_key),
            key_id="operator-test-key",
        )
        if not verify_dsse_envelope(signed, str(public_key)):
            raise AssertionError("signed envelope should verify")
        tampered = dict(signed)
        tampered_payload = json.dumps({"tampered": True}, sort_keys=True).encode("utf-8")
        tampered["payload"] = base64.b64encode(tampered_payload).decode("ascii")
        if verify_dsse_envelope(tampered, str(public_key)):
            raise AssertionError("tampered payload should not verify")
        wrong_dir = temp_dir / "wrong"
        wrong_dir.mkdir()
        wrong_private, wrong_public = _generate_ed25519_keypair(wrong_dir)
        _ = wrong_private
        if verify_dsse_envelope(signed, str(wrong_public)):
            raise AssertionError("wrong public key should not verify")
    print("depone agent-fabric-sign --self-test: pass")
