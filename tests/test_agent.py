"""Tests for non-interactive agent integration commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from cli import agent
from core import config as config_module


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path: Path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(config_module, "GLOBAL_CONFIG_DIR", fake_home / ".big-brain")
    monkeypatch.setattr(
        config_module, "GLOBAL_CONFIG_PATH", fake_home / ".big-brain" / "config.json"
    )
    yield fake_home


def test_install_codex_agent_integration_writes_global_files(tmp_path: Path):
    codex_home = tmp_path / "codex"

    installed = agent.install_codex_agent_integration(codex_home)

    assert installed == [
        codex_home / "AGENTS.md",
        codex_home / "skills" / "big-brain" / "SKILL.md",
        tmp_path / "plugins" / "big-brain",
        tmp_path / ".agents" / "plugins" / "marketplace.json",
    ]
    assert "big-brain context" in installed[0].read_text(encoding="utf-8")
    assert "big-brain capture" in installed[1].read_text(encoding="utf-8")
    assert (installed[2] / ".codex-plugin" / "plugin.json").exists()
    assert (installed[2] / "hooks.json").exists()


def test_custom_instruction_discovery_includes_claude_when_present(tmp_path: Path):
    codex_home = tmp_path / ".codex"
    (tmp_path / ".claude").mkdir()

    targets = agent.discover_custom_instruction_files(codex_home)

    assert codex_home / "AGENTS.md" in targets
    assert tmp_path / ".claude" / "CLAUDE.md" in targets


def test_custom_instruction_block_tells_ai_to_act_automatically():
    block = agent.build_agent_instruction_block()

    assert "A IA deve fazer isso por conta propria" in block
    assert "big-brain context" in block
    assert "big-brain capture --stdin" in block


def test_upsert_block_replaces_existing_managed_block():
    first = agent.build_agent_instruction_block()
    changed = first.replace("big-brain context", "big-brain context --path .")

    merged = agent._upsert_block(first, changed)

    assert "big-brain context --path ." in merged
    assert merged.count(agent.BEGIN_MARKER) == 1


def test_ensure_project_config_auto_initializes_git_root(_tmp_home: Path, tmp_path: Path):
    project = tmp_path / "repo"
    nested = project / "sub"
    nested.mkdir(parents=True)
    (project / ".git").mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    config, initialized = agent.ensure_project_config(nested)

    assert initialized is True
    assert config.project_root == project
    assert (project / ".big-brain" / "project.json").exists()
    assert (config.notes_dir / "_index.md").exists()


def test_capture_text_creates_note(_tmp_home: Path, tmp_path: Path):
    project = tmp_path / "repo"
    project.mkdir()
    config, _ = agent.ensure_project_config(project)

    outcome = agent.capture_text(config, "Nao pode remover notas sem confirmacao.")

    assert outcome.note_slugs
    note_path = config.notes_dir / f"{outcome.note_slugs[0]}.md"
    assert note_path.exists()
    assert "Nao pode remover notas" in note_path.read_text(encoding="utf-8")


def test_hook_session_start_writes_agent_context(_tmp_home: Path, tmp_path: Path):
    project = tmp_path / "repo"
    project.mkdir()

    outcome = agent.handle_hook_event("session-start", path=project)

    assert outcome is not None
    assert (_tmp_home / ".big-brain" / "agent-context.md").exists()


def test_extract_hook_text_reads_transcript_path(tmp_path: Path):
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        '{"message":{"role":"user","content":"Decidimos usar SQLite local."}}\n'
        '{"message":{"role":"assistant","content":"ok"}}\n',
        encoding="utf-8",
    )
    payload = json_dump({"transcript_path": str(transcript)})

    text = agent.extract_hook_text(payload)

    assert "Decidimos usar SQLite local" in text
    assert "ok" not in text


def test_hook_session_end_captures_transcript(_tmp_home: Path, tmp_path: Path):
    project = tmp_path / "repo"
    project.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        '{"message":{"role":"user","content":"Nao pode apagar o vault global."}}\n',
        encoding="utf-8",
    )

    outcome = agent.handle_hook_event(
        "session-end",
        json_dump({"transcript_path": str(transcript)}),
        path=project,
    )

    assert outcome is not None
    assert outcome.note_slugs


def json_dump(value: object) -> str:
    import json

    return json.dumps(value)
