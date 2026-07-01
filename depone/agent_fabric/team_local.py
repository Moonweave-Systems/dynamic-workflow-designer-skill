"""Minimal local Depone team loop over existing safe primitives."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any

from depone.agent_fabric.claim_gate import canonical_hash
from depone.agent_fabric.team_dry_run import TeamDryRunError, build_team_dry_run
from depone.agent_fabric.team_launch_preflight import build_team_launch_preflight
from depone.agent_fabric.team_ledger import build_team_ledger_verdict
from depone.agent_fabric.team_shell_lane_launch import (
    DEFAULT_AGENT_ROLE_ID,
    TeamShellLaneLaunchError,
    run_shell_lane_command,
    write_receipt,
)
from depone.agent_fabric.team_worktree_prep import build_team_worktree_prep
from depone.agent_fabric.worktree_receipt import WorktreeReceiptError, build_worktree_lane_receipt
from depone.cli.evidence_next import evaluate_evidence_dir

TEAM_LOCAL_RUN_LEDGER_KIND = "depone-team-local-run-ledger"
TEAM_LOCAL_SCHEMA_VERSION = "0.1"
_ALLOWED_RUNTIME_TOKENS = frozenset({"repo_root", "worktree_path", "evidence_dir", "evidence_dir_abs", "lane_id"})
_RUNTIME_TOKEN_PATTERN = re.compile(r"\{([^{}]+)\}")


class TeamLocalError(ValueError):
    """Structured team-local orchestration error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def run_team_local(
    plan: dict[str, Any],
    *,
    allowlist: dict[str, object] | None,
    repo_root: Path,
    worktree_root: Path,
    out_dir: Path,
    base_commit: str | None = None,
    create_worktree: bool = False,
    execute_lanes: bool = False,
    timeout_seconds: int = 120,
    agent_role_id: str = DEFAULT_AGENT_ROLE_ID,
) -> dict[str, Any]:
    """Run one fail-closed local team loop and write a run ledger artifact."""

    if not isinstance(plan, dict):
        raise TeamLocalError("ERR_TEAM_LOCAL_PLAN_INVALID", "plan root must be an object")
    _ensure_relative(out_dir, "out_dir")
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {}
    lane_records: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []

    try:
        dry_run = build_team_dry_run(plan, out_dir=out_dir)
    except TeamDryRunError as exc:
        raise TeamLocalError(exc.code, exc.message) from exc
    _write_json(out_dir / "team-dry-run.json", dry_run)
    artifacts["team_dry_run"] = (out_dir / "team-dry-run.json").as_posix()

    effective_base_commit = base_commit or str(dry_run.get("base_commit") or "")
    launch_intent = "launch-ready" if execute_lanes else "plan-only"
    adapter_availability = {"shell": {"available": True, "source": "team-local"}}
    preflight = build_team_launch_preflight(
        dry_run,
        repo_root=repo_root,
        base_commit=effective_base_commit,
        launch_intent=launch_intent,
        adapter_availability=adapter_availability,
    )
    _write_json(out_dir / "team-launch-preflight.json", preflight)
    artifacts["team_launch_preflight"] = (out_dir / "team-launch-preflight.json").as_posix()
    if preflight["decision"] != "pass":
        blocking_reasons.extend(_error_messages(preflight.get("errors"), "preflight blocked"))

    worktree_prep = build_team_worktree_prep(
        preflight,
        repo_root=repo_root,
        worktree_root=worktree_root,
        create_worktree=create_worktree,
    )
    _write_json(out_dir / "team-worktree-prep.json", worktree_prep)
    artifacts["team_worktree_prep"] = (out_dir / "team-worktree-prep.json").as_posix()
    if worktree_prep["decision"] != "pass":
        blocking_reasons.extend(_error_messages(worktree_prep.get("errors"), "worktree prep blocked"))

    team_ledger = dict(dry_run["team_ledger"])
    team_ledger["stop_rule"] = "team-local stops on first blocked lane"
    team_ledger["lanes"] = [dict(lane) for lane in team_ledger.get("lanes", [])]
    plan_lanes = _plan_lanes_by_id(plan)
    prep_lanes = _prep_lanes_by_id(worktree_prep)

    stopped = preflight["decision"] != "pass" or worktree_prep["decision"] != "pass"
    for lane in team_ledger["lanes"]:
        if not isinstance(lane, dict):
            continue
        lane_id = str(lane.get("lane_id") or "")
        lane_record: dict[str, Any] = {
            "lane_id": lane_id,
            "decision": "blocked",
            "blocking_reasons": [],
            "shell_receipt": None,
            "shell_transcript": None,
            "shell_receipts": [],
            "shell_transcripts": [],
            "worktree_receipt": None,
            "evidence_next_verdict": None,
        }
        lane["verification_state"] = "blocked"
        lane["blocked_reason"] = "team-local stopped before lane execution"
        if stopped:
            lane_record["blocking_reasons"].append("upstream primitive blocked before lane execution")
            lane_records.append(lane_record)
            continue
        if not execute_lanes:
            lane_record["blocking_reasons"].append("execute_lanes is false; no shell command was run")
            lane["blocked_reason"] = "execute_lanes is false; no shell command was run"
            lane_records.append(lane_record)
            stopped = True
            continue
        if allowlist is None:
            lane_record["blocking_reasons"].append("allowlist is required when execute_lanes is true")
            lane["blocked_reason"] = "allowlist is required when execute_lanes is true"
            lane_records.append(lane_record)
            stopped = True
            continue

        plan_lane = plan_lanes.get(lane_id, {})
        try:
            command_ids = _command_ids_for_lane(plan_lane)
        except TeamLocalError as exc:
            lane_record["blocking_reasons"].append(f"{exc.code}: {exc.message}")
            lane["blocked_reason"] = lane_record["blocking_reasons"][0]
            lane_records.append(lane_record)
            stopped = True
            continue

        prep_lane = prep_lanes.get(lane_id, {})
        worktree_path = prep_lane.get("worktree_path")
        if not isinstance(worktree_path, str) or not worktree_path:
            lane_record["blocking_reasons"].append("prepared worktree path is missing")
            lane["blocked_reason"] = "prepared worktree path is missing"
            lane_records.append(lane_record)
            stopped = True
            continue

        lane_dir = out_dir / lane_id
        commands_dir = lane_dir / "commands"
        command_receipts: list[dict[str, Any]] = []
        shell_receipt_paths: list[str] = []
        shell_transcript_paths: list[str] = []
        try:
            runtime_allowlist = _expand_allowlist_runtime_tokens(
                allowlist,
                repo_root=repo_root,
                worktree_path=Path(worktree_path),
                evidence_dir=Path(lane_id),
                evidence_dir_abs=lane_dir,
                lane_id=lane_id,
            )
            for index, command_id in enumerate(command_ids):
                receipt_path = commands_dir / f"{_command_artifact_stem(command_id)}-receipt.json"
                transcript_path = commands_dir / f"{_command_artifact_stem(command_id)}-transcript.json"
                shell_receipt = run_shell_lane_command(
                    allowlist=runtime_allowlist,
                    command_id=command_id,
                    cwd=Path(worktree_path),
                    transcript_path=transcript_path,
                    timeout_seconds=timeout_seconds,
                    agent_role_id=agent_role_id,
                )
                write_receipt(receipt_path, shell_receipt)
                command_receipts.append(shell_receipt)
                shell_receipt_paths.append(receipt_path.as_posix())
                shell_transcript_paths.append(transcript_path.as_posix())
                if index == 0:
                    legacy_receipt_path = lane_dir / "shell-receipt.json"
                    legacy_transcript_path = lane_dir / "shell-transcript.json"
                    write_receipt(legacy_receipt_path, shell_receipt)
                    legacy_transcript_path.write_text(
                        transcript_path.read_text(encoding="utf-8"),
                        encoding="utf-8",
                    )
                    lane_record["shell_receipt"] = legacy_receipt_path.as_posix()
                    lane_record["shell_transcript"] = legacy_transcript_path.as_posix()
                if shell_receipt.get("decision") != "pass":
                    lane_record["blocking_reasons"].append(f"shell command {command_id} did not pass")
                    break
        except (TeamShellLaneLaunchError, TeamLocalError) as exc:
            code = getattr(exc, "code", exc.__class__.__name__)
            message = getattr(exc, "message", str(exc))
            lane_record["blocking_reasons"].append(f"{code}: {message}")
            lane["blocked_reason"] = lane_record["blocking_reasons"][0]
            lane_records.append(lane_record)
            stopped = True
            continue

        lane_record["shell_receipts"] = shell_receipt_paths
        lane_record["shell_transcripts"] = shell_transcript_paths
        if lane_record["blocking_reasons"]:
            lane["blocked_reason"] = lane_record["blocking_reasons"][0]
            lane_records.append(lane_record)
            stopped = True
            continue

        evidence_dir = out_dir / lane_id
        evidence_next = evaluate_evidence_dir(evidence_dir)
        evidence_next_path = evidence_dir / "evidence-next-verdict.json"
        _write_json(evidence_next_path, evidence_next)
        lane_record["evidence_next_verdict"] = evidence_next_path.as_posix()
        lane["evidence_next_verdict"] = f"{lane_id}/evidence-next-verdict.json"
        lane["verification_artifacts"] = ["team-shell-lane-launch", "evidence-next", "worktree-lane-receipt"]
        lane["touched_files"] = _repo_relative_list(plan_lane.get("touched_files"))
        if evidence_next.get("decision") == "continue" and not evidence_next.get("blocking_reasons"):
            try:
                worktree_receipt = build_worktree_lane_receipt(
                    worktree=Path(worktree_path),
                    base_commit=effective_base_commit,
                    evidence_dir=Path(lane_id),
                    commands=command_receipts,
                )
            except WorktreeReceiptError as exc:
                lane_record["blocking_reasons"].append(f"{exc.code}: {exc.message}")
                lane["blocked_reason"] = lane_record["blocking_reasons"][0]
                stopped = True
            else:
                worktree_receipt_path = lane_dir / "worktree-receipt.json"
                _write_json(worktree_receipt_path, worktree_receipt)
                lane_record["worktree_receipt"] = worktree_receipt_path.as_posix()
                lane["worktree_receipt"] = f"{lane_id}/worktree-receipt.json"
                lane["end_commit"] = str(worktree_receipt.get("head_commit") or lane.get("end_commit") or "")
                if not lane["touched_files"]:
                    lane["touched_files"] = _repo_relative_list(worktree_receipt.get("changed_files"))
                lane["verification_state"] = "pass"
                lane.pop("blocked_reason", None)
                lane_record["decision"] = "pass"
        else:
            reasons = evidence_next.get("blocking_reasons")
            if isinstance(reasons, list) and reasons:
                lane_record["blocking_reasons"].extend(str(reason) for reason in reasons)
            else:
                lane_record["blocking_reasons"].append("evidence-next did not continue")
            lane["blocked_reason"] = "; ".join(lane_record["blocking_reasons"])
            stopped = True
        if lane_record["blocking_reasons"] and lane_record["decision"] != "pass":
            lane["blocked_reason"] = "; ".join(lane_record["blocking_reasons"])
        lane_records.append(lane_record)
        if stopped:
            break

    team_ledger_path = out_dir / "team-ledger.json"
    _write_json(team_ledger_path, team_ledger)
    artifacts["team_ledger"] = team_ledger_path.as_posix()
    verdict = build_team_ledger_verdict(team_ledger, base_dir=out_dir)
    verdict_path = out_dir / "team-ledger-verdict.json"
    _write_json(verdict_path, verdict)
    artifacts["team_ledger_verdict"] = verdict_path.as_posix()

    decision = "pass" if verdict.get("decision") == "pass" else "blocked"
    if verdict.get("errors"):
        blocking_reasons.extend(_error_messages(verdict.get("errors"), "team ledger blocked"))
    for lane_record in lane_records:
        blocking_reasons.extend(str(reason) for reason in lane_record.get("blocking_reasons", []))

    run_ledger = {
        "kind": TEAM_LOCAL_RUN_LEDGER_KIND,
        "schema_version": TEAM_LOCAL_SCHEMA_VERSION,
        "decision": decision,
        "leader_objective": dry_run.get("leader_objective"),
        "base_commit": effective_base_commit,
        "out_dir": out_dir.as_posix(),
        "lane_count": verdict.get("lane_count", 0),
        "passed_lane_count": verdict.get("passed_lane_count", 0),
        "blocked_lane_count": verdict.get("blocked_lane_count", 0),
        "artifacts": artifacts,
        "lanes": lane_records,
        "blocking_reasons": _dedupe(blocking_reasons),
        "source_hashes": {
            "plan": canonical_hash(plan),
            **({"allowlist": canonical_hash(allowlist)} if allowlist is not None else {}),
            "team_dry_run": canonical_hash(dry_run),
            "team_launch_preflight": canonical_hash(preflight),
            "team_worktree_prep": canonical_hash(worktree_prep),
            "team_ledger": canonical_hash(team_ledger),
        },
        "boundary": {
            "launches_agents": False,
            "calls_live_models": False,
            "executes_unlisted_shell_commands": False,
            "executes_allowlisted_shell_commands": bool(execute_lanes and allowlist is not None),
            "creates_worktrees": create_worktree,
            "raises_assurance": False,
            "approves_merge": False,
        },
    }
    run_ledger_path = out_dir / "team-run-ledger.json"
    _write_json(run_ledger_path, run_ledger)
    run_ledger["artifacts"]["team_run_ledger"] = run_ledger_path.as_posix()
    _write_json(run_ledger_path, run_ledger)
    return run_ledger


