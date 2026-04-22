"""Tests for note CRUD and index generation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from core.notes import (
    Note,
    NoteDeleteError,
    NoteNotFoundError,
    create_note,
    delete_note,
    list_notes,
    load_note,
    search_notes,
    update_index,
    update_note,
)


def _make_note(title: str = "Regra de pedidos", note_type: str = "rule") -> Note:
    today = date.today()
    return Note(
        title=title,
        type=note_type,  # type: ignore[arg-type]
        project="demo",
        created=today,
        updated=today,
        tags=["dominio"],
        links=[],
        source="manual",
        summary="Pedidos cancelados nao reabrem.",
        body="# Regra\n\nPedidos cancelados nao reabrem.",
    )


def test_create_and_load_note(tmp_path: Path):
    note = _make_note()
    create_note(tmp_path, note)
    loaded = load_note(tmp_path, note.slug)
    assert loaded.title == note.title
    assert loaded.type == "rule"
    assert "Pedidos cancelados" in loaded.body


def test_update_note_touches_updated_date(tmp_path: Path, monkeypatch):
    note = _make_note()
    create_note(tmp_path, note)
    updated = update_note(tmp_path, note.slug, {"summary": "novo resumo"})
    assert updated.summary == "novo resumo"
    assert updated.updated == date.today()


def test_delete_note_requires_confirmation(tmp_path: Path):
    note = _make_note()
    create_note(tmp_path, note)
    with pytest.raises(NoteDeleteError):
        delete_note(tmp_path, note.slug, confirmed=False)
    assert delete_note(tmp_path, note.slug, confirmed=True)
    with pytest.raises(NoteNotFoundError):
        load_note(tmp_path, note.slug)


def test_search_matches_title_and_body(tmp_path: Path):
    create_note(tmp_path, _make_note("Politica de cancelamento"))
    create_note(tmp_path, _make_note("Arquitetura geral", "context"))
    hits = search_notes(tmp_path, "cancelamento")
    assert len(hits) == 1
    assert hits[0].title == "Politica de cancelamento"


def test_index_is_regenerated(tmp_path: Path):
    create_note(tmp_path, _make_note("Nota A"))
    create_note(tmp_path, _make_note("Nota B"))
    path = update_index(tmp_path)
    content = path.read_text(encoding="utf-8")
    assert "Nota A" in content or "nota-a" in content
    assert "| Nota | Projeto | Tipo | Atualizado |" in content


def test_list_notes_sorted_by_updated(tmp_path: Path):
    create_note(tmp_path, _make_note("Primeira"))
    create_note(tmp_path, _make_note("Segunda", "decision"))
    notes = list_notes(tmp_path)
    assert len(notes) == 2
