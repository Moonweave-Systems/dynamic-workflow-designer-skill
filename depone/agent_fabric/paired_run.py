"""V126 paired-run observer and runner receipt helpers.

This module is deliberately small: it records local evidence for a real
direct-vs-governed run without calling models or executing arbitrary transcript
commands. The only command it runs is the caller-declared verification command.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from depone.agent_fabric.capture_bridge import OBSERVER_ID
from depone.agent_fabric.claim_gate import canonical_hash

RUNNER_RECEIPT_KIND = "agent-fabric-runner-receipt"
RUNNER_RECEIPT_VERSION = "1.0"
PAIRED_RUN_REPORT_KIND = "agent-fabric-paired-run-report"
PAIRED_RUN_REPORT_VERSION = "1.0"
PAIRED_RUN_READY_DECISION = "paired-run-observed"
VALID_ARMS = frozenset({"direct", "governed"})
VALID_RUNNERS = frozenset({"codex-cli", "manual"})
VALID_TEST_STATUSES = frozenset({"passed", "failed", "error"})


class PairedRunError(ValueError):
    """Structured V126 paired-run failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message

    def to_record(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _require_string(value: object, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty string")


def codex_command_candidates() -> list[str]:
    """Return Codex CLI candidates, preferring the current user's npm shim."""

    candidates: list[str] = []
    override = os.environ.get("DEPONE_CODEX_COMMAND")
    if override:
        candidates.append(override)
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(str(Path(appdata) / "npm" / "codex.cmd"))
    discovered = shutil.which("codex")
    if discovered:
        candidates.append(discovered)
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.lower()
        if key not in seen:
            deduped.append(candidate)
            seen.add(key)
    return deduped


def resolve_codex_command() -> str:
    """Find a runnable Codex CLI command without trusting stale PATH shims."""

    failures: list[str] = []
    for candidate in codex_command_candidates():
        result = subprocess.run(
            [candidate, "--version"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return candidate
        reason = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        failures.append(f"{candidate}: {reason}")
    raise PairedRunError(
        "ERR_CODEX_COMMAND_UNAVAILABLE",
        "no runnable Codex CLI command found; " + "; ".join(failures),
    )


def _git_lines(repo: Path, args: list[str]) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PairedRunError(
            "ERR_PAIRED_RUN_GIT_FAILED",
            f"git {' '.join(args)} failed: {completed.stderr.strip()}",
        )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def changed_files(repo: Path) -> list[str]:
    """Return files changed in a worktree, including untracked files."""

    files: list[str] = []
    for line in _git_lines(repo, ["status", "--porcelain"]):
        path = line[3:] if len(line) > 3 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            files.append(path.replace("\\", "/"))
    return sorted(set(files))


def diff_summary(repo: Path) -> dict[str, Any]:
    files = changed_files(repo)
    stat_lines = _git_lines(repo, ["diff", "--stat"])
    return {
        "changed_files": files,
        "changed_file_count": len(files),
        "stat": "\n".join(stat_lines),
    }


def _write_command_log(
    log_path: Path,
    *,
    command: list[str],
    cwd: Path,
    stdout: str,
    stderr: str,
    exit_code: int,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "command": command,
        "cwd": str(cwd),
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
    }
    log_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_verification_command(
    repo: Path,
    command: list[str],
    *,
    log_path: Path,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    if not command:
        raise PairedRunError(
            "ERR_PAIRED_RUN_COMMAND_MISSING",
            "verification command must not be empty",
        )
    started_at = now_utc()
    try:
        completed = subprocess.run(
            command,
            cwd=repo,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        status = "passed" if exit_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        status = "error"
    except FileNotFoundError as exc:
        exit_code = 127
        stdout = ""
        stderr = f"command not found: {exc.filename or command[0]}"
        status = "error"
    ended_at = now_utc()
    _write_command_log(
        log_path,
        command=command,
        cwd=repo,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
    )
    return {
        "command": command,
        "cwd": str(repo),
        "exit_code": exit_code,
        "log_path": str(log_path),
        "started_at": started_at,
        "ended_at": ended_at,
        "status": status,
    }


def run_codex_exec(
    repo: Path,
    *,
    arm: str,
    task_id: str,
    prompt: str,
    transcript_path: Path,
    log_path: Path,
    timeout_seconds: int = 120,
    sandbox: str = "workspace-write",
) -> dict[str, Any]:
    """Run Codex non-interactively and return a runner receipt."""

    if not prompt.strip():
        raise PairedRunError("ERR_CODEX_PROMPT_MISSING", "codex prompt must not be empty")
    codex = resolve_codex_command()
    repo = repo.resolve(strict=False)
    transcript_path = transcript_path.resolve(strict=False)
    log_path = log_path.resolve(strict=False)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        codex,
        "--sandbox",
        sandbox,
        "exec",
        "--skip-git-repo-check",
        "--cd",
        str(repo),
        "--output-last-message",
        str(transcript_path),
        "-",
    ]
    started_at = now_utc()
    try:
        completed = subprocess.run(
            command,
            cwd=repo,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    ended_at = now_utc()
    _write_command_log(
        log_path,
        command=command,
        cwd=repo,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
    )
    if not transcript_path.exists():
        transcript_path.write_text((stdout or "") + (stderr or ""), encoding="utf-8")
    return build_runner_receipt(
        runner_kind="codex-cli",
        arm=arm,
        task_id=task_id,
        worktree=str(repo),
        invocation=command,
        transcript_path=str(transcript_path),
        exit_code=exit_code,
        touched_files=changed_files(repo),
        started_at=started_at,
        ended_at=ended_at,
    )


def build_observer_capture(
    repo: Path,
    *,
    source_fixture_hash: str,
    verification_command: list[str],
    log_path: Path,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    repo = repo.resolve(strict=False)
    before = diff_summary(repo)
    receipt = run_verification_command(
        repo,
        verification_command,
        log_path=log_path,
        timeout_seconds=timeout_seconds,
    )
    after = diff_summary(repo)
    return {
        "observed_by": OBSERVER_ID,
        "source_fixture_hash": source_fixture_hash,
        "diff_summary": after,
        "touched_files": after["changed_files"],
        "test_output": {
            "status": receipt["status"],
            "command": verification_command,
            "summary": f"exit {receipt['exit_code']}",
            "pre_verification_changed_files": before["changed_files"],
        },
        "command_receipts": [receipt],
    }


def build_runner_receipt(
    *,
    runner_kind: str,
    arm: str,
    task_id: str,
    worktree: str,
    invocation: list[str],
    transcript_path: str,
    exit_code: int,
    touched_files: list[str],
    started_at: str,
    ended_at: str,
    human_intervened: bool = False,
) -> dict[str, Any]:
    receipt = {
        "kind": RUNNER_RECEIPT_KIND,
        "schema_version": RUNNER_RECEIPT_VERSION,
        "runner_kind": runner_kind,
        "arm": arm,
        "task_id": task_id,
        "worktree": worktree,
        "invocation": invocation,
        "transcript_path": transcript_path,
        "exit_code": exit_code,
        "touched_files": touched_files,
        "started_at": started_at,
        "ended_at": ended_at,
        "human_intervened": human_intervened,
    }
    receipt["source_hashes"] = {"receipt": canonical_hash(receipt)}
    return receipt


def validate_runner_receipt(receipt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if receipt.get("kind") != RUNNER_RECEIPT_KIND:
        errors.append(f"kind must be {RUNNER_RECEIPT_KIND!r}")
    if receipt.get("schema_version") != RUNNER_RECEIPT_VERSION:
        errors.append(f"schema_version must be {RUNNER_RECEIPT_VERSION!r}")
    if receipt.get("runner_kind") not in VALID_RUNNERS:
        errors.append(f"runner_kind must be one of {sorted(VALID_RUNNERS)}")
    if receipt.get("arm") not in VALID_ARMS:
        errors.append(f"arm must be one of {sorted(VALID_ARMS)}")
    for field in ("task_id", "worktree", "transcript_path", "started_at", "ended_at"):
        _require_string(receipt.get(field), field, errors)
    if not isinstance(receipt.get("exit_code"), int):
        errors.append("exit_code must be an int")
    if not isinstance(receipt.get("human_intervened"), bool):
        errors.append("human_intervened must be a bool")
    if not _string_list(receipt.get("invocation")):
        errors.append("invocation must be a non-empty list of strings")
    if not isinstance(receipt.get("touched_files"), list) or not all(
        isinstance(item, str) for item in receipt.get("touched_files", [])
    ):
        errors.append("touched_files must be a list of strings")
    source_hashes = receipt.get("source_hashes")
    if not isinstance(source_hashes, dict):
        errors.append("source_hashes must be an object")
    elif source_hashes.get("receipt") != canonical_hash(
        {key: value for key, value in receipt.items() if key != "source_hashes"}
    ):
        errors.append("source_hashes.receipt mismatch")
    return errors


def _observer_test_status(observer_capture: dict[str, Any]) -> object:
    test_output = observer_capture.get("test_output")
    if isinstance(test_output, dict):
        return test_output.get("status")
    return None


def _observer_touched_files(observer_capture: dict[str, Any]) -> list[str]:
    return _string_list(observer_capture.get("touched_files"))


def build_paired_run_report(
    *,
    task_id: str,
    direct_runner: dict[str, Any],
    direct_observer: dict[str, Any],
    governed_runner: dict[str, Any],
    governed_observer: dict[str, Any],
) -> dict[str, Any]:
    """Summarize one direct-vs-governed paired run without making claims."""

    blockers: list[dict[str, Any]] = []
    arms = [
        ("direct", direct_runner, direct_observer),
        ("governed", governed_runner, governed_observer),
    ]
    arm_reports: list[dict[str, Any]] = []
    for arm, runner, observer in arms:
        runner_errors = validate_runner_receipt(runner)
        test_status = _observer_test_status(observer)
        runner_exit_code = runner.get("exit_code")
        arm_report = {
            "arm": arm,
            "runner_kind": runner.get("runner_kind"),
            "runner_exit_code": runner_exit_code,
            "verification_status": test_status,
            "runner_touched_files": _string_list(runner.get("touched_files")),
            "observer_touched_files": _observer_touched_files(observer),
            "transcript_path": runner.get("transcript_path"),
            "runner_validation_errors": runner_errors,
        }
        arm_reports.append(arm_report)
        if runner.get("arm") != arm:
            blockers.append(
                {
                    "code": "ERR_PAIRED_RUN_ARM_MISMATCH",
                    "message": "runner receipt arm does not match report slot",
                    "arm": arm,
                    "actual": runner.get("arm"),
                }
            )
        if runner_errors:
            blockers.append(
                {
                    "code": "ERR_PAIRED_RUN_RUNNER_RECEIPT_INVALID",
                    "message": "runner receipt failed validation",
                    "arm": arm,
                    "validation_errors": runner_errors,
                }
            )
        if runner_exit_code != 0:
            blockers.append(
                {
                    "code": "ERR_PAIRED_RUN_RUNNER_FAILED",
                    "message": "runner did not exit cleanly",
                    "arm": arm,
                    "exit_code": runner_exit_code,
                }
            )
        if test_status != "passed":
            blockers.append(
                {
                    "code": "ERR_PAIRED_RUN_VERIFICATION_NOT_PASSED",
                    "message": "observer verification did not pass",
                    "arm": arm,
                    "test_status": test_status,
                }
            )

    return {
        "kind": PAIRED_RUN_REPORT_KIND,
        "schema_version": PAIRED_RUN_REPORT_VERSION,
        "decision": PAIRED_RUN_READY_DECISION
        if not blockers
        else "blocked-paired-run-not-ready",
        "task_id": task_id,
        "arms": arm_reports,
        "blockers": blockers,
        "claim_policy": "observed run only; no direct-agent superiority claim",
        "source_hashes": {
            "direct_runner": canonical_hash(direct_runner),
            "direct_observer": canonical_hash(direct_observer),
            "governed_runner": canonical_hash(governed_runner),
            "governed_observer": canonical_hash(governed_observer),
        },
        "boundary": {
            "approves_public_claim": False,
            "trust_upgrade": False,
        },
    }


def _self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        (repo / "task.txt").write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "add", "task.txt"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "seed", "--author", "Depone <depone@example.com>"],
            cwd=repo,
            check=True,
            capture_output=True,
            env={
                **os.environ,
                "GIT_COMMITTER_NAME": "Depone",
                "GIT_COMMITTER_EMAIL": "depone@example.com",
            },
        )
        (repo / "task.txt").write_text("after\n", encoding="utf-8")
        capture = build_observer_capture(
            repo,
            source_fixture_hash="fixture-hash",
            verification_command=[sys.executable, "--version"],
            log_path=root / "verification.log",
        )
        if capture["test_output"]["status"] != "passed":
            raise AssertionError("expected verification command to pass")
        if capture["touched_files"] != ["task.txt"]:
            raise AssertionError("expected touched file to be observed")
        receipt = build_runner_receipt(
            runner_kind="codex-cli",
            arm="governed",
            task_id="self-test",
            worktree=str(repo),
            invocation=["codex", "run"],
            transcript_path=str(root / "transcript.txt"),
            exit_code=0,
            touched_files=["task.txt"],
            started_at=now_utc(),
            ended_at=now_utc(),
        )
        if validate_runner_receipt(receipt):
            raise AssertionError("expected runner receipt to validate")
        previous = os.environ.get("DEPONE_CODEX_COMMAND")
        os.environ["DEPONE_CODEX_COMMAND"] = sys.executable
        try:
            if resolve_codex_command() != sys.executable:
                raise AssertionError("expected DEPONE_CODEX_COMMAND override")
        finally:
            if previous is None:
                os.environ.pop("DEPONE_CODEX_COMMAND", None)
            else:
                os.environ["DEPONE_CODEX_COMMAND"] = previous
