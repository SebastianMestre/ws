from __future__ import annotations

import subprocess
from pathlib import Path

from ws.errors import WsError


class GitRepo:
    """A git checkout or worktree we run commands in."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def run(self, *args: str, cwd: Path | None = None) -> str:
        result = subprocess.run(
            ["git", "-C", str(cwd or self.path), *args],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or "git failed"
            raise WsError(detail)
        return result.stdout.strip()

    def fetch(self) -> None:
        remotes = self.run("remote")
        if not remotes:
            return
        self.run("fetch", "--all", "--prune")

    def rev_parse(self, ref: str) -> str:
        return self.run("rev-parse", "--verify", ref)

    def is_dirty(self) -> bool:
        return bool(self.run("status", "--porcelain"))

    def worktree_add_detach(self, path: Path, ref: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.run("worktree", "add", "--detach", str(path.resolve()), ref)

    def worktree_add_branch(self, path: Path, branch: str, start: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.run("worktree", "add", "-b", branch, str(path.resolve()), start)

    def worktree_remove(self, path: Path, force: bool = False) -> None:
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(path.resolve()))
        try:
            self.run(*args)
        except WsError:
            self.run("worktree", "prune")
            if path.exists():
                raise


def is_git_repo(path: Path) -> bool:
    return git_kind(path) is not None


def is_working_tree(path: Path) -> bool:
    return git_kind(path) == "worktree"


def git_kind(path: Path) -> str | None:
    """Return 'bare', 'worktree', or None."""
    if not path.exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-bare-repository"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return "bare" if result.stdout.strip() == "true" else "worktree"


def clone_bare(source: str, dest: Path) -> None:
    """Bare clone configured so fetch updates `origin/*`, not local heads."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--bare", source, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "git clone failed"
        raise WsError(detail)
    setup_bare_store(dest)


def setup_bare_store(dest: Path) -> None:
    """Point `origin` fetch at `refs/remotes/origin/*` so workspace
    branches under `refs/heads/ws/` are not clobbered. HEAD stays on a
    local branch — git worktree requires that on a bare repo.
    """
    git = GitRepo(dest)
    remotes = git.run("remote")
    if not remotes:
        return
    git.run("config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    git.run("fetch", "origin")
    try:
        git.run("remote", "set-head", "origin", "--auto")
    except WsError:
        pass
