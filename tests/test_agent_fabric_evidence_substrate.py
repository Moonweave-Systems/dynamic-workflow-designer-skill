from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.evidence_substrate import (
    build_evidence_bundle,
    decode_dsse_payload,
    DIGEST_MODE_CANONICAL_JSON,
    evaluate_external_statement_subjects,
    ingest_external_evidence,
    validate_statement_for_capture,
)


class AgentFabricEvidenceSubstrateTests(unittest.TestCase):
    def _capture(self) -> dict[str, object]:
        return json.loads(
            Path(
                "depone/fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json"
            ).read_text(encoding="utf-8")
        )

    def test_bundle_round_trips_unsigned_statement_and_spans(self) -> None:
        capture = self._capture()
        bundle = build_evidence_bundle(capture)

        self.assertEqual(bundle["signing_status"], "unsigned-content-addressed")
        self.assertEqual(bundle["dsse_envelope"]["signatures"], [])
        self.assertEqual(decode_dsse_payload(bundle["dsse_envelope"]), bundle["statement"])
        self.assertEqual(validate_statement_for_capture(bundle["statement"], capture), [])

        operations = {
            span["attributes"]["gen_ai.operation.name"]
            for span in bundle["otel_spans"]
        }
        self.assertIn("invoke_agent", operations)
        self.assertIn("execute_tool", operations)
        usage_keys = [
            key
            for span in bundle["otel_spans"]
            for key in span["attributes"]
            if key.startswith("gen_ai.usage.")
        ]
        self.assertEqual(usage_keys, [])

    def test_tampered_statement_and_external_mismatch_do_not_pass(self) -> None:
        capture = self._capture()
        statement = build_evidence_bundle(capture)["statement"]
        tampered = deepcopy(statement)
        tampered["subject"][0]["digest"]["sha256"] = "0" * 64

        self.assertTrue(validate_statement_for_capture(tampered, capture))
        external = evaluate_external_statement_subjects(
            tampered,
            {"depone-capture-manifest": canonical_hash(capture)},
        )
        self.assertEqual(external["decision"], "blocked")

    def test_bundle_ingest_passes_with_rehashed_disk_artifacts(self) -> None:
        # Hermetic: build the bundle from the committed fixture and re-hash its
        # subjects from artifacts written to a temp dir. No dependency on
        # gitignored out/ artifacts, so this is reproducible on a fresh clone.
        capture = self._capture()
        bundle = build_evidence_bundle(capture)

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "capture-manifest.json"
            observer_path = Path(temp_dir) / "observer-capture.json"
            manifest_path.write_text(json.dumps(capture), encoding="utf-8")
            observer_path.write_text(
                json.dumps(capture["observer_capture"]), encoding="utf-8"
            )

            verdict = ingest_external_evidence(
                bundle["dsse_envelope"],
                {
                    "source_fixture": "depone/fixtures/agent_fabric/reference_adapter_shell.json",
                    "depone-capture-manifest": str(manifest_path),
                    "observer_capture": str(observer_path),
                },
                artifact_digest_modes={
                    "source_fixture": DIGEST_MODE_CANONICAL_JSON,
                    "depone-capture-manifest": DIGEST_MODE_CANONICAL_JSON,
                    "observer_capture": DIGEST_MODE_CANONICAL_JSON,
                },
                otel_spans=bundle["otel_spans"],
            )

        self.assertEqual(verdict["decision"], "pass")
        self.assertEqual(
            {result["status"] for result in verdict["subject_results"]},
            {"verified"},
        )


if __name__ == "__main__":
    unittest.main()
