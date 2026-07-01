from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from depone.agent_fabric.team_local import TeamLocalError, run_team_local, validate_team_local_run_ledger


class AgentFabricTeamLocalTests(unittest.TestCase):
    def test_missing_worktree_blocks_before_shell_execution(self) -> None:
        with _git_repo() as repo:
            plan = _plan(repo.head)
            allowlist = {"commands": [{"id": "ok", "argv": ["python3", "-c", "print('ok')"]}]}
            ledger = run_team_local(
                plan,
                allowlist=allowlist,
                repo_root=repo.path,
                worktree_root=repo.temp / "worktrees",
                out_dir=Path("out/team-local-test"),
                create_worktree=False,
                execute_lanes=True,
            )
            ledger_path = repo.temp / "out" / "team-local-test" / "team-run-ledger.json"
            loaded = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual([], validate_team_local_run_ledger(loaded, base_dir=repo.temp))
        self.assertEqual("blocked", ledger["decision"])
        self.assertFalse(ledger["boundary"]["launches_agents"])
        self.assertIn("team_worktree_prep", ledger["artifacts"])
        self.assertTrue(
            any("WORKTREE_PREP" in reason for reason in ledger["blocking_reasons"]),
            ledger["blocking_reasons"],
        )

    def test_prohibited_agent_executable_blocks_lane(self) -> None:
        with _git_repo() as repo:
            plan = _plan(repo.head)
            allowlist = {"commands": [{"id": "ok", "argv": ["codex", "--version"]}]}
            ledger = run_team_local(
                plan,
                allowlist=allowlist,
                repo_root=repo.path,
                worktree_root=repo.temp / "worktrees",
                out_dir=Path("out/team-local-test"),
                create_worktree=True,
                execute_lanes=True,
            )
        self.assertEqual("blocked", ledger["decision"])
        self.assertFalse(ledger["boundary"]["calls_live_models"])
        self.assertTrue(
            any("AGENT_EXECUTABLE_BLOCKED" in reason for reason in ledger["blocking_reasons"]),
            ledger["blocking_reasons"],
        )

    def test_validator_rejects_overclaiming_boundary(self) -> None:
        with _git_repo() as repo:
            plan = _plan(repo.head)
            allowlist = {"commands": [{"id": "ok", "argv": ["python3", "-c", "print('ok')"]}]}
            ledger = run_team_local(
                plan,
                allowlist=allowlist,
                repo_root=repo.path,
                worktree_root=repo.temp / "worktrees",
                out_dir=Path("out/team-local-test"),
                create_worktree=False,
                execute_lanes=True,
            )
            ledger["boundary"]["raises_assurance"] = True
            errors = validate_team_local_run_ledger(ledger, base_dir=repo.temp)
        self.assertIn("boundary.raises_assurance must be false", errors)

    def test_ordered_commands_can_produce_passed_lane(self) -> None:
        with _git_repo() as repo:
            plan = _plan(repo.head)
            plan["lanes"][0].pop("command_id")
            plan["lanes"][0]["command_ids"] = [
                "write-marker",
                "evidence-run",
                "git-add",
                "git-commit",
            ]
            plan["lanes"][0]["touched_files"] = ["team-local-marker.txt"]
            allowlist = {
                "commands": [
                    {
                        "id": "write-marker",
                        "argv": [
                            sys.executable,
                            "-c",
                            (
                                "from pathlib import Path; "
                                "Path('team-local-marker.txt').write_text('ok\\n', encoding='utf-8')"
                            ),
                        ],
                    },
                    {
                        "id": "evidence-run",
                        "argv": [
                            sys.executable,
                            "-m",
                            "depone",
                            "evidence-run",
                            "--runner-sandbox",
                            ".",
                            "--source-fixture",
                            "{repo_root}/depone/fixtures/agent_fabric/reference_adapter_shell.json",
                            "--out",
                            "{evidence_dir_abs}",
                            "--allow-touched-file",
                            "team-local-marker.txt",
                            "--json",
                            "--",
                            sys.executable,
                            "-c",
                            "from pathlib import Path; assert Path('team-local-marker.txt').exists()",
                        ],
                    },
                    {"id": "git-add", "argv": ["git", "add", "team-local-marker.txt"]},
                    {
                        "id": "git-commit",
                        "argv": [
                            "git",
                            "-c",
                            "user.name=Depone",
                            "-c",
                            "user.email=depone@example.invalid",
                            "commit",
                            "-m",
                            "team local marker",
                        ],
                    },
                ]
            }

            ledger = run_team_local(
                plan,
                allowlist=allowlist,
                repo_root=repo.path,
                worktree_root=repo.temp / "worktrees",
                out_dir=Path("out/team-local-test"),
                create_worktree=True,
                execute_lanes=True,
            )

            self.assertEqual("pass", ledger["decision"], ledger["blocking_reasons"])
            self.assertEqual(1, ledger["passed_lane_count"])
            self.assertEqual(0, ledger["blocked_lane_count"])
            lane_record = ledger["lanes"][0]
            self.assertEqual(4, len(lane_record["shell_receipts"]))
            self.assertEqual([], validate_team_local_run_ledger(ledger, base_dir=repo.temp))
            verdict = json.loads(
                (repo.temp / "out" / "team-local-test" / "team-ledger-verdict.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("pass", verdict["decision"])

    def test_unknown_runtime_token_blocks_before_shell_execution(self) -> None:
        with _git_repo() as repo:
            plan = _plan(repo.head)
            allowlist = {"commands": [{"id": "ok", "argv": [sys.executable, "-c", "{bad_token}"]}]}
            with self.assertRaises(TeamLocalError) as raised:
                run_team_local(
                    plan,
                    allowlist=allowlist,
                    repo_root=repo.path,
                    worktree_root=repo.temp / "worktrees",
                    out_dir=Path("out/team-local-test"),
                    create_worktree=True,
                    execute_lanes=True,
                )
        self.assertEqual("ERR_TEAM_LOCAL_TOKEN_INVALID", raised.exception.code)


def _plan(head: str) -> dict[str, object]:
    return {
        "leader_objective": "Run one local lane",
        "base_commit": head,
        "lanes": [
            {
                "lane_id": "lane-1",
                "objective": "Run safe command",
                "runner_adapter_kind": "shell",
                "team_adapter_kind": "depone-native",
                "planned_worktree": "lane-1-worktree",
                "command_id": "ok",
                "touched_files": ["README.md"],
            }
        ],
    }


class _Repo:
    def __init__(self, temp: Path, path: Path, head: str) -> None:
        self.temp = temp
        self.path = path
        self.head = head


class _git_repo:
    def __enter__(self) -> _Repo:
        self._tmp = tempfile.TemporaryDirectory(prefix="depone-team-local-test-")
        temp = Path(self._tmp.name)
        self._cwd = Path.cwd()
        os.chdir(temp)
        repo = temp / "repo"
        repo.mkdir()
        _git(repo, "init")
        (repo / "README.md").write_text("# test\n", encoding="utf-8")
        _git(repo, "add", "README.md")
        _git(
            repo,
            "-c",
            "user.name=Depone",
            "-c",
            "user.email=depone@example.invalid",
            "commit",
            "-m",
            "init",
        )
        return _Repo(temp=temp, path=repo, head=_git(repo, "rev-parse", "HEAD"))

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        os.chdir(self._cwd)
        self._tmp.cleanup()


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed.stdout.strip()


if __name__ == "__main__":
    unittest.main()
