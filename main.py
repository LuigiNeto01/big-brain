"""Big Brain CLI entry point."""

from __future__ import annotations

from pathlib import Path

import typer

from cli import chat as chat_cmd
from cli import init as init_cmd
from cli import notes_cmd
from cli import status as status_cmd


app = typer.Typer(
    name="big-brain",
    help="Big Brain — camada de memoria e documentacao automatica para projetos.",
    no_args_is_help=True,
    add_completion=False,
)

notes_app = typer.Typer(help="Operacoes sobre notas do projeto.", no_args_is_help=True)
app.add_typer(notes_app, name="notes")


@app.command("init")
def init_command(
    path: Path = typer.Argument(
        None, help="Raiz do projeto (padrao: diretorio atual)."
    ),
    force: bool = typer.Option(
        False, "--force", help="Sobrescreve um project.json existente."
    ),
) -> None:
    """Inicializa o big-brain no projeto atual."""
    init_cmd.run(root=path, force=force)


@app.command("chat")
def chat_command() -> None:
    """Abre o modo interativo big-brain chat."""
    chat_cmd.run()


@app.command("status")
def status_command() -> None:
    """Exibe o estado atual do big-brain para o projeto."""
    status_cmd.run()


@notes_app.command("list")
def notes_list_command() -> None:
    """Lista todas as notas do projeto."""
    notes_cmd.cmd_list()


@notes_app.command("show")
def notes_show_command(slug: str = typer.Argument(..., help="Slug da nota.")) -> None:
    """Exibe uma nota com frontmatter e corpo."""
    notes_cmd.cmd_show(slug)


@notes_app.command("search")
def notes_search_command(
    query: str = typer.Argument(..., help="Texto a buscar em titulo, tags e corpo."),
) -> None:
    """Busca notas por substring."""
    notes_cmd.cmd_search(query)


@notes_app.command("delete")
def notes_delete_command(
    slug: str = typer.Argument(..., help="Slug da nota a remover."),
    confirm: bool = typer.Option(
        False, "--confirm", help="Confirma a remocao da nota."
    ),
) -> None:
    """Remove uma nota do projeto."""
    notes_cmd.cmd_delete(slug, confirm)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
