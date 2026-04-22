"""`big-brain status` — show project config, notes, and last big-brain commit."""

from __future__ import annotations

import typer
from pathlib import Path

from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError
from rich.table import Table

from core.config import load_config
from core.notes import list_notes
from utils.ui import console, error_panel


def run() -> None:
    """Entry point invoked by the Typer command."""
    config = load_config()
    if not config.is_initialized:
        error_panel(
            "Big Brain nao inicializado",
            "Execute `big-brain init` para criar o project.json local.",
        )
        raise typer.Exit(code=1)

    project = config.project_config
    project_root = config.project_root
    assert project is not None
    assert project_root is not None

    meta = Table(title=f"Big Brain — {project.project_name}", show_header=False)
    meta.add_column("campo", style="bold cyan")
    meta.add_column("valor")
    meta.add_row("root", str(project_root))
    meta.add_row("notes_dir", str(config.notes_dir))
    meta.add_row("descricao", project.description or "—")
    meta.add_row("stack", ", ".join(project.stack) if project.stack else "—")
    meta.add_row("arquitetura", project.architecture or "—")
    meta.add_row("remote", project.git_remote or "—")
    meta.add_row("confianca", project.confidence)
    meta.add_row("criado", project.created_at)
    meta.add_row("ultima sessao", project.last_session)
    console.print(meta)

    notes = list_notes(config.notes_dir)
    notes_table = Table(title=f"Notas ({len(notes)})")
    notes_table.add_column("Slug", style="cyan")
    notes_table.add_column("Tipo")
    notes_table.add_column("Atualizado", style="dim")
    for note in notes:
        notes_table.add_row(note.slug, note.type, note.updated.isoformat())
    if not notes:
        notes_table.add_row("—", "—", "—")
    console.print(notes_table)

    last_commit = _last_big_brain_commit(config.notes_dir)
    if last_commit:
        console.print(
            f"[bold]Ultimo commit big-brain:[/bold] {last_commit[0][:7]} — {last_commit[1]}"
        )
    else:
        console.print("[dim]Nenhum commit big-brain encontrado ainda.[/dim]")


def _last_big_brain_commit(path: Path) -> tuple[str, str] | None:
    """Return (sha, message) of the most recent big-brain commit, if any."""
    try:
        repo = Repo(path, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return None
    try:
        for commit in repo.iter_commits(max_count=50):
            message = (
                commit.message.strip()
                if isinstance(commit.message, str)
                else str(commit.message).strip()
            )
            if message.startswith("big-brain:"):
                return commit.hexsha, message.splitlines()[0]
    except Exception:
        return None
    return None
