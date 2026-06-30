"""Machine-readable Agent Fabric operating contract validation."""

from __future__ import annotations

import json
from pathlib import Path

from depone.agent_fabric.claim_gate import canonical_hash

AGENT_OPERATING_CONTRACT_KIND = "depone-agent-operating-contract"
AGENT_OPERATING_CONTRACT_SCHEMA_VERSION = "0.1"
AGENT_OPERATING_CONTRACT_ID = "depone-agent-operating-contract.v0.1"
AGENT_OPERATING_CONTRACT_PATH = Path("packaging/depone-agent-operating-contract.json")
DWM_ROLES_PATH = Path("packaging/dwm-roles.json")
V22_WORKER_ROLE_ID = "worker"
V22_REQUIRED_ROLE_FIELDS = frozenset(
    {
        "id",
        "purpose",
        "allowed_tools",
        "output_schema",
        "evidence_obligations",
        "trust_boundary",
    }
)


def build_agent_operating_contract(role_registry: dict[str, object]) -> dict[str, object]:
    """Build the minimal contract payload bound to the V22 worker role registry."""

    payload: dict[str, object] = {
        "kind": AGENT_OPERATING_CONTRACT_KIND,
        "schema_version": AGENT_OPERATING_CONTRACT_SCHEMA_VERSION,
        "contract_id": AGENT_OPERATING_CONTRACT_ID,
        "agent_contract_id": AGENT_OPERATING_CONTRACT_ID,
        "role_registry": {
            "path": DWM_ROLES_PATH.as_posix(),
            "sha256": canonical_hash(role_registry),
        },
        "v22_role_binding": {
            "source_path": DWM_ROLES_PATH.as_posix(),
            "required_role_id": V22_WORKER_ROLE_ID,
            "required_fields": sorted(V22_REQUIRED_ROLE_FIELDS),
        },
        "boundary": {
            "executes_commands": False,
            "launches_agents": False,
            "calls_live_models": False,
            "raises_assurance": False,
        },
    }
    payload["agent_contract_hash"] = _contract_payload_hash(payload)
    return payload


def load_agent_operating_contract(repo_root: Path = Path(".")) -> dict[str, object]:
    """Load the repo-local agent operating contract JSON."""

    return _load_json_object(repo_root / AGENT_OPERATING_CONTRACT_PATH, "agent operating contract")


def load_v22_role_registry(repo_root: Path = Path(".")) -> dict[str, object]:
    """Load the repo-local V22 role registry JSON."""

    return _load_json_object(repo_root / DWM_ROLES_PATH, "V22 role registry")


def validate_agent_operating_contract(
    contract: dict[str, object],
    role_registry: dict[str, object],
) -> list[dict[str, str]]:
    """Return fail-closed validation errors for the contract and V22 role binding."""

    errors: list[dict[str, str]] = []
    if not isinstance(contract, dict):
        return [_error("ERR_AGENT_CONTRACT_INVALID", "contract must be an object")]
    if not isinstance(role_registry, dict):
        return [_error("ERR_AGENT_CONTRACT_ROLE_REGISTRY_INVALID", "role registry must be an object")]

    _validate_contract_identity(contract, errors)
    _validate_boundary(contract, errors)
    _validate_contract_hash(contract, errors)
    _validate_role_registry_hash(contract, role_registry, errors)
    _validate_v22_role_binding(contract, role_registry, errors)
    return errors


def validate_repo_agent_operating_contract(repo_root: Path = Path(".")) -> list[dict[str, str]]:
    """Validate the repo-local contract against the repo-local V22 roles file."""

    try:
        contract = load_agent_operating_contract(repo_root)
        role_registry = load_v22_role_registry(repo_root)
    except ValueError as exc:
        return [_error("ERR_AGENT_CONTRACT_LOAD_FAILED", str(exc))]
    return validate_agent_operating_contract(contract, role_registry)


def build_agent_contract_facts(
    contract: dict[str, object],
    role_registry: dict[str, object],
    role_id: str,
) -> dict[str, object]:
    """Return contract facts for a lane role, or raise ValueError fail-closed."""

    errors = [
        *validate_agent_operating_contract(contract, role_registry),
        *validate_v22_role_id(role_registry, role_id),
    ]
    if errors:
        codes = ", ".join(error["code"] for error in errors)
        raise ValueError(f"agent contract facts invalid: {codes}")
    registry = contract["role_registry"]
    if not isinstance(registry, dict):
        raise ValueError("agent contract facts invalid: role_registry")
    binding = contract.get("v22_role_binding")
    if not isinstance(binding, dict) or binding.get("required_role_id") != role_id:
        raise ValueError("agent contract facts invalid: ERR_AGENT_CONTRACT_V22_ROLE_ID_MISMATCH")
    return {
        "agent_contract_id": contract["agent_contract_id"],
        "agent_contract_hash": contract["agent_contract_hash"],
        "role_id": role_id,
        "role_registry_path": registry["path"],
        "role_registry_sha256": registry["sha256"],
    }


