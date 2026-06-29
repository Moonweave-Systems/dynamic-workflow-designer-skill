"""V128 in-toto/DSSE and OTel GenAI evidence substrate helpers.

The substrate is a derived view over existing Depone evidence. It does not
upgrade assurance and it does not claim signatures when ``signatures`` is empty.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from depone._resources import resource_text
from depone.agent_fabric.capture_bridge import validate_capture_manifest
from depone.agent_fabric.claim_gate import canonical_hash

INTOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
INTOTO_STATEMENT_TYPE_V01 = "https://in-toto.io/Statement/v0.1"
DEPONE_PREDICATE_TYPE = "https://depone.dev/attestations/evidence/v1"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
SPAN_SCHEMA_VERSION = "1.0"
DIGEST_MODE_RAW = "raw"
DIGEST_MODE_CANONICAL_JSON = "canonical-json"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _span_id(seed: str, offset: int = 0) -> str:
    digest = canonical_hash({"seed": seed, "offset": offset})
    return digest[:16]


def _trace_id(seed: str) -> str:
    return canonical_hash({"trace": seed})[:32]


def build_intoto_statement_from_capture(
    capture_manifest: dict[str, Any],
    *,
    name: str = "depone-capture-manifest",
) -> dict[str, Any]:
    """Serialize an existing capture manifest as an in-toto Statement."""

    validation_errors = validate_capture_manifest(capture_manifest)
    observer_capture = (
        capture_manifest.get("observer_capture")
        if isinstance(capture_manifest.get("observer_capture"), dict)
        else {}
    )
    subject = [
        {
            "name": name,
            "digest": {"sha256": canonical_hash(capture_manifest)},
        },
        {
            "name": "source_fixture",
            "digest": {"sha256": str(capture_manifest.get("source_fixture_hash", ""))},
        },
    ]
    observer_hash = capture_manifest.get("observer_capture_hash")
    if isinstance(observer_hash, str) and observer_hash:
        subject.append(
            {
                "name": "observer_capture",
                "digest": {"sha256": observer_hash},
            }
        )

    prev_capture_hash = capture_manifest.get("prev_capture_hash")
    if isinstance(prev_capture_hash, str) and prev_capture_hash:
        # Carry the append-only chain link into the portable statement so an
        # external verifier that also holds the predecessor manifest can confirm
        # the link with the existing subject-digest ingest path (prev_capture is
        # the predecessor's canonical-json hash). A broken link is then a digest
        # mismatch, which ingest already treats as blocked.
        subject.append(
            {
                "name": "prev_capture",
                "digest": {"sha256": prev_capture_hash},
            }
        )

    return {
        "_type": INTOTO_STATEMENT_TYPE,
        "subject": subject,
        "predicateType": DEPONE_PREDICATE_TYPE,
        "predicate": {
            "schema_version": "1.0",
            "source_kind": capture_manifest.get("kind"),
            "assurance": capture_manifest.get("assurance"),
            "decision": capture_manifest.get("decision"),
            "validation_errors": validation_errors,
            "allowed_touched_files": capture_manifest.get("allowed_touched_files", []),
            "observer": {
                "observed_by": observer_capture.get("observed_by"),
                "touched_files": observer_capture.get("touched_files", []),
                "test_output": observer_capture.get("test_output", {}),
                "command_receipts": observer_capture.get("command_receipts", []),
            },
            "boundary": {
                "raises_assurance": False,
                "signed": False,
                "signing_status": "unsigned-content-addressed",
            },
        },
    }


def wrap_statement_in_dsse(statement: dict[str, Any]) -> dict[str, Any]:
    """Wrap an in-toto Statement in an unsigned DSSE envelope."""

    payload = _canonical_json(statement).encode("utf-8")
    return {
        "payloadType": DSSE_PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode("ascii"),
        "signatures": [],
    }


def decode_dsse_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    if envelope.get("payloadType") != DSSE_PAYLOAD_TYPE:
        raise ValueError("unsupported DSSE payloadType")
    payload = envelope.get("payload")
    if not isinstance(payload, str):
        raise ValueError("DSSE payload must be a base64 string")
    decoded = base64.b64decode(payload.encode("ascii")).decode("utf-8")
    value = json.loads(decoded)
    if not isinstance(value, dict):
        raise ValueError("DSSE payload must decode to an object")
    return value


def _subject_names(statement: dict[str, Any]) -> list[str]:
    subjects = statement.get("subject")
    if not isinstance(subjects, list):
        return []
    names: list[str] = []
    for item in subjects:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def resolve_present_artifact_digests(
    subject_names: list[str],
    artifact_paths: dict[str, str],
    artifact_digest_modes: dict[str, str] | None = None,
) -> tuple[dict[str, str], set[str]]:
    """Recompute subject digests from present on-disk artifacts.

    Returns ``(digests, unreadable)``. ``unreadable`` names a subject whose
    artifact is present on disk but could not be hashed (corrupt JSON in
    canonical mode, an I/O error, or an unknown digest mode). Keeping these
    separate from absent subjects matters for honesty (the verdict must not
    claim a present file is missing) and for safety: an artifact whose real
    bytes would mismatch must not be downgradable to ``inconclusive`` by
    corrupting it on disk.
    """

    digests: dict[str, str] = {}
    unreadable: set[str] = set()
    for name in subject_names:
        path_text = artifact_paths.get(name)
        if not path_text:
            continue
        path = Path(path_text)
        if not path.exists() or not path.is_file():
            continue
        mode = (artifact_digest_modes or {}).get(name, DIGEST_MODE_RAW)
        try:
            if mode == DIGEST_MODE_RAW:
                digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            elif mode == DIGEST_MODE_CANONICAL_JSON:
                value = json.loads(path.read_text(encoding="utf-8"))
                digests[name] = canonical_hash(value)
            else:
                # Present artifact with an unrecognized mode: cannot verify, so
                # fail closed rather than silently treat the subject as absent.
                unreadable.add(name)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            unreadable.add(name)
    return digests, unreadable


def _blocked_verdict(reason: str, *, signing_status: str | None = None) -> dict[str, Any]:
    # Carry predicate_type / predicate_recognized on every verdict so consumers
    # can read them unconditionally; a payload blocked before its statement is
    # parsed has no known predicate, hence None / False.
    verdict: dict[str, Any] = {
        "decision": "blocked",
        "subject_results": [],
        "reasons": [reason],
        "predicate_type": None,
        "predicate_recognized": False,
    }
    if signing_status is not None:
        verdict["signing_status"] = signing_status
    return verdict


def ingest_external_statement(
    statement: dict[str, Any],
    present_digests: dict[str, str],
    unreadable: set[str] | None = None,
) -> dict[str, Any]:
    """Evaluate an untrusted in-toto Statement against recomputed digests."""

    unreadable = unreadable or set()
    reasons: list[str] = []
    subject_results: list[dict[str, Any]] = []
    blocked = False

    statement_type = statement.get("_type")
    predicate_type = statement.get("predicateType")
    predicate_recognized = predicate_type == DEPONE_PREDICATE_TYPE

    if statement_type not in (INTOTO_STATEMENT_TYPE, INTOTO_STATEMENT_TYPE_V01):
        reasons.append("statement._type is not a supported in-toto Statement type")
        blocked = True
    if not isinstance(predicate_type, str) or not predicate_type:
        reasons.append("statement.predicateType must be a non-empty string")
        blocked = True
    elif not predicate_recognized:
        reasons.append("foreign predicate not interpreted")

    subjects = statement.get("subject")
    if not isinstance(subjects, list):
        reasons.append("statement.subject must be a list")
        return {
            "decision": "blocked",
            "subject_results": subject_results,
            "reasons": reasons,
            "predicate_type": predicate_type,
            "predicate_recognized": predicate_recognized,
        }
    if not subjects:
        reasons.append("statement has no subjects to verify")

    verified_count = 0
    for item in subjects:
        if not isinstance(item, dict):
            reasons.append("statement.subject contains a non-object item")
            blocked = True
            continue
        name = item.get("name")
        digest = item.get("digest")
        expected = digest.get("sha256") if isinstance(digest, dict) else None
        if not isinstance(name, str) or not isinstance(expected, str) or not expected:
            reasons.append("statement.subject item lacks name or digest.sha256")
            blocked = True
            subject_results.append(
                {
                    "name": str(name),
                    "expected": str(expected),
                    "actual": None,
                    "status": "mismatch",
                }
            )
            continue
        actual = present_digests.get(name)
        if actual is None and name in unreadable:
            blocked = True
            subject_results.append(
                {
                    "name": name,
                    "expected": expected,
                    "actual": None,
                    "status": "unreadable",
                }
            )
            reasons.append(f"subject artifact present but could not be hashed: {name}")
        elif actual is None:
            subject_results.append(
                {
                    "name": name,
                    "expected": expected,
                    "actual": None,
                    "status": "missing",
                }
            )
            reasons.append(f"subject artifact not present on disk: {name}")
        elif actual == expected:
            verified_count += 1
            subject_results.append(
                {
                    "name": name,
                    "expected": expected,
                    "actual": actual,
                    "status": "verified",
                }
            )
        else:
            blocked = True
            subject_results.append(
                {
                    "name": name,
                    "expected": expected,
                    "actual": actual,
                    "status": "mismatch",
                }
            )
            reasons.append(f"subject digest mismatch: {name}")

    if blocked:
        decision = "blocked"
    elif verified_count > 0 and all(
        result.get("status") == "verified" for result in subject_results
    ):
        decision = "pass"
    else:
        decision = "inconclusive"
    return {
        "decision": decision,
        "subject_results": subject_results,
        "reasons": reasons,
        "verified_subject_count": verified_count,
        "predicate_type": predicate_type,
        "predicate_recognized": predicate_recognized,
    }


def ingest_dsse_envelope(
    envelope: dict[str, Any],
    present_digests: dict[str, str],
    unreadable: set[str] | None = None,
) -> dict[str, Any]:
    """Safely ingest an untrusted DSSE envelope without raising."""

    if not isinstance(envelope, dict):
        return _blocked_verdict("DSSE envelope must be an object")
    if envelope.get("payloadType") != DSSE_PAYLOAD_TYPE:
        return _blocked_verdict("unsupported DSSE payloadType")
    signatures = envelope.get("signatures")
    if signatures != []:
        return _blocked_verdict(
            "DSSE envelope contains unverifiable signatures",
            signing_status="unverifiable-signature",
        )
    payload = envelope.get("payload")
    if not isinstance(payload, str):
        return _blocked_verdict(
            "DSSE payload must be a base64 string",
            signing_status="unsigned-content-addressed",
        )
    try:
        decoded = base64.b64decode(payload.encode("ascii"), validate=True).decode(
            "utf-8"
        )
        value = json.loads(decoded)
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return _blocked_verdict(
            "DSSE payload is not decodable in-toto JSON",
            signing_status="unsigned-content-addressed",
        )
    if not isinstance(value, dict):
        return _blocked_verdict(
            "DSSE payload must decode to an object",
            signing_status="unsigned-content-addressed",
        )
    verdict = ingest_external_statement(value, present_digests, unreadable)
    verdict["signing_status"] = "unsigned-content-addressed"
    return verdict


def _finalize_ingest_verdict(
    verdict: dict[str, Any],
    otel_spans: Any,
    *,
    trusts_external_signature: bool,
) -> dict[str, Any]:
    otel_errors = validate_external_otel_spans(otel_spans) if otel_spans is not None else []
    if otel_errors:
        verdict["reasons"] = list(verdict.get("reasons", [])) + otel_errors
        if verdict.get("decision") == "pass":
            verdict["decision"] = "blocked"
    verdict["otel_errors"] = otel_errors
    verdict["boundary"] = {
        "raises_assurance": False,
        "trusts_external_signature": trusts_external_signature,
    }
    return verdict


def validate_external_otel_spans(spans: Any) -> list[str]:
    """Return structural errors for externally supplied static OTel spans."""

    if not isinstance(spans, list):
        return ["otel_spans must be a list"]
    errors: list[str] = []
    for index, span in enumerate(spans):
        prefix = f"otel_spans[{index}]"
        if not isinstance(span, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in ("trace_id", "span_id", "name"):
            if not isinstance(span.get(key), str) or not span.get(key):
                errors.append(f"{prefix}.{key} must be a non-empty string")
        parent = span.get("parent_span_id")
        if parent is not None and not isinstance(parent, str):
            errors.append(f"{prefix}.parent_span_id must be a string or null")
        attributes = span.get("attributes")
        if not isinstance(attributes, dict):
            errors.append(f"{prefix}.attributes must be an object")
            continue
        operation = attributes.get("gen_ai.operation.name")
        if operation is not None and not isinstance(operation, str):
            errors.append(
                f"{prefix}.attributes.gen_ai.operation.name must be a string"
            )
    return errors


def _safe_decoded_dsse_statement(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("payloadType") != DSSE_PAYLOAD_TYPE:
        return None
    dsse_payload = payload.get("payload")
    if not isinstance(dsse_payload, str):
        return None
    try:
        decoded = base64.b64decode(
            dsse_payload.encode("ascii"),
            validate=True,
        ).decode("utf-8")
        value = json.loads(decoded)
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def ingest_external_evidence(
    payload: dict[str, Any],
    artifact_paths: dict[str, str],
    *,
    artifact_digest_modes: dict[str, str] | None = None,
    otel_spans: Any = None,
) -> dict[str, Any]:
    """Ingest external evidence as untrusted input and fail closed."""

    if not isinstance(payload, dict):
        verdict = _blocked_verdict("external evidence payload must be an object")
    else:
        # The subjects we hash from disk must come from the SAME content we go on
        # to verify. A DSSE envelope (payloadType present) is verified through its
        # decoded payload, so its subject names must come from there too — never
        # from any top-level _type/subject the envelope also happens to carry. A
        # decoy top-level subject list would otherwise steer hashing away from the
        # real artifacts and silently downgrade a mismatch (blocked) to a missing
        # subject (inconclusive). DSSE therefore takes precedence over _type.
        if "payloadType" in payload:
            decoded = _safe_decoded_dsse_statement(payload)
            subject_names = _subject_names(decoded) if isinstance(decoded, dict) else []
            present_digests, unreadable = resolve_present_artifact_digests(
                subject_names,
                artifact_paths,
                artifact_digest_modes,
            )
            verdict = ingest_dsse_envelope(payload, present_digests, unreadable)
        elif payload.get("_type") in (INTOTO_STATEMENT_TYPE, INTOTO_STATEMENT_TYPE_V01):
            subject_names = _subject_names(payload)
            present_digests, unreadable = resolve_present_artifact_digests(
                subject_names,
                artifact_paths,
                artifact_digest_modes,
            )
            verdict = ingest_external_statement(payload, present_digests, unreadable)
        else:
            verdict = _blocked_verdict(
                "external evidence must be a DSSE envelope or in-toto Statement"
            )

    return _finalize_ingest_verdict(
        verdict,
        otel_spans,
        trusts_external_signature=False,
    )


def ingest_signed_evidence_bundle(
    bundle: dict[str, Any],
    public_key_path: str,
    artifact_paths: dict[str, str],
    *,
    artifact_digest_modes: dict[str, str] | None = None,
    otel_spans: Any = None,
) -> dict[str, Any]:
    """Verify an operator-key signed bundle, then ingest its signed subjects.

    This verifies integrity relative to the supplied public key only. It never
    raises Depone assurance and it does not claim Fulcio/Rekor/keyless identity.
    """

    from depone.agent_fabric.sign import (  # local import avoids a module cycle
        SIGNING_STATUS_OPERATOR_KEY,
        verify_signed_bundle,
    )

    if not isinstance(bundle, dict):
        verdict = _blocked_verdict(
            "signed evidence bundle must be an object",
            signing_status="unverifiable-signature",
        )
        verdict["signature_verified"] = False
        return _finalize_ingest_verdict(
            verdict,
            otel_spans,
            trusts_external_signature=False,
        )
    if not verify_signed_bundle(bundle, public_key_path):
        verdict = _blocked_verdict(
            "signed evidence bundle did not verify with public key",
            signing_status="unverifiable-signature",
        )
        verdict["signature_verified"] = False
        return _finalize_ingest_verdict(
            verdict,
            otel_spans,
            trusts_external_signature=False,
        )

    envelope = bundle.get("dsse_envelope")
    if not isinstance(envelope, dict):
        verdict = _blocked_verdict(
            "signed evidence bundle missing DSSE envelope",
            signing_status="unverifiable-signature",
        )
        verdict["signature_verified"] = False
        return _finalize_ingest_verdict(
            verdict,
            otel_spans,
            trusts_external_signature=False,
        )
    statement = _safe_decoded_dsse_statement(envelope)
    if not isinstance(statement, dict):
        verdict = _blocked_verdict(
            "signed evidence bundle DSSE payload is not decodable in-toto JSON",
            signing_status="unverifiable-signature",
        )
        verdict["signature_verified"] = False
        return _finalize_ingest_verdict(
            verdict,
            otel_spans,
            trusts_external_signature=False,
        )

    subject_names = _subject_names(statement)
    present_digests, unreadable = resolve_present_artifact_digests(
        subject_names,
        artifact_paths,
        artifact_digest_modes,
    )
    verdict = ingest_external_statement(statement, present_digests, unreadable)
    verdict["signing_status"] = SIGNING_STATUS_OPERATOR_KEY
    verdict["signature_verified"] = True
    verdict["signature_boundary"] = bundle.get("signature_boundary")
    return _finalize_ingest_verdict(
        verdict,
        otel_spans,
        trusts_external_signature=True,
    )


def build_otel_genai_spans(
    capture_manifest: dict[str, Any],
    *,
    runner_receipt: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Emit static OTel GenAI-shaped spans without inventing usage fields."""

    seed = canonical_hash(
        {
            "capture": capture_manifest,
            "runner": runner_receipt or {},
        }
    )
    trace_id = _trace_id(seed)
    root_span_id = _span_id(seed, 0)
    runner_kind = (
        runner_receipt.get("runner_kind")
        if isinstance(runner_receipt, dict)
        else "unknown"
    )
    arm = runner_receipt.get("arm") if isinstance(runner_receipt, dict) else "unknown"
    spans = [
        {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_span_id": None,
            "name": "invoke_agent",
            "attributes": {
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.name": str(runner_kind),
                "depone.arm": str(arm),
                "depone.assurance": str(capture_manifest.get("assurance", "")),
                "depone.decision": str(capture_manifest.get("decision", "")),
            },
        }
    ]

    observer_capture = (
        capture_manifest.get("observer_capture")
        if isinstance(capture_manifest.get("observer_capture"), dict)
        else {}
    )
    receipts = observer_capture.get("command_receipts", [])
    if isinstance(receipts, list):
        for index, receipt in enumerate(receipts, start=1):
            if not isinstance(receipt, dict):
                continue
            spans.append(
                {
                    "trace_id": trace_id,
                    "span_id": _span_id(seed, index),
                    "parent_span_id": root_span_id,
                    "name": "execute_tool",
                    "attributes": {
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": "verification_command",
                        "depone.command": receipt.get("command", []),
                        "depone.exit_code": receipt.get("exit_code"),
                        "depone.status": receipt.get("status"),
                    },
                }
            )
    return spans


