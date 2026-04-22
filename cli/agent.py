"""Agent-facing non-interactive commands and one-time setup."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer
from rich.markdown import Markdown

from core.config import Config, ProjectConfig, load_config, save_project_config
from core.git_sync import GitConflictError, SyncResult, sync as git_sync
from core.inference import infer_project
from core.linker import detect_and_link
from core.notes import Note, create_note, note_path, update_index
from core.session import Session, build_note_from_trigger, detect_triggers
from utils.ui import (
    config_action,
    console,
    error_panel,
    git_committed,
    links_created,
    note_created,
    status_line,
    warning,
)


BEGIN_MARKER = "<!-- big-brain:agent-instructions:start -->"
END_MARKER = "<!-- big-brain:agent-instructions:end -->"


@dataclass
class CaptureOutcome:
    """Result of capturing agent conversation text into notes."""

    project_initialized: bool
    project_changed: bool
    note_slugs: list[str] = field(default_factory=list)
    links: dict[str, list[str]] = field(default_factory=dict)
    sync_results: list[SyncResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def cmd_context(path: Path | None = None) -> None:
    """Print a machine-readable project memory context for agents."""
    config, initialized = ensure_project_config(path)
    session = Session(config=config)

    if initialized:
        config_action(f"projeto inicializado automaticamente em {config.project_root}")

    console.print(Markdown(session.load_context()))


def cmd_capture(
    text: str | None = None,
    *,
    use_stdin: bool = False,
    path: Path | None = None,
) -> None:
    """Capture durable facts from arbitrary agent conversation text."""
    captured_text = _read_capture_text(text, use_stdin)
    if not captured_text.strip():
        error_panel(
            "Texto vazio",
            "Informe um texto ou use `big-brain capture --stdin` com stdin.",
        )
        raise typer.Exit(code=2)

    config, _ = ensure_project_config(path)
    outcome = capture_text(config, captured_text)

    if outcome.project_changed:
        status_line("⚙️ ", "project.json enriquecido com o contexto capturado")

    if not outcome.note_slugs:
        status_line("📝", "Nenhum gatilho de nota encontrado no texto capturado.")
        return

    for slug in outcome.note_slugs:
        note_created(slug)
        links_created(slug, outcome.links.get(slug, []))

    for result in outcome.sync_results:
        if result.success and result.commit_hash:
            git_committed(result.commit_hash, result.pushed)
        elif result.error:
            warning(result.error)

    for message in outcome.warnings:
        warning(message)


def cmd_setup_agent(codex_home: Path | None = None, force: bool = False) -> None:
    """Install one-time Codex agent instructions for automatic Big Brain use."""
    home = (codex_home or (Path.home() / ".codex")).expanduser().resolve()
    installed = install_codex_agent_integration(home, force=force)
    for path in installed:
        config_action(f"integracao de agent instalada em {path}")

    config, _ = ensure_project_config()
    config.notes_dir.mkdir(parents=True, exist_ok=True)
    update_index(config.notes_dir)
    config_action(f"vault global de notas pronto em {config.notes_dir}")


def cmd_hook(event: str, *, use_stdin: bool = False) -> None:
    """Handle plugin hook events quietly."""
    payload = sys.stdin.read() if use_stdin else ""
    handle_hook_event(event, payload)


def ensure_project_config(path: Path | None = None) -> tuple[Config, bool]:
    """Load config, creating local project config automatically if missing."""
    start = (path or Path.cwd()).resolve()
    config = load_config(start)
    if config.is_initialized:
        config.notes_dir.mkdir(parents=True, exist_ok=True)
        update_index(config.notes_dir)
        return config, False

    project_root = _find_workspace_root(start)
    project = ProjectConfig(**infer_project(project_root))
    save_project_config(project_root, project)

    config = load_config(project_root)
    config.notes_dir.mkdir(parents=True, exist_ok=True)
    update_index(config.notes_dir)
    return config, True


def capture_text(config: Config, text: str) -> CaptureOutcome:
    """Persist notes detected in `text` without opening an interactive chat."""
    assert config.project_config is not None
    outcome = CaptureOutcome(project_initialized=False, project_changed=False)

    session = Session(config=config)
    outcome.project_changed = session.enrich(text)
    project_name = config.project_config.project_name

    for hit in detect_triggers(text):
        note = build_note_from_trigger(hit, project_name=project_name)
        links, sync_result, sync_warning = _persist_agent_note(config, note)
        outcome.note_slugs.append(note.slug)
        outcome.links[note.slug] = links
        if sync_result is not None:
            outcome.sync_results.append(sync_result)
        if sync_warning:
            outcome.warnings.append(sync_warning)

    return outcome


def handle_hook_event(
    event: str, payload: str = "", path: Path | None = None
) -> CaptureOutcome | None:
    """Run automatic memory work for a session hook."""
    normalized = event.strip().lower().replace("_", "-")
    config, initialized = ensure_project_config(path)
    write_agent_context(config)

    if normalized in {"session-start", "startup", "resume"}:
        return CaptureOutcome(
            project_initialized=initialized,
            project_changed=False,
        )

    if normalized not in {"session-end", "pre-compact", "stop"}:
        return None

    text = extract_hook_text(payload)
    if not text.strip():
        return CaptureOutcome(
            project_initialized=initialized,
            project_changed=False,
        )

    outcome = capture_text(config, text)
    outcome.project_initialized = initialized
    return outcome


def write_agent_context(config: Config) -> Path:
    """Write the current context to a global file hooks can keep fresh."""
    path = config.global_path.parent / "agent-context.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(Session(config=config).load_context(), encoding="utf-8")
    return path


def extract_hook_text(payload: str) -> str:
    """Extract useful user text from hook JSON or raw payload text."""
    stripped = payload.strip()
    if not stripped:
        return ""

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped

    transcript_path = _find_transcript_path(data)
    if transcript_path:
        return extract_transcript_text(transcript_path)

    return "\n".join(_collect_text_fields(data))


def extract_transcript_text(path: Path) -> str:
    """Best-effort extraction of user text from JSONL or plain transcripts."""
    if not path.exists() or not path.is_file():
        return ""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    extracted: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError:
            extracted.append(stripped)
            continue
        extracted.extend(_collect_user_text(item))

    return "\n".join(extracted)[-20000:]


def install_codex_agent_integration(codex_home: Path, force: bool = False) -> list[Path]:
    """Install global Codex instructions, skill, and local plugin hooks."""
    codex_home.mkdir(parents=True, exist_ok=True)

    instruction_files = install_custom_instruction_files(codex_home, force=force)

    skill_dir = codex_home / "skills" / "big-brain"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_text = build_big_brain_skill_text()
    if force or not skill_path.exists() or skill_path.read_text(encoding="utf-8") != skill_text:
        skill_path.write_text(skill_text, encoding="utf-8")

    plugin_root = install_local_plugin(codex_home, force=force)
    marketplace = install_local_marketplace(codex_home, plugin_root)

    return [*instruction_files, skill_path, plugin_root, marketplace]


def install_custom_instruction_files(
    codex_home: Path, force: bool = False
) -> list[Path]:
    """Install the Big Brain behavior block into known custom instruction files."""
    block = build_agent_instruction_block()
    installed: list[Path] = []

    for path in discover_custom_instruction_files(codex_home):
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        updated = _upsert_block(existing, block)
        if force or not path.exists() or existing != updated:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(updated, encoding="utf-8")
        installed.append(path)

    return installed


def discover_custom_instruction_files(codex_home: Path) -> list[Path]:
    """Find local custom instruction files that agents naturally load."""
    home = codex_home.expanduser().resolve().parent
    targets = [codex_home / "AGENTS.md"]

    claude_dir = home / ".claude"
    if claude_dir.exists():
        targets.append(claude_dir / "CLAUDE.md")

    cursor_dir = home / ".cursor"
    if cursor_dir.exists():
        targets.append(cursor_dir / "rules" / "big-brain.mdc")

    return targets


def install_local_plugin(codex_home: Path, force: bool = False) -> Path:
    """Install a home-local Codex plugin with hooks and skills."""
    plugin_root = codex_home.parent / "plugins" / "big-brain"
    if plugin_root.exists() and force:
        shutil.rmtree(plugin_root)

    (plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (plugin_root / "skills" / "big-brain").mkdir(parents=True, exist_ok=True)
    (plugin_root / "scripts").mkdir(parents=True, exist_ok=True)

    _write_if_needed(
        plugin_root / ".codex-plugin" / "plugin.json",
        build_codex_plugin_manifest(),
        force,
    )
    _write_if_needed(plugin_root / "hooks.json", build_codex_hooks_json(), force)
    _write_if_needed(
        plugin_root / "skills" / "big-brain" / "SKILL.md",
        build_big_brain_skill_text(),
        force,
    )

    for event in ("session-start", "session-end", "pre-compact"):
        script_path = plugin_root / "scripts" / f"big-brain-{event}.sh"
        _write_if_needed(script_path, build_hook_script(event), force)
        script_path.chmod(0o755)

    return plugin_root


def install_local_marketplace(codex_home: Path, plugin_root: Path) -> Path:
    """Create/update a home marketplace entry for the local plugin."""
    marketplace = codex_home.parent / ".agents" / "plugins" / "marketplace.json"
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    relative_path = _relative_to_home(plugin_root)
    entry = {
        "name": "big-brain",
        "source": {
            "source": "local",
            "path": relative_path,
        },
        "policy": {
            "installation": "INSTALLED_BY_DEFAULT",
            "authentication": "ON_USE",
        },
        "category": "Productivity",
    }

    if marketplace.exists():
        try:
            data = json.loads(marketplace.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = _empty_marketplace()
    else:
        data = _empty_marketplace()

    plugins = data.setdefault("plugins", [])
    if not isinstance(plugins, list):
        plugins = []
        data["plugins"] = plugins

    plugins[:] = [
        plugin
        for plugin in plugins
        if not (isinstance(plugin, dict) and plugin.get("name") == "big-brain")
    ]
    plugins.append(entry)
    marketplace.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return marketplace


def build_agent_instruction_block() -> str:
    """Return the managed global AGENTS.md block."""
    return f"""{BEGIN_MARKER}
