from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ws.errors import WsError


@dataclass
class Defaults:
    ref: str = "origin/main"
    mode: str = "readonly"


@dataclass
class RepoConfig:
    name: str
    path: str
    remote: str | None = None


@dataclass
class SharedConfig:
    repo: str
    ref: str
    retain: bool = False


@dataclass
class Config:
    defaults: Defaults = field(default_factory=Defaults)
    repos: list[RepoConfig] = field(default_factory=list)
    shared: list[SharedConfig] = field(default_factory=list)

    def repo(self, name: str) -> RepoConfig:
        for repo in self.repos:
            if repo.name == name:
                return repo
        raise WsError(f"unknown repo {name!r}")

    def has_repo(self, name: str) -> bool:
        return any(repo.name == name for repo in self.repos)

    def add_repo(self, spec: RepoConfig) -> None:
        if self.has_repo(spec.name):
            raise WsError(f"repo {spec.name!r} already registered")
        self.repos.append(spec)

    @classmethod
    def load(cls, path: Path) -> Config:
        raw = yaml.safe_load(path.read_text()) or {}
        defaults_raw = raw.get("defaults") or {}
        defaults = Defaults(
            ref=defaults_raw.get("ref", Defaults.ref),
            mode=defaults_raw.get("mode", Defaults.mode),
        )
        repos = [
            RepoConfig(
                name=item["name"],
                path=item["path"],
                remote=item.get("remote"),
            )
            for item in raw.get("repos") or []
        ]
        shared = [
            SharedConfig(
                repo=item["repo"],
                ref=item["ref"],
                retain=bool(item.get("retain", False)),
            )
            for item in raw.get("shared") or []
        ]
        return cls(defaults=defaults, repos=repos, shared=shared)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(self.to_dict(), sort_keys=False, default_flow_style=False)
        )

    def to_dict(self) -> dict:
        repos = []
        for repo in self.repos:
            item = {"name": repo.name, "path": repo.path}
            if repo.remote:
                item["remote"] = repo.remote
            repos.append(item)
        shared = []
        for item in self.shared:
            shared.append({"repo": item.repo, "ref": item.ref, "retain": item.retain})
        return {
            "defaults": {"ref": self.defaults.ref, "mode": self.defaults.mode},
            "repos": repos,
            "shared": shared,
        }