def validate_v22_role_id(
    role_registry: dict[str, object],
    role_id: str,
) -> list[dict[str, str]]:
    """Validate that a lane role id exists in packaging/dwm-roles.json."""

    errors: list[dict[str, str]] = []
    if not isinstance(role_id, str) or not role_id.strip():
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_V22_ROLE_ID_REQUIRED",
                "role_id must be a non-empty string",
            )
        )
        return errors
    roles = role_registry.get("roles") if isinstance(role_registry, dict) else None
    if not isinstance(roles, list):
        errors.append(_error("ERR_AGENT_CONTRACT_V22_ROLES_INVALID", "role registry roles must be a list"))
        return errors
    role_ids = [role.get("id") for role in roles if isinstance(role, dict)]
    if role_id not in role_ids:
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_V22_ROLE_ID_UNKNOWN",
                f"role_id must exist in {DWM_ROLES_PATH.as_posix()}",
            )
        )
    if len(role_ids) != len(set(role_ids)):
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_V22_ROLE_ID_DUPLICATE",
                f"role ids in {DWM_ROLES_PATH.as_posix()} must be unique",
            )
        )
    return errors


def _validate_contract_identity(contract: dict[str, object], errors: list[dict[str, str]]) -> None:
    if contract.get("kind") != AGENT_OPERATING_CONTRACT_KIND:
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_KIND_INVALID",
                f"kind must be {AGENT_OPERATING_CONTRACT_KIND}",
            )
        )
    if contract.get("schema_version") != AGENT_OPERATING_CONTRACT_SCHEMA_VERSION:
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_SCHEMA_VERSION_INVALID",
                f"schema_version must be {AGENT_OPERATING_CONTRACT_SCHEMA_VERSION}",
            )
        )
    if contract.get("contract_id") != AGENT_OPERATING_CONTRACT_ID:
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_ID_INVALID",
                f"contract_id must be {AGENT_OPERATING_CONTRACT_ID}",
            )
        )
    if contract.get("agent_contract_id") != AGENT_OPERATING_CONTRACT_ID:
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_AGENT_ID_INVALID",
                f"agent_contract_id must be {AGENT_OPERATING_CONTRACT_ID}",
            )
        )


def _validate_boundary(contract: dict[str, object], errors: list[dict[str, str]]) -> None:
    boundary = contract.get("boundary")
    if not isinstance(boundary, dict):
        errors.append(_error("ERR_AGENT_CONTRACT_BOUNDARY_INVALID", "boundary must be an object"))
        return
    for key in ("executes_commands", "launches_agents", "calls_live_models", "raises_assurance"):
        if boundary.get(key) is not False:
            errors.append(
                _error(
                    "ERR_AGENT_CONTRACT_BOUNDARY_INVALID",
                    f"boundary.{key} must be false",
                )
            )


def _validate_contract_hash(contract: dict[str, object], errors: list[dict[str, str]]) -> None:
    expected = _contract_payload_hash(contract)
    if contract.get("agent_contract_hash") != expected:
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_HASH_MISMATCH",
                "agent_contract_hash must match the canonical contract payload",
            )
        )


def _validate_role_registry_hash(
    contract: dict[str, object],
    role_registry: dict[str, object],
    errors: list[dict[str, str]],
) -> None:
    registry = contract.get("role_registry")
    if not isinstance(registry, dict):
        errors.append(_error("ERR_AGENT_CONTRACT_ROLE_REGISTRY_INVALID", "role_registry must be an object"))
        return
    if registry.get("path") != DWM_ROLES_PATH.as_posix():
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_ROLE_REGISTRY_PATH_INVALID",
                f"role_registry.path must be {DWM_ROLES_PATH.as_posix()}",
            )
        )
    if registry.get("sha256") != canonical_hash(role_registry):
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_ROLE_REGISTRY_HASH_MISMATCH",
                "role_registry.sha256 must bind packaging/dwm-roles.json",
            )
        )


def _validate_v22_role_binding(
    contract: dict[str, object],
    role_registry: dict[str, object],
    errors: list[dict[str, str]],
) -> None:
    binding = contract.get("v22_role_binding")
    if not isinstance(binding, dict):
        errors.append(_error("ERR_AGENT_CONTRACT_V22_BINDING_INVALID", "v22_role_binding must be an object"))
        return
    if binding.get("source_path") != DWM_ROLES_PATH.as_posix():
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_V22_BINDING_PATH_INVALID",
                f"v22_role_binding.source_path must be {DWM_ROLES_PATH.as_posix()}",
            )
        )
    if binding.get("required_role_id") != V22_WORKER_ROLE_ID:
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_V22_ROLE_ID_INVALID",
                f"v22_role_binding.required_role_id must be {V22_WORKER_ROLE_ID}",
            )
        )
    required_fields = binding.get("required_fields")
    if required_fields != sorted(V22_REQUIRED_ROLE_FIELDS):
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_V22_REQUIRED_FIELDS_INVALID",
                "v22_role_binding.required_fields must match the V22 role contract fields",
            )
        )

    roles = role_registry.get("roles")
    if not isinstance(roles, list):
        errors.append(_error("ERR_AGENT_CONTRACT_V22_ROLES_INVALID", "role registry roles must be a list"))
        return
    worker_role = next(
        (role for role in roles if isinstance(role, dict) and role.get("id") == V22_WORKER_ROLE_ID),
        None,
    )
    if worker_role is None:
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_V22_ROLE_MISSING",
                "V22 worker role must exist in packaging/dwm-roles.json",
            )
        )
        return
    missing = sorted(field for field in V22_REQUIRED_ROLE_FIELDS if field not in worker_role)
    if missing:
        errors.append(
            _error(
                "ERR_AGENT_CONTRACT_V22_ROLE_INCOMPLETE",
                f"V22 worker role missing fields: {', '.join(missing)}",
            )
        )


def _contract_payload_hash(contract: dict[str, object]) -> str:
    payload = dict(contract)
    payload.pop("agent_contract_hash", None)
    return canonical_hash(payload)


def _load_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read {label}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"could not parse {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}