# Big Brain Agent Memory

Use o Big Brain automaticamente em toda conversa de desenvolvimento quando o
comando `big-brain` estiver disponivel.

Rotina obrigatoria da propria IA:

1. No inicio de uma tarefa em um repositorio, antes de analisar ou editar
   codigo, rode `big-brain context`. Esse comando tambem inicializa
   `.big-brain/project.json` automaticamente se estiver faltando.
2. Use o contexto retornado e as notas em `~/.big-brain/agent-context.md` como
   memoria do projeto. Consulte essa memoria antes de decisoes de arquitetura,
   dominio, UX ou comportamento.
3. Quando o usuario declarar regra, decisao, pedido, bug, feature ou contexto
   duravel, registre imediatamente o trecho exato com:
   `printf '%s\\n' "<texto exato>" | big-brain capture --stdin`
4. Antes da resposta final, se alguma informacao duravel surgiu e ainda nao foi
   capturada, registre um resumo curto com `big-brain capture --stdin`.
5. Nao peca ao usuario para rodar `big-brain init`, `big-brain context` ou
   comandos de hook. A IA deve fazer isso por conta propria.
6. Nao abra `big-brain chat` dentro de uma conversa com agent; o agent atual ja
   e o chat. Use apenas `context`, `capture`, `status` e `notes`.
