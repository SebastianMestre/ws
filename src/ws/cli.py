from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ws.errors import WsError
from ws.project import Project
from ws.repo import Repo
from ws.shared import SharedCheckout
from ws.workspace import Workspace


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except WsError as exc:
        print(f"ws: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ws",
        description="Manage multi-repo workspaces for agentic workflows.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create a ws project")
    p.add_argument("path", nargs="?", default=".", type=Path)
    p.set_defaults(func=cmd_init)

    repo = sub.add_parser("repo", help="register or list repos")
    repo_sub = repo.add_subparsers(dest="repo_cmd", required=True)
    p = repo_sub.add_parser("add", help="clone a remote or register a local checkout")
    p.add_argument("source", help="git remote URL or local path")
    p.add_argument("--name", help="repo name (default: basename)")
    p.set_defaults(func=cmd_repo_add)
    p = repo_sub.add_parser("ls", help="list registered repos")
    p.set_defaults(func=cmd_repo_ls)

    p = sub.add_parser("add", help="create a workspace")
    p.add_argument("name")
    p.set_defaults(func=cmd_ws_add)

    p = sub.add_parser("ls", help="list workspaces")
    p.set_defaults(func=cmd_ws_ls)

    p = sub.add_parser("rm", help="remove a workspace")
    p.add_argument("name")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_ws_rm)

    checkout = sub.add_parser("checkout", help="add, remove, or promote checkouts")
    co = checkout.add_subparsers(dest="checkout_cmd", required=True)
    p = co.add_parser("add", help="add a checkout to a workspace")
    p.add_argument(
        "tokens",
        nargs="*",
        metavar="ARG",
        help="[workspace] repo [ref] — workspace can be omitted inside wt/<name>/",
    )
    p.add_argument("--name", help="checkout name (default: repo name)")
    p.add_argument("--mode", choices=("readonly", "readwrite"))
    p.set_defaults(func=cmd_checkout_add)
    p = co.add_parser("ls", help="list checkouts in a workspace")
    p.add_argument("workspace", nargs="?", help="omit if cwd is inside a workspace")
    p.set_defaults(func=cmd_checkout_ls)
    p = co.add_parser("rm", help="remove a checkout")
    p.add_argument("tokens", nargs="*", metavar="ARG")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_checkout_rm)
    p = co.add_parser("promote", help="turn a readonly checkout into a worktree")
    p.add_argument("tokens", nargs="*", metavar="ARG")
    p.set_defaults(func=cmd_checkout_promote)

    p = sub.add_parser("sync", help="fetch and update shared readonly trees")
    p.add_argument("repo", nargs="?")
    p.set_defaults(func=cmd_sync)

    return parser


def cmd_init(args: argparse.Namespace) -> None:
    project = Project.init(args.path)
    print(project.root)


def cmd_repo_add(args: argparse.Namespace) -> None:
    project = Project.find()
    with project.mutate():
        repo = Repo.add(project, args.source, args.name)
    print(f"{repo.name}\t{repo.spec.path}")


def cmd_repo_ls(args: argparse.Namespace) -> None:
    project = Project.find()
    if not project.config.repos:
        return
    print("NAME\tPATH")
    for spec in project.config.repos:
        print(f"{spec.name}\t{spec.path}")


def cmd_ws_add(args: argparse.Namespace) -> None:
    project = Project.find()
    with project.mutate():
        workspace = Workspace(project, args.name)
        workspace.create()
    print(workspace.path())


def cmd_ws_ls(args: argparse.Namespace) -> None:
    project = Project.find()
    if not project.state.workspaces:
        return
    print("NAME\tCHECKOUTS")
    for workspace in project.state.workspaces:
        names = ",".join(c.name for c in workspace.checkouts) or "-"
        print(f"{workspace.name}\t{names}")


def cmd_ws_rm(args: argparse.Namespace) -> None:
    project = Project.find()
    with project.mutate():
        Workspace(project, args.name).remove(force=args.force)


def resolve_workspace(project: Project, tokens: list[str]) -> tuple[str, list[str]]:
    if tokens and project.state.has_workspace(tokens[0]):
        return tokens[0], tokens[1:]
    inferred = project.workspace_from_cwd()
    if inferred:
        return inferred, tokens
    raise WsError("not inside a workspace; pass the workspace name first")


def cmd_checkout_add(args: argparse.Namespace) -> None:
    project = Project.find()
    workspace_name, rest = resolve_workspace(project, args.tokens)
    if not rest:
        raise WsError("repo is required")
    if len(rest) > 2:
        raise WsError("usage: ws checkout add [workspace] repo [ref]")
    repo, ref = rest[0], rest[1] if len(rest) > 1 else None
    with project.mutate():
        checkout = Workspace(project, workspace_name).checkout(args.name or repo)
        record = checkout.add(repo, ref, args.mode)
    print(f"{record.name}\t{record.repo}\t{record.ref}\t{record.mode}")


def cmd_checkout_ls(args: argparse.Namespace) -> None:
    project = Project.find()
    name = args.workspace or project.workspace_from_cwd()
    if not name:
        raise WsError("not inside a workspace; pass the workspace name")
    record = project.state.workspace(name)
    if not record.checkouts:
        return
    print("NAME\tREPO\tREF\tMODE\tBRANCH")
    for checkout in record.checkouts:
        print(
            f"{checkout.name}\t{checkout.repo}\t{checkout.ref}\t"
            f"{checkout.mode}\t{checkout.branch or '-'}"
        )


def cmd_checkout_rm(args: argparse.Namespace) -> None:
    project = Project.find()
    workspace_name, rest = resolve_workspace(project, args.tokens)
    if len(rest) != 1:
        raise WsError("usage: ws checkout rm [workspace] <name>")
    with project.mutate():
        Workspace(project, workspace_name).checkout(rest[0]).remove(force=args.force)


def cmd_checkout_promote(args: argparse.Namespace) -> None:
    project = Project.find()
    workspace_name, rest = resolve_workspace(project, args.tokens)
    if len(rest) != 1:
        raise WsError("usage: ws checkout promote [workspace] <name>")
    with project.mutate():
        record = Workspace(project, workspace_name).checkout(rest[0]).promote()
    print(f"{record.name}\t{record.mode}\t{record.branch}")


def cmd_sync(args: argparse.Namespace) -> None:
    project = Project.find()
    with project.mutate():
        shared = list(project.state.shared)
        if args.repo:
            shared = [s for s in shared if s.repo == args.repo]
        if not shared:
            return
        for item in shared:
            SharedCheckout(project, item.repo, item.ref).sync()
            print(f"{item.repo}\t{item.ref}")
