"""Team Ledger v0 validation for Depone-observed team lanes.

This module records and validates evidence about externally-run team lanes. It
is deliberately non-executing: it does not launch agents, inspect cloud state,
or raise assurance. It only checks that a leader ledger and lane receipts have
honest, present evidence before fan-in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from depone.agent_fabric.claim_gate import canonical_hash

TEAM_LEDGER_KIND = "depone-team-ledger"
TEAM_LEDGER_SCHEMA_VERSION = "0.1"
TEAM_LEDGER_VERDICT_KIND = "depone-team-ledger-verdict"
VALID_ENV_KINDS = frozenset({"local", "container", "cloud"})
VALID_ADAPTER_KINDS = frozenset(
    {
        "codex",
        "claude-code",
        "opencode",
        "omx",
        "lazycodex",
        "github-copilot",
        "depone-native",
        "shell",
        "external",
    }
)
VALID_LANE_VERIFICATION_STATES = frozenset({"pass", "blocked"})


class TeamLedgerError(ValueError):
    """Structured Team Ledger v0 validation error."""

    def __init__(self, code: str, message: str, *, lane_id: str | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.lane_id = lane_id

    def to_record(self) -> dict[str, str]:
        record = {"code": self.code, "message": self.message}
        if self.lane_id is not None:
            record["lane_id"] = self.lane_id
        return record


def build_team_ledger_verdict(ledger: dict[str, Any], *, base_dir: Path | None = None) -> dict[str, Any]:
    """Return a fail-closed validation verdict for a Team Ledger v0 object."""

    root = base_dir or Path.cwd()
    errors: list[dict[str, str]] = []
    lane_results: list[dict[str, Any]] = []

    _validate_ledger_header(ledger, errors)
    lanes = ledger.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_LANES_REQUIRED",
                "message": "lanes must be a non-empty list",
            }
        )
        lanes = []

    seen_lane_ids: set[str] = set()
    for index, raw_lane in enumerate(lanes):
        if not isinstance(raw_lane, dict):
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_LANE_INVALID",
                    "message": f"lanes[{index}] must be an object",
                }
            )
            continue
        lane_result = _validate_lane(raw_lane, root, seen_lane_ids)
        lane_results.append(lane_result)
        errors.extend(lane_result["errors"])

    blocked = sum(1 for lane in lane_results if lane["decision"] != "pass")
    passed = len(lane_results) - blocked
    if errors:
        decision = "blocked"
    elif any(lane["verification_state"] == "blocked" for lane in lane_results):
        decision = "blocked-explicit"
    else:
        decision = "pass"

    return {
        "kind": TEAM_LEDGER_VERDICT_KIND,
        "schema_version": TEAM_LEDGER_SCHEMA_VERSION,
        "decision": decision,
        "leader_objective": ledger.get("leader_objective"),
        "lane_count": len(lane_results),
        "passed_lane_count": passed,
        "blocked_lane_count": blocked,
        "lane_results": lane_results,
        "errors": errors,
        "source_hashes": {"team_ledger": canonical_hash(ledger)},
        "boundary": {
            "executes_commands": False,
            "launches_agents": False,
            "calls_live_models": False,
            "inspects_cloud_runtime": False,
            "raises_assurance": False,
            "approves_merge": False,
        },
    }


def validate_team_ledger(ledger: dict[str, Any], *, base_dir: Path | None = None) -> list[dict[str, str]]:
    """Return validation errors for a Team Ledger v0 object."""

    return list(build_team_ledger_verdict(ledger, base_dir=base_dir)["errors"])


def _validate_ledger_header(ledger: dict[str, Any], errors: list[dict[str, str]]) -> None:
    if ledger.get("kind") != TEAM_LEDGER_KIND:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_KIND_INVALID",
                "message": f"kind must be {TEAM_LEDGER_KIND}",
            }
        )
    if ledger.get("schema_version") != TEAM_LEDGER_SCHEMA_VERSION:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_SCHEMA_VERSION_INVALID",
                "message": f"schema_version must be {TEAM_LEDGER_SCHEMA_VERSION}",
            }
        )
    _require_non_empty_string(ledger, "leader_objective", errors)
    _require_non_empty_string(ledger, "leader_id", errors)
    _require_non_empty_string(ledger, "start_commit", errors)
    _require_non_empty_string(ledger, "stop_rule", errors)


def _validate_lane(
    lane: dict[str, Any],
    base_dir: Path,
    seen_lane_ids: set[str],
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    lane_id = lane.get("lane_id") if isinstance(lane.get("lane_id"), str) else ""
    lane_error_id = lane_id or "<missing>"

    _require_non_empty_string(lane, "lane_id", errors, lane_id=lane_error_id)
    if lane_id:
        if lane_id in seen_lane_ids:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_LANE_ID_DUPLICATE",
                    "message": "lane_id must be unique",
                    "lane_id": lane_id,
                }
            )
        seen_lane_ids.add(lane_id)

    _require_non_empty_string(lane, "objective", errors, lane_id=lane_error_id)
    _require_non_empty_string(lane, "start_commit", errors, lane_id=lane_error_id)
    _require_non_empty_string(lane, "end_commit", errors, lane_id=lane_error_id)
    _require_non_empty_string(lane, "evidence_dir", errors, lane_id=lane_error_id)

    _validate_choice(lane, "env_kind", VALID_ENV_KINDS, errors, lane_id=lane_error_id)
    _validate_choice(
        lane,
        "runner_adapter_kind",
        VALID_ADAPTER_KINDS,
        errors,
        lane_id=lane_error_id,
    )
    _validate_choice(
        lane,
        "team_adapter_kind",
        VALID_ADAPTER_KINDS,
        errors,
        lane_id=lane_error_id,
    )
    state = _validate_choice(
        lane,
        "verification_state",
        VALID_LANE_VERIFICATION_STATES,
        errors,
        lane_id=lane_error_id,
    )

    evidence_dir = lane.get("evidence_dir")
    evidence_dir_exists = False
    if isinstance(evidence_dir, str) and evidence_dir:
        evidence_path = (base_dir / evidence_dir).resolve(strict=False)
        evidence_dir_exists = evidence_path.is_dir()
        if state == "pass" and not evidence_dir_exists:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_EVIDENCE_DIR_MISSING",
                    "message": "passed lane evidence_dir must exist",
                    "lane_id": lane_error_id,
                }
            )

    evidence_next_verdict = lane.get("evidence_next_verdict")
    evidence_next_summary = _validate_evidence_next_verdict(
        evidence_next_verdict,
        base_dir,
        errors,
        lane_id=lane_error_id,
        required=state == "pass",
    )

    blocked_reason = lane.get("blocked_reason")
    if state == "blocked" and (not isinstance(blocked_reason, str) or not blocked_reason.strip()):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_BLOCKED_REASON_REQUIRED",
                "message": "blocked lane must include a non-empty blocked_reason",
                "lane_id": lane_error_id,
            }
        )

    verification_artifacts = lane.get("verification_artifacts", [])
    if verification_artifacts is None:
        verification_artifacts = []
    if not isinstance(verification_artifacts, list) or not all(
        isinstance(item, str) and item for item in verification_artifacts
    ):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_VERIFICATION_ARTIFACTS_INVALID",
                "message": "verification_artifacts must be a list of non-empty strings",
                "lane_id": lane_error_id,
            }
        )
        verification_artifacts = []

    pr_url = lane.get("pr_url")
    if pr_url is not None and not isinstance(pr_url, str):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_PR_URL_INVALID",
                "message": "pr_url must be a string when present",
                "lane_id": lane_error_id,
            }
        )

    return {
        "lane_id": lane_error_id,
        "env_kind": lane.get("env_kind"),
        "runner_adapter_kind": lane.get("runner_adapter_kind"),
        "team_adapter_kind": lane.get("team_adapter_kind"),
        "verification_state": state,
        "decision": "blocked" if errors or state == "blocked" else "pass",
        "evidence_dir": evidence_dir,
        "evidence_dir_exists": evidence_dir_exists,
        "evidence_next_verdict": evidence_next_verdict,
        "evidence_next": evidence_next_summary,
        "verification_artifact_count": len(verification_artifacts),
        "errors": errors,
    }


def _require_non_empty_string(
    value: dict[str, Any],
    field: str,
    errors: list[dict[str, str]],
    *,
    lane_id: str | None = None,
) -> None:
    if not isinstance(value.get(field), str) or not str(value.get(field)).strip():
        record = {
            "code": "ERR_TEAM_LEDGER_REQUIRED_FIELD_MISSING",
            "message": f"{field} must be a non-empty string",
        }
        if lane_id is not None:
            record["lane_id"] = lane_id
        errors.append(record)


def _validate_choice(
    value: dict[str, Any],
    field: str,
    valid: frozenset[str],
    errors: list[dict[str, str]],
    *,
    lane_id: str,
) -> str | None:
    raw = value.get(field)
    if isinstance(raw, str) and raw in valid:
        return raw
    errors.append(
        {
            "code": "ERR_TEAM_LEDGER_CHOICE_INVALID",
            "message": f"{field} must be one of {sorted(valid)}",
            "lane_id": lane_id,
        }
    )
    return raw if isinstance(raw, str) else None


def _validate_evidence_next_verdict(
    evidence_next_verdict: Any,
    base_dir: Path,
    errors: list[dict[str, str]],
    *,
    lane_id: str,
    required: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": evidence_next_verdict if isinstance(evidence_next_verdict, str) else None,
        "decision": None,
        "blocking_reason_count": None,
    }
    if not isinstance(evidence_next_verdict, str) or not evidence_next_verdict.strip():
        if required:
            errors.append(
                {
                    "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_REQUIRED",
                    "message": "passed lane must include evidence_next_verdict",
                    "lane_id": lane_id,
                }
            )
        return summary

    verdict_path = Path(evidence_next_verdict)
    if verdict_path.is_absolute():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_PATH_INVALID",
                "message": "evidence_next_verdict must be relative to the ledger base directory",
                "lane_id": lane_id,
            }
        )
        return summary

    resolved = (base_dir / verdict_path).resolve(strict=False)
    base_resolved = base_dir.resolve(strict=False)
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_PATH_INVALID",
                "message": "evidence_next_verdict must stay under the ledger base directory",
                "lane_id": lane_id,
            }
        )
        return summary

    if not resolved.is_file():
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_MISSING",
                "message": "evidence_next_verdict file must exist",
                "lane_id": lane_id,
            }
        )
        return summary

    try:
        verdict = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_INVALID",
                "message": f"evidence_next_verdict must be readable JSON: {exc}",
                "lane_id": lane_id,
            }
        )
        return summary
    if not isinstance(verdict, dict):
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_INVALID",
                "message": "evidence_next_verdict root must be an object",
                "lane_id": lane_id,
            }
        )
        return summary

    blocking_reasons = verdict.get("blocking_reasons", [])
    if not isinstance(blocking_reasons, list):
        blocking_reasons = []
    summary["decision"] = verdict.get("decision")
    summary["blocking_reason_count"] = len(blocking_reasons)
    if verdict.get("command") != "evidence-next":
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_VERDICT_INVALID",
                "message": "evidence_next_verdict command must be evidence-next",
                "lane_id": lane_id,
            }
        )
    if verdict.get("decision") != "continue" or blocking_reasons:
        errors.append(
            {
                "code": "ERR_TEAM_LEDGER_EVIDENCE_NEXT_NOT_CONTINUE",
                "message": "evidence_next_verdict must have decision=continue and no blocking_reasons",
                "lane_id": lane_id,
            }
        )
    return summary


def build_sample_team_ledger(evidence_dir: str) -> dict[str, Any]:
    """Return a minimal valid Team Ledger v0 object for tests and examples."""

    return {
        "kind": TEAM_LEDGER_KIND,
        "schema_version": TEAM_LEDGER_SCHEMA_VERSION,
        "leader_objective": "Validate a small team fan-in before integration",
        "leader_id": "leader-fixed",
        "start_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "end_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "stop_rule": "fan-in only after every lane passes or is explicitly blocked",
        "lanes": [
            {
                "lane_id": "lane-docs",
                "objective": "Document the control plane direction",
                "env_kind": "local",
                "runner_adapter_kind": "codex",
                "team_adapter_kind": "omx",
                "start_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "end_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "evidence_dir": evidence_dir,
                "pr_url": "",
                "verification_state": "pass",
                "verification_artifacts": ["unittest"],
            }
        ],
    }


def _self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as temp_text:
        root = Path(temp_text)
        evidence = root / "lane-evidence"
        evidence.mkdir()
        evidence_next = evidence / "evidence-next-verdict.json"
        evidence_next.write_text(
            json.dumps(
                {
                    "command": "evidence-next",
                    "schema_version": "1.0",
                    "decision": "continue",
                    "blocking_reasons": [],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        ledger = build_sample_team_ledger("lane-evidence")
        ledger["lanes"][0]["evidence_next_verdict"] = "lane-evidence/evidence-next-verdict.json"
        verdict = build_team_ledger_verdict(ledger, base_dir=root)
        if verdict["decision"] != "pass":
            raise AssertionError("valid ledger must pass")

        missing = build_sample_team_ledger("missing")
        missing["lanes"][0]["evidence_next_verdict"] = "missing/evidence-next-verdict.json"
        missing_verdict = build_team_ledger_verdict(missing, base_dir=root)
        if missing_verdict["decision"] != "blocked":
            raise AssertionError("passed lane with missing evidence must block")

        blocked = build_sample_team_ledger("missing")
        blocked["lanes"][0]["verification_state"] = "blocked"
        blocked["lanes"][0]["blocked_reason"] = "lane waiting on peer merge"
        blocked_verdict = build_team_ledger_verdict(blocked, base_dir=root)
        if blocked_verdict["decision"] != "blocked-explicit":
            raise AssertionError("explicitly blocked lane must fan in as blocked-explicit")

        invalid = build_sample_team_ledger("lane-evidence")
        invalid["lanes"][0]["env_kind"] = "bare-metal"
        invalid_verdict = build_team_ledger_verdict(invalid, base_dir=root)
        if invalid_verdict["decision"] != "blocked":
            raise AssertionError("invalid env kind must block")


def read_team_ledger(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Team Ledger root must be an object: {path}")
    return value
