"""`big-brain chat` — interactive chat loop with automatic note creation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.markdown import Markdown
from rich.prompt import Prompt

from core.config import Config, load_config
from core.git_sync import GitConflictError, sync as git_sync
from core.linker import detect_and_link
from core.notes import Note, create_note, note_path
from core.session import (
    LLMClient,
    LLMMessage,
    Session,
    build_note_from_trigger,
    detect_triggers,
)
from utils.ui import (
    brain_banner,
    console,
    error_panel,
    git_committed,
    links_created,
    note_created,
    status_line,
    warning,
)


def run() -> None:
    """Entry point for the interactive chat command."""
    config = load_config()
    if not config.is_initialized:
        error_panel(
            "Big Brain nao inicializado",
            "Execute `big-brain init` antes de abrir o chat.",
        )
        raise typer.Exit(code=1)

    assert config.project_config is not None

    brain_banner(
        config.project_config.project_name, list(config.project_config.stack)
    )
    console.print(
        "[dim]Digite /sair para encerrar, /notas para listar, /status para o projeto.[/dim]"
    )

    session = Session(config=config)
    llm = LLMClient(config=config)

    while True:
        try:
            user_input = Prompt.ask("[bold green]voce[/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        if not user_input:
            continue

        if _handle_internal_command(user_input, config):
            if user_input.strip().lower() in {"/sair", "/exit", "/quit"}:
                break
            continue

        _turn(session, llm, user_input)


def _turn(session: Session, llm: LLMClient, user_input: str) -> None:
    """Execute one round-trip: enrich → LLM → note detection → git sync."""
    project_changed = session.enrich(user_input)

    system = session.load_context()
    session.append_user(user_input)
    response = llm.chat(system, session.history)
    session.append_assistant(response)

    console.print()
    console.print("[bold cyan]big-brain[/bold cyan]:")
    console.print(Markdown(response))
    console.print()

    if project_changed:
        status_line("⚙️ ", "project.json enriquecido com o contexto da conversa")

    hits = detect_triggers(user_input)
    if not hits:
        return

    assert session.config.project_config is not None
    project_name = session.config.project_config.project_name

    for hit in hits:
        title, summary = llm.generate_title_and_summary(hit.snippet)
        note = build_note_from_trigger(
            hit, project_name=project_name, title=title, summary=summary
        )
        _persist_note(session.config, note)


def _persist_note(config: Config, note: Note) -> None:
    """Create the note file in the global vault, link it, and git-sync it."""
    assert config.project_root is not None

    path = create_note(config.notes_dir, note)
    links = detect_and_link(config.notes_dir, note)
    note_created(note.slug)
    links_created(note.slug, links)

    if not config.global_config.git_auto_sync:
        return

    files = [path, config.notes_dir / "_index.md"]
    for link_slug in links:
        files.append(note_path(config.notes_dir, link_slug))

    try:
        result = git_sync(
            project_root=config.notes_dir,
            files=files,
            action="create",
            note_slug=note.slug,
            commit_message_pattern=config.global_config.commit_message_pattern,
        )
    except GitConflictError as exc:
        warning(f"Conflito git em: {', '.join(exc.conflicting_files)}")
        return

    if result.success and result.commit_hash:
        git_committed(result.commit_hash, result.pushed)
    elif result.error:
        warning(result.error)


def _handle_internal_command(user_input: str, config: Config) -> bool:
    """Handle `/notas`, `/status`, `/sair`. Returns True when matched."""
    cmd = user_input.strip().lower()

    if cmd in {"/sair", "/exit", "/quit"}:
        status_line("👋", "Encerrando sessao.")
        return True

    if cmd in {"/notas", "/notes"}:
        from cli.notes_cmd import cmd_list

        cmd_list()
        return True

    if cmd in {"/status", "/info"}:
        from cli.status import run as status_run

        status_run()
        return True

    return False
