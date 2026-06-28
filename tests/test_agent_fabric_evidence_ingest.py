from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.evidence_substrate import (
    build_evidence_bundle,
    DIGEST_MODE_CANONICAL_JSON,
    ingest_external_evidence,
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
