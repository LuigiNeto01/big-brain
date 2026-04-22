"""Tests for config loading and global+local merging."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import config as config_module


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path: Path):
    """Redirect the global config dir to a temp location for every test."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(config_module, "GLOBAL_CONFIG_DIR", fake_home / ".big-brain")
    monkeypatch.setattr(
        config_module, "GLOBAL_CONFIG_PATH", fake_home / ".big-brain" / "config.json"
    )
    yield fake_home


def test_ensure_global_config_creates_defaults(_tmp_home: Path):
    cfg = config_module.ensure_global_config()
    assert cfg.language == "pt-BR"
    assert cfg.llm.provider == "codex-bridge"
    assert config_module.GLOBAL_CONFIG_PATH.exists()


def test_merge_dict_overrides_keys():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 20}, "e": 5}
    merged = config_module._merge_dict(base, override)
    assert merged == {"a": 1, "b": {"c": 20, "d": 3}, "e": 5}


def test_find_project_root_walks_up(tmp_path: Path):
    project = tmp_path / "proj"
    (project / "sub" / "deep").mkdir(parents=True)
    (project / ".big-brain").mkdir()
    (project / ".big-brain" / "project.json").write_text(
        json.dumps({"project_name": "proj"}), encoding="utf-8"
    )
    found = config_module.find_project_root(project / "sub" / "deep")
    assert found == project


def test_load_config_with_local_project(tmp_path: Path):
    project = tmp_path / "p"
    project.mkdir()
    (project / ".big-brain").mkdir()
    (project / ".big-brain" / "project.json").write_text(
        json.dumps({"project_name": "p"}), encoding="utf-8"
    )
    cfg = config_module.load_config(project)
    assert cfg.is_initialized
    assert cfg.project_config.project_name == "p"
    assert cfg.notes_dir == _tmp_notes_dir()


def test_notes_dir_compatibility_for_old_relative_default(_tmp_home: Path):
    raw = config_module.DEFAULT_GLOBAL_CONFIG | {"notes_dir": ".big-brain/notes"}
    cfg = config_module.Config(
        global_config=config_module.GlobalConfig(**raw),
        project_config=None,
        project_root=None,
        global_path=config_module.GLOBAL_CONFIG_PATH,
    )
    assert cfg.notes_dir == _tmp_home / ".big-brain" / "notes"


def test_migrates_anthropic_config_to_codex_bridge(_tmp_home: Path):
    config_module.GLOBAL_CONFIG_DIR.mkdir(parents=True)
    config_module.GLOBAL_CONFIG_PATH.write_text(
        json.dumps(
            {
                "llm": {
                    "provider": "anthropic",
                    "model": "claude-opus-4-7",
                    "base_url": "https://api.anthropic.com/v1/messages",
                }
            }
        ),
        encoding="utf-8",
    )

    cfg = config_module.ensure_global_config()

    assert cfg.llm.provider == "codex-bridge"
    assert cfg.llm.base_url == "http://127.0.0.1:47831"


def _tmp_notes_dir() -> Path:
    return config_module.GLOBAL_CONFIG_DIR / "notes"
