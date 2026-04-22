"""Tests for trigger detection and note building from triggers."""

from __future__ import annotations

import httpx

from core.config import Config, GlobalConfig
from core.session import (
    LLMClient,
    LLMMessage,
    build_note_from_trigger,
    detect_triggers,
)


def test_detect_rule_trigger():
    text = "Aqui vai uma explicacao. Nao pode reabrir pedidos cancelados. Isso vale sempre."
    hits = detect_triggers(text)
    kinds = {hit.type for hit in hits}
    assert "rule" in kinds


def test_detect_request_trigger():
    hits = detect_triggers("Preciso de uma rota nova para pedidos.")
    assert any(hit.type == "request" for hit in hits)


def test_detect_decision_trigger():
    hits = detect_triggers("Decidimos migrar para postgres.")
    assert any(hit.type == "decision" for hit in hits)


def test_detect_no_trigger():
    hits = detect_triggers("oi, tudo bem?")
    assert hits == []


def test_build_note_from_trigger_has_body_and_summary():
    hits = detect_triggers("Nao pode reabrir pedido cancelado. Isso eh critico.")
    assert hits
    note = build_note_from_trigger(hits[0], project_name="demo")
    assert note.type == "rule"
    assert note.project == "demo"
    assert note.title
    assert note.body.startswith("# ")


def test_llm_client_posts_to_codex_bridge(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"outputText": "ok"}

    def fake_post(url, json, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LLMClient(Config(GlobalConfig(), project_config=None, project_root=None))

    reply = client.chat("sistema", [LLMMessage(role="user", content="oi")])

    assert reply == "ok"
    assert captured["url"] == "http://127.0.0.1:47831/v1/chat"
    assert captured["json"]["reasoningEffort"] == "medium"
    assert captured["json"]["messages"][0] == {"role": "system", "content": "sistema"}


def test_llm_client_falls_back_when_bridge_is_unavailable(monkeypatch):
    def fake_post(url, json, timeout):  # noqa: ANN001
        raise httpx.ConnectError("bridge offline")

    monkeypatch.setattr(httpx, "post", fake_post)
    client = LLMClient(Config(GlobalConfig(), project_config=None, project_root=None))

    reply = client.chat("sistema", [LLMMessage(role="user", content="oi")])

    assert "codex-bridge serve" in reply
    assert "oi" in reply
