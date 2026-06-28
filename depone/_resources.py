"""Installed-package resource helpers for Depone fixtures."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    # importlib.resources.abc only exists on 3.11+; keep it type-check-only so
    # the package still imports on the declared 3.10 floor. Annotations are lazy
    # via `from __future__ import annotations`, so runtime never evaluates them.
    from importlib.resources.abc import Traversable


def _resource(relpath: str) -> Traversable:
    clean = relpath.replace("\\", "/").strip("/")
    resource = resources.files("depone")
    for part in clean.split("/"):
        if part:
            resource = resource / part
    return resource


def resource_text(relpath: str) -> str:
    return _resource(relpath).read_text(encoding="utf-8")


def resource_bytes(relpath: str) -> bytes:
    return _resource(relpath).read_bytes()


def resource_children(relpath: str) -> list[Traversable]:
    resource = _resource(relpath)
    if not resource.is_dir():
        return []
    return list(resource.iterdir())


@contextmanager
def resource_path(relpath: str) -> Iterator[Path]:
    with resources.as_file(_resource(relpath)) as path:
        yield path