7. Se `big-brain` nao estiver instalado ou falhar por dependencia/permissao,
   continue a tarefa normalmente e mencione o problema de forma breve.
{END_MARKER}
"""


def build_big_brain_skill_text() -> str:
    """Return a Codex skill file that nudges future sessions to use Big Brain."""
    return """---
name: big-brain
description: >
  Use automaticamente em conversas de agent dentro de repositorios para carregar
  memoria do projeto com big-brain context e registrar informacoes duraveis com
  big-brain capture.
---

# Big Brain

Use esta skill no inicio de tarefas de desenvolvimento quando o comando
`big-brain` existir no ambiente.

## Fluxo

1. Rode `big-brain context` por conta propria no inicio da tarefa, antes de
   analisar ou editar codigo.
2. Trabalhe normalmente usando esse contexto e `~/.big-brain/agent-context.md`.
3. Quando o usuario revelar informacao duravel, registre imediatamente:

```bash
printf '%s\\n' "texto importante do usuario" | big-brain capture --stdin
```

4. Antes da resposta final, capture qualquer decisao/regra/pedido/bug/feature
   que ainda nao tenha sido salvo.

Nao peca ao usuario para rodar Big Brain. Nao use `big-brain chat` dentro de
uma conversa de agent.
"""


def build_codex_plugin_manifest() -> str:
    """Return the local Codex plugin manifest."""
    return json.dumps(
        {
            "name": "big-brain",
            "version": "0.1.0",
            "description": (
                "Automatic project memory for coding agents using a global "
                "Markdown note vault."
            ),
            "author": {
                "name": "Luigi Neto",
                "email": "luigicode01@gmail.com",
            },
            "homepage": "https://github.com/luigineto/big-brain",
            "repository": "https://github.com/luigineto/big-brain",
            "license": "MIT",
            "keywords": ["memory", "notes", "agents", "codex", "automation"],
            "skills": "./skills/",
            "hooks": "./hooks.json",
            "interface": {
                "displayName": "Big Brain",
                "shortDescription": "Automatic Markdown memory for coding agents",
                "longDescription": (
                    "Big Brain initializes projects, keeps a global Markdown "
                    "vault, refreshes agent context on session start, and "
                    "captures durable rules, decisions, bugs, features, and "
                    "requests from agent transcripts."
                ),
                "developerName": "Luigi Neto",
                "category": "Productivity",
                "capabilities": ["Interactive", "Read", "Write"],
                "defaultPrompt": [
                    "Use Big Brain memory for this repository.",
                    "Capture durable decisions from this conversation.",
                    "Show me this project's memory notes.",
                ],
                "brandColor": "#2563EB",
                "screenshots": [],
            },
        },
        indent=2,
        ensure_ascii=False,
    )


def build_codex_hooks_json() -> str:
    """Return Codex hook config for automatic session memory."""
    hooks = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "./scripts/big-brain-session-start.sh",
                            "timeout": 20,
                            "async": True,
                            "statusMessage": "Loading Big Brain memory...",
                        }
                    ],
                }
            ],
            "SessionEnd": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "./scripts/big-brain-session-end.sh",
                            "timeout": 30,
                            "async": True,
                            "statusMessage": "Saving Big Brain memory...",
                        }
                    ],
                }
            ],
            "PreCompact": [
                {
                    "matcher": "auto",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "./scripts/big-brain-pre-compact.sh",
                            "timeout": 20,
                            "async": True,
                        }
                    ],
                }
            ],
        }
    }
    return json.dumps(hooks, indent=2, ensure_ascii=False)


def build_hook_script(event: str) -> str:
    """Return a small shell wrapper used by plugin hooks."""
    return f"""#!/usr/bin/env bash
