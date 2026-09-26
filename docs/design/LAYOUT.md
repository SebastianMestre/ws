# On-disk layout (v1)

Sits on the existing Claude Code project tree. `.ws/` is tool state.
Workspaces live in `wt/`. Shared readonly trees live under `.ws/shared/`.

Decisions:

- Shared trees are detached worktrees tracking remote-tracking refs
  (`origin/main`). Sync is fetch + `reset --hard`. Live readonly views
  may change.
- Readonly → readwrite is promote-only. No demote.
- No daemon. One lockfile. Isolation is convention plus a generated
  workspace `CLAUDE.md`.
- The repo store is **bare** clones under `.ws/repos/<name>.git`. Humans
  and agents only work in workspaces. Fetch updates `origin/*`; local
  branches are workspace branches (`ws/...`).
- `docs/` and `data/` are project-level and symlinked into every
  workspace. Scratch is **private** per workspace (boot disk is small).

## Tree

```
<project>/
  CLAUDE.md                     # human’s; ws does not overwrite
  .claude/
  docs/                         # project docs
  data/                         # datasets (often a symlink)
  tmp/                          # usually a symlink to /scratch
    ws/<workspace>/             # private scratch
  wt/<workspace>/               # subagent cwd
    CLAUDE.md                   # generated overlay
    docs -> ../../docs
    data -> ../../data
    tmp  -> ../../tmp/ws/<workspace>
    repo/<checkout>/            # symlink → shared, or RW worktree
  .ws/
    lock
    config.yaml                 # repos, defaults, retain
    state.yaml                  # workspaces, checkouts, shared trees
    .gitignore                  # lock, state.yaml, shared/
    repos/<name>.git/           # bare clone
    shared/<repo>/origin/main/  # detached worktree of the bare repo
```

Discovery: walk up to `.ws/config.yaml`. If cwd is under
`wt/<name>/`, that is the implicit workspace.

## Mapping

| Object | Path |
| --- | --- |
| Marker / config | `<project>/.ws/config.yaml` |
| Lock | `<project>/.ws/lock` |
| Bare repo | `<project>/.ws/repos/<name>.git` |
| Shared tree | `<project>/.ws/shared/<repo>/<ref as dirs>/` |
| Workspace | `<project>/wt/<workspace>/` |
| Checkout | `wt/<workspace>/repo/<checkout>/` |
| Scratch | `<project>/tmp/ws/<workspace>/` |

`origin/main` → `origin/main/`. Refs with `..` or a leading `/` are
rejected. Shared identity is `(repo, ref)`.

## Checkouts

**Readonly.** Symlink to the shared detached worktree. First workspace
that needs `(repo, ref)` creates it; the rest link.

```
git -C .ws/repos/foo.git fetch
git -C .ws/repos/foo.git worktree add --detach \
    .ws/shared/foo/origin/main origin/main
```

**Readwrite.** Worktree on a new branch `ws/<workspace>/<checkout>` so
two agents can both edit “main.”

**Promote.** Unlink, then `worktree add -b` at the current HEAD.

## Config

`.ws/config.yaml` is what the user sets. `.ws/state.yaml` is what `ws`
created. YAML, not toml.

```yaml
defaults:
  ref: origin/main
  mode: readonly

repos:
  - name: foo
    path: .ws/repos/foo.git
    remote: git@github.com:org/foo.git

shared:
  - repo: foo
    ref: origin/main
    retain: true
```

`retain` is recorded so later GC can skip those trees. v1 does not GC.

## Lock

`flock` on `.ws/lock` for mutating commands. Coarse, simple.

## v1 CLI

```
ws init [project_root]
ws repo add <remote_or_path> [--name NAME]
ws repo ls
ws add <workspace>
ws ls
ws rm <workspace> [--force]
ws checkout add <workspace> <repo> [ref] [--name NAME] [--mode MODE]
ws checkout ls <workspace>
ws checkout rm <workspace> <name> [--force]
ws checkout promote <workspace> <name>
ws sync [repo]
```

Deferred: daemon, demote, land/rebase helpers, `ws run`, `ws git`,
hard isolation, GC.
