"""Bidirectional wikilink detection and creation across notes."""

from __future__ import annotations

import re
from pathlib import Path

from core.notes import (
    Note,
    list_notes,
    load_note,
    note_path,
    update_index,
    write_note_file,
)


WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")


def _candidate_variants(note: Note) -> list[str]:
    """Return searchable variants of a note's identity (title + slug)."""
    variants = {note.title, note.slug}
    return [v for v in variants if v]


def _already_linked(body: str, target_slug: str) -> bool:
    """Return True when `[[target_slug]]` already appears in the body."""
    for match in WIKILINK_RE.findall(body):
        if match.strip() == target_slug:
            return True
    return False


def _wikilinkify(body: str, title: str, slug: str) -> tuple[str, bool]:
    """Replace the first plain-text occurrence of title or slug with `[[slug]]`.

    Only touches matches that are NOT already inside existing wikilinks.
    Returns the updated body and whether a replacement was made.
    """
    if _already_linked(body, slug):
        return body, False

    for needle in (title, slug):
        if not needle:
            continue
        pattern = re.compile(
            r"(?<!\[\[)" + re.escape(needle) + r"(?!\]\])",
            flags=re.IGNORECASE,
        )
        updated, count = pattern.subn(f"[[{slug}]]", body, count=1)
        if count > 0:
            return updated, True

    return body, False


def detect_and_link(notes_dir: Path, note: Note) -> list[str]:
    """Detect references to other notes in `note.body` and link them both ways.

    For each other note whose title or slug appears in `note.body`:
      - Replace the first plain occurrence in `note.body` with `[[other.slug]]`
      - Add the other slug to `note.links`
      - Add the current note's slug to the other note's `links` and persist

    Returns the list of newly created link slugs.
    """
    created: list[str] = []
    others = [other for other in list_notes(notes_dir) if other.slug != note.slug]

    updated_body = note.body
    current_links = list(note.links)

    for other in others:
        for variant in _candidate_variants(other):
            new_body, replaced = _wikilinkify(updated_body, variant, other.slug)
            if replaced:
                updated_body = new_body
                if other.slug not in current_links:
                    current_links.append(other.slug)
                created.append(other.slug)
                _apply_inverse_link(notes_dir, other.slug, note.slug)
                break

    note.body = updated_body
    note.links = current_links
    write_note_file(notes_dir, note)
    update_index(notes_dir)
    return created


def _apply_inverse_link(notes_dir: Path, target_slug: str, source_slug: str) -> None:
    """Ensure `source_slug` is listed in the target note's links metadata."""
    path = note_path(notes_dir, target_slug)
    if not path.exists():
        return
    target = load_note(notes_dir, target_slug)
    if source_slug in target.links:
        return
    target.links.append(source_slug)
    write_note_file(notes_dir, target)


def extract_wikilinks(body: str) -> list[str]:
    """Return all wikilink targets in a markdown body."""
    return [match.strip() for match in WIKILINK_RE.findall(body)]


def rebuild_all_links(notes_dir: Path) -> dict[str, list[str]]:
    """Re-run link detection across every note in `notes_dir`.

    Useful after bulk edits or imports. Returns a mapping of
    slug → list of newly detected link targets.
    """
    report: dict[str, list[str]] = {}
    for note in list_notes(notes_dir):
        report[note.slug] = detect_and_link(notes_dir, note)
    return report
