from __future__ import annotations

from typing import TYPE_CHECKING

from ws.templates import WORKSPACE_DOC

if TYPE_CHECKING:
    from ws.workspace import Workspace


class Overlay:
    """Generated `CLAUDE.md` inside a workspace. No checkout inventory."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def path(self):
        return self.workspace.path() / "CLAUDE.md"

    def render(self) -> str:
        return (
            f"# Workspace `{self.workspace.name}`\n"
            "\n"
            "Stay inside this directory.\n"
            "\n"
            f"Instructions: [docs/{WORKSPACE_DOC}](docs/{WORKSPACE_DOC}).\n"
        )

    def write(self) -> None:
        self.path().write_text(self.render())
