from __future__ import annotations

from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent
PROJECT_DOC = "ws-project.md"
WORKSPACE_DOC = "ws-workspace.md"

CLAUDE_BEGIN = "<!-- ws:docs -->"
CLAUDE_END = "<!-- /ws:docs -->"

PROJECT_CLAUDE = f"""\
{CLAUDE_BEGIN}
This is a `ws` project. Main-agent instructions: [docs/{PROJECT_DOC}](docs/{PROJECT_DOC}).
{CLAUDE_END}
"""


def template_text(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text()


def install_docs(docs_dir: Path) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    for name in (PROJECT_DOC, WORKSPACE_DOC):
        (docs_dir / name).write_text(template_text(name))


def install_project_claude(root: Path) -> None:
    path = root / "CLAUDE.md"
    if not path.exists():
        path.write_text(PROJECT_CLAUDE)
        return
    text = path.read_text()
    if CLAUDE_BEGIN in text:
        return
    path.write_text(text.rstrip() + "\n\n" + PROJECT_CLAUDE)
