#!/usr/bin/env python3
"""Seed the contract workspace with committed golden upstream artifacts.

The changed-tier gate consumes a few canonical artifacts produced only deep in
the full pipeline, rooted in hand-curated inputs that no step regenerates. So on
a fresh clone those inputs do not exist and --tier changed cannot run. The exact
artifacts are committed under fixtures/contract-seed/ and copied into out/ here,
making the changed tier reproducible from a clean checkout. The full tier still
regenerates and validates the real artifacts, so drift is caught there.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "fixtures" / "contract-seed"

EXPECTED = {
    "dogfood-acquisitions/v61-final/summary.json",
    "graph-timing/v78-canonical/graph-timing.json",
    "large-workflow-queue-preflight/v77-canonical/queue-preflight.json",
    "v9/v32-semantic-dogfood/status.json",
}


def seed() -> int:
    if not SEED.is_dir():
        print(f"contract seed dir missing: {SEED}", file=sys.stderr)
        return 1
    count = 0
    for src in sorted(SEED.rglob("*")):
        if not src.is_file():
            continue
        dst = ROOT / "out" / src.relative_to(SEED)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        count += 1
    print(f"seeded {count} contract-workspace artifact(s) into out/")
    return 0


def _self_test() -> None:
    present = {
        str(p.relative_to(SEED)).replace("\\", "/")
        for p in SEED.rglob("*")
        if p.is_file()
    }
    missing = EXPECTED - present
    if missing:
        raise AssertionError(f"contract seed missing: {sorted(missing)}")
    print("scripts/seed_contract_workspace.py --self-test: pass")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        sys.exit(seed())