def validate_team_local_run_ledger(
    run_ledger: dict[str, Any], *, base_dir: Path = Path(".")
) -> list[str]:
    """Validate a committed team-local run ledger without re-running lanes."""

    errors: list[str] = []
    if run_ledger.get("kind") != TEAM_LOCAL_RUN_LEDGER_KIND:
        errors.append("kind must be depone-team-local-run-ledger")
    if run_ledger.get("schema_version") != TEAM_LOCAL_SCHEMA_VERSION:
        errors.append("schema_version must be 0.1")
    if run_ledger.get("decision") not in {"pass", "blocked"}:
        errors.append("decision must be pass or blocked")

    boundary = run_ledger.get("boundary")
    if not isinstance(boundary, dict):
        errors.append("boundary must be an object")
    else:
        expected_false = {
            "launches_agents",
            "calls_live_models",
            "executes_unlisted_shell_commands",
            "raises_assurance",
            "approves_merge",
        }
        for key in expected_false:
            if boundary.get(key) is not False:
                errors.append(f"boundary.{key} must be false")
        for key in ("executes_allowlisted_shell_commands", "creates_worktrees"):
            if not isinstance(boundary.get(key), bool):
                errors.append(f"boundary.{key} must be boolean")

    artifacts = run_ledger.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("artifacts must be an object")
        artifacts = {}
    source_hashes = run_ledger.get("source_hashes")
    if not isinstance(source_hashes, dict):
        errors.append("source_hashes must be an object")
        source_hashes = {}

    hash_artifact_names = {
        "team_dry_run",
        "team_launch_preflight",
        "team_worktree_prep",
        "team_ledger",
    }
    for name, raw_path in artifacts.items():
        if not isinstance(raw_path, str) or not raw_path:
            errors.append(f"artifacts.{name} must be a non-empty string")
            continue
        artifact_path = _validated_artifact_path(raw_path)
        if artifact_path is None:
            errors.append(f"artifacts.{name} must be repo-relative")
            continue
        full_path = base_dir / artifact_path
        if not full_path.is_file():
            errors.append(f"artifacts.{name} file is missing")
            continue
        if name in hash_artifact_names:
            try:
                artifact_value = json.loads(full_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"artifacts.{name} is not readable JSON: {exc}")
                continue
            expected_hash = source_hashes.get(name)
            if expected_hash != canonical_hash(artifact_value):
                errors.append(f"source_hashes.{name} mismatch")

    lanes = run_ledger.get("lanes")
    if not isinstance(lanes, list):
        errors.append("lanes must be a list")
    else:
        for index, lane in enumerate(lanes, start=1):
            if not isinstance(lane, dict):
                errors.append(f"lanes[{index}] must be an object")
                continue
            if lane.get("decision") not in {"pass", "blocked"}:
                errors.append(f"lanes[{index}].decision must be pass or blocked")
            for key in ("shell_receipt", "shell_transcript", "evidence_next_verdict", "worktree_receipt"):
                raw_path = lane.get(key)
                if raw_path is None:
                    continue
                if not isinstance(raw_path, str):
                    errors.append(f"lanes[{index}].{key} must be a string or null")
                    continue
                artifact_path = _validated_artifact_path(raw_path)
                if artifact_path is None:
                    errors.append(f"lanes[{index}].{key} must be repo-relative")
                elif not (base_dir / artifact_path).is_file():
                    errors.append(f"lanes[{index}].{key} file is missing")
            for key in ("shell_receipts", "shell_transcripts"):
                raw_paths = lane.get(key)
                if raw_paths is None:
                    continue
                if not isinstance(raw_paths, list) or not all(isinstance(item, str) for item in raw_paths):
                    errors.append(f"lanes[{index}].{key} must be a list of strings")
                    continue
                for item_index, raw_path in enumerate(raw_paths, start=1):
                    artifact_path = _validated_artifact_path(raw_path)
                    if artifact_path is None:
                        errors.append(f"lanes[{index}].{key}[{item_index}] must be repo-relative")
                    elif not (base_dir / artifact_path).is_file():
                        errors.append(f"lanes[{index}].{key}[{item_index}] file is missing")

    return errors


