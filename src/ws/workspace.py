from __future__ import annotations

import shutil
from pathlib import Path

from ws.errors import WsError
from ws.names import require_slug
from ws.overlay import Overlay
from ws.paths import symlink_relative
from ws.project import Project
from ws.state import WorkspaceState


class Workspace:
    """A directory under `wt/` for one agent or task."""

    def __init__(self, project: Project, name: str) -> None:
        self.project = project
        self.name = require_slug(name, "workspace name")

    def path(self) -> Path:
        return self.project.workspace_path(self.name)

    def record(self) -> WorkspaceState | None:
        if not self.project.state.has_workspace(self.name):
            return None
        return self.project.state.workspace(self.name)

    def require_record(self) -> WorkspaceState:
        return self.project.state.workspace(self.name)

    def overlay(self) -> Overlay:
        return Overlay(self)

    def create(self) -> None:
        dest = self.path()
        if self.project.state.has_workspace(self.name) or dest.exists():
            raise WsError(f"workspace {self.name!r} already exists")
        dest.mkdir(parents=True)
        (dest / "repo").mkdir()
        scratch = self.project.scratch_path(self.name)
        scratch.mkdir(parents=True, exist_ok=True)
        self.project.docs_path().mkdir(exist_ok=True)
        self.project.data_path().mkdir(exist_ok=True)
        symlink_relative(dest / "docs", self.project.docs_path())
        symlink_relative(dest / "data", self.project.data_path())
        symlink_relative(dest / "tmp", scratch)
        self.project.state.add_workspace(self.name)
        self.overlay().write()

    def remove(self, *, force: bool = False) -> None:
        from ws.checkout import Checkout

        record = self.require_record()
        for checkout in list(record.checkouts):
            Checkout(self, checkout.name).remove(force=force)
        dest = self.path()
        if dest.exists():
            shutil.rmtree(dest)
        scratch = self.project.scratch_path(self.name)
        if scratch.exists():
            shutil.rmtree(scratch)
        self.project.state.remove_workspace(self.name)

    def checkout(self, name: str):
        from ws.checkout import Checkout

        return Checkout(self, name)
