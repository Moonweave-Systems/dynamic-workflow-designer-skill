"""Keelplane — workflow designer + cross-platform evidence verifier.

Keelplane designs multi-agent workflows and verifies their execution evidence.
It does not execute agents. It makes runs from other frameworks trustworthy.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure existing scripts/ are importable during migration phase.
_PKG_ROOT = Path(__file__).resolve().parent          # keelplane/
_REPO_ROOT = _PKG_ROOT.parent                        # repo root
_SCRIPTS = _REPO_ROOT / "scripts"
if _SCRIPTS.is_dir() and str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

__version__ = "104.0.0"
