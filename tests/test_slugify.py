"""Tests for slugify helper."""

from __future__ import annotations

from utils.slugify import slugify


def test_lowercase_and_hyphens():
    assert slugify("Pedidos Cancelados") == "pedidos-cancelados"


def test_removes_accents():
    assert slugify("Política de Cancelamento") == "politica-de-cancelamento"


def test_strips_special_chars():
    assert slugify("Bug #123: falha em /api") == "bug-123-falha-em-api"


def test_fallback_when_empty():
    assert slugify("") == "untitled"
    assert slugify("!!!") == "untitled"
