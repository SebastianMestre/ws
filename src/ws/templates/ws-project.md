# `ws` for the main agent

You manage this project for yourself and for subagents. Subagents do
not start here. You create a workspace, attach the repos they need,
and point them at `wt/<name>/`.

Do not inventory repos or workspaces in this file. Run commands.

## Concepts

`ws` manages workspaces for agents. It extends git worktrees to
projects that span more than one repo.

- **Project** — this directory: one `.ws/` plus many workspaces. `ws`
  finds it by walking up to `.ws/config.yaml`.
- **Repo** — a git remote registered with `ws repo add`. The clone is
  bare, under `.ws/repos/`. It is not a place to edit files.
- **Workspace** — `wt/<name>/`, a sandbox for you or a subagent. This
  is where work happens.
- **Checkout** — one repo as it appears inside a workspace, at
  `repo/<name>/`.
  - **readonly** — shared tree, many workspaces may see the same
    files. Do not edit; `ws` does not enforce that.
  - **readwrite** — a private worktree at
    `wt/<workspace>/repo/<checkout>/` on branch
    `ws/<workspace>/<checkout>`. Edit and run git here.

## Where things live

- `.ws/` — data directory managed by `ws`. Do not edit it.
- `docs/`, `data/` — shared into every workspace.
- `wt/<name>/` — one workspace. This is the subagent’s cwd.
- `tmp/ws/<name>/` — that workspace’s scratch.

If you are going to do any code changes, you must work in a workspace
too.

## Repos

```
ws repo ls
ws repo add <git-url-or-local-path> [--name NAME]
```

`repo add` makes a bare clone under `.ws/repos/`. The default checkout
ref is `origin/main`. If a later `checkout add` fails, inspect
`origin/HEAD` on the bare repo and pass that ref (for example
`origin/master`).

## Create a workspace for a subagent

```
ws add <name>
ws checkout add <name> <repo> [ref] [--mode readonly|readwrite]
```

- `readonly` (default): shared tree, many workspaces can see it.
  The subagent must not edit it; `ws` does not enforce that.
- `readwrite`: a worktree on `ws/<name>/<checkout>`. The subagent
  may edit and run git there.

You can attach several repos. Then start the subagent with cwd
`wt/<name>/` and tell it to read `CLAUDE.md`.

From the project root you must pass `<name>`. Inside `wt/<name>/`
you can omit it (`ws checkout add <repo>`).

```
ws ls
ws checkout ls <name>
```

## When the subagent is done

Inspect `wt/<name>/` if you want, then:

```
ws rm <name>
ws rm <name> --force
```

`--force` is required if a readwrite checkout is dirty. Bare clones
and shared trees stay; only that workspace goes away.

## Other commands you will need

```
ws checkout promote <name> <checkout>
ws checkout rm <name> <checkout> [--force]
ws sync [repo]
```

`promote` turns a readonly checkout into a readwrite worktree. There
is no demote. `sync` fetches and resets shared readonly trees in
place; live workspaces will see files change.
