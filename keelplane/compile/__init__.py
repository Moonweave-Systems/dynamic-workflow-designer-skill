"""Compile workflow plans into target framework formats.

Supported targets:
  - conductor: Microsoft Conductor workflow YAML
  - langgraph: stub (not yet implemented in V104.0)
"""

from __future__ import annotations

import argparse
import sys

from keelplane.compile import conductor


def run(args: argparse.Namespace) -> None:
    """Dispatch compile to the appropriate target emitter."""
    # Self-test bypasses target requirement
    if getattr(args, "self_test", False):
        conductor.run(args)
        return

    target = args.target
    if target is None:
        print("Error: --target is required (choices: conductor, langgraph)", file=sys.stderr)
        sys.exit(1)

    if target == "conductor":
        conductor.run(args)
    elif target == "langgraph":
        print("[stub] langgraph compile not yet implemented in V104.0", file=sys.stderr)
        sys.exit(0)
    else:
        print(f"Error: unknown compile target: {target}", file=sys.stderr)
        sys.exit(1)
