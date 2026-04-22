"""Tests for project inference from filesystem sentinels."""

from __future__ import annotations

import json
from pathlib import Path

from core.inference import enrich, infer_project


def test_infer_python_project(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    result = infer_project(tmp_path)
    assert "Python" in result["stack"]
    assert result["project_name"] == tmp_path.name
    assert result["confidence"] in {"low", "medium", "high"}


def test_infer_node_project_with_next(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"next": "14.0.0", "react": "18.0.0"}}),
        encoding="utf-8",
    )
    result = infer_project(tmp_path)
    assert "Node.js" in result["stack"]
    assert "Next.js" in result["stack"]
    assert "React" in result["stack"]


def test_enrich_adds_postgres(tmp_path: Path):
    project = {"project_name": "x", "stack": [], "description": "", "inferred_from": []}
    updated, changed = enrich(project, "Estamos usando PostgreSQL para o banco.")
    assert changed
    assert "PostgreSQL" in updated["stack"]
    assert "conversation" in updated["inferred_from"]


def test_enrich_no_change_returns_false():
    project = {"project_name": "x", "stack": ["PostgreSQL"], "description": "ok"}
    _, changed = enrich(project, "mensagem generica sem nada relevante")
    assert changed is False
