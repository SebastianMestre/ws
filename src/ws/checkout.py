from __future__ import annotations

from pathlib import Path

from ws.errors import WsError
from ws.gitutil import GitRepo
from ws.names import branch_for, require_ref, require_slug
from ws.paths import symlink_relative
from ws.repo import Repo
from ws.shared import SharedCheckout
from ws.state import CheckoutState
from ws.workspace import Workspace

MODES = ("readonly", "readwrite")


class Checkout:
    """One named repo view inside a workspace."""

    def __init__(self, workspace: Workspace, name: str) -> None:
        self.workspace = workspace
        self.name = require_slug(name, "checkout name")

    @property
    def project(self):
        return self.workspace.project

    def path(self) -> Path:
        return self.workspace.path() / "repo" / self.name

    def record(self) -> CheckoutState:
        return self.workspace.require_record().checkout(self.name)

    def add(
        self,
        repo: str,
        ref: str | None = None,
        mode: str | None = None,
    ) -> CheckoutState:
        ws = self.workspace.require_record()
        if ws.has_checkout(self.name):
            raise WsError(
                f"checkout {self.name!r} already exists in workspace "
                f"{self.workspace.name!r}"
            )
        spec = self.project.config.repo(repo)
        ref = require_ref(ref or self.project.config.defaults.ref)
        mode = mode or self.project.config.defaults.mode
        if mode not in MODES:
            raise WsError(f"mode must be readonly or readwrite, got {mode!r}")

        dest = self.path()
        if dest.exists() or dest.is_symlink():
            raise WsError(f"path already exists: {dest}")

        if mode == "readonly":
            shared = SharedCheckout(self.project, spec.name, ref)
            shared.ensure()
            symlink_relative(dest, shared.path)
            record = CheckoutState(
                name=self.name, repo=spec.name, ref=ref, mode=mode, branch=None
            )
        else:
            branch = branch_for(self.workspace.name, self.name)
            repo_obj = Repo(self.project, spec)
            repo_obj.fetch()
            repo_obj.git.worktree_add_branch(dest, branch, ref)
            record = CheckoutState(
                name=self.name, repo=spec.name, ref=ref, mode=mode, branch=branch
            )

        ws.checkouts.append(record)
        self.workspace.overlay().write()
        return record

    def remove(self, *, force: bool = False) -> None:
        record = self.record()
        dest = self.path()
        if record.mode == "readwrite":
            git = Repo(self.project, self.project.config.repo(record.repo)).git
            if dest.exists() and GitRepo(dest).is_dirty() and not force:
                raise WsError(
                    f"checkout {self.name!r} has uncommitted changes "
                    "(pass --force to discard)"
                )
            if dest.exists():
                git.worktree_remove(dest, force=force)
        elif dest.is_symlink() or dest.exists():
            if dest.is_symlink() or dest.is_file():
                dest.unlink()
            else:
                raise WsError(f"readonly checkout is not a symlink: {dest}")

        ws = self.workspace.require_record()
        ws.checkouts = [c for c in ws.checkouts if c.name != self.name]
        self.workspace.overlay().write()

    def promote(self) -> CheckoutState:
        record = self.record()
        if record.mode != "readonly":
            raise WsError(f"checkout {self.name!r} is already readwrite")
        dest = self.path()
        if not dest.is_symlink():
            raise WsError(f"readonly checkout is not a symlink: {dest}")
        head = GitRepo(dest).rev_parse("HEAD")
        dest.unlink()
        branch = branch_for(self.workspace.name, self.name)
        git = Repo(self.project, self.project.config.repo(record.repo)).git
        git.worktree_add_branch(dest, branch, head)
        record.mode = "readwrite"
        record.branch = branch
        self.workspace.overlay().write()
        return record
