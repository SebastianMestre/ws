from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ws.cli import main
from ws.errors import WsError
from ws.gitutil import git_kind
from ws.project import Project
from ws.repo import Repo
from ws.shared import SharedCheckout
from ws.workspace import Workspace


def git(*args: str, cwd: Path) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=ws@test",
            "-c",
            "user.name=ws",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def make_git_repo(path: Path, text: str = "hello\n") -> Path:
    path.mkdir()
    git("init", "-b", "main", cwd=path)
    (path / "README").write_text(text)
    git("add", ".", cwd=path)
    git("commit", "-m", "init", cwd=path)
    return path


def attach_origin(repo: Path, bare: Path) -> None:
    subprocess.run(
        ["git", "clone", "--bare", str(repo), str(bare)],
        check=True,
        capture_output=True,
        text=True,
    )
    git("remote", "add", "origin", str(bare), cwd=repo)
    git("push", "-u", "origin", "main", cwd=repo)


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project.init(tmp_path / "proj")


@pytest.fixture
def foo_repo(project: Project, tmp_path: Path) -> Path:
    """Working tree with origin; the ws store is a bare clone of that origin."""
    src = make_git_repo(tmp_path / "foo.git-src")
    attach_origin(src, tmp_path / "foo.git")
    Repo.add(project, str(tmp_path / "foo.git"), "foo")
    project.save()
    return src


def test_init_creates_layout(project: Project) -> None:
    assert (project.root / ".ws" / "config.yaml").is_file()
    assert (project.root / ".ws" / "repos").is_dir()
    assert not (project.root / "repo").exists()
    assert (project.root / "wt").is_dir()
    assert (project.root / "docs").is_dir()
    assert (project.root / "data").is_dir()
    assert (project.root / "tmp").is_dir()
    assert (project.root / "CLAUDE.md").is_file()
    claude = (project.root / "CLAUDE.md").read_text()
    assert "docs/ws-project.md" in claude
    assert "ws repo ls" not in claude
    assert (project.root / "docs" / "ws-project.md").is_file()
    assert (project.root / "docs" / "ws-workspace.md").is_file()
    assert "ws checkout ls" in (project.root / "docs" / "ws-workspace.md").read_text()
    assert "ws add" in (project.root / "docs" / "ws-project.md").read_text()


def test_init_appends_claude_link(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# My project\n")
    Project.init(root)
    text = (root / "CLAUDE.md").read_text()
    assert text.startswith("# My project")
    assert "docs/ws-project.md" in text


def test_init_twice_fails(project: Project) -> None:
    with pytest.raises(WsError, match="already"):
        Project.init(project.root)


def test_workspace_links_docs_data_tmp(project: Project) -> None:
    ws = Workspace(project, "task")
    ws.create()
    project.save()
    root = ws.path()
    assert (root / "docs").is_symlink()
    assert (root / "docs").resolve() == project.docs_path().resolve()
    assert (root / "data").resolve() == project.data_path().resolve()
    assert (root / "tmp").resolve() == project.scratch_path("task").resolve()
    assert (root / "CLAUDE.md").is_file()
    claude = (root / "CLAUDE.md").read_text()
    assert "stay inside" in claude.lower()
    assert "docs/ws-workspace.md" in claude
    assert "readonly" not in claude.lower()
    assert "|" not in claude


def test_readonly_checkout_is_shared_symlink(project: Project, foo_repo: Path) -> None:
    a = Workspace(project, "a")
    b = Workspace(project, "b")
    a.create()
    b.create()
    a.checkout("foo").add("foo")
    b.checkout("foo").add("foo")
    project.save()

    path_a = a.checkout("foo").path()
    path_b = b.checkout("foo").path()
    shared = project.shared_path("foo", "origin/main")
    assert path_a.is_symlink()
    assert path_b.is_symlink()
    assert path_a.resolve() == shared.resolve()
    assert path_b.resolve() == shared.resolve()
    assert (path_a / "README").read_text() == "hello\n"
    assert git_kind(project.repo_path("foo")) == "bare"
    claude = (a.path() / "CLAUDE.md").read_text()
    assert "foo" not in claude
    assert "origin/main" not in claude


def test_readwrite_uses_unique_branch(project: Project, foo_repo: Path) -> None:
    ws = Workspace(project, "edit")
    ws.create()
    record = ws.checkout("foo").add("foo", mode="readwrite")
    project.save()
    dest = ws.checkout("foo").path()
    assert dest.is_dir()
    assert not dest.is_symlink()
    assert record.branch == "ws/edit/foo"
    head = subprocess.run(
        ["git", "-C", str(dest), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert head.stdout.strip() == "ws/edit/foo"


def test_promote(project: Project, foo_repo: Path) -> None:
    ws = Workspace(project, "p")
    ws.create()
    checkout = ws.checkout("foo")
    checkout.add("foo", mode="readonly")
    checkout.promote()
    project.save()
    dest = checkout.path()
    assert not dest.is_symlink()
    assert dest.is_dir()
    assert checkout.record().mode == "readwrite"
    assert checkout.record().branch == "ws/p/foo"


def test_sync_updates_shared_tree(project: Project, foo_repo: Path) -> None:
    ws = Workspace(project, "reader")
    ws.create()
    ws.checkout("foo").add("foo")
    project.save()

    (foo_repo / "NEW").write_text("there\n")
    git("add", ".", cwd=foo_repo)
    git("commit", "-m", "update", cwd=foo_repo)
    git("push", cwd=foo_repo)

    SharedCheckout(project, "foo", "origin/main").sync()
    shared = project.shared_path("foo", "origin/main")
    assert (shared / "NEW").read_text() == "there\n"
    assert (ws.checkout("foo").path() / "NEW").read_text() == "there\n"


def test_rm_refuses_dirty_worktree(project: Project, foo_repo: Path) -> None:
    ws = Workspace(project, "dirty")
    ws.create()
    ws.checkout("foo").add("foo", mode="readwrite")
    (ws.checkout("foo").path() / "README").write_text("changed\n")
    with pytest.raises(WsError, match="uncommitted"):
        ws.remove()
    ws.remove(force=True)
    project.save()
    assert not ws.path().exists()
    assert not project.state.has_workspace("dirty")


def test_cli_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = make_git_repo(tmp_path / "src")
    attach_origin(src, tmp_path / "src.git")
    root = tmp_path / "proj"
    assert main(["init", str(root)]) == 0
    monkeypatch.chdir(root)
    assert main(["repo", "add", str(tmp_path / "src.git"), "--name", "src"]) == 0
    assert main(["add", "job"]) == 0
    monkeypatch.chdir(root / "wt" / "job")
    assert main(["checkout", "add", "src"]) == 0
    assert main(["checkout", "ls"]) == 0
    assert main(["ls"]) == 0
    assert main(["repo", "ls"]) == 0
    assert main(["checkout", "promote", "src"]) == 0
    monkeypatch.chdir(root)
    assert main(["rm", "job", "--force"]) == 0
    project = Project.load(root)
    assert not project.state.has_workspace("job")
