"""Project inference via git, filesystem, and incremental conversation."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from git import InvalidGitRepositoryError, Repo


SENTINELS: dict[str, tuple[str, ...]] = {
    "pom.xml": ("Java", "Maven"),
    "build.gradle": ("Java", "Gradle"),
    "build.gradle.kts": ("Java", "Kotlin", "Gradle"),
    "package.json": ("Node.js",),
    "pyproject.toml": ("Python",),
    "requirements.txt": ("Python",),
    "Cargo.toml": ("Rust",),
    "go.mod": ("Go",),
    "Gemfile": ("Ruby",),
    "composer.json": ("PHP",),
}


ARCH_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("src/main/java", "controller", "service", "repository"), "Spring Boot MVC"),
    (("app/routers", "app/models"), "FastAPI"),
    (("src/routes", "src/controllers"), "Express / NestJS"),
    (("src/components", "src/pages"), "React / Next.js"),
    (("src/components", "app/"), "Next.js App Router"),
    (("src/main/kotlin",), "Kotlin/JVM"),
    (("cmd", "internal"), "Go standard layout"),
]


TECH_KEYWORDS: dict[str, str] = {
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mariadb": "MariaDB",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "kafka": "Kafka",
    "rabbitmq": "RabbitMQ",
    "elasticsearch": "Elasticsearch",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "terraform": "Terraform",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "spring boot": "Spring Boot",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "react": "React",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "vue": "Vue",
    "angular": "Angular",
    "typescript": "TypeScript",
    "graphql": "GraphQL",
}


class InferenceError(Exception):
    """Raised when inference completely fails (handled by callers)."""


def infer_project(project_root: Path) -> dict[str, Any]:
    """Run all inference passes and return a project.json-shaped dict.

    Never raises — if everything fails, returns a minimal low-confidence
    descriptor derived from the folder name.
    """
    sources: list[str] = []
    stack: set[str] = set()
    architecture: str = ""
    description: str = ""
    project_name: str = project_root.name
    git_remote: str = ""

    git_data = _infer_from_git(project_root)
    if git_data:
        sources.append("git")
        project_name = git_data.get("project_name", project_name) or project_name
        git_remote = git_data.get("git_remote", "") or git_remote

    fs_data = _infer_from_filesystem(project_root)
    if fs_data:
        sources.append("filesystem")
        stack.update(fs_data.get("stack", []))
        architecture = fs_data.get("architecture", "") or architecture
        description = fs_data.get("description", "") or description

    today = date.today().isoformat()
    confidence = _confidence(sources, stack, architecture)

    return {
        "project_name": project_name,
        "inferred_from": sources or ["folder_name"],
        "stack": sorted(stack),
        "architecture": architecture,
        "description": description,
        "git_remote": git_remote,
        "confidence": confidence,
        "created_at": today,
        "last_session": today,
    }


def _infer_from_git(project_root: Path) -> dict[str, Any]:
    """Extract project_name and remote URL from the git repo."""
    try:
        repo = Repo(project_root)
    except InvalidGitRepositoryError:
        return {}

    data: dict[str, Any] = {}
    try:
        origin = next((r for r in repo.remotes if r.name == "origin"), None)
        if origin is not None:
            url = next(iter(origin.urls), "")
            data["git_remote"] = url
            data["project_name"] = _project_name_from_url(url) or project_root.name
    except Exception:
        pass

    return data


def _project_name_from_url(url: str) -> str:
    """Extract the repo name from an HTTPS or SSH git URL."""
    if not url:
        return ""
    cleaned = url.rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]
    segment = cleaned.rsplit("/", 1)[-1]
    segment = segment.rsplit(":", 1)[-1]
    return segment


def _infer_from_filesystem(project_root: Path) -> dict[str, Any]:
    """Scan sentinel files and directory shapes to infer stack and architecture."""
    stack: list[str] = []
    for sentinel, technologies in SENTINELS.items():
        if "*" in sentinel:
            if any(project_root.glob(sentinel)):
                stack.extend(technologies)
        elif (project_root / sentinel).exists():
            stack.extend(technologies)

    if any(project_root.glob("*.csproj")):
        stack.extend(["C#", ".NET"])

    package_json = project_root / "package.json"
    if package_json.exists():
        stack.extend(_infer_from_package_json(package_json))

    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        stack.extend(_infer_from_pyproject(pyproject))

    architecture = _detect_architecture(project_root)
    description = _read_readme_summary(project_root)

    return {
        "stack": list(dict.fromkeys(stack)),
        "architecture": architecture,
        "description": description,
    }


def _infer_from_package_json(path: Path) -> list[str]:
    """Inspect dependencies of a package.json to add frameworks."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies"):
        value = raw.get(key) or {}
        if isinstance(value, dict):
            deps.update(value)

    hits: list[str] = []
    mapping = {
        "next": "Next.js",
        "react": "React",
        "vue": "Vue",
        "@angular/core": "Angular",
        "express": "Express",
        "@nestjs/core": "NestJS",
        "fastify": "Fastify",
        "typescript": "TypeScript",
    }
    for dep_name, label in mapping.items():
        if dep_name in deps:
            hits.append(label)
    return hits


