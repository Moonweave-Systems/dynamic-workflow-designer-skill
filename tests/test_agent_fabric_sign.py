from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from depone._resources import resource_text
from depone.agent_fabric.evidence_substrate import build_evidence_bundle
from depone.agent_fabric.sign import (
    DsseSigningError,
    _generate_ed25519_keypair,
    dsse_pae,
    openssl_error_record,
    openssl_path,
    sign_dsse_envelope,
    verify_dsse_envelope,
    verify_signed_bundle,
)


class AgentFabricSignTest(unittest.TestCase):
    def _bundle(self) -> dict[str, object]:
        capture = json.loads(
            resource_text(
                "fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json"
            )
        )
        return build_evidence_bundle(capture)

    def _require_openssl(self) -> None:
        if openssl_path() is None:
            self.skipTest("openssl executable is not on PATH")

    def test_dsse_pae_vector(self) -> None:
        self.assertEqual(dsse_pae("x", b"abc"), b"DSSEv1 1 x 3 abc")
        self.assertEqual(
            dsse_pae("application/vnd.in-toto+json", b"{}"),
            b"DSSEv1 28 application/vnd.in-toto+json 2 {}",
        )

    def test_sign_and_verify_with_ephemeral_ed25519_key(self) -> None:
        self._require_openssl()
        bundle = self._bundle()
        with tempfile.TemporaryDirectory() as temp_text:
            temp_dir = Path(temp_text)
            private_key, public_key = _generate_ed25519_keypair(temp_dir)
            signed = sign_dsse_envelope(
                bundle["dsse_envelope"],
                str(private_key),
                key_id="operator-test-key",
            )
            self.assertTrue(verify_dsse_envelope(signed, str(public_key)))
            self.assertEqual(len(signed["signatures"]), 1)

    def test_verify_signed_bundle_rejects_tampered_plaintext_statement(self) -> None:
        self._require_openssl()
        bundle = self._bundle()
        with tempfile.TemporaryDirectory() as temp_text:
            temp_dir = Path(temp_text)
            private_key, public_key = _generate_ed25519_keypair(temp_dir)
            signed_bundle = dict(bundle)
            signed_bundle["dsse_envelope"] = sign_dsse_envelope(
                bundle["dsse_envelope"], str(private_key), key_id="operator-test-key"
            )
            self.assertTrue(verify_signed_bundle(signed_bundle, str(public_key)))

            # Tampering the UNSIGNED plaintext statement must fail the bundle even
            # though the DSSE signature over the payload still verifies on its own.
            tampered = json.loads(json.dumps(signed_bundle))
            tampered["statement"]["predicateType"] = "https://evil.example/v1"
            self.assertTrue(
                verify_dsse_envelope(tampered["dsse_envelope"], str(public_key))
            )
            self.assertFalse(verify_signed_bundle(tampered, str(public_key)))

    def test_verify_signed_bundle_rejects_upgraded_top_level_claims(self) -> None:
        # The signature covers only the statement. Top-level fields that echo
        # signed content (assurance, overlapping boundary keys) must agree with
        # the signed predicate, or a forged upgrade would ride along with a
        # valid signature.
        self._require_openssl()
        bundle = self._bundle()
        with tempfile.TemporaryDirectory() as temp_text:
            temp_dir = Path(temp_text)
            private_key, public_key = _generate_ed25519_keypair(temp_dir)
            signed_bundle = dict(bundle)
            signed_bundle["dsse_envelope"] = sign_dsse_envelope(
                bundle["dsse_envelope"], str(private_key), key_id="operator-test-key"
            )
            self.assertTrue(verify_signed_bundle(signed_bundle, str(public_key)))

            upgraded = json.loads(json.dumps(signed_bundle))
            upgraded["assurance"] = "A3-keyless-signed-rekor"
            self.assertFalse(verify_signed_bundle(upgraded, str(public_key)))

            flipped = json.loads(json.dumps(signed_bundle))
            flipped["boundary"]["signed"] = True
            self.assertFalse(verify_signed_bundle(flipped, str(public_key)))

    def test_tamper_wrong_key_and_malformed_signatures_fail_closed(self) -> None:
        self._require_openssl()
        bundle = self._bundle()
        with tempfile.TemporaryDirectory() as temp_text:
            temp_dir = Path(temp_text)
            private_key, public_key = _generate_ed25519_keypair(temp_dir)
            wrong_dir = temp_dir / "wrong"
            wrong_dir.mkdir()
            _wrong_private, wrong_public = _generate_ed25519_keypair(wrong_dir)
            signed = sign_dsse_envelope(
                bundle["dsse_envelope"],
                str(private_key),
                key_id="operator-test-key",
            )

            tampered = dict(signed)
            tampered["payload"] = base64.b64encode(b'{"tampered":true}').decode("ascii")
            self.assertFalse(verify_dsse_envelope(tampered, str(public_key)))
            self.assertFalse(verify_dsse_envelope(signed, str(wrong_public)))

            empty = dict(signed)
            empty["signatures"] = []
            self.assertFalse(verify_dsse_envelope(empty, str(public_key)))
            wrong_alg = dict(signed)
            wrong_sig = dict(signed["signatures"][0])
            wrong_sig["alg"] = "RSA"
            wrong_alg["signatures"] = [wrong_sig]
            self.assertFalse(verify_dsse_envelope(wrong_alg, str(public_key)))
            malformed = dict(signed)
            malformed["signatures"] = [{"keyid": "operator-test-key", "sig": "!!"}]
            self.assertFalse(verify_dsse_envelope(malformed, str(public_key)))

    def test_openssl_absent_path_is_structured_and_never_verified(self) -> None:
        bundle = self._bundle()
        with mock.patch.dict(os.environ, {"PATH": ""}):
            self.assertIsNone(openssl_path())
            self.assertEqual(
                openssl_error_record()["code"],
                "ERR_OPENSSL_UNAVAILABLE",
            )
            with self.assertRaises(DsseSigningError) as raised:
                sign_dsse_envelope(
                    bundle["dsse_envelope"],
                    "missing-private-key.pem",
                    key_id="operator-test-key",
                )
            self.assertEqual(raised.exception.code, "ERR_OPENSSL_UNAVAILABLE")
            self.assertFalse(
                verify_dsse_envelope(
                    bundle["dsse_envelope"],
                    "missing-public-key.pem",
                )
            )

    def test_sign_and_verify_cli_round_trip(self) -> None:
        self._require_openssl()
        bundle = self._bundle()
        with tempfile.TemporaryDirectory() as temp_text:
            temp_dir = Path(temp_text)
            private_key, public_key = _generate_ed25519_keypair(temp_dir)
            bundle_path = temp_dir / "bundle.json"
            signed_path = temp_dir / "signed-bundle.json"
            bundle_path.write_text(
                json.dumps(bundle, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            sign_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "agent-fabric-sign",
                    "--bundle",
                    str(bundle_path),
                    "--private-key",
                    str(private_key),
                    "--key-id",
                    "operator-test-key",
                    "--out",
                    str(signed_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(sign_result.returncode, 0, sign_result.stderr)
            signed_bundle = json.loads(signed_path.read_text(encoding="utf-8"))
            self.assertEqual(
                signed_bundle["signing_status"],
                "signed-ed25519-operator-key",
            )
            verify_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "agent-fabric-verify-signature",
                    "--bundle",
                    str(signed_path),
                    "--public-key",
                    str(public_key),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(verify_result.returncode, 0, verify_result.stderr)
            self.assertIn("verified: true", verify_result.stdout)


if __name__ == "__main__":
    unittest.main()
