"""Git synchronization for big-brain notes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError


class GitSyncError(Exception):
    """Base class for git sync errors."""


class GitConflictError(GitSyncError):
    """Raised when a `pull --rebase` produces conflicts."""

    def __init__(self, conflicting_files: list[str]):
        super().__init__(
            "Conflito detectado durante rebase: "
            + ", ".join(conflicting_files)
        )
        self.conflicting_files = conflicting_files


@dataclass
class SyncResult:
    """Outcome of a sync() call."""

    success: bool
    commit_hash: str | None
    pushed: bool
    error: str | None = None


def _open_repo(project_root: Path) -> Repo | None:
    """Open the git repo at or above `project_root` or return None if absent."""
    try:
        return Repo(project_root, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return None


def _has_remote(repo: Repo) -> bool:
    try:
        return bool(repo.remotes and "origin" in [r.name for r in repo.remotes])
    except Exception:
        return False


def _format_commit_message(
    pattern: str, action: str, note_slug: str
) -> str:
    try:
        return pattern.format(action=action, note=note_slug)
    except (KeyError, IndexError):
        return f"big-brain: {action} {note_slug}"


def sync(
    project_root: Path,
    files: list[Path],
    action: str,
    note_slug: str,
    commit_message_pattern: str = "big-brain: {action} {note}",
    push: bool = True,
) -> SyncResult:
    """Stage, commit, rebase, and optionally push the provided files.

    Returns a SyncResult describing the outcome. Raises GitConflictError
    when a pull --rebase conflict appears.
    """
    repo = _open_repo(project_root)
    if repo is None:
        return SyncResult(
            success=False,
            commit_hash=None,
            pushed=False,
            error="Diretorio nao e um repositorio git — git sync ignorado.",
        )

    repo_root = Path(repo.working_tree_dir or project_root).resolve()
    try:
        relative_files = [str(f.resolve().relative_to(repo_root)) for f in files]
    except ValueError as exc:
        return SyncResult(
            success=False,
            commit_hash=None,
            pushed=False,
            error=f"Arquivo fora do repositorio: {exc}",
        )

    if not relative_files:
        return SyncResult(
            success=False,
            commit_hash=None,
            pushed=False,
            error="Nenhum arquivo para commitar.",
        )

    try:
        repo.index.add(relative_files)
    except GitCommandError as exc:
        return SyncResult(
            success=False, commit_hash=None, pushed=False, error=str(exc)
        )

    if not repo.is_dirty(index=True, working_tree=False, untracked_files=False):
        return SyncResult(
            success=True,
            commit_hash=repo.head.commit.hexsha if _has_commits(repo) else None,
            pushed=False,
            error="Nada a commitar — arvore limpa.",
        )

    message = _format_commit_message(commit_message_pattern, action, note_slug)
    try:
        commit = repo.index.commit(message)
    except GitCommandError as exc:
        return SyncResult(
            success=False, commit_hash=None, pushed=False, error=str(exc)
        )

    pushed = False
    if _has_remote(repo):
        try:
            repo.git.pull("--rebase", "origin", repo.active_branch.name)
        except GitCommandError as exc:
            conflicting = _collect_conflicting_files(repo)
            if conflicting:
                raise GitConflictError(conflicting) from exc
            return SyncResult(
                success=False,
                commit_hash=commit.hexsha,
                pushed=False,
                error=f"Rebase falhou: {exc}",
            )

        if push:
            try:
                repo.git.push("origin", repo.active_branch.name)
                pushed = True
            except GitCommandError as exc:
                return SyncResult(
                    success=False,
                    commit_hash=commit.hexsha,
                    pushed=False,
                    error=f"Push falhou: {exc}",
                )

    return SyncResult(
        success=True, commit_hash=commit.hexsha, pushed=pushed, error=None
    )


def _has_commits(repo: Repo) -> bool:
    try:
        _ = repo.head.commit
        return True
    except Exception:
        return False


def _collect_conflicting_files(repo: Repo) -> list[str]:
    """Return unmerged paths from the current index."""
    try:
        unmerged = repo.index.unmerged_blobs()
        return sorted(unmerged.keys())
    except Exception:
        return []
