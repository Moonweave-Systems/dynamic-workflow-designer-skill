from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from depone.agent_fabric.evidence_substrate import (
    build_evidence_bundle,
    DIGEST_MODE_CANONICAL_JSON,
    DIGEST_MODE_RAW,
    ingest_external_evidence,
)


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    statement_arg = getattr(args, "statement", None)
    dsse_arg = getattr(args, "dsse", None)
    if bool(statement_arg) == bool(dsse_arg):
        print("Error: provide exactly one of --statement or --dsse", file=sys.stderr)
        sys.exit(1)

    try:
        payload = (
            _load_json_selector(str(statement_arg), "statement")
            if statement_arg
            else _load_json_selector(str(dsse_arg), "dsse_envelope")
        )
        artifact_paths, artifact_digest_modes = _parse_artifacts(
            getattr(args, "artifact", []) or []
        )
        otel_spans = None
        if getattr(args, "otel_spans", None):
            otel_spans = _load_json_selector(str(args.otel_spans), "otel_spans")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    verdict = ingest_external_evidence(
        payload,
        artifact_paths,
        artifact_digest_modes=artifact_digest_modes,
        otel_spans=otel_spans,
    )
    out_path = Path(str(getattr(args, "out", "evidence-ingest-verdict.json")))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Evidence ingest decision: {verdict['decision']}")
    print(f"Evidence ingest verdict written to {out_path}")
    if verdict["decision"] == "blocked":
        sys.exit(1)


def _load_json_selector(spec: str, default_key: str) -> Any:
    path_text, selector = _split_selector(spec)
    value = json.loads(Path(path_text).read_text(encoding="utf-8"))
    key = selector or default_key
    if selector:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"JSON selector not found: {key}")
        return value[key]
    if default_key == "dsse_envelope":
        if isinstance(value, dict) and value.get("payloadType"):
            return value
        if isinstance(value, dict) and "dsse_envelope" in value:
            return value["dsse_envelope"]
    if default_key == "statement":
        if isinstance(value, dict) and value.get("_type"):
            return value
        if isinstance(value, dict) and "statement" in value:
            return value["statement"]
    if default_key == "otel_spans":
        if isinstance(value, dict) and "otel_spans" in value:
            return value["otel_spans"]
        return value
    raise ValueError(f"JSON does not contain {default_key}")


def _split_selector(spec: str) -> tuple[str, str | None]:
    if Path(spec).exists():
        return spec, None
    if ":" not in spec:
        return spec, None
    path_text, selector = spec.rsplit(":", 1)
    if Path(path_text).exists():
        return path_text, selector
    return spec, None


def _parse_artifacts(items: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    artifacts: dict[str, str] = {}
    digest_modes: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"--artifact must be name=path: {item}")
        name, path_text = item.split("=", 1)
        if not name or not path_text:
            raise ValueError(f"--artifact must be name=path: {item}")
        mode = DIGEST_MODE_RAW
        if path_text.endswith(":raw"):
            path_text = path_text[:-4]
            mode = DIGEST_MODE_RAW
        elif path_text.endswith(":json"):
            path_text = path_text[:-5]
            mode = DIGEST_MODE_CANONICAL_JSON
        artifacts[name] = path_text
        digest_modes[name] = mode
    return artifacts, digest_modes


