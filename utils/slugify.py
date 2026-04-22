"""Slug generation for note filenames."""

from __future__ import annotations

import re
import unicodedata


def slugify(text: str, max_length: int = 80) -> str:
    """Generate a filesystem-safe slug.

    - lowercase
    - strip accents
    - spaces and separators become hyphens
    - non-alphanumeric (other than hyphens) removed
    - collapsed repeated hyphens
    - trimmed to max_length
    """
    if not text:
        return "untitled"

    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    replaced = re.sub(r"[\s_]+", "-", lowered)
    cleaned = re.sub(r"[^a-z0-9\-]", "", replaced)
    collapsed = re.sub(r"-+", "-", cleaned).strip("-")

    if not collapsed:
        return "untitled"

    return collapsed[:max_length].rstrip("-")