def _command_ids_for_lane(plan_lane: dict[str, Any]) -> list[str]:
    command_id = plan_lane.get("command_id")
    command_ids = plan_lane.get("command_ids")
    has_command_id = isinstance(command_id, str) and bool(command_id.strip())
    has_command_ids = command_ids is not None
    if has_command_id and has_command_ids:
        raise TeamLocalError(
            "ERR_TEAM_LOCAL_COMMAND_IDS_INVALID",
            "lane must not set both command_id and command_ids",
        )
    if has_command_id:
        return [_normalize_command_id(command_id)]
    if not isinstance(command_ids, list) or not command_ids:
        raise TeamLocalError(
            "ERR_TEAM_LOCAL_COMMAND_IDS_INVALID",
            "lane command_ids must be a non-empty list or command_id must be set",
        )
    return [_normalize_command_id(item) for item in command_ids]


def _normalize_command_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TeamLocalError(
            "ERR_TEAM_LOCAL_COMMAND_ID_INVALID",
            "command ids must be non-empty strings",
        )
    command_id = value.strip()
    path = PurePosixPath(command_id)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise TeamLocalError(
            "ERR_TEAM_LOCAL_COMMAND_ID_INVALID",
            "command ids must be path-safe names",
        )
    return command_id


def _command_artifact_stem(command_id: str) -> str:
    return _normalize_command_id(command_id)


