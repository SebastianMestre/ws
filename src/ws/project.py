from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ws.config import Config
from ws.errors import WsError
from ws.lock import ProjectLock
from ws.names import require_ref
from ws.state import State

WS_GITIGNORE = """\
lock
state.yaml
shared/
repos/
"""


class Project:
    """A directory with `.ws/config.yaml`."""

    def __init__(self, root: Path, config: Config, state: State) -> None:
        self.root = root.resolve()
        self.config = config
        self.state = state

    @property
    def ws_dir(self) -> Path:
        return self.root / ".ws"

    @property
    def config_path(self) -> Path:
        return self.ws_dir / "config.yaml"

    @property
    def state_path(self) -> Path:
        return self.ws_dir / "state.yaml"

    @property
    def lock_path(self) -> Path:
        return self.ws_dir / "lock"

    def bare_path(self, name: str) -> Path:
        return self.ws_dir / "repos" / f"{name}.git"

    def repo_path(self, name: str) -> Path:
        spec = self.config.repo(name)
        path = Path(spec.path)
        return path if path.is_absolute() else self.root / path

    def shared_path(self, repo: str, ref: str) -> Path:
        parts = require_ref(ref).split("/")
        return self.ws_dir / "shared" / repo / Path(*parts)

    def workspace_path(self, name: str) -> Path:
        return self.root / "wt" / name

    def scratch_path(self, name: str) -> Path:
        return self.root / "tmp" / "ws" / name

    def docs_path(self) -> Path:
        return self.root / "docs"

    def data_path(self) -> Path:
        return self.root / "data"

    def save(self) -> None:
        self.config.save(self.config_path)
        self.state.save(self.state_path)

    def lock(self) -> ProjectLock:
        return ProjectLock(self.lock_path)

    @contextmanager
    def mutate(self) -> Iterator[Project]:
        with self.lock():
            yield self
            self.save()

    @classmethod
    def load(cls, root: Path) -> Project:
        root = root.resolve()
        config = Config.load(root / ".ws" / "config.yaml")
        state = State.load(root / ".ws" / "state.yaml")
        return cls(root, config, state)

    @classmethod
    def find(cls, start: Path | None = None) -> Project:
        start = (start or Path.cwd()).resolve()
        for path in [start, *start.parents]:
            if (path / ".ws" / "config.yaml").is_file():
                return cls.load(path)
        raise WsError("not a ws project (no .ws/config.yaml above here)")

    @classmethod
    def init(cls, root: Path) -> Project:
        root = root.resolve()
        marker = root / ".ws" / "config.yaml"
        if marker.exists():
            raise WsError(f"already a ws project: {root}")
        root.mkdir(parents=True, exist_ok=True)
        for dirname in (".ws", "wt", "docs", "data", "tmp"):
            (root / dirname).mkdir(exist_ok=True)
        (root / ".ws" / "repos").mkdir(exist_ok=True)
        config = Config()
        state = State()
        project = cls(root, config, state)
        project.save()
        (project.ws_dir / ".gitignore").write_text(WS_GITIGNORE)
        return project

    def workspace_from_cwd(self, cwd: Path | None = None) -> str | None:
        cwd = (cwd or Path.cwd()).resolve()
        wt = (self.root / "wt").resolve()
        try:
            relative = cwd.relative_to(wt)
        except ValueError:
            return None
        parts = relative.parts
        if not parts:
            return None
        name = parts[0]
        if self.state.has_workspace(name):
            return name
        return None
