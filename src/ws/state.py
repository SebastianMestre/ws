from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ws.errors import WsError


@dataclass
class CheckoutState:
    name: str
    repo: str
    ref: str
    mode: str
    branch: str | None = None


@dataclass
class WorkspaceState:
    name: str
    checkouts: list[CheckoutState] = field(default_factory=list)

    def checkout(self, name: str) -> CheckoutState:
        for checkout in self.checkouts:
            if checkout.name == name:
                return checkout
        raise WsError(f"unknown checkout {name!r} in workspace {self.name!r}")

    def has_checkout(self, name: str) -> bool:
        return any(checkout.name == name for checkout in self.checkouts)


@dataclass
class SharedState:
    repo: str
    ref: str


@dataclass
class State:
    workspaces: list[WorkspaceState] = field(default_factory=list)
    shared: list[SharedState] = field(default_factory=list)

    def workspace(self, name: str) -> WorkspaceState:
        for workspace in self.workspaces:
            if workspace.name == name:
                return workspace
        raise WsError(f"unknown workspace {name!r}")

    def has_workspace(self, name: str) -> bool:
        return any(workspace.name == name for workspace in self.workspaces)

    def add_workspace(self, name: str) -> WorkspaceState:
        if self.has_workspace(name):
            raise WsError(f"workspace {name!r} already exists")
        record = WorkspaceState(name=name)
        self.workspaces.append(record)
        return record

    def remove_workspace(self, name: str) -> None:
        self.workspaces = [w for w in self.workspaces if w.name != name]

    def has_shared(self, repo: str, ref: str) -> bool:
        return any(s.repo == repo and s.ref == ref for s in self.shared)

    def add_shared(self, repo: str, ref: str) -> None:
        if not self.has_shared(repo, ref):
            self.shared.append(SharedState(repo=repo, ref=ref))

    @classmethod
    def load(cls, path: Path) -> State:
        if not path.exists():
            return cls()
        raw = yaml.safe_load(path.read_text()) or {}
        workspaces = []
        for item in raw.get("workspaces") or []:
            checkouts = [
                CheckoutState(
                    name=c["name"],
                    repo=c["repo"],
                    ref=c["ref"],
                    mode=c["mode"],
                    branch=c.get("branch"),
                )
                for c in item.get("checkouts") or []
            ]
            workspaces.append(WorkspaceState(name=item["name"], checkouts=checkouts))
        shared = [
            SharedState(repo=s["repo"], ref=s["ref"]) for s in raw.get("shared") or []
        ]
        return cls(workspaces=workspaces, shared=shared)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(self.to_dict(), sort_keys=False, default_flow_style=False)
        )

    def to_dict(self) -> dict:
        return {
            "workspaces": [
                {
                    "name": workspace.name,
                    "checkouts": [
                        {
                            "name": c.name,
                            "repo": c.repo,
                            "ref": c.ref,
                            "mode": c.mode,
                            "branch": c.branch,
                        }
                        for c in workspace.checkouts
                    ],
                }
                for workspace in self.workspaces
            ],
            "shared": [{"repo": s.repo, "ref": s.ref} for s in self.shared],
        }
