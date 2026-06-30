from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.agent_operating_contract import (
    AGENT_OPERATING_CONTRACT_ID,
    AGENT_OPERATING_CONTRACT_KIND,
    build_agent_contract_facts,
    build_agent_operating_contract,
    load_agent_operating_contract,
    load_v22_role_registry,
    validate_agent_operating_contract,
    validate_repo_agent_operating_contract,
    validate_v22_role_id,
)


class AgentFabricAgentOperatingContractTests(unittest.TestCase):
    def _roles(self) -> dict[str, object]:
        return json.loads(Path("packaging/dwm-roles.json").read_text(encoding="utf-8"))

    def _contract(self) -> dict[str, object]:
        return json.loads(
            Path("packaging/depone-agent-operating-contract.json").read_text(encoding="utf-8")
        )

    def assertBlockedBy(self, errors: list[dict[str, str]], code: str) -> None:
        self.assertIn(code, {error["code"] for error in errors})

    def test_packaged_contract_validates_against_v22_roles(self) -> None:
        contract = self._contract()
        roles = self._roles()

        self.assertEqual(contract["kind"], AGENT_OPERATING_CONTRACT_KIND)
        self.assertEqual(contract["contract_id"], AGENT_OPERATING_CONTRACT_ID)
        self.assertEqual(contract["agent_contract_id"], AGENT_OPERATING_CONTRACT_ID)
        self.assertEqual(contract["v22_role_binding"]["required_role_id"], "worker")
        self.assertEqual(validate_agent_operating_contract(contract, roles), [])
        self.assertEqual(validate_repo_agent_operating_contract(Path(".")), [])

    def test_builder_recreates_packaged_contract(self) -> None:
        roles = self._roles()

        self.assertEqual(build_agent_operating_contract(roles), self._contract())

    def test_contract_hash_tamper_blocks(self) -> None:
        contract = self._contract()
        contract["boundary"]["raises_assurance"] = True

        errors = validate_agent_operating_contract(contract, self._roles())

        self.assertBlockedBy(errors, "ERR_AGENT_CONTRACT_BOUNDARY_INVALID")
        self.assertBlockedBy(errors, "ERR_AGENT_CONTRACT_HASH_MISMATCH")

    def test_role_registry_hash_mismatch_blocks(self) -> None:
        roles = copy.deepcopy(self._roles())
        roles["roles"][0]["purpose"] = "tampered"

        errors = validate_agent_operating_contract(self._contract(), roles)

        self.assertBlockedBy(errors, "ERR_AGENT_CONTRACT_ROLE_REGISTRY_HASH_MISMATCH")

    def test_missing_v22_worker_role_blocks(self) -> None:
        roles = self._roles()
        roles["roles"] = [role for role in roles["roles"] if role["id"] != "worker"]
        contract = build_agent_operating_contract(roles)

        errors = validate_agent_operating_contract(contract, roles)

        self.assertBlockedBy(errors, "ERR_AGENT_CONTRACT_V22_ROLE_MISSING")

    def test_wrong_v22_role_id_blocks(self) -> None:
        contract = self._contract()
        contract["v22_role_binding"]["required_role_id"] = "executor"

        errors = validate_agent_operating_contract(contract, self._roles())

        self.assertBlockedBy(errors, "ERR_AGENT_CONTRACT_V22_ROLE_ID_INVALID")
        self.assertBlockedBy(errors, "ERR_AGENT_CONTRACT_HASH_MISMATCH")

    def test_real_v22_lane_role_ids_are_validated_from_registry(self) -> None:
        roles = self._roles()
        role_ids = [role["id"] for role in roles["roles"]]

        self.assertEqual(
            role_ids,
            ["planner", "explorer", "worker", "reviewer", "verifier", "operator"],
        )
        for role_id in role_ids:
            with self.subTest(role_id=role_id):
                self.assertEqual(validate_v22_role_id(roles, role_id), [])

        self.assertBlockedBy(
            validate_v22_role_id(roles, "executor"),
            "ERR_AGENT_CONTRACT_V22_ROLE_ID_UNKNOWN",
        )

    def test_agent_contract_facts_bind_contract_hash_and_role_id(self) -> None:
        facts = build_agent_contract_facts(self._contract(), self._roles(), "worker")

        self.assertEqual(facts["agent_contract_id"], AGENT_OPERATING_CONTRACT_ID)
        self.assertEqual(facts["role_id"], "worker")
        self.assertEqual(facts["role_registry_path"], "packaging/dwm-roles.json")
        self.assertRegex(str(facts["agent_contract_hash"]), r"^[0-9a-f]{64}$")
        self.assertRegex(str(facts["role_registry_sha256"]), r"^[0-9a-f]{64}$")

    def test_agent_contract_facts_fail_closed_for_unknown_role(self) -> None:
        with self.assertRaisesRegex(ValueError, "ERR_AGENT_CONTRACT_V22_ROLE_ID_UNKNOWN"):
            build_agent_contract_facts(self._contract(), self._roles(), "executor")

    def test_repo_loader_fails_closed_for_missing_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "packaging").mkdir()
            (root / "packaging" / "dwm-roles.json").write_text(
                json.dumps(self._roles()),
                encoding="utf-8",
            )

            errors = validate_repo_agent_operating_contract(root)

        self.assertBlockedBy(errors, "ERR_AGENT_CONTRACT_LOAD_FAILED")

    def test_loaders_read_repo_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "packaging").mkdir()
            (root / "packaging" / "dwm-roles.json").write_text(
                json.dumps(self._roles()),
                encoding="utf-8",
            )
            (root / "packaging" / "depone-agent-operating-contract.json").write_text(
                json.dumps(self._contract()),
                encoding="utf-8",
            )

            self.assertEqual(load_v22_role_registry(root), self._roles())
            self.assertEqual(load_agent_operating_contract(root), self._contract())


if __name__ == "__main__":
    unittest.main()
