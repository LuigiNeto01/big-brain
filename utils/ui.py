"""Shared Rich-based UI helpers for consistent CLI output."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


console = Console()


def brain_banner(project_name: str, stack: list[str]) -> None:
    """Top-of-chat banner line."""
    stack_text = " · ".join(stack) if stack else "stack desconhecida"
    console.print(
        f"[bold]📂 Big Brain ativo[/bold] — {project_name} · [dim]{stack_text}[/dim]"
    )


def status_line(icon: str, message: str) -> None:
    """Print a discreet status line in dim gray after a main response."""
    console.print(f"[dim]{icon} {message}[/dim]")


def note_created(slug: str) -> None:
    status_line("📝", f"Nota criada: {slug}")


def note_updated(slug: str) -> None:
    status_line("🔄", f"Nota atualizada: {slug}")


def links_created(source_slug: str, targets: list[str]) -> None:
    if not targets:
        return
    linked = " ".join(f"[[{t}]]" for t in targets)
    status_line("🔗", f"Links: {source_slug} → {linked}")


def git_committed(commit_hash: str, pushed: bool) -> None:
    short = commit_hash[:7] if commit_hash else "???????"
    suffix = " (push ok)" if pushed else ""
    status_line("✅", f"Git: commit {short}{suffix}")


def warning(message: str) -> None:
    status_line("⚠️ ", message)


def config_action(message: str) -> None:
    status_line("⚙️ ", message)


def error_panel(title: str, message: str) -> None:
    """Render a critical error inside a red-bordered panel."""
    console.print(
        Panel(
            Text(message, style="white"),
            title=title,
            border_style="red",
            expand=False,
        )
    )
