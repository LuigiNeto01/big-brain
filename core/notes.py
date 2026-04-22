"""Note CRUD, Note model, and central _index.md management."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from utils.frontmatter import read_note, write_note
from utils.slugify import slugify


NoteType = Literal["context", "rule", "request", "decision", "feature", "bug"]
NoteSource = Literal["conversation", "inferred", "manual"]

INDEX_FILENAME = "_index.md"


class NoteError(Exception):
    """Base class for note-related errors."""


class NoteNotFoundError(NoteError):
    """Raised when a note slug cannot be located."""


class NoteDeleteError(NoteError):
    """Raised when a delete operation requires explicit confirmation."""


class Note(BaseModel):
    """A single big-brain note."""

    title: str
    type: NoteType
    project: str
    created: date
    updated: date
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    source: NoteSource = "conversation"
    summary: str = ""
    body: str = ""

    @property
    def slug(self) -> str:
        return f"{self.type}__{slugify(self.title)}"

    @property
    def filename(self) -> str:
        return f"{self.slug}.md"

    def metadata(self) -> dict[str, Any]:
        """Return a serializable metadata dict for frontmatter."""
        return {
            "title": self.title,
            "type": self.type,
            "project": self.project,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "tags": list(self.tags),
            "links": list(self.links),
            "source": self.source,
            "summary": self.summary,
        }


def _parse_note(path: Path) -> Note:
    """Load a note from disk into a Note object."""
    metadata, body = read_note(path)
    created = metadata.get("created")
    updated = metadata.get("updated")
    return Note(
        title=metadata.get("title", path.stem),
        type=metadata.get("type", "context"),
        project=metadata.get("project", ""),
        created=_coerce_date(created),
        updated=_coerce_date(updated),
        tags=list(metadata.get("tags", []) or []),
        links=list(metadata.get("links", []) or []),
        source=metadata.get("source", "manual"),
        summary=metadata.get("summary", ""),
        body=body,
    )


def _coerce_date(value: Any) -> date:
    """Accept strings or date objects and return a date."""
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return date.today()


def _ensure_notes_dir(notes_dir: Path) -> None:
    notes_dir.mkdir(parents=True, exist_ok=True)


def note_path(notes_dir: Path, slug: str) -> Path:
    """Resolve a slug to its markdown file path."""
    return notes_dir / f"{slug}.md"


def list_notes(notes_dir: Path) -> list[Note]:
    """Return every note on disk, sorted by updated date descending."""
    if not notes_dir.exists():
        return []
    notes: list[Note] = []
    for path in sorted(notes_dir.glob("*.md")):
        if path.name == INDEX_FILENAME:
            continue
        try:
            notes.append(_parse_note(path))
        except Exception:
            continue
    notes.sort(key=lambda n: n.updated, reverse=True)
    return notes


def load_note(notes_dir: Path, slug: str) -> Note:
    """Load a single note by slug."""
    path = note_path(notes_dir, slug)
    if not path.exists():
        raise NoteNotFoundError(f"Nota nao encontrada: {slug}")
    return _parse_note(path)


def search_notes(notes_dir: Path, query: str) -> list[Note]:
    """Case-insensitive search across title, tags, and body."""
    if not query:
        return list_notes(notes_dir)
    needle = query.lower()
    hits: list[Note] = []
    for note in list_notes(notes_dir):
        haystack = " ".join(
            [
                note.title.lower(),
                " ".join(tag.lower() for tag in note.tags),
                note.body.lower(),
                note.summary.lower(),
            ]
        )
        if needle in haystack:
            hits.append(note)
    return hits


def write_note_file(notes_dir: Path, note: Note) -> Path:
    """Low-level: serialize a Note to disk and return the path."""
    _ensure_notes_dir(notes_dir)
    path = note_path(notes_dir, note.slug)
    write_note(path, note.metadata(), note.body)
    return path


def create_note(notes_dir: Path, note: Note) -> Path:
    """Create a new note file. Overwrites if the slug already exists."""
    path = write_note_file(notes_dir, note)
    update_index(notes_dir)
    return path


def update_note(notes_dir: Path, slug: str, partial: dict[str, Any]) -> Note:
    """Merge `partial` into an existing note, touch `updated`, and persist."""
    existing = load_note(notes_dir, slug)
    data = existing.model_dump()
    data.update(partial)
    data["updated"] = date.today()
    merged = Note(**data)

    old_path = note_path(notes_dir, existing.slug)
    new_path = note_path(notes_dir, merged.slug)
    if old_path != new_path and old_path.exists():
        old_path.unlink()

    write_note_file(notes_dir, merged)
    update_index(notes_dir)
    return merged


def delete_note(notes_dir: Path, slug: str, confirmed: bool = False) -> bool:
    """Delete a note. Requires `confirmed=True`, else raises NoteDeleteError."""
    path = note_path(notes_dir, slug)
    if not path.exists():
        raise NoteNotFoundError(f"Nota nao encontrada: {slug}")
    if not confirmed:
        raise NoteDeleteError(
            f"Confirmacao necessaria para remover a nota '{slug}'. "
            "Execute novamente com --confirm."
        )
    path.unlink()
    update_index(notes_dir)
    return True


def update_index(notes_dir: Path) -> Path:
    """Rebuild the central `_index.md` with a table of all project notes."""
    _ensure_notes_dir(notes_dir)
    notes = list_notes(notes_dir)
    lines: list[str] = [
        "# Big Brain — Indice Central de Notas",
        "",
        "| Nota | Projeto | Tipo | Atualizado |",
        "|---|---|---|---|",
    ]
    for note in notes:
        lines.append(
            f"| [[{note.slug}]] | {note.project or '—'} | "
            f"{note.type} | {note.updated.isoformat()} |"
        )
    if not notes:
        lines.append("| _sem notas ainda_ | — | — | — |")
    lines.append("")

    path = notes_dir / INDEX_FILENAME
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