def _expand_allowlist_runtime_tokens(
    allowlist: dict[str, object],
    *,
    repo_root: Path,
    worktree_path: Path,
    evidence_dir: Path,
    evidence_dir_abs: Path,
    lane_id: str,
) -> dict[str, object]:
    replacements = {
        "repo_root": repo_root.resolve(strict=False).as_posix(),
        "worktree_path": worktree_path.resolve(strict=False).as_posix(),
        "evidence_dir": evidence_dir.as_posix(),
        "evidence_dir_abs": evidence_dir_abs.resolve(strict=False).as_posix(),
        "lane_id": lane_id,
    }
    expanded = deepcopy(allowlist)
    commands = expanded.get("commands")
    if not isinstance(commands, list):
        return expanded
    for command in commands:
        if not isinstance(command, dict):
            continue
        argv = command.get("argv")
        if not isinstance(argv, list):
            continue
        command["argv"] = [
            _expand_runtime_tokens(part, replacements) if isinstance(part, str) else part
            for part in argv
        ]
    return expanded


def _expand_runtime_tokens(value: str, replacements: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if token not in _ALLOWED_RUNTIME_TOKENS:
            raise TeamLocalError(
                "ERR_TEAM_LOCAL_TOKEN_INVALID",
                f"runtime token {{{token}}} is not allowed",
            )
        return replacements[token]

    return _RUNTIME_TOKEN_PATTERN.sub(replace, value)


def _plan_lanes_by_id(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lanes = plan.get("lanes")
    if not isinstance(lanes, list):
        return {}
    by_id: dict[str, dict[str, Any]] = {}
    for index, lane in enumerate(lanes, start=1):
        if not isinstance(lane, dict):
            continue
        raw_id = lane.get("lane_id")
        lane_id = raw_id.strip() if isinstance(raw_id, str) and raw_id.strip() else f"lane-{index}"
        by_id[lane_id] = lane
    return by_id


def _prep_lanes_by_id(worktree_prep: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lanes = worktree_prep.get("lanes")
    if not isinstance(lanes, list):
        return {}
    return {
        str(lane.get("lane_id")): lane
        for lane in lanes
        if isinstance(lane, dict) and isinstance(lane.get("lane_id"), str)
    }


def _repo_relative_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    paths: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        path = PurePosixPath(item)
        if path.is_absolute() or ".." in path.parts:
            continue
        paths.append(path.as_posix())
    return paths


def _ensure_relative(path: Path, label: str) -> None:
    posix = PurePosixPath(path.as_posix())
    if path.is_absolute() or ".." in posix.parts:
        raise TeamLocalError("ERR_TEAM_LOCAL_PATH_INVALID", f"{label} must be repo-relative")


def _validated_artifact_path(raw_path: str) -> Path | None:
    path = Path(raw_path)
    posix = PurePosixPath(raw_path)
    if path.is_absolute() or ".." in posix.parts:
        return None
    return path


def _error_messages(value: object, fallback: str) -> list[str]:
    if not isinstance(value, list):
        return [fallback]
    messages: list[str] = []
    for item in value:
        if isinstance(item, dict):
            code = item.get("code")
            message = item.get("message")
            if isinstance(code, str) and isinstance(message, str):
                messages.append(f"{code}: {message}")
            elif isinstance(message, str):
                messages.append(message)
        elif isinstance(item, str):
            messages.append(item)
    return messages or [fallback]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(repo: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def _self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="depone-team-local-") as temp_text:
        temp = Path(temp_text)
        repo = temp / "repo"
        repo.mkdir()
        _git(repo, ["init"])
        (repo / "README.md").write_text("# test\n", encoding="utf-8")
        _git(repo, ["add", "README.md"])
        _git(
            repo,
            [
                "-c",
                "user.name=Depone",
                "-c",
                "user.email=depone@example.invalid",
                "commit",
                "-m",
                "init",
            ],
        )
        head = _git(repo, ["rev-parse", "HEAD"])
        plan = {
            "leader_objective": "Run one local lane",
            "base_commit": head,
            "lanes": [
                {
                    "lane_id": "lane-1",
                    "objective": "Run a safe shell command",
                    "runner_adapter_kind": "shell",
                    "team_adapter_kind": "depone-native",
                    "planned_worktree": "lane-1-worktree",
                    "command_id": "ok",
                    "touched_files": ["README.md"],
                }
            ],
        }
        allowlist = {"commands": [{"id": "ok", "argv": ["python3", "-c", "print('ok')"]}]}
        current_dir = Path.cwd()
        os.chdir(temp)
        try:
            ledger = run_team_local(
                plan,
                allowlist=allowlist,
                repo_root=repo,
                worktree_root=temp / "worktrees",
                out_dir=Path("out/team-local"),
                create_worktree=False,
                execute_lanes=True,
            )
        finally:
            os.chdir(current_dir)
        if ledger["decision"] != "blocked":
            raise AssertionError("missing worktree must block before shell execution")
        if ledger["boundary"]["launches_agents"] is not False:
            raise AssertionError("team-local must not launch agents")
        errors = validate_team_local_run_ledger(ledger, base_dir=temp)
        if errors:
            raise AssertionError(f"team-local ledger validation failed: {errors}")
