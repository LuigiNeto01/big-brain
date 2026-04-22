"""`big-brain init` — bootstrap a project's big-brain directory."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.table import Table

from core.config import (
    LOCAL_CONFIG_DIR_NAME,
    LOCAL_CONFIG_FILE_NAME,
    ProjectConfig,
    ensure_global_config,
    load_project_config,
    save_project_config,
)
from core.inference import infer_project
from core.notes import update_index
from utils.ui import config_action, console


def run(root: Path | None = None, force: bool = False) -> None:
    """Initialize big-brain for the project at `root` (defaults to cwd)."""
    project_root = (root or Path.cwd()).resolve()
    ensure_global_config()

    project_file = project_root / LOCAL_CONFIG_DIR_NAME / LOCAL_CONFIG_FILE_NAME
    if project_file.exists() and not force:
        existing = load_project_config(project_root)
        config_action(f"project.json ja existe em {project_file}")
        _print_summary(existing)
        raise typer.Exit(code=0)

    inferred = infer_project(project_root)
    if project_file.exists() and force:
        current = load_project_config(project_root).model_dump()
        current.update(inferred)
        current["last_session"] = date.today().isoformat()
        project = ProjectConfig(**current)
    else:
        project = ProjectConfig(**inferred)

    save_project_config(project_root, project)

    from core.config import load_config

    config = load_config(project_root)
    config.notes_dir.mkdir(parents=True, exist_ok=True)
    update_index(config.notes_dir)

    config_action(f"project.json criado em {project_file}")
    config_action(f"vault global de notas pronto em {config.notes_dir}")
    _print_summary(project)


def _print_summary(project: ProjectConfig) -> None:
    table = Table(title="Big Brain — Projeto detectado", show_header=False)
    table.add_column("campo", style="bold cyan")
    table.add_column("valor")
    table.add_row("nome", project.project_name)
    table.add_row("descricao", project.description or "—")
    table.add_row("stack", ", ".join(project.stack) if project.stack else "—")
    table.add_row("arquitetura", project.architecture or "—")
    table.add_row("remote", project.git_remote or "—")
    table.add_row("confianca", project.confidence)
    table.add_row("inferido via", ", ".join(project.inferred_from) or "—")
    console.print(table)
