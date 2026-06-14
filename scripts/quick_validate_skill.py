#!/usr/bin/env python3
"""Repo-local skill package validator.

This intentionally covers the small release-gate surface needed by this skill
without depending on the host Codex installation or PyYAML.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


ALLOWED_FRONTMATTER_KEYS = {"name", "description", "license", "allowed-tools", "metadata"}
REQUIRED_FILES = [
    "SKILL.md",
    "README.md",
    "agents/openai.yaml",
    "docs/github-research.md",
    "docs/fixture-smoke/v0-smoke.md",
    "docs/spec.md",
    "references/workflow-patterns.md",
    "references/workflow-plan-schema.md",
]
MAX_SKILL_NAME_LENGTH = 64


class ValidationError(ValueError):
    """Raised when the skill package is invalid."""


def parse_simple_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        raise ValidationError("No YAML frontmatter found")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        raise ValidationError("Invalid frontmatter format")
    result: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise ValidationError(f"Unsupported frontmatter line: {line}")
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key in result:
            raise ValidationError(f"Duplicate frontmatter key: {key}")
        result[key] = value.strip().strip("\"'")
    return result


def validate_skill(root: Path) -> None:
    for rel_path in REQUIRED_FILES:
        path = root / rel_path
        if not path.exists():
            raise ValidationError(f"Required file missing: {rel_path}")
        if not path.is_file():
            raise ValidationError(f"Required path is not a file: {rel_path}")

    frontmatter = parse_simple_frontmatter((root / "SKILL.md").read_text())
    extra = sorted(set(frontmatter) - ALLOWED_FRONTMATTER_KEYS)
    if extra:
        raise ValidationError(f"Unexpected SKILL.md frontmatter keys: {extra}")
    for key in ["name", "description"]:
        if key not in frontmatter:
            raise ValidationError(f"Missing SKILL.md frontmatter key: {key}")
        if not isinstance(frontmatter[key], str) or not frontmatter[key].strip():
            raise ValidationError(f"SKILL.md frontmatter key is empty: {key}")

    name = frontmatter["name"].strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValidationError("Skill name must be hyphen-case")
    if len(name) > MAX_SKILL_NAME_LENGTH:
        raise ValidationError(f"Skill name is too long: {len(name)}")

    description = frontmatter["description"].strip()
    if len(description.split()) < 10:
        raise ValidationError("Skill description is too short to route reliably")


def self_test() -> None:
    good = "---\nname: sample-skill\ndescription: This sample skill has enough words to route a realistic request.\n---\n"
    frontmatter = parse_simple_frontmatter(good)
    if frontmatter["name"] != "sample-skill":
        raise ValidationError("self-test failed: frontmatter parse mismatch")
    try:
        parse_simple_frontmatter("name: missing-boundary\n")
    except ValidationError:
        pass
    else:
        raise ValidationError("self-test failed: missing boundary passed")
    print("quick skill validator self-test: pass")


def main() -> int:
    root = Path(".")
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        self_test()
        return 0
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    try:
        validate_skill(root)
    except ValidationError as exc:
        print(f"quick_validate_skill: {exc}", file=sys.stderr)
        return 1
    print("Skill is valid!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
