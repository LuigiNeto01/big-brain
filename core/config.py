"""Global + local configuration loading and merging."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


GLOBAL_CONFIG_DIR = Path.home() / ".big-brain"
GLOBAL_CONFIG_PATH = GLOBAL_CONFIG_DIR / "config.json"

LOCAL_CONFIG_DIR_NAME = ".big-brain"
LOCAL_CONFIG_FILE_NAME = "project.json"


DEFAULT_GLOBAL_CONFIG: dict[str, Any] = {
    "language": "pt-BR",
    "git_auto_sync": True,
    "auto_link": True,
    "commit_message_pattern": "big-brain: {action} {note}",
    "notes_dir": "notes",
    "default_note_types": [
        "context",
        "rule",
        "request",
        "decision",
        "feature",
        "bug",
    ],
    "llm": {
        "provider": "codex-bridge",
        "model": "gpt-5.4",
        "reasoning_effort": "medium",
        "base_url": "http://127.0.0.1:47831",
        "timeout_seconds": 120,
    },
}


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "codex-bridge"
    model: str = "gpt-5.4"
    reasoning_effort: str = "medium"
    base_url: str = "http://127.0.0.1:47831"
    timeout_seconds: int = 120


class GlobalConfig(BaseModel):
    """Schema of ~/.big-brain/config.json."""

    language: str = "pt-BR"
    git_auto_sync: bool = True
    auto_link: bool = True
    commit_message_pattern: str = "big-brain: {action} {note}"
    notes_dir: str = "notes"
    default_note_types: list[str] = Field(
        default_factory=lambda: [
            "context",
            "rule",
            "request",
            "decision",
            "feature",
            "bug",
        ]
    )
    llm: LLMConfig = Field(default_factory=LLMConfig)


class ProjectConfig(BaseModel):
    """Schema of {project_root}/.big-brain/project.json."""

    project_name: str
    inferred_from: list[str] = Field(default_factory=list)
    stack: list[str] = Field(default_factory=list)
    architecture: str = ""
    description: str = ""
    git_remote: str = ""
    confidence: str = "low"
    created_at: str = ""
    last_session: str = ""


@dataclass
class Config:
    """Merged runtime configuration."""

    global_config: GlobalConfig
    project_config: ProjectConfig | None
    project_root: Path | None
    global_path: Path = field(default_factory=lambda: GLOBAL_CONFIG_PATH)
    project_path: Path | None = None

    @property
    def notes_dir(self) -> Path:
        """Absolute path to the global notes vault.

        Relative values are resolved from the global config directory
        (`~/.big-brain`), so one folder can hold notes from every project.
        The previous default `.big-brain/notes` is kept compatible and also
        resolves to `~/.big-brain/notes`.
        """
        configured = Path(self.global_config.notes_dir).expanduser()
        if configured.is_absolute():
            return configured
        if configured.parts and configured.parts[0] == LOCAL_CONFIG_DIR_NAME:
            return (self.global_path.parent.parent / configured).resolve()
        return (self.global_path.parent / configured).resolve()

    @property
    def is_initialized(self) -> bool:
        return self.project_config is not None and self.project_root is not None


def ensure_global_config() -> GlobalConfig:
    """Ensure the global config file exists, creating defaults if missing."""
    if not GLOBAL_CONFIG_PATH.exists():
        GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        GLOBAL_CONFIG_PATH.write_text(
            json.dumps(DEFAULT_GLOBAL_CONFIG, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return GlobalConfig(**DEFAULT_GLOBAL_CONFIG)

    try:
        raw = json.loads(GLOBAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raw = DEFAULT_GLOBAL_CONFIG
        GLOBAL_CONFIG_PATH.write_text(
            json.dumps(DEFAULT_GLOBAL_CONFIG, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    migrated = _migrate_global_config(raw)
    if migrated != raw:
        GLOBAL_CONFIG_PATH.write_text(
            json.dumps(migrated, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    merged = _merge_dict(DEFAULT_GLOBAL_CONFIG, migrated)
    return GlobalConfig(**merged)


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk upward from `start` looking for a `.big-brain/project.json`.

    Mirrors how `.git` discovery works.
    """
    cursor = (start or Path.cwd()).resolve()
    for candidate in [cursor, *cursor.parents]:
        if (candidate / LOCAL_CONFIG_DIR_NAME / LOCAL_CONFIG_FILE_NAME).exists():
            return candidate
    return None


def load_project_config(project_root: Path) -> ProjectConfig:
    """Load the per-project config file from disk."""
    path = project_root / LOCAL_CONFIG_DIR_NAME / LOCAL_CONFIG_FILE_NAME
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ProjectConfig(**raw)


def save_project_config(project_root: Path, project_config: ProjectConfig) -> Path:
    """Persist the project config to disk and return the path written."""
    path = project_root / LOCAL_CONFIG_DIR_NAME / LOCAL_CONFIG_FILE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(project_config.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def load_config(start: Path | None = None) -> Config:
    """Load global config and, if available, the local project config."""
    global_config = ensure_global_config()
    project_root = find_project_root(start)
    project_config = (
        load_project_config(project_root) if project_root is not None else None
    )
    project_path = (
        (project_root / LOCAL_CONFIG_DIR_NAME / LOCAL_CONFIG_FILE_NAME)
        if project_root is not None
        else None
    )
    return Config(
        global_config=global_config,
        project_config=project_config,
        project_root=project_root,
        project_path=project_path,
    )


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge two dictionaries. `override` wins on conflicts."""
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _migrate_global_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Migrate older global config values to the current local bridge defaults."""
    migrated = dict(raw)
    llm = migrated.get("llm")
    if not isinstance(llm, dict):
        return migrated

    provider = str(llm.get("provider", "")).lower()
    base_url = str(llm.get("base_url", "")).lower()
    if provider == "anthropic" or "anthropic.com" in base_url:
        migrated["llm"] = dict(DEFAULT_GLOBAL_CONFIG["llm"])

    return migrated