set -u

if command -v big-brain >/dev/null 2>&1; then
  big-brain hook {event} --stdin || true
fi
"""


def _persist_agent_note(
    config: Config, note: Note
) -> tuple[list[str], SyncResult | None, str | None]:
    """Create/link/sync a note captured by an external agent conversation."""
    path = create_note(config.notes_dir, note)
    links = detect_and_link(config.notes_dir, note)

    if not config.global_config.git_auto_sync:
        return links, None, None

    files = [path, config.notes_dir / "_index.md"]
    for link_slug in links:
        files.append(note_path(config.notes_dir, link_slug))

    try:
        result = git_sync(
            project_root=config.notes_dir,
            files=files,
            action="capture",
            note_slug=note.slug,
            commit_message_pattern=config.global_config.commit_message_pattern,
        )
    except GitConflictError as exc:
        return links, None, f"Conflito git em: {', '.join(exc.conflicting_files)}"

    return links, result, None


def _find_transcript_path(value: Any) -> Path | None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower().replace("_", "").replace("-", "")
            if normalized in {"transcriptpath", "transcriptfile", "sessionfile"}:
                if isinstance(item, str) and item:
                    return Path(item).expanduser()
            found = _find_transcript_path(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_transcript_path(item)
            if found is not None:
                return found
    return None


def _collect_text_fields(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        if value.strip():
            texts.append(value.strip())
    elif isinstance(value, list):
        for item in value:
            texts.extend(_collect_text_fields(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"content", "text", "prompt", "message"}:
                texts.extend(_collect_text_fields(item))
            elif isinstance(item, (dict, list)):
                texts.extend(_collect_text_fields(item))
    return texts


def _collect_user_text(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []

    role = str(value.get("role") or value.get("type") or "").lower()
    message = value.get("message")
    if isinstance(message, dict):
        role = str(message.get("role") or role).lower()
        value = message

    if role in {"user", "human"}:
        return _collect_text_fields(value.get("content", value))

    texts: list[str] = []
    for item in value.values():
        if isinstance(item, dict):
            texts.extend(_collect_user_text(item))
        elif isinstance(item, list):
            for nested in item:
                texts.extend(_collect_user_text(nested))
    return texts


def _read_capture_text(text: str | None, use_stdin: bool) -> str:
    if use_stdin:
        return sys.stdin.read()
    return text or ""


def _write_if_needed(path: Path, content: str, force: bool) -> None:
    if force or not path.exists() or path.read_text(encoding="utf-8") != content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _empty_marketplace() -> dict[str, Any]:
    return {
        "name": "local",
        "interface": {"displayName": "Local Plugins"},
        "plugins": [],
    }


def _relative_to_home(path: Path) -> str:
    try:
        return "./" + str(path.resolve().relative_to(Path.home().resolve()))
    except ValueError:
        return str(path.resolve())


def _find_workspace_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def _upsert_block(existing: str, block: str) -> str:
    if BEGIN_MARKER in existing and END_MARKER in existing:
        before, rest = existing.split(BEGIN_MARKER, 1)
        _, after = rest.split(END_MARKER, 1)
        return f"{before.rstrip()}\n\n{block.rstrip()}\n{after.lstrip()}".rstrip() + "\n"

    if not existing.strip():
        return block.rstrip() + "\n"

    return f"{existing.rstrip()}\n\n{block.rstrip()}\n"
