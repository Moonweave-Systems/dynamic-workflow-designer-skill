"""Stdlib-only shell lane command adapter with argv allowlist receipts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

TEAM_SHELL_LANE_LAUNCH_KIND = "depone-team-shell-lane-launch"
TEAM_SHELL_LANE_LAUNCH_SCHEMA_VERSION = "0.1"
PROHIBITED_EXECUTABLES = frozenset({"codex", "claude", "opencode"})


class TeamShellLaneLaunchError(Exception):
    """Structured shell lane launch failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def run_shell_lane_command(
    *,
    allowlist: dict[str, object],
    command_id: str,
    cwd: Path,
    transcript_path: Path,
    timeout_seconds: int = 120,
) -> dict[str, object]:
    """Run one allowlisted argv command and return a hash-bound receipt."""

    argv = _resolve_allowlisted_argv(allowlist, command_id)
    _validate_timeout(timeout_seconds)
    resolved_cwd = _resolve_cwd(cwd)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)

    completed = subprocess.run(
        argv,
        cwd=resolved_cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    stdout = completed.stdout
    stderr = completed.stderr
    transcript = {
        "command_id": command_id,
        "cwd": resolved_cwd.as_posix(),
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout_text": stdout.decode("utf-8", errors="replace"),
        "stderr_text": stderr.decode("utf-8", errors="replace"),
    }
    transcript_path.write_text(
        json.dumps(transcript, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "kind": TEAM_SHELL_LANE_LAUNCH_KIND,
        "schema_version": TEAM_SHELL_LANE_LAUNCH_SCHEMA_VERSION,
        "decision": "pass" if completed.returncode == 0 else "failed",
        "command_id": command_id,
        "cwd": resolved_cwd.as_posix(),
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256_bytes(stdout),
        "stderr_sha256": _sha256_bytes(stderr),
        "transcript_path": transcript_path.as_posix(),
        "transcript_sha256": _sha256_bytes(transcript_path.read_bytes()),
        "allowlist_sha256": _canonical_hash(allowlist),
        "boundary": {
            "uses_shell": False,
            "uses_argv_allowlist": True,
            "executes_commands": True,
            "launches_agents": False,
            "calls_live_models": False,
            "allows_arbitrary_shell_string": False,
        },
    }


def load_allowlist(path: Path) -> dict[str, object]:
    """Load a JSON allowlist object from disk."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_ALLOWLIST_READ_FAILED",
            str(exc),
        ) from exc
    except json.JSONDecodeError as exc:
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_ALLOWLIST_JSON_INVALID",
            str(exc),
        ) from exc
    if not isinstance(value, dict):
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_ALLOWLIST_INVALID",
            "allowlist must be a JSON object",
        )
    return value


def write_receipt(path: Path, receipt: dict[str, object]) -> None:
    """Write a shell lane launch receipt."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_allowlisted_argv(allowlist: dict[str, object], command_id: str) -> list[str]:
    if not command_id.strip():
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_COMMAND_ID_REQUIRED",
            "command_id must be a non-empty string",
        )
    commands = allowlist.get("commands")
    if not isinstance(commands, list):
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_ALLOWLIST_COMMANDS_INVALID",
            "allowlist.commands must be a list",
        )
    selected: dict[str, object] | None = None
    for command in commands:
        if not isinstance(command, dict):
            raise TeamShellLaneLaunchError(
                "ERR_TEAM_SHELL_LANE_ALLOWLIST_COMMAND_INVALID",
                "allowlist command entries must be objects",
            )
        if command.get("id") == command_id:
            selected = command
            break
    if selected is None:
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_COMMAND_NOT_ALLOWED",
            "command_id is not present in allowlist",
        )
    argv = selected.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(part, str) and part for part in argv):
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_ARGV_INVALID",
            "allowlisted argv must be a non-empty list of non-empty strings",
        )
    normalized = list(argv)
    executable = Path(normalized[0]).name.lower()
    if executable in PROHIBITED_EXECUTABLES:
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_AGENT_EXECUTABLE_BLOCKED",
            "Codex, Claude, and OpenCode executables are not permitted in shell lane launch",
        )
    return normalized


def _resolve_cwd(cwd: Path) -> Path:
    try:
        resolved = cwd.resolve(strict=True)
    except OSError as exc:
        raise TeamShellLaneLaunchError("ERR_TEAM_SHELL_LANE_CWD_INVALID", str(exc)) from exc
    if not resolved.is_dir():
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_CWD_INVALID",
            "cwd must be an existing directory",
        )
    return resolved


def _validate_timeout(timeout_seconds: int) -> None:
    if timeout_seconds < 1 or timeout_seconds > 3600:
        raise TeamShellLaneLaunchError(
            "ERR_TEAM_SHELL_LANE_TIMEOUT_INVALID",
            "timeout_seconds must be between 1 and 3600",
        )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def _self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        allowlist = {
            "commands": [
                {
                    "id": "hello",
                    "argv": [sys.executable, "-c", "print('hello shell lane')"],
                }
            ]
        }
        receipt = run_shell_lane_command(
            allowlist=allowlist,
            command_id="hello",
            cwd=root,
            transcript_path=root / "transcript.json",
            timeout_seconds=30,
        )
        assert receipt["decision"] == "pass"
        assert receipt["exit_code"] == 0
        assert receipt["boundary"]["uses_shell"] is False
        assert receipt["boundary"]["allows_arbitrary_shell_string"] is False
        assert Path(str(receipt["transcript_path"])).exists()
