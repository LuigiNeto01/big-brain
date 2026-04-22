"""`big-brain notes ...` — inspect, search, and delete notes."""

from __future__ import annotations

import typer
from rich.markdown import Markdown
from rich.table import Table

from core.config import load_config
from core.notes import (
    NoteDeleteError,
    NoteNotFoundError,
    delete_note,
    list_notes,
    load_note,
    search_notes,
)
from utils.ui import console, error_panel, status_line


def _require_initialized():
    config = load_config()
    if not config.is_initialized:
        error_panel(
            "Big Brain nao inicializado",
            "Execute `big-brain init` antes de usar comandos de notas.",
        )
        raise typer.Exit(code=1)
    return config


def cmd_list() -> None:
    """List every note in the project."""
    config = _require_initialized()
    notes = list_notes(config.notes_dir)

    if not notes:
        status_line("📝", "Nenhuma nota ainda — comece com `big-brain chat`.")
        return

    table = Table(title=f"Big Brain — Notas ({config.project_config.project_name})")
    table.add_column("Slug", style="cyan")
    table.add_column("Tipo")
    table.add_column("Titulo")
    table.add_column("Atualizado", style="dim")
    for note in notes:
        table.add_row(note.slug, note.type, note.title, note.updated.isoformat())
    console.print(table)


def cmd_show(slug: str) -> None:
    """Render a single note with its frontmatter and body."""
    config = _require_initialized()
    try:
        note = load_note(config.notes_dir, slug)
    except NoteNotFoundError as exc:
        error_panel("Nota nao encontrada", str(exc))
        raise typer.Exit(code=1) from exc

    console.rule(f"[bold cyan]{note.slug}")
    console.print(f"[bold]{note.title}[/bold]")
    console.print(
        f"[dim]tipo: {note.type} · criado: {note.created} · atualizado: {note.updated}[/dim]"
    )
    if note.tags:
        console.print(f"[dim]tags: {', '.join(note.tags)}[/dim]")
    if note.links:
        console.print(f"[dim]links: {', '.join(note.links)}[/dim]")
    console.print()
    console.print(Markdown(note.body))


def cmd_search(query: str) -> None:
    """Search notes by a substring across title, tags, body."""
    config = _require_initialized()
    hits = search_notes(config.notes_dir, query)

    if not hits:
        status_line("🔎", f"Nenhum resultado para: {query}")
        return

    table = Table(title=f"Big Brain — Resultados para: {query}")
    table.add_column("Slug", style="cyan")
    table.add_column("Tipo")
    table.add_column("Titulo")
    for note in hits:
        table.add_row(note.slug, note.type, note.title)
    console.print(table)


def cmd_delete(slug: str, confirm: bool) -> None:
    """Delete a note by slug. Requires --confirm."""
    config = _require_initialized()
    try:
        delete_note(config.notes_dir, slug, confirmed=confirm)
    except NoteNotFoundError as exc:
        error_panel("Nota nao encontrada", str(exc))
        raise typer.Exit(code=1) from exc
    except NoteDeleteError as exc:
        error_panel("Confirmacao necessaria", str(exc))
        raise typer.Exit(code=2) from exc
    status_line("🗑️", f"Nota removida: {slug}")
