"""In-memory session state + LLM interaction + note trigger detection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from core.config import Config, ProjectConfig, save_project_config
from core.inference import enrich as enrich_project
from core.notes import Note, NoteType, list_notes


TRIGGERS: dict[NoteType, list[str]] = {
    "rule": [
        r"\ba regra e\b",
        r"\bnao pode\b",
        r"\bnunca deve\b",
        r"\bsempre deve\b",
        r"\bobrigatoriamente\b",
    ],
    "request": [
        r"\bquero que\b",
        r"\bpreciso de\b",
        r"\badiciona\b",
        r"\bcria uma\b",
        r"\bimplementa\b",
    ],
    "decision": [
        r"\bvamos usar\b",
        r"\bdecidimos\b",
        r"\boptamos por\b",
        r"\bao inves de\b",
    ],
    "bug": [
        r"\btem um bug\b",
        r"\besta quebrando\b",
        r"\berro em\b",
        r"\bnao funciona\b",
    ],
    "feature": [
        r"\ba feature\b",
        r"\ba funcionalidade\b",
        r"\bo modulo de\b",
    ],
    "context": [
        r"\bo sistema e\b",
        r"\ba arquitetura\b",
        r"\bo projeto faz\b",
        r"\bbasicamente\b",
    ],
}


@dataclass
class TriggerHit:
    """A detected note trigger with surrounding context."""

    type: NoteType
    pattern: str
    snippet: str


@dataclass
class LLMMessage:
    """A single message in the LLM chat history."""

    role: str
    content: str


@dataclass
class Session:
    """Runtime state of an interactive big-brain chat session."""

    config: Config
    history: list[LLMMessage] = field(default_factory=list)
    pending_project_updates: dict[str, Any] = field(default_factory=dict)

    def load_context(self) -> str:
        """Build a system-prompt context block from project.json + notes."""
        project = self.config.project_config
        parts: list[str] = ["# Big Brain — Contexto do Projeto", ""]

        if project is not None:
            parts.append(f"**Projeto:** {project.project_name}")
            if project.description:
                parts.append(f"**Descricao:** {project.description}")
            if project.stack:
                parts.append(f"**Stack:** {', '.join(project.stack)}")
            if project.architecture:
                parts.append(f"**Arquitetura:** {project.architecture}")
            parts.append(f"**Confianca da inferencia:** {project.confidence}")
            parts.append("")

        if self.config.is_initialized:
            notes = list_notes(self.config.notes_dir)
            if notes:
                parts.append("## Notas existentes")
                for note in notes:
                    first_body_line = (
                        note.body.splitlines()[0] if note.body else ""
                    )
                    summary = note.summary or first_body_line
                    parts.append(
                        f"- **{note.type}** — [[{note.slug}]] · {note.title}"
                        + (f" — {summary}" if summary else "")
                    )
                parts.append("")

        parts.append(
            "Voce e um assistente integrado ao Big Brain. Responda em "
            f"{self.config.global_config.language}. Use o contexto acima ao responder."
        )
        return "\n".join(parts)

    def enrich(self, text: str) -> bool:
        """Incrementally update project.json from a user message.

        Returns True when the project config was changed and persisted.
        """
        if self.config.project_config is None or self.config.project_root is None:
            return False

        existing = self.config.project_config.model_dump()
        updated, changed = enrich_project(existing, text)
        if not changed:
            return False

        new_project = ProjectConfig(**updated)
        self.config.project_config = new_project
        save_project_config(self.config.project_root, new_project)
        self.pending_project_updates = updated
        return True

    def append_user(self, text: str) -> None:
        self.history.append(LLMMessage(role="user", content=text))

    def append_assistant(self, text: str) -> None:
        self.history.append(LLMMessage(role="assistant", content=text))


def detect_triggers(text: str) -> list[TriggerHit]:
    """Return all trigger matches in `text` with a ±2-sentence snippet."""
    normalized = _strip_accents(text)
    sentences = _split_sentences(text)
    sentence_starts = _sentence_offsets(text, sentences)

    hits: list[TriggerHit] = []
    seen: set[tuple[str, str]] = set()

    for note_type, patterns in TRIGGERS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
                key = (note_type, pattern)
                if key in seen:
                    break
                idx = _sentence_index_for_offset(sentence_starts, match.start())
                start = max(0, idx - 2)
                end = min(len(sentences), idx + 3)
                snippet = " ".join(sentences[start:end]).strip()
                hits.append(
                    TriggerHit(type=note_type, pattern=pattern, snippet=snippet)
                )
                seen.add(key)
                break

    return hits


def _strip_accents(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def _sentence_offsets(text: str, sentences: list[str]) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    for sentence in sentences:
        idx = text.find(sentence, cursor)
        if idx == -1:
            idx = cursor
        offsets.append(idx)
        cursor = idx + len(sentence)
    return offsets


def _sentence_index_for_offset(offsets: list[int], offset: int) -> int:
    for i, start in enumerate(offsets):
        if offset < start:
            return max(0, i - 1)
    return max(0, len(offsets) - 1)


def build_note_from_trigger(
    hit: TriggerHit,
    project_name: str,
    title: str | None = None,
    summary: str | None = None,
) -> Note:
    """Build a Note object from a trigger hit, using defaults when needed."""
    today = date.today()
    derived_title = title or _title_from_snippet(hit.snippet)
    derived_summary = summary or hit.snippet
    return Note(
        title=derived_title,
        type=hit.type,
        project=project_name,
        created=today,
        updated=today,
        tags=[],
        links=[],
        source="conversation",
        summary=derived_summary,
        body=f"# {derived_title}\n\n{hit.snippet}\n",
    )


def _title_from_snippet(snippet: str) -> str:
    """Turn the first sentence of the snippet into a title."""
    first = _split_sentences(snippet)
    candidate = first[0] if first else snippet
    candidate = candidate.strip().strip(".!?")
    words = candidate.split()
    return " ".join(words[:10]) or "Nota sem titulo"


class LLMClient:
    """Minimal codex-bridge HTTP client using the local broker."""

    def __init__(self, config: Config):
        self.config = config

    def _chat_endpoint(self) -> str:
        """Return the configured codex-bridge chat endpoint."""
        base_url = self.config.global_config.llm.base_url.rstrip("/")
        if base_url.endswith("/v1/chat"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/chat"
        return f"{base_url}/v1/chat"

    def chat(self, system: str, messages: list[LLMMessage]) -> str:
        """Send a completion request and return the assistant text.

        Falls back to a local stub response when the codex-bridge broker is
        unavailable, so the CLI remains usable in offline/dev environments.
        """
        llm = self.config.global_config.llm
        payload = {
            "model": llm.model,
            "reasoningEffort": llm.reasoning_effort,
            "messages": [
                {"role": "system", "content": system},
                *[{"role": m.role, "content": m.content} for m in messages],
            ],
            "metadata": {"client": "big-brain"},
        }

        try:
            response = httpx.post(
                self._chat_endpoint(),
                json=payload,
                timeout=float(llm.timeout_seconds),
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                return "[big-brain] codex-bridge retornou uma resposta invalida."
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            return self._offline_reply(messages, error=str(exc))

        return _extract_bridge_text(data)

    def generate_title_and_summary(self, snippet: str) -> tuple[str, str]:
        """Ask the LLM to produce a compact title + summary for a trigger hit.

        Uses a lightweight prompt. Degrades gracefully offline.
        """
        system = (
            "Voce gera titulos curtos e resumos de uma linha para notas de projeto. "
            "Responda estritamente em JSON com as chaves 'title' e 'summary'."
        )
        user = f"Gere um titulo curto e um resumo de uma linha para:\n\n{snippet}"
        text = self.chat(system, [LLMMessage(role="user", content=user)])

        try:
            data = json.loads(_extract_json_object(text))
            return str(data.get("title") or _default_title(snippet)), str(
                data.get("summary") or snippet
            )
        except (json.JSONDecodeError, ValueError):
            return _default_title(snippet), snippet

    @staticmethod
    def _offline_reply(messages: list[LLMMessage], error: str | None = None) -> str:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        detail = f"\nDetalhe: {error}" if error else ""
        return (
            "[modo offline — execute `codex-bridge serve` para respostas reais]"
            f"{detail}\nRecebi: {last_user[:200]}"
        )


def _extract_bridge_text(data: dict[str, Any]) -> str:
    """Extract plain text from the codex-bridge chat response payload."""
    return str(data.get("outputText", "")).strip() or "[sem resposta do modelo]"


def _extract_json_object(text: str) -> str:
    """Return the first JSON object found in a model response."""
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match:
        return match.group(0)
    return stripped


def _default_title(snippet: str) -> str:
    words = snippet.strip().split()
    return " ".join(words[:8]) or "Nota"
