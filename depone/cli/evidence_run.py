from __future__ import annotations

import argparse
import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from depone._resources import resource_text
from depone.agent_fabric.capture_bridge import (
    ASSURANCE_A2,
    build_capture_manifest,
    validate_capture_manifest,
)
from depone.agent_fabric.isolation import (
    CONTAINER_ISOLATION_MODEL,
    UID_OBSERVER_LAUNCHED_ISOLATION_MODEL,
    probe_container_isolation_facts,
    probe_isolation_facts,
)
from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.evidence_substrate import (
    DIGEST_MODE_CANONICAL_JSON,
    build_evidence_bundle,
    ingest_external_evidence,
    validate_statement_for_capture,
)
from depone.agent_fabric.observe import (
    build_separated_observer_capture,
    write_observer_capture,
)
from depone.agent_fabric.paired_run import PairedRunError
from depone.agent_fabric.sign import (
    DsseSigningError,
    sign_evidence_bundle,
    verify_signed_bundle,
)
from depone.cli._response import (
    EXIT_FAILED,
    EXIT_INCONCLUSIVE,
    EXIT_INTERNAL,
    emit_error,
    emit_result,
    exit_code_for_decision,
)
from depone.core.plan_schema import load_plan
from depone.verify.adapters import resolve
from depone.verify.engine import run_verification
from depone.verify.operator_view import write_operator_view


def run(args: argparse.Namespace) -> None:
    if getattr(args, "self_test", False):
        _self_test()
        return

    try:
        payload = run_evidence_loop(args)
    except PairedRunError as exc:
        record = exc.to_record()
        emit_error(
            args,
            code=str(record.get("code", "ERR_EVIDENCE_RUN_OBSERVE")),
            message=str(record.get("message", exc)),
            path=record.get("path"),
        )
    except (OSError, json.JSONDecodeError, ValueError, NotADirectoryError) as exc:
        emit_error(
            args,
            code="ERR_EVIDENCE_RUN_INPUT",
            message=str(exc),
        )
    except Exception as exc:
        emit_error(
            args,
            code="ERR_EVIDENCE_RUN_INTERNAL",
            message=str(exc),
            exit_code=EXIT_INTERNAL,
        )

    emit_result(
        args,
        payload,
        human=[
            f"Evidence run decision: {payload['decision']}",
            f"Evidence run output: {payload['out']}",
            f"  observe: {payload['observe']['decision']}",
            f"  evidence-ingest: {payload['evidence_ingest']['decision']}",
            f"  verify: {payload['verify']['decision']}",
        ],
    )
    exit_code = exit_code_for_decision(str(payload["decision"]))
    if exit_code:
        sys.exit(exit_code)


