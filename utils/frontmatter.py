"""YAML frontmatter parsing and writing for markdown notes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter


def read_note(path: Path) -> tuple[dict[str, Any], str]:
    """Read a markdown file with YAML frontmatter.

    Returns a tuple of (metadata_dict, body).
    """
    with path.open("r", encoding="utf-8") as handle:
        post = frontmatter.load(handle)
    return dict(post.metadata), post.content


def write_note(path: Path, metadata: dict[str, Any], body: str) -> None:
    """Write a markdown file with YAML frontmatter.

    Overwrites any existing file. The body is written as-is.
    """
    post = frontmatter.Post(body, **metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        frontmatter.dump(post, handle)
