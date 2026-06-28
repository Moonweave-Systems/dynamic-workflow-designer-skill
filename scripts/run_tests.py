#!/usr/bin/env python3
"""Run the git-tracked unittest suite hermetically.

The suite under ``tests/`` was wired into no gate, so regressions there were
invisible. This runner wires it in, but loads only *tracked* test modules: an
untracked local draft sitting in ``tests/`` can neither break the gate nor
silently pad it, and a fresh clone runs exactly the committed suite. Falls back
to discovery when not in a git checkout.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tracked_test_modules() -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "tests/test_*.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    modules: list[str] = []
    for line in result.stdout.splitlines():
        name = line.strip()
        if name.endswith(".py"):
            modules.append(name[:-3].replace("/", "."))
    return sorted(modules)


def build_suite() -> unittest.TestSuite:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    loader = unittest.defaultTestLoader
    modules = tracked_test_modules()
    if modules:
        return loader.loadTestsFromNames(modules)
    return loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))


def run() -> int:
    result = unittest.TextTestRunner(verbosity=1).run(build_suite())
    return 0 if result.wasSuccessful() else 1


def _self_test() -> None:
    modules = tracked_test_modules()
    if not all(module.startswith("tests.") for module in modules):
        raise AssertionError("tracked test modules must import as tests.*")
    print("scripts/run_tests.py --self-test: pass")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        sys.exit(run())
