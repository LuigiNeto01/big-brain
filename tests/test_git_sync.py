"""Tests for git_sync — primarily against an isolated local repo."""

from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from core.git_sync import sync


@pytest.fixture
def local_repo(tmp_path: Path) -> Path:
    repo = Repo.init(tmp_path)
    with repo.config_writer() as cfg:
        cfg.set_value("user", "email", "big-brain@test")
        cfg.set_value("user", "name", "big-brain test")
    seed = tmp_path / "seed.txt"
    seed.write_text("hello", encoding="utf-8")
    repo.index.add(["seed.txt"])
    repo.index.commit("seed")
    return tmp_path


def test_sync_commits_a_new_file(local_repo: Path):
    note_path = local_repo / "note.md"
    note_path.write_text("hello world", encoding="utf-8")

    result = sync(
        project_root=local_repo,
        files=[note_path],
        action="create",
        note_slug="rule__x",
        push=False,
    )
    assert result.success
    assert result.commit_hash is not None
    repo = Repo(local_repo)
    assert "rule__x" in repo.head.commit.message


def test_sync_without_git_returns_failure(tmp_path: Path):
    target = tmp_path / "note.md"
    target.write_text("x", encoding="utf-8")
    result = sync(
        project_root=tmp_path,
        files=[target],
        action="create",
        note_slug="rule__x",
        push=False,
    )
    assert not result.success
    assert "nao e um repositorio" in (result.error or "").lower()


def test_sync_noop_when_no_changes(local_repo: Path):
    seed = local_repo / "seed.txt"
    result = sync(
        project_root=local_repo,
        files=[seed],
        action="update",
        note_slug="rule__x",
        push=False,
    )
    assert result.success
    assert "nada a commitar" in (result.error or "").lower()


def test_sync_can_start_from_notes_subdirectory(local_repo: Path):
    notes_dir = local_repo / "notes"
    notes_dir.mkdir()
    note_path = notes_dir / "note.md"
    note_path.write_text("hello world", encoding="utf-8")

    result = sync(
        project_root=notes_dir,
        files=[note_path],
        action="create",
        note_slug="rule__x",
        push=False,
    )

    assert result.success
    assert result.commit_hash is not None
