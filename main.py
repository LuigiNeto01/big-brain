"""Big Brain CLI entry point."""

from __future__ import annotations

from pathlib import Path

import typer

from cli import agent as agent_cmd
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


@app.command("context")
def context_command(
    path: Path | None = typer.Option(
        None, "--path", help="Diretorio do projeto (padrao: diretorio atual)."
    ),
) -> None:
    """Imprime contexto de memoria para agents."""
    agent_cmd.cmd_context(path)


@app.command("capture")
def capture_command(
    text: str | None = typer.Argument(None, help="Texto da conversa a capturar."),
    use_stdin: bool = typer.Option(
        False, "--stdin", help="Le o texto da conversa via stdin."
    ),
    path: Path | None = typer.Option(
        None, "--path", help="Diretorio do projeto (padrao: diretorio atual)."
    ),
) -> None:
    """Captura informacoes duraveis de uma conversa de agent."""
    agent_cmd.cmd_capture(text, use_stdin=use_stdin, path=path)


@app.command("setup-agent")
def setup_agent_command(
    codex_home: Path | None = typer.Option(
        None, "--codex-home", help="Diretorio de configuracao do Codex."
    ),
    force: bool = typer.Option(
        False, "--force", help="Regrava os arquivos de integracao."
    ),
) -> None:
    """Instala integracao global para agents usarem o Big Brain."""
    agent_cmd.cmd_setup_agent(codex_home, force)


@app.command("hook", hidden=True)
def hook_command(
    event: str = typer.Argument(..., help="Evento de hook recebido do agent."),
    use_stdin: bool = typer.Option(
        True, "--stdin/--no-stdin", help="Le payload do hook via stdin."
    ),
) -> None:
    """Executa automacoes internas chamadas por plugin hooks."""
    agent_cmd.cmd_hook(event, use_stdin=use_stdin)


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