def _infer_from_pyproject(path: Path) -> list[str]:
    """Best-effort scan of pyproject.toml dependency strings for frameworks."""
    try:
        text = path.read_text(encoding="utf-8").lower()
    except OSError:
        return []

    hits: list[str] = []
    mapping = {
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "typer": "Typer",
        "pydantic": "Pydantic",
        "sqlalchemy": "SQLAlchemy",
    }
    for needle, label in mapping.items():
        if needle in text:
            hits.append(label)
    return hits


def _detect_architecture(project_root: Path) -> str:
    """Return the first architecture whose sentinels all exist."""
    for sentinels, label in ARCH_PATTERNS:
        if all(_matches_sentinel(project_root, sentinel) for sentinel in sentinels):
            return label
    return ""


def _matches_sentinel(project_root: Path, sentinel: str) -> bool:
    """Check whether the project contains a path or substring sentinel."""
    if "/" in sentinel or sentinel.endswith("/"):
        candidate = project_root / sentinel.rstrip("/")
        if candidate.exists():
            return True
        return any(
            p.is_dir() and sentinel.rstrip("/") in str(p.relative_to(project_root))
            for p in project_root.rglob("*")
            if p.is_dir() and not _is_excluded(p)
        )
    return any(
        sentinel.lower() in p.name.lower()
        for p in project_root.rglob(sentinel)
        if not _is_excluded(p)
    )


def _is_excluded(path: Path) -> bool:
    excluded = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    return any(part in excluded for part in path.parts)


def _read_readme_summary(project_root: Path) -> str:
    """Read the first ~20 non-empty lines of README.md as a description."""
    for candidate in ("README.md", "readme.md", "README.MD"):
        path = project_root / candidate
        if path.exists():
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                return ""
            kept: list[str] = []
            for line in lines:
                if line.strip():
                    kept.append(line.rstrip())
                if len(kept) >= 20:
                    break
            return "\n".join(kept)
    return ""


def _confidence(
    sources: list[str], stack: set[str], architecture: str
) -> str:
    """Heuristic confidence rating."""
    score = len(sources)
    if stack:
        score += 1
    if architecture:
        score += 1
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def enrich(existing: dict[str, Any], text: str) -> tuple[dict[str, Any], bool]:
    """Incrementally enrich a project.json dict from a user message.

    Detects tech keywords and purpose hints in `text` and merges them into
    `existing`. Returns the updated dict and a flag indicating whether
    anything changed.
    """
    changed = False
    lowered = text.lower()

    current_stack = list(existing.get("stack", []))
    stack_set = {s.lower(): s for s in current_stack}
    for needle, label in TECH_KEYWORDS.items():
        if re.search(rf"\b{re.escape(needle)}\b", lowered) and label.lower() not in stack_set:
            current_stack.append(label)
            stack_set[label.lower()] = label
            changed = True

    if changed:
        existing["stack"] = sorted(set(current_stack))

    if not existing.get("description"):
        purpose = _detect_purpose(text)
        if purpose:
            existing["description"] = purpose
            changed = True

    if changed:
        existing["last_session"] = date.today().isoformat()
        sources = list(existing.get("inferred_from", []))
        if "conversation" not in sources:
            sources.append("conversation")
            existing["inferred_from"] = sources

    return existing, changed


_PURPOSE_PATTERNS = [
    re.compile(r"o projeto (?:e|faz|serve para) (.+?)\.", re.IGNORECASE),
    re.compile(r"o sistema (?:e|faz|serve para) (.+?)\.", re.IGNORECASE),
    re.compile(r"basicamente,? (.+?)\.", re.IGNORECASE),
]


def _detect_purpose(text: str) -> str:
    for pattern in _PURPOSE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip().capitalize()
    return ""
