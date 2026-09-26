from __future__ import annotations

from pathlib import Path

from ws.config import RepoConfig
from ws.errors import WsError
from ws.gitutil import GitRepo, clone_bare, git_kind
from ws.names import require_slug
from ws.paths import relative_to
from ws.project import Project


def looks_like_remote(source: str) -> bool:
    if source.startswith(("git@", "ssh://", "https://", "http://", "file://")):
        return True
    if "://" in source:
        return True
    path = Path(source)
    return source.endswith(".git") and not path.exists()


def default_name(source: str) -> str:
    name = Path(source.rstrip("/")).name
    if name.endswith(".git"):
        name = name[: -len(".git")]
    return name


def origin_url(path: Path) -> str | None:
    kind = git_kind(path)
    if kind is None:
        return None
    try:
        return GitRepo(path).run("remote", "get-url", "origin")
    except WsError:
        return None


class Repo:
    """A registered bare clone under `.ws/repos/`."""

    def __init__(self, project: Project, spec: RepoConfig) -> None:
        self.project = project
        self.spec = spec

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def path(self) -> Path:
        return self.project.repo_path(self.spec.name)

    @property
    def git(self) -> GitRepo:
        return GitRepo(self.path)

    def fetch(self) -> None:
        self.git.fetch()

    @classmethod
    def add(cls, project: Project, source: str, name: str | None = None) -> Repo:
        name = require_slug(name or default_name(source), "repo name")
        if project.config.has_repo(name):
            raise WsError(f"repo {name!r} already registered")

        dest = project.bare_path(name)
        if dest.exists():
            raise WsError(f"destination already exists: {dest}")

        src_path = Path(source).expanduser()
        kind = git_kind(src_path) if src_path.exists() else None
        if looks_like_remote(source):
            clone_source = source
            remote = source
        elif kind is not None:
            clone_source = str(src_path.resolve())
            remote = origin_url(src_path.resolve()) or source
        else:
            raise WsError(f"not a git repo: {src_path.resolve()}")

        clone_bare(clone_source, dest)
        spec = RepoConfig(
            name=name,
            path=relative_to(project.root, dest),
            remote=remote,
        )
        project.config.add_repo(spec)
        return cls(project, spec)