def build_evidence_bundle(
    capture_manifest: dict[str, Any],
    *,
    runner_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    statement = build_intoto_statement_from_capture(capture_manifest)
    return {
        "kind": "depone-evidence-substrate-bundle",
        "schema_version": "1.0",
        "statement": statement,
        "dsse_envelope": wrap_statement_in_dsse(statement),
        "otel_spans": build_otel_genai_spans(
            capture_manifest,
            runner_receipt=runner_receipt,
        ),
        "assurance": capture_manifest.get("assurance"),
        "signing_status": "unsigned-content-addressed",
        "boundary": {
            "raises_assurance": False,
            "signed": False,
            "approves_public_claim": False,
        },
    }


def validate_statement_for_capture(
    statement: dict[str, Any],
    capture_manifest: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if statement.get("_type") != INTOTO_STATEMENT_TYPE:
        errors.append("statement._type is not in-toto Statement v1")
    if statement.get("predicateType") != DEPONE_PREDICATE_TYPE:
        errors.append("statement.predicateType is not Depone evidence v1")
    subjects = statement.get("subject")
    if not isinstance(subjects, list):
        return errors + ["statement.subject must be a list"]
    digests = {
        item.get("name"): item.get("digest", {}).get("sha256")
        for item in subjects
        if isinstance(item, dict) and isinstance(item.get("digest"), dict)
    }
    expected = {
        "depone-capture-manifest": canonical_hash(capture_manifest),
        "source_fixture": capture_manifest.get("source_fixture_hash"),
    }
    observer_hash = capture_manifest.get("observer_capture_hash")
    if observer_hash:
        expected["observer_capture"] = observer_hash
    for name, digest in expected.items():
        if digests.get(name) != digest:
            errors.append(f"statement subject digest mismatch: {name}")
    return errors


def evaluate_external_statement_subjects(
    statement: dict[str, Any],
    artifact_digests: dict[str, str],
) -> dict[str, Any]:
    """Evaluate externally supplied subjects against present artifact digests."""

    verdict = ingest_external_statement(statement, artifact_digests)
    mismatches = [
        {
            "name": str(result.get("name")),
            "expected": str(result.get("expected")),
            "actual": str(result.get("actual")),
        }
        for result in verdict.get("subject_results", [])
        if result.get("status") != "verified"
    ]
    return {
        "decision": verdict["decision"],
        "mismatches": mismatches,
    }


def verify_capture_chain(manifests: Any) -> dict[str, Any]:
    """Verify an ordered append-only chain of capture manifests.

    Each manifest after the genesis must carry ``prev_capture_hash`` equal to the
    canonical hash of its immediate predecessor. A non-genesis head, a dropped or
    reordered step (predecessor hash no longer matches), a tampered predecessor,
    or a structurally invalid manifest all break the chain and yield ``blocked``.
    An empty list is ``inconclusive`` (nothing to verify). This is the cross-step
    integrity that per-subject digest checks cannot provide on their own: it makes
    an omitted intermediate step detectable rather than silent.
    """

    if not isinstance(manifests, list):
        return {"decision": "blocked", "links": [], "reasons": ["manifests must be a list"]}
    if not manifests:
        return {
            "decision": "inconclusive",
            "links": [],
            "reasons": ["no captures to verify"],
        }

    links: list[dict[str, Any]] = []
    reasons: list[str] = []
    blocked = False
    prev_hash: str | None = None

    for index, manifest in enumerate(manifests):
        if not isinstance(manifest, dict):
            links.append({"index": index, "status": "malformed", "capture_hash": None})
            reasons.append(f"chain[{index}] is not an object")
            blocked = True
            prev_hash = None
            continue

        capture_hash = canonical_hash(manifest)
        declared_prev = manifest.get("prev_capture_hash")
        status = "linked"

        if index == 0:
            if declared_prev is None:
                status = "genesis"
            else:
                status = "broken"
                reasons.append("chain head must be genesis (prev_capture_hash=null)")
                blocked = True
        elif declared_prev != prev_hash:
            status = "broken"
            reasons.append(
                f"chain[{index}] prev_capture_hash does not match predecessor"
            )
            blocked = True

        validation_errors = validate_capture_manifest(manifest)
        if validation_errors:
            status = "invalid"
            reasons.append(f"chain[{index}] manifest invalid: {validation_errors[0]}")
            blocked = True

        links.append(
            {
                "index": index,
                "capture_hash": capture_hash,
                "declared_prev": declared_prev,
                "expected_prev": prev_hash,
                "status": status,
            }
        )
        prev_hash = capture_hash

    return {
        "decision": "blocked" if blocked else "pass",
        "links": links,
        "reasons": reasons,
    }


def _self_test() -> None:
    from copy import deepcopy

    capture = json.loads(
        resource_text(
            "fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json"
        )
    )
    bundle = build_evidence_bundle(capture)
    statement = bundle["statement"]
    if validate_statement_for_capture(statement, capture):
        raise AssertionError("expected statement to validate against capture")
    decoded = decode_dsse_payload(bundle["dsse_envelope"])
    if decoded != statement:
        raise AssertionError("expected DSSE payload to round-trip")
    if bundle["dsse_envelope"]["signatures"] != []:
        raise AssertionError("V128 DSSE envelope must remain unsigned")
    spans = bundle["otel_spans"]
    operations = {
        span.get("attributes", {}).get("gen_ai.operation.name")
        for span in spans
        if isinstance(span.get("attributes"), dict)
    }
    if not {"invoke_agent", "execute_tool"}.issubset(operations):
        raise AssertionError("expected invoke_agent and execute_tool spans")
    if any(
        key.startswith("gen_ai.usage.")
        for span in spans
        for key in span.get("attributes", {})
    ):
        raise AssertionError("unobserved gen_ai.usage.* fields must be omitted")
    tampered = deepcopy(statement)
    tampered["subject"][0]["digest"]["sha256"] = "0" * 64
    if not validate_statement_for_capture(tampered, capture):
        raise AssertionError("expected tampered statement to fail validation")
    external = evaluate_external_statement_subjects(
        tampered,
        {"depone-capture-manifest": canonical_hash(capture)},
    )
    if external["decision"] != "blocked":
        raise AssertionError("digest mismatch must be blocked, not pass")

    # --- Append-only capture chain ---------------------------------------
    step0 = deepcopy(capture)
    step0["prev_capture_hash"] = None
    step1 = deepcopy(capture)
    step1["prev_capture_hash"] = canonical_hash(step0)
    step2 = deepcopy(capture)
    step2["prev_capture_hash"] = canonical_hash(step1)
    chain = [step0, step1, step2]

    if verify_capture_chain(chain)["decision"] != "pass":
        raise AssertionError("intact append-only chain must pass")

    if verify_capture_chain([])["decision"] != "inconclusive":
        raise AssertionError("empty chain must be inconclusive, not pass")

    if verify_capture_chain([step1])["decision"] != "blocked":
        raise AssertionError("non-genesis head must be blocked")

    dropped_middle = [step0, step2]
    if verify_capture_chain(dropped_middle)["decision"] != "blocked":
        raise AssertionError("dropped intermediate step must break the chain")

    reordered = [step0, step2, step1]
    if verify_capture_chain(reordered)["decision"] != "blocked":
        raise AssertionError("reordered chain must be blocked")

    tampered_chain = deepcopy(chain)
    tampered_chain[1]["allowed_touched_files"] = ["smuggled.py"]
    if verify_capture_chain(tampered_chain)["decision"] != "blocked":
        raise AssertionError("tampered predecessor must break downstream link")

    # The link travels into the portable statement and re-verifies via ingest.
    linked_statement = build_intoto_statement_from_capture(step1)
    if "prev_capture" not in _subject_names(linked_statement):
        raise AssertionError("statement must carry the prev_capture chain subject")
    broken_link = evaluate_external_statement_subjects(
        linked_statement,
        {
            "depone-capture-manifest": canonical_hash(step1),
            "source_fixture": str(step1.get("source_fixture_hash", "")),
            "observer_capture": str(step1.get("observer_capture_hash", "")),
            "prev_capture": "0" * 64,
        },
    )
    if broken_link["decision"] != "blocked":
        raise AssertionError("a broken prev_capture link must be blocked on ingest")


if __name__ == "__main__":
    _self_test()