def run_evidence_loop(args: argparse.Namespace) -> dict[str, Any]:
    command = list(getattr(args, "verification_command", []) or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError(
            "verification command is required after --, for example -- python -m unittest"
        )
    runner_sandbox = Path(str(getattr(args, "runner_sandbox", "") or ""))
    if not str(runner_sandbox):
        raise ValueError("--runner-sandbox is required")
    source_fixture_path = Path(str(getattr(args, "source_fixture", "") or ""))
    if not str(source_fixture_path):
        raise ValueError("--source-fixture is required")

    verify_plan = str(getattr(args, "verify_plan", "") or "")
    verify_evidence = str(getattr(args, "verify_evidence", "") or "")
    if bool(verify_plan) != bool(verify_evidence):
        raise ValueError("--verify-plan and --verify-evidence must be provided together")
    sign_private_key = str(getattr(args, "sign_private_key", "") or "")
    sign_key_id = str(getattr(args, "sign_key_id", "") or "")
    sign_public_key = str(getattr(args, "sign_public_key", "") or "")
    if bool(sign_private_key) != bool(sign_key_id):
        raise ValueError("--sign-private-key and --sign-key-id must be provided together")
    if sign_public_key and not sign_private_key:
        raise ValueError("--sign-public-key requires --sign-private-key")

    out_dir = Path(str(getattr(args, "out", "evidence-run")))
    observer_dir = out_dir / "observer-owned"
    out_dir.mkdir(parents=True, exist_ok=True)
    observer_dir.mkdir(parents=True, exist_ok=True)
    _restrict_observer_dir(observer_dir)

    # Isolation facts are observer-attested. A free-form --runner-uid preserves
    # the legacy uid path for existing artifacts. The stronger uid and container
    # paths launch the runner from the observer process and bind the observed
    # boundary facts to that launch receipt.
    runner_uid_arg = getattr(args, "runner_uid", None)
    runner_user = str(getattr(args, "runner_user", "") or "")
    runner_command = str(getattr(args, "runner_command", "") or "")
    runner_container_id = str(getattr(args, "runner_container_id", "") or "")
    runner_container_image = str(getattr(args, "runner_container_image", "") or "")
    runner_container_command = str(getattr(args, "runner_container_command", "") or "")
    launched_uid_runner: dict[str, Any] | None = None
    launched_container: dict[str, Any] | None = None
    cleanup_registered = False
    if bool(runner_user) != bool(runner_command):
        raise ValueError("--runner-user and --runner-command must be provided together")
    if bool(runner_container_image) != bool(runner_container_command):
        raise ValueError(
            "--runner-container-image and --runner-container-command must be provided together"
        )
    if runner_user and (
        runner_uid_arg is not None
        or runner_container_id
        or runner_container_image
    ):
        raise ValueError(
            "--runner-user is mutually exclusive with --runner-uid and container isolation options"
        )
    if runner_uid_arg is not None and (
        runner_container_id or runner_container_image
    ):
        raise ValueError("--runner-uid is mutually exclusive with container isolation options")
    if runner_container_id and runner_container_image:
        raise ValueError(
            "--runner-container-id is mutually exclusive with observer-launched container options"
        )
    if runner_user:
        launched_uid_runner = _launch_runner_user(
            runner_sandbox,
            user=runner_user,
            shell_command=runner_command,
        )
    if runner_container_image:
        launched_container = _launch_runner_container(
            runner_sandbox,
            image=runner_container_image,
            shell_command=runner_container_command,
            hold_seconds=int(getattr(args, "runner_container_hold_seconds", 600)),
        )
        runner_container_id = str(launched_container["container_id"])
        atexit.register(_cleanup_runner_container, runner_container_id)
        cleanup_registered = True

    source_fixture = _read_json(source_fixture_path)
    source_fixture_hash = canonical_hash(source_fixture)
    observer_path = observer_dir / "observer-capture.json"
    log_path = observer_dir / "verify-log.json"
    capture = build_separated_observer_capture(
        runner_sandbox=runner_sandbox,
        source_fixture_hash=source_fixture_hash,
        verification_command=command,
        out_path=observer_path,
        log_path=log_path,
        timeout_seconds=int(getattr(args, "timeout_seconds", 120)),
    )
    if launched_uid_runner is not None:
        capture["runner_uid_launch"] = launched_uid_runner
    if launched_container is not None:
        capture["runner_container_launch"] = launched_container
    observer_capture_hash = write_observer_capture(observer_path, capture)

    allowed_touched_files = list(getattr(args, "allow_touched_file", []) or [])
    isolation_facts = None
    if launched_uid_runner is not None:
        isolation_facts = probe_isolation_facts(
            observer_dir,
            runner_uid=int(launched_uid_runner["observed_uid"]),
            model=UID_OBSERVER_LAUNCHED_ISOLATION_MODEL,
            observer_launched=True,
        )
    elif runner_container_id:
        isolation_facts = probe_container_isolation_facts(
            observer_dir,
            container_id=runner_container_id,
            observer_launched=launched_container is not None,
        )
    elif runner_uid_arg is not None:
        isolation_facts = probe_isolation_facts(
            observer_dir, runner_uid=int(runner_uid_arg)
        )
    capture_manifest = build_capture_manifest(
        source_fixture,
        observer_capture=capture,
        allowed_touched_files=allowed_touched_files,
        isolation=isolation_facts,
    )
    capture_errors = validate_capture_manifest(capture_manifest)
    capture_manifest_path = out_dir / "capture-manifest.json"
    _write_json(capture_manifest_path, capture_manifest)

    bundle = build_evidence_bundle(capture_manifest)
    substrate_errors = validate_statement_for_capture(
        bundle["statement"], capture_manifest
    )
    bundle_path = out_dir / "evidence-bundle.json"
    _write_json(bundle_path, bundle)
    signed_bundle_payload = _maybe_write_signed_bundle(
        out_dir,
        bundle,
        private_key_path=sign_private_key,
        key_id=sign_key_id,
        public_key_path=sign_public_key,
    )

    ingest_verdict = ingest_external_evidence(
        bundle["dsse_envelope"],
        {
            "depone-capture-manifest": str(capture_manifest_path),
            "source_fixture": str(source_fixture_path),
            "observer_capture": str(observer_path),
        },
        artifact_digest_modes={
            "depone-capture-manifest": DIGEST_MODE_CANONICAL_JSON,
            "source_fixture": DIGEST_MODE_CANONICAL_JSON,
            "observer_capture": DIGEST_MODE_CANONICAL_JSON,
        },
        otel_spans=bundle["otel_spans"],
    )
    ingest_path = out_dir / "ingest-verdict.json"
    _write_json(ingest_path, ingest_verdict)

    verify_payload: dict[str, Any]
    if verify_plan and verify_evidence:
        verify_payload = _run_verify(args, out_dir, verify_plan, verify_evidence)
    else:
        verify_payload = {
            "decision": "skipped",
            "verdict": "skipped",
            "out": None,
            "operator_view_out": None,
        }

    observer_status = _observer_status(capture)
    observer_decision = "pass" if observer_status == "passed" else "blocked"
    decision = _aggregate_decision(
        [
            observer_decision,
            "blocked" if capture_errors or substrate_errors else "pass",
            str(ingest_verdict.get("decision", "blocked")),
            str(verify_payload["decision"]),
        ]
    )
    payload = {
        "command": "evidence-run",
        "decision": decision,
        "out": str(out_dir),
        "observe": {
            "decision": observer_decision,
            "status": observer_status,
            "out": str(observer_path),
            "log": str(log_path),
            "observer_capture_hash": observer_capture_hash,
        },
        "capture_manifest": {
            "path": str(capture_manifest_path),
            "assurance": capture_manifest.get("assurance"),
            "decision": capture_manifest.get("decision"),
            "error_count": len(capture_errors),
            "errors": capture_errors,
        },
        "evidence_substrate": {
            "decision": "blocked" if substrate_errors else "pass",
            "out": str(bundle_path),
            "assurance": bundle.get("assurance"),
            "signing_status": bundle.get("signing_status"),
            "subject_count": len(bundle["statement"].get("subject", [])),
            "otel_span_count": len(bundle["otel_spans"]),
            "error_count": len(substrate_errors),
            "errors": substrate_errors,
        },
        "signed_evidence_bundle": signed_bundle_payload,
        "evidence_ingest": {
            "decision": ingest_verdict.get("decision"),
            "out": str(ingest_path),
            "subject_count": len(ingest_verdict.get("subject_results", [])),
            "verified_subject_count": ingest_verdict.get("verified_subject_count", 0),
            "signing_status": ingest_verdict.get("signing_status"),
        },
        "verify": verify_payload,
        "boundary": {
            "observer_assurance": capture_manifest.get("assurance"),
            "privilege_isolated": capture_manifest.get("assurance") == ASSURANCE_A2,
            "isolation": capture_manifest.get("isolation"),
            "note": _boundary_note(capture_manifest),
        },
    }
    _write_json(out_dir / "evidence-run-summary.json", payload)
    if launched_container is not None:
        _cleanup_runner_container(str(launched_container["container_id"]))
        if cleanup_registered:
            atexit.unregister(_cleanup_runner_container)
    return payload


def _run_verify(
    args: argparse.Namespace,
    out_dir: Path,
    verify_plan: str,
    verify_evidence: str,
) -> dict[str, Any]:
    import importlib

    adapter = str(getattr(args, "verify_adapter", "generic"))
    plan = load_plan(verify_plan)
    adapter_mod = resolve(adapter)
    mod = importlib.import_module(adapter_mod)
    evidence = mod.read_evidence(verify_evidence)
    report = run_verification(plan, evidence, framework=adapter)
    report_dict = asdict(report)
    report_path = out_dir / "verify-report.json"
    _write_json(report_path, report_dict)

    operator_view_arg = str(getattr(args, "operator_view_out", "") or "")
    operator_view_path = (
        Path(operator_view_arg) if operator_view_arg else out_dir / "operator-view.md"
    )
    write_operator_view(report, str(operator_view_path))
    return {
        "decision": report_dict["decision"],
        "verdict": report_dict["verdict"],
        "assurance": report_dict["assurance"],
        "out": str(report_path),
        "operator_view_out": str(operator_view_path),
        "phase_count": len(report_dict["phases"]),
    }


def _aggregate_decision(decisions: list[str]) -> str:
    normalized = [decision.lower() for decision in decisions]
    if any(decision in {"fail", "blocked", "refuted"} for decision in normalized):
        return "blocked"
    if any(
        decision in {"inconclusive", "insufficient-evidence", "skipped"}
        for decision in normalized
    ):
        return "inconclusive"
    return "pass"


def _observer_status(capture: dict[str, Any]) -> str:
    test_output = capture.get("test_output")
    if isinstance(test_output, dict):
        return str(test_output.get("status", "unknown"))
    return "unknown"


def _boundary_note(capture_manifest: dict[str, Any]) -> str:
    if capture_manifest.get("assurance") != ASSURANCE_A2:
        return "A1 local observed evidence; not A2 privilege isolation."
    isolation = capture_manifest.get("isolation")
    if (
        isinstance(isolation, dict)
        and isolation.get("model") == CONTAINER_ISOLATION_MODEL
    ):
        return (
            "A2 isolated observed: observer-launched Docker runner was inspected "
            "and could not write the observer output."
        )
    if (
        isinstance(isolation, dict)
        and isolation.get("model") == UID_OBSERVER_LAUNCHED_ISOLATION_MODEL
    ):
        return (
            "A2 isolated observed: observer-launched uid runner ran under a "
            "different uid and could not write the observer output."
        )
    return (
        "A2 isolated observed: runner ran under a different uid and could "
        "not write the observer output."
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _restrict_observer_dir(observer_dir: Path) -> None:
    """Tighten the observer-owned dir so a different-uid runner cannot write it.

    A2 requires the runner cannot write the observer output. In the field the dir
    was auto-created group-writable by the operator's umask, which made the probe
    fail closed to A1 until a manual chmod. The tool now hardens its own dir to
    0700 so A2 is reachable without that manual step. A no-op on platforms
    without POSIX modes (e.g. native Windows), where capture stays A1 anyway.
    """
    try:
        os.chmod(observer_dir, 0o700)
    except (OSError, NotImplementedError):
        pass


def _launch_runner_container(
    runner_sandbox: Path,
    *,
    image: str,
    shell_command: str,
    hold_seconds: int,
) -> dict[str, Any]:
    if hold_seconds < 1:
        raise ValueError("--runner-container-hold-seconds must be positive")
    docker = shutil.which("docker")
    if docker is None:
        raise ValueError("docker is required for observer-launched container runner")
    sandbox = runner_sandbox.expanduser().resolve(strict=False)
    command = [
        docker,
        "run",
        "-d",
        "-v",
        f"{sandbox}:/work",
        "-w",
        "/work",
        image,
        "sh",
        "-lc",
        f"set -eu\n{shell_command}\nsleep {hold_seconds}",
    ]
    result = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or result.stdout.strip())
    container_id = result.stdout.strip()
    if not container_id:
        raise ValueError("docker run did not return a container id")
    return {
        "runtime": "docker",
        "container_id": container_id,
        "image": image,
        "command": shell_command,
        "mount": f"{sandbox}:/work",
        "hold_seconds": hold_seconds,
        "invocation": command,
    }


_RUNNER_UID_MARKER = "__DEPONE_RUNNER_UID="


def _launch_runner_user(
    runner_sandbox: Path,
    *,
    user: str,
    shell_command: str,
) -> dict[str, Any]:
    sudo = shutil.which("sudo")
    if sudo is None:
        raise ValueError("sudo is required for observer-launched uid runner")
    sandbox = runner_sandbox.expanduser().resolve(strict=False)
    id_result = subprocess.run(
        ["id", "-u", user],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if id_result.returncode != 0:
        raise ValueError(id_result.stderr.strip() or id_result.stdout.strip())
    uid_text = id_result.stdout.strip()
    if not uid_text.isdigit():
        raise ValueError(f"runner user uid is not numeric: {uid_text!r}")
    expected_uid = int(uid_text)
    command = [
        sudo,
        "-u",
        user,
        "bash",
        "-lc",
        f'set -eu\nprintf "{_RUNNER_UID_MARKER}%s\\n" "$(id -u)"\n{shell_command}',
    ]
    result = subprocess.run(
        command,
        cwd=sandbox,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or result.stdout.strip())
    observed_uid, stdout = _extract_runner_uid_marker(result.stdout)
    if observed_uid != expected_uid:
        raise ValueError(
            "observer-launched runner uid mismatch: "
            f"expected {expected_uid}, got {observed_uid}"
        )
    return {
        "runtime": "posix-sudo",
        "user": user,
        "uid": expected_uid,
        "observed_uid": observed_uid,
        "command": shell_command,
        "cwd": str(sandbox),
        "exit_code": result.returncode,
        "stdout": stdout,
        "stderr": result.stderr,
        "invocation": command,
    }


def _extract_runner_uid_marker(stdout: str) -> tuple[int, str]:
    observed_uid: int | None = None
    output_lines: list[str] = []
    for line in stdout.splitlines(keepends=True):
        if line.startswith(_RUNNER_UID_MARKER) and observed_uid is None:
            uid_text = line[len(_RUNNER_UID_MARKER) :].strip()
            if uid_text.isdigit():
                observed_uid = int(uid_text)
                continue
        output_lines.append(line)
    if observed_uid is None:
        raise ValueError("observer-launched runner did not report its uid")
    return observed_uid, "".join(output_lines)


def _maybe_write_signed_bundle(
    out_dir: Path,
    bundle: dict[str, Any],
    *,
    private_key_path: str,
    key_id: str,
    public_key_path: str,
) -> dict[str, Any]:
    if not private_key_path:
        return {
            "decision": "skipped",
            "out": None,
            "signing_status": bundle.get("signing_status"),
            "verified": None,
            "public_key": None,
        }
    try:
        signed_bundle = sign_evidence_bundle(
            bundle,
            private_key_path,
            key_id=key_id,
        )
    except DsseSigningError as exc:
        raise ValueError(exc.message) from exc
    verified = None
    if public_key_path:
        verified = verify_signed_bundle(signed_bundle, public_key_path)
        if verified is not True:
            raise ValueError("signed evidence bundle did not verify with --sign-public-key")
    signed_path = out_dir / "signed-evidence-bundle.json"
    _write_json(signed_path, signed_bundle)
    return {
        "decision": "pass",
        "out": str(signed_path),
        "signing_status": signed_bundle.get("signing_status"),
        "verified": verified,
        "public_key": public_key_path or None,
    }


def _cleanup_runner_container(container_id: str) -> None:
    docker = shutil.which("docker")
    if docker is None:
        return
    subprocess.run(
        [docker, "rm", "-f", container_id],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _self_test() -> None:
    import subprocess

    def run_git(repo: Path, args: list[str]) -> None:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr.strip() or result.stdout.strip())

    with tempfile.TemporaryDirectory(prefix="depone-evidence-run-") as temp_dir:
        root = Path(temp_dir)
        runner = root / "runner-sandbox"
        runner.mkdir()
        run_git(runner, ["init"])
        run_git(runner, ["config", "user.email", "observer@example.invalid"])
        run_git(runner, ["config", "user.name", "Observer Test"])
        (runner / "sample.txt").write_text("before\n", encoding="utf-8")
        run_git(runner, ["add", "sample.txt"])
        run_git(runner, ["commit", "-m", "seed"])
        (runner / "sample.txt").write_text("after\n", encoding="utf-8")

        source_fixture = root / "reference_adapter_shell.json"
        source_fixture.write_text(
            resource_text("fixtures/agent_fabric/reference_adapter_shell.json"),
            encoding="utf-8",
        )
        repo_root = Path(__file__).resolve().parents[2]
        plan_path = repo_root / "fixtures" / "v105-verify-wedge" / "plan.json"
        evidence_path = repo_root / "fixtures" / "v105-verify-wedge" / "evidence" / "good"
        args = argparse.Namespace(
            runner_sandbox=str(runner),
            source_fixture=str(source_fixture),
            out=str(root / "evidence-run"),
            allow_touched_file=["sample.txt"],
            verify_plan=str(plan_path),
            verify_evidence=str(evidence_path),
            verify_adapter="generic",
            operator_view_out="",
            timeout_seconds=120,
            runner_uid=None,
            runner_user="",
            runner_command="",
            runner_container_id="",
            runner_container_image="",
            runner_container_command="",
            runner_container_hold_seconds=600,
            sign_private_key="",
            sign_key_id="",
            sign_public_key="",
            verification_command=[
                sys.executable,
                "-c",
                "from pathlib import Path; assert Path('sample.txt').exists()",
            ],
            json=False,
        )
        payload = run_evidence_loop(args)
        if payload["decision"] != "pass":
            raise AssertionError(f"expected evidence-run pass: {payload}")
        # Same-uid host (no --runner-uid): must stay honestly at A1, never A2.
        if payload["boundary"]["observer_assurance"] != "A1-local-observed":
            raise AssertionError(f"same-uid run must stay A1: {payload['boundary']}")
        if payload["boundary"]["privilege_isolated"] is not False:
            raise AssertionError("same-uid run must not claim privilege isolation")
        # The tool must harden its own observer dir so A2 needs no manual chmod:
        # the auto-created dir must not be writable by a different uid.
        if hasattr(os, "getuid"):
            observer_dir = Path(str(payload["out"])) / "observer-owned"
            mode = observer_dir.stat().st_mode & 0o777
            if mode & 0o022:
                raise AssertionError(
                    f"observer dir must not be group/other writable, got {oct(mode)}"
                )
        summary_path = Path(str(payload["out"])) / "evidence-run-summary.json"
        if not summary_path.is_file():
            raise AssertionError("expected evidence-run summary")
    print("depone evidence-run --self-test: pass")
