from __future__ import annotations

from pathlib import Path

from ws.errors import WsError
from ws.names import require_ref
from ws.project import Project
from ws.repo import Repo


class SharedCheckout:
    """Detached worktree under `.ws/shared/<repo>/<ref>/`, shared by workspaces."""

    def __init__(self, project: Project, repo: str, ref: str) -> None:
        self.project = project
        self.repo_name = repo
        self.ref = require_ref(ref)

    @property
    def path(self) -> Path:
        return self.project.shared_path(self.repo_name, self.ref)

    def repo(self) -> Repo:
        return Repo(self.project, self.project.config.repo(self.repo_name))

    def ensure(self) -> Path:
        dest = self.path
        if dest.exists():
            self.project.state.add_shared(self.repo_name, self.ref)
            return dest
        repo = self.repo()
        if not repo.path.exists():
            raise WsError(f"repo path missing: {repo.path}")
        repo.fetch()
        repo.git.worktree_add_detach(dest, self.ref)
        self.project.state.add_shared(self.repo_name, self.ref)
        return dest

    def sync(self) -> None:
        dest = self.ensure()
        repo = self.repo()
        repo.fetch()
        repo.git.run("reset", "--hard", self.ref, cwd=dest)
