from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from depone.agent_fabric.team_launch_preflight import (
    TEAM_LAUNCH_PREFLIGHT_KIND,
    build_team_launch_preflight,
    build_team_launch_preflight_ledger,
    validate_team_launch_preflight,
)


class AgentFabricTeamLaunchPreflightTests(unittest.TestCase):
    def _fixture(self) -> dict[str, object]:
        return json.loads(Path("docs/team-dry-run/team-dry-run.json").read_text(encoding="utf-8"))

    def _preflight(self, team_dry_run: dict[str, object] | None = None, **kwargs: object) -> dict[str, object]:
        dry_run = team_dry_run if team_dry_run is not None else self._fixture()
        return build_team_launch_preflight(
            dry_run,
            repo_root=Path("."),
            base_commit=str(dry_run["base_commit"]),
            launch_intent=str(kwargs.pop("launch_intent", "plan-only")),
            adapter_availability=kwargs.pop(
                "adapter_availability",
                {"codex": {"available": False, "source": "declared-unavailable"}},
            ),
        )

    def assertBlockedBy(self, payload: dict[str, object], code: str) -> None:
        self.assertEqual(payload["decision"], "blocked")
        self.assertIn(code, {error["code"] for error in payload["errors"]})

    def test_build_team_launch_preflight_passes_for_team_dry_run_fixture(self) -> None:
        team_dry_run = self._fixture()
        base_commit = team_dry_run["base_commit"]

        payload = build_team_launch_preflight(
            team_dry_run,
            repo_root=Path("."),
            base_commit=str(base_commit),
            launch_intent="plan-only",
            adapter_availability={"codex": {"available": False, "source": "declared-unavailable"}},
        )

        self.assertEqual(payload["kind"], TEAM_LAUNCH_PREFLIGHT_KIND)
        self.assertEqual(payload["decision"], "pass")
        self.assertEqual(payload["launch_intent"], "plan-only")
        self.assertFalse(payload["boundary"]["launches_agents"])
        self.assertFalse(payload["boundary"]["creates_worktrees"])
        self.assertEqual(validate_team_launch_preflight(payload), [])

    def test_build_team_launch_preflight_ledger_binds_preflight_lanes(self) -> None:
        team_dry_run = self._fixture()
        preflight = self._preflight(team_dry_run)

        ledger = build_team_launch_preflight_ledger(team_dry_run, preflight)

        self.assertEqual(ledger["kind"], "depone-team-ledger")
        self.assertIn("team_launch_preflight", ledger["source_hashes"])
        self.assertEqual(
            [lane["lane_id"] for lane in ledger["lanes"]],
            [lane["lane_id"] for lane in preflight["lanes"]],
        )
        self.assertEqual(
            [lane["planned_worktree"] for lane in ledger["lanes"]],
            [lane["planned_worktree"] for lane in preflight["lanes"]],
        )

    def test_missing_kind_in_input_blocks(self) -> None:
        team_dry_run = self._fixture()
        team_dry_run.pop("kind")

        self.assertBlockedBy(
            self._preflight(team_dry_run),
            "ERR_TEAM_LAUNCH_PREFLIGHT_DRY_RUN_KIND_INVALID",
        )

    def test_mismatched_base_commit_blocks(self) -> None:
        team_dry_run = self._fixture()

        payload = build_team_launch_preflight(
            team_dry_run,
            repo_root=Path("."),
            base_commit="deadbeef",
            launch_intent="plan-only",
            adapter_availability={"codex": {"available": True, "source": "test"}},
        )

        self.assertBlockedBy(payload, "ERR_TEAM_LAUNCH_PREFLIGHT_BASE_COMMIT_MISMATCH")

    def test_absolute_planned_worktree_blocks(self) -> None:
        team_dry_run = self._fixture()
        team_dry_run["lanes"][0]["planned_worktree"] = "/tmp/lane"

        self.assertBlockedBy(
            self._preflight(team_dry_run),
            "ERR_TEAM_LAUNCH_PREFLIGHT_PLANNED_WORKTREE_INVALID",
        )

    def test_path_traversal_planned_worktree_blocks(self) -> None:
        team_dry_run = self._fixture()
        team_dry_run["lanes"][0]["planned_worktree"] = "../lane"

        self.assertBlockedBy(
            self._preflight(team_dry_run),
            "ERR_TEAM_LAUNCH_PREFLIGHT_PLANNED_WORKTREE_INVALID",
        )

    def test_duplicate_lane_ids_block(self) -> None:
        team_dry_run = self._fixture()
        team_dry_run["lanes"][1]["lane_id"] = team_dry_run["lanes"][0]["lane_id"]

        self.assertBlockedBy(
            self._preflight(team_dry_run),
            "ERR_TEAM_LAUNCH_PREFLIGHT_LANE_ID_DUPLICATE",
        )

    def test_missing_lane_evidence_path_blocks(self) -> None:
        team_dry_run = self._fixture()
        team_dry_run["lanes"][0].pop("evidence_dir")

        self.assertBlockedBy(
            self._preflight(team_dry_run),
            "ERR_TEAM_LAUNCH_PREFLIGHT_LANE_EVIDENCE_PATH_REQUIRED",
        )

    def test_missing_adapter_availability_blocks_for_launch_ready(self) -> None:
        payload = self._preflight(launch_intent="launch-ready", adapter_availability=None)

        self.assertBlockedBy(
            payload,
            "ERR_TEAM_LAUNCH_PREFLIGHT_ADAPTER_AVAILABILITY_REQUIRED",
        )

    def test_unavailable_adapter_blocks_for_launch_ready(self) -> None:
        payload = self._preflight(
            launch_intent="launch-ready",
            adapter_availability={"codex": {"available": False, "source": "declared-unavailable"}},
        )

        self.assertBlockedBy(payload, "ERR_TEAM_LAUNCH_PREFLIGHT_ADAPTER_UNAVAILABLE")

    def test_unavailable_adapter_does_not_block_plan_only_when_not_required(self) -> None:
        team_dry_run = copy.deepcopy(self._fixture())
        for lane in team_dry_run["lanes"]:
            lane["availability_required"] = False

        payload = self._preflight(
            team_dry_run,
            launch_intent="plan-only",
            adapter_availability={"codex": {"available": False, "source": "declared-unavailable"}},
        )

        self.assertEqual(payload["decision"], "pass")


    def test_invalid_launch_intent_blocks(self) -> None:
        team_dry_run = self._fixture()

        payload = build_team_launch_preflight(
            team_dry_run,
            repo_root=Path("."),
            base_commit=str(team_dry_run["base_commit"]),
            launch_intent="run-now",
            adapter_availability={"codex": {"available": True, "source": "test"}},
        )

        self.assertBlockedBy(payload, "ERR_TEAM_LAUNCH_PREFLIGHT_LAUNCH_INTENT_INVALID")

    def test_executing_dry_run_boundary_blocks(self) -> None:
        team_dry_run = self._fixture()
        team_dry_run["boundary"]["launches_agents"] = True

        self.assertBlockedBy(
            self._preflight(team_dry_run),
            "ERR_TEAM_LAUNCH_PREFLIGHT_DRY_RUN_BOUNDARY_INVALID",
        )

    def test_launch_ready_uses_runner_adapter_kind_from_embedded_ledger(self) -> None:
        team_dry_run = self._fixture()
        team_dry_run["team_ledger"]["lanes"][0]["runner_adapter_kind"] = "opencode"

        payload = self._preflight(
            team_dry_run,
            launch_intent="launch-ready",
            adapter_availability={
                "codex": {"available": True, "source": "test"},
                "opencode": {"available": False, "source": "test"},
            },
        )

        self.assertBlockedBy(payload, "ERR_TEAM_LAUNCH_PREFLIGHT_ADAPTER_UNAVAILABLE")
        self.assertEqual(payload["lanes"][0]["runner_adapter_kind"], "opencode")

    def test_missing_next_command_lane_blocks(self) -> None:
        team_dry_run = self._fixture()
        team_dry_run["next_commands"] = [team_dry_run["next_commands"][0]]

        self.assertBlockedBy(
            self._preflight(team_dry_run),
            "ERR_TEAM_LAUNCH_PREFLIGHT_NEXT_COMMANDS_INCOMPLETE",
        )

    def test_validate_team_launch_preflight_reports_bad_boundary(self) -> None:
        payload = self._preflight()
        payload["boundary"]["launches_agents"] = True

        errors = validate_team_launch_preflight(payload)

        self.assertIn(
            "ERR_TEAM_LAUNCH_PREFLIGHT_BOUNDARY_INVALID",
            {error["code"] for error in errors},
        )


if __name__ == "__main__":
    unittest.main()
