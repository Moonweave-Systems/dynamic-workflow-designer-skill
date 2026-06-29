from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.evidence_substrate import (
    build_evidence_bundle,
    DIGEST_MODE_CANONICAL_JSON,
    ingest_external_evidence,
    ingest_signed_evidence_bundle,
)
from depone.agent_fabric.sign import (
    _generate_ed25519_keypair,
    openssl_path,
    sign_evidence_bundle,
)


class AgentFabricEvidenceIngestTests(unittest.TestCase):
    # Hermetic: build the bundle from a committed fixture and materialize the
    # manifest/observer subjects in a temp dir, so these tests never depend on
    # gitignored out/ artifacts and stay reproducible on a fresh clone.
    def setUp(self) -> None:
        self._capture = json.loads(
            Path(
                "depone/fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json"
            ).read_text(encoding="utf-8")
        )
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        (tmp / "capture-manifest.json").write_text(
            json.dumps(self._capture), encoding="utf-8"
        )
        (tmp / "observer-capture.json").write_text(
            json.dumps(self._capture["observer_capture"]), encoding="utf-8"
        )
        self._tmp_dir = tmp

    def _bundle(self) -> dict[str, object]:
        return build_evidence_bundle(self._capture)

    def _artifact_paths(self) -> dict[str, str]:
        return {
            "source_fixture": "depone/fixtures/agent_fabric/reference_adapter_shell.json",
            "depone-capture-manifest": str(self._tmp_dir / "capture-manifest.json"),
            "observer_capture": str(self._tmp_dir / "observer-capture.json"),
        }

    def _artifact_digest_modes(self) -> dict[str, str]:
        return {
            "source_fixture": DIGEST_MODE_CANONICAL_JSON,
            "depone-capture-manifest": DIGEST_MODE_CANONICAL_JSON,
            "observer_capture": DIGEST_MODE_CANONICAL_JSON,
        }

    def _external_dir(self) -> Path:
        return Path("depone/fixtures/agent_fabric/external")

    def _require_openssl(self) -> None:
        if openssl_path() is None:
            self.skipTest("openssl executable is not on PATH")

    def test_pass_when_all_real_bundle_subjects_match_disk(self) -> None:
        bundle = self._bundle()

        verdict = ingest_external_evidence(
            bundle["dsse_envelope"],
            self._artifact_paths(),
            artifact_digest_modes=self._artifact_digest_modes(),
            otel_spans=bundle["otel_spans"],
        )

        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["verified_subject_count"], 3)
        self.assertFalse(verdict["boundary"]["raises_assurance"])
        self.assertFalse(verdict["boundary"]["trusts_external_signature"])

    def test_inconclusive_when_subject_artifact_is_absent(self) -> None:
        bundle = self._bundle()

        verdict = ingest_external_evidence(
            bundle["dsse_envelope"],
            {"source_fixture": self._artifact_paths()["source_fixture"]},
            artifact_digest_modes={"source_fixture": DIGEST_MODE_CANONICAL_JSON},
        )

        self.assertEqual(verdict["decision"], "inconclusive")
        self.assertIn(
            "missing",
            {result["status"] for result in verdict["subject_results"]},
        )

    def test_blocked_when_present_artifact_hash_mismatches(self) -> None:
        bundle = self._bundle()
        artifact_paths = self._artifact_paths()

        with tempfile.TemporaryDirectory() as temp_dir:
            tampered_path = Path(temp_dir) / "reference_adapter_shell.json"
            tampered_path.write_text('{"tampered": true}\n', encoding="utf-8")
            artifact_paths["source_fixture"] = str(tampered_path)
            verdict = ingest_external_evidence(
                bundle["dsse_envelope"],
                artifact_paths,
                artifact_digest_modes=self._artifact_digest_modes(),
            )

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "mismatch",
            {result["status"] for result in verdict["subject_results"]},
        )

    def test_blocked_when_present_artifact_is_unreadable(self) -> None:
        # A present-but-corrupt artifact must not be reported as absent and
        # downgraded to inconclusive: that would let an artifact whose real
        # bytes would mismatch be softened by corrupting it on disk.
        bundle = self._bundle()
        artifact_paths = self._artifact_paths()

        with tempfile.TemporaryDirectory() as temp_dir:
            corrupt_path = Path(temp_dir) / "capture-manifest.json"
            corrupt_path.write_text("present but not valid json", encoding="utf-8")
            artifact_paths["depone-capture-manifest"] = str(corrupt_path)
            verdict = ingest_external_evidence(
                bundle["dsse_envelope"],
                artifact_paths,
                artifact_digest_modes=self._artifact_digest_modes(),
            )

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "unreadable",
            {result["status"] for result in verdict["subject_results"]},
        )
        self.assertTrue(
            any(
                "could not be hashed" in reason
                for reason in verdict["reasons"]
            )
        )

    def test_decoy_top_level_subject_cannot_downgrade_dsse_mismatch(self) -> None:
        # A DSSE envelope is verified through its decoded payload. A decoy
        # top-level _type/subject must not steer subject hashing away from the
        # real artifacts and downgrade a digest mismatch (blocked) into a
        # missing subject (inconclusive).
        bundle = self._bundle()
        artifact_paths = self._artifact_paths()

        with tempfile.TemporaryDirectory() as temp_dir:
            tampered_path = Path(temp_dir) / "reference_adapter_shell.json"
            tampered_path.write_text('{"tampered": true}\n', encoding="utf-8")
            artifact_paths["source_fixture"] = str(tampered_path)

            envelope = dict(bundle["dsse_envelope"])
            envelope["_type"] = "https://in-toto.io/Statement/v1"
            envelope["subject"] = []

            verdict = ingest_external_evidence(
                envelope,
                artifact_paths,
                artifact_digest_modes=self._artifact_digest_modes(),
            )

        self.assertEqual(verdict["decision"], "blocked")
        self.assertIn(
            "mismatch",
            {result["status"] for result in verdict["subject_results"]},
        )

    def test_blocked_when_dsse_claims_unverifiable_signatures(self) -> None:
        bundle = self._bundle()
        envelope = dict(bundle["dsse_envelope"])
        envelope["signatures"] = [{"keyid": "unknown", "sig": "claimed"}]

        verdict = ingest_external_evidence(
            envelope,
            self._artifact_paths(),
            artifact_digest_modes=self._artifact_digest_modes(),
        )

        self.assertEqual(verdict["decision"], "blocked")
        self.assertEqual(verdict["signing_status"], "unverifiable-signature")

    def test_signed_bundle_passes_when_public_key_and_subjects_verify(self) -> None:
        self._require_openssl()
        with tempfile.TemporaryDirectory() as temp_text:
            temp_dir = Path(temp_text)
            private_key, public_key = _generate_ed25519_keypair(temp_dir)
            signed_bundle = sign_evidence_bundle(
                self._bundle(),
                str(private_key),
                key_id="operator-test-key",
            )

            verdict = ingest_signed_evidence_bundle(
                signed_bundle,
                str(public_key),
                self._artifact_paths(),
                artifact_digest_modes=self._artifact_digest_modes(),
                otel_spans=signed_bundle["otel_spans"],
            )

        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(verdict["verified_subject_count"], 3)
        self.assertEqual(verdict["signing_status"], "signed-ed25519-operator-key")
        self.assertTrue(verdict["signature_verified"])
        self.assertFalse(verdict["boundary"]["raises_assurance"])
        self.assertTrue(verdict["boundary"]["trusts_external_signature"])

    def test_signed_bundle_blocks_when_public_key_does_not_verify(self) -> None:
        self._require_openssl()
        with tempfile.TemporaryDirectory() as temp_text:
            temp_dir = Path(temp_text)
            private_key, _public_key = _generate_ed25519_keypair(temp_dir)
            wrong_dir = temp_dir / "wrong"
            wrong_dir.mkdir()
            _wrong_private, wrong_public = _generate_ed25519_keypair(wrong_dir)
            signed_bundle = sign_evidence_bundle(
                self._bundle(),
                str(private_key),
                key_id="operator-test-key",
            )

            verdict = ingest_signed_evidence_bundle(
                signed_bundle,
                str(wrong_public),
                self._artifact_paths(),
                artifact_digest_modes=self._artifact_digest_modes(),
            )

        self.assertEqual(verdict["decision"], "blocked")
        self.assertEqual(verdict["signing_status"], "unverifiable-signature")
        self.assertFalse(verdict["signature_verified"])

    def test_signed_bundle_cli_round_trip_passes_with_public_key(self) -> None:
        self._require_openssl()
        with tempfile.TemporaryDirectory() as temp_text:
            temp_dir = Path(temp_text)
            private_key, public_key = _generate_ed25519_keypair(temp_dir)
            signed_bundle = sign_evidence_bundle(
                self._bundle(),
                str(private_key),
                key_id="operator-test-key",
            )
            signed_path = temp_dir / "signed-bundle.json"
            verdict_path = temp_dir / "verdict.json"
            signed_path.write_text(
                json.dumps(signed_bundle, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "depone",
                    "evidence-ingest",
                    "--signed-bundle",
                    str(signed_path),
                    "--public-key",
                    str(public_key),
                    "--artifact",
                    f"source_fixture={self._artifact_paths()['source_fixture']}:json",
                    "--artifact",
                    (
                        "depone-capture-manifest="
                        f"{self._artifact_paths()['depone-capture-manifest']}:json"
                    ),
                    "--artifact",
                    f"observer_capture={self._artifact_paths()['observer_capture']}:json",
                    "--out",
                    str(verdict_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            verdict = json.loads(verdict_path.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(verdict["decision"], "pass")
        self.assertTrue(verdict["signature_verified"])
        self.assertEqual(verdict["signing_status"], "signed-ed25519-operator-key")

    def test_cli_rejects_signed_bundle_without_public_key_before_loading(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "evidence-ingest",
                "--signed-bundle",
                "missing.json",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 3)
        self.assertEqual(
            json.loads(result.stdout)["error"]["code"],
            "ERR_EVIDENCE_INGEST_PUBLIC_KEY_REQUIRED",
        )

    def test_cli_rejects_public_key_without_signed_bundle_before_loading(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "depone",
                "evidence-ingest",
                "--dsse",
                "missing.json",
                "--public-key",
                "operator.pub.pem",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 3)
        self.assertEqual(
            json.loads(result.stdout)["error"]["code"],
            "ERR_EVIDENCE_INGEST_PUBLIC_KEY_WITHOUT_SIGNED_BUNDLE",
        )

    def test_blocked_when_dsse_is_malformed_without_raise(self) -> None:
        verdict = ingest_external_evidence(
            {
                "payloadType": "application/vnd.in-toto+json",
                "payload": "not base64",
                "signatures": [],
            },
            self._artifact_paths(),
            artifact_digest_modes=self._artifact_digest_modes(),
        )

        self.assertEqual(verdict["decision"], "blocked")
        # Verdicts blocked before a statement is parsed still carry the predicate
        # keys, so consumers can read them unconditionally.
        self.assertIsNone(verdict["predicate_type"])
        self.assertFalse(verdict["predicate_recognized"])

    def test_otel_structural_errors_do_not_upgrade_to_pass(self) -> None:
        bundle = self._bundle()

        verdict = ingest_external_evidence(
            bundle["dsse_envelope"],
            self._artifact_paths(),
            artifact_digest_modes=self._artifact_digest_modes(),
            otel_spans=[{"trace_id": "trace"}],
        )

        self.assertEqual(verdict["decision"], "blocked")
        self.assertTrue(verdict["otel_errors"])

    def test_foreign_real_statement_with_absent_artifact_is_inconclusive(self) -> None:
        statement = json.loads(
            (self._external_dir() / "external_intoto_statement_real.json").read_text(
                encoding="utf-8"
            )
        )

        verdict = ingest_external_evidence(statement, {})

        self.assertEqual(verdict["decision"], "inconclusive")
        self.assertFalse(verdict["predicate_recognized"])
        self.assertEqual(verdict["predicate_type"], "https://slsa.dev/provenance/v1.0")

    def test_foreign_slsa_shaped_statement_passes_with_raw_subject_digest(self) -> None:
        external_dir = self._external_dir()
        statement = json.loads(
            (external_dir / "external_slsa_statement_bound.json").read_text(
                encoding="utf-8"
            )
        )

        verdict = ingest_external_evidence(
            statement,
            {"external_artifact.bin": str(external_dir / "external_artifact.bin")},
        )

        self.assertEqual(verdict["decision"], "pass")
        self.assertFalse(verdict["predicate_recognized"])
        self.assertEqual(verdict["subject_results"][0]["status"], "verified")

    def test_foreign_slsa_shaped_statement_blocks_on_tampered_raw_bytes(self) -> None:
        external_dir = self._external_dir()
        statement = json.loads(
            (external_dir / "external_slsa_statement_bound.json").read_text(
                encoding="utf-8"
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            tampered_path = Path(temp_dir) / "external_artifact.bin"
            tampered_path.write_bytes(b"tampered\n")
            verdict = ingest_external_evidence(
                statement,
                {"external_artifact.bin": str(tampered_path)},
            )

        self.assertEqual(verdict["decision"], "blocked")
        self.assertEqual(verdict["subject_results"][0]["status"], "mismatch")

    def test_foreign_signed_dsse_is_blocked_before_signature_trust(self) -> None:
        envelope = json.loads(
            (self._external_dir() / "external_signed_dsse_nonempty.json").read_text(
                encoding="utf-8"
            )
        )

        verdict = ingest_external_evidence(envelope, {})

        self.assertEqual(verdict["decision"], "blocked")
        self.assertEqual(verdict["signing_status"], "unverifiable-signature")


if __name__ == "__main__":
    unittest.main()
