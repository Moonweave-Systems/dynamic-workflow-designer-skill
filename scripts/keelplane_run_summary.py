#!/usr/bin/env python3
"""Write a Keelplane run status summary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def hash_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_summary(run_dir: Path, out_path: Path) -> dict[str, Any]:
    status = read_json(run_dir / "status.json")
    summary = {
        "artifact_count": sum(1 for path in run_dir.iterdir() if path.is_file()),
        "decision": status.get("decision"),
        "source_hash": hash_file(run_dir / "source.txt"),
        "valid": status.get("valid"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path, help="Keelplane run directory containing status.json")
    parser.add_argument("--out", required=True, type=Path, help="Path to write summary JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    write_summary(args.run, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
