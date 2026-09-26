from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ws.workspace import Workspace


class Overlay:
    """Generated `CLAUDE.md` inside a workspace."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def path(self):
        return self.workspace.path() / "CLAUDE.md"

    def render(self) -> str:
        rows = []
        record = self.workspace.record()
        if record is not None:
            for checkout in record.checkouts:
                rows.append(
                    f"| `{checkout.name}` | `{checkout.repo}` | `{checkout.ref}` "
                    f"| {checkout.mode} |"
                )
        table = "\n".join(rows) or "| *(none)* | | | |"
        return (
            f"# Workspace `{self.workspace.name}`\n"
            "\n"
            "You are in a `ws` workspace. Stay inside this directory.\n"
            "\n"
            "## Layout\n"
            "\n"
            "- `repo/<name>/` — checkouts (see table)\n"
            "- `docs/` — project docs (symlink; treat as reference)\n"
            "- `data/` — datasets (symlink)\n"
            "- `tmp/` — your private scratch space\n"
            "\n"
            "## Checkouts\n"
            "\n"
            "| name | repo | ref | mode |\n"
            "| --- | --- | --- | --- |\n"
            f"{table}\n"
            "\n"
            "## Rules\n"
            "\n"
            "- Do not `cd` to the parent project or other workspaces.\n"
            "- Readonly checkouts: do not edit files and do not run mutating git "
            "(`commit`, `checkout`, `rebase`, `reset`, `push`).\n"
            "- Readwrite checkouts: you may edit and run git as usual.\n"
            "- Write build artifacts and temp files under `tmp/`.\n"
        )

    def write(self) -> None:
        path = self.path()
        path.write_text(self.render())
