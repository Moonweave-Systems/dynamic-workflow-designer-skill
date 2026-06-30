"""Read-only local worktree lane receipt producer for Team Ledger lanes."""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

WORKTREE_LANE_RECEIPT_KIND = "depone-worktree-lane-receipt"
WORKTREE_LANE_RECEIPT_SCHEMA_VERSION = "0.1"


class WorktreeReceiptError(ValueError):
    """Structured worktree receipt producer error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def build_worktree_lane_receipt(
    *,
    worktree: Path,
    base_commit: str,
    evidence_dir: Path,
    commands: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a deterministic local worktree receipt using read-only git state."""

    if not str(base_commit).strip():
        raise WorktreeReceiptError(
            "ERR_WORKTREE_RECEIPT_BASE_COMMIT_REQUIRED",
            "base_commit must be a non-empty git revision",
        )
    evidence_dir_text = _normalize_relative_path(evidence_dir, "evidence_dir")
    repo_root = _repo_root(worktree)
    _verify_commit(repo_root, base_commit)
    head_commit = _git(repo_root, ["rev-parse", "HEAD"])
    branch = _git(repo_root, ["branch", "--show-current"])
    if not branch:
        branch = _git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    changed_files = _git_lines(repo_root, ["diff", "--name-only", base_commit, "HEAD", "--"])
    dirty_files = _dirty_files(repo_root)
    command_receipts = commands or []
    if not isinstance(command_receipts, list) or not all(
        isinstance(item, dict) for item in command_receipts
    ):
        raise WorktreeReceiptError(
            "ERR_WORKTREE_RECEIPT_COMMAND_RECEIPTS_INVALID",
            "command receipts must be JSON objects",
        )

    return {
        "kind": WORKTREE_LANE_RECEIPT_KIND,
        "schema_version": WORKTREE_LANE_RECEIPT_SCHEMA_VERSION,
        "worktree": str(repo_root),
        "branch": branch,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "dirty": bool(dirty_files),
        "dirty_files": dirty_files,
        "changed_files": changed_files,
        "evidence_dir": evidence_dir_text,
        "command_receipts": command_receipts,
        "boundary": {
            "executes_commands": False,
            "launches_agents": False,
            "mutates_worktree": False,
            "git_read_only": True,
        },
    }


def _repo_root(worktree: Path) -> Path:
    if not worktree.is_dir():
        raise WorktreeReceiptError(
            "ERR_WORKTREE_RECEIPT_REPO_MISSING",
            "worktree must be an existing git worktree directory",
        )
    try:
        root = _git(worktree, ["rev-parse", "--show-toplevel"])
    except WorktreeReceiptError as exc:
        raise WorktreeReceiptError(
            "ERR_WORKTREE_RECEIPT_REPO_MISSING",
            "worktree must be an existing git worktree directory",
        ) from exc
    return Path(root)


def _verify_commit(repo_root: Path, revision: str) -> None:
    _git(repo_root, ["cat-file", "-e", f"{revision}^{{commit}}"])


def _dirty_files(repo_root: Path) -> list[str]:
    files: set[str] = set()
    for line in _git_lines(repo_root, ["status", "--porcelain=v1"]):
        if len(line) < 4:
            continue
        path_text = line[3:]
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        files.add(_normalize_relative_path(Path(path_text), "dirty file"))
    return sorted(files)


def _git_lines(cwd: Path, args: list[str]) -> list[str]:
    output = _git(cwd, args)
    return sorted(line for line in output.splitlines() if line)


def _git(cwd: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise WorktreeReceiptError("ERR_WORKTREE_RECEIPT_GIT_FAILED", message)
    return completed.stdout.strip()


def _normalize_relative_path(path: Path, label: str) -> str:
    text = path.as_posix()
    posix = PurePosixPath(text)
    if not text or posix.is_absolute() or ".." in posix.parts:
        raise WorktreeReceiptError(
            "ERR_WORKTREE_RECEIPT_PATH_INVALID",
            f"{label} must be a non-empty relative path",
        )
    return posix.as_posix()


def _self_test() -> None:
    import tempfile
    import subprocess as subprocess_mod

    with tempfile.TemporaryDirectory() as temp_text:
        repo = Path(temp_text) / "repo"
        repo.mkdir()
        subprocess_mod.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess_mod.run(["git", "config", "user.email", "r@x.invalid"], cwd=repo, check=True)
        subprocess_mod.run(["git", "config", "user.name", "receipt-test"], cwd=repo, check=True)
        (repo / "sample.txt").write_text("before\n", encoding="utf-8")
        subprocess_mod.run(["git", "add", "sample.txt"], cwd=repo, check=True)
        subprocess_mod.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
        base = _git(repo, ["rev-parse", "HEAD"])
        (repo / "sample.txt").write_text("after\n", encoding="utf-8")
        subprocess_mod.run(["git", "commit", "-am", "change", "-q"], cwd=repo, check=True)
        receipt = build_worktree_lane_receipt(
            worktree=repo,
            base_commit=base,
            evidence_dir=Path("lane-evidence"),
            commands=[{"command": "python3 -m unittest", "exit_code": 0}],
        )
        if receipt["changed_files"] != ["sample.txt"]:
            raise AssertionError("worktree receipt must record changed files")
        if receipt["dirty"]:
            raise AssertionError("clean committed worktree must not be dirty")