def _self_test() -> None:
    # Hermetic: build a bundle from a committed fixture and re-hash its subjects
    # from artifacts written to a temp dir, so the self-test never depends on
    # gitignored out/ artifacts and stays reproducible on a fresh clone.
    capture = json.loads(
        Path(
            "depone/fixtures/agent_fabric/capture_manifest_v126_governed_utf8.json"
        ).read_text(encoding="utf-8")
    )
    bundle = build_evidence_bundle(capture)

    with tempfile.TemporaryDirectory() as temp_dir:
        manifest_path = Path(temp_dir) / "capture-manifest.json"
        observer_path = Path(temp_dir) / "observer-capture.json"
        manifest_path.write_text(json.dumps(capture), encoding="utf-8")
        observer_path.write_text(
            json.dumps(capture["observer_capture"]), encoding="utf-8"
        )
        artifact_paths = {
            "source_fixture": "depone/fixtures/agent_fabric/reference_adapter_shell.json",
            "depone-capture-manifest": str(manifest_path),
            "observer_capture": str(observer_path),
        }
        artifact_digest_modes = {
            "source_fixture": DIGEST_MODE_CANONICAL_JSON,
            "depone-capture-manifest": DIGEST_MODE_CANONICAL_JSON,
            "observer_capture": DIGEST_MODE_CANONICAL_JSON,
        }

        pass_verdict = ingest_external_evidence(
            bundle["dsse_envelope"],
            artifact_paths,
            artifact_digest_modes=artifact_digest_modes,
            otel_spans=bundle["otel_spans"],
        )
        if pass_verdict["decision"] != "pass":
            raise AssertionError("V128 bundle should pass with present artifacts")

        missing = ingest_external_evidence(
            bundle["dsse_envelope"],
            {"source_fixture": artifact_paths["source_fixture"]},
            artifact_digest_modes={"source_fixture": DIGEST_MODE_CANONICAL_JSON},
        )
        if missing["decision"] != "inconclusive":
            raise AssertionError("missing subjects should be inconclusive")

        tampered_path = Path(temp_dir) / "tampered.json"
        tampered_path.write_text('{"tampered": true}\n', encoding="utf-8")
        tampered_paths = dict(artifact_paths)
        tampered_paths["source_fixture"] = str(tampered_path)
        tampered = ingest_external_evidence(
            bundle["dsse_envelope"],
            tampered_paths,
            artifact_digest_modes=artifact_digest_modes,
        )
        if tampered["decision"] != "blocked":
            raise AssertionError("present digest mismatch should be blocked")

        signed = dict(bundle["dsse_envelope"])
        signed["signatures"] = [{"keyid": "unverified", "sig": "claim"}]
        signed_verdict = ingest_external_evidence(
            signed,
            artifact_paths,
            artifact_digest_modes=artifact_digest_modes,
        )
        if signed_verdict["decision"] != "blocked":
            raise AssertionError("unverifiable signatures should be blocked")

        malformed = {
            "payloadType": "application/vnd.in-toto+json",
            "payload": "!!",
            "signatures": [],
        }
        malformed_verdict = ingest_external_evidence(
            malformed,
            artifact_paths,
            artifact_digest_modes=artifact_digest_modes,
        )
        if malformed_verdict["decision"] != "blocked":
            raise AssertionError("malformed DSSE should be blocked")

        bad_spans = ingest_external_evidence(
            bundle["dsse_envelope"],
            artifact_paths,
            artifact_digest_modes=artifact_digest_modes,
            otel_spans=[{"trace_id": "trace"}],
        )
        if bad_spans["decision"] == "pass":
            raise AssertionError("OTel structural errors must not pass")

    external_dir = Path("depone/fixtures/agent_fabric/external")
    foreign_statement = json.loads(
        (external_dir / "external_intoto_statement_real.json").read_text(
            encoding="utf-8"
        )
    )
    foreign_missing = ingest_external_evidence(foreign_statement, {})
    if foreign_missing["decision"] != "inconclusive":
        raise AssertionError("foreign statement with absent artifact is inconclusive")
    if foreign_missing.get("predicate_recognized") is not False:
        raise AssertionError("foreign predicate must remain unrecognized")

    bound_statement = json.loads(
        (external_dir / "external_slsa_statement_bound.json").read_text(
            encoding="utf-8"
        )
    )
    bound_pass = ingest_external_evidence(
        bound_statement,
        {"external_artifact.bin": str(external_dir / "external_artifact.bin")},
    )
    if bound_pass["decision"] != "pass":
        raise AssertionError("foreign raw-byte subject should pass")

    signed_fixture = json.loads(
        (external_dir / "external_signed_dsse_nonempty.json").read_text(
            encoding="utf-8"
        )
    )
    signed_external = ingest_external_evidence(signed_fixture, {})
    if signed_external.get("signing_status") != "unverifiable-signature":
        raise AssertionError("non-empty external signatures are unverifiable")
    print("depone agent-fabric-evidence-ingest --self-test: pass")
