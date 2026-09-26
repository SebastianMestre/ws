# Reference

Facts about `ws` as implemented. For a first run, use
[Getting started](getting-started.md). For design intent, see
[docs/design/](design/LAYOUT.md).

Commands print `ws: <message>` on stderr and exit `1` on failure, `0`
on success. Mutating commands take an exclusive `flock` on
`.ws/lock` for the whole operation (including clone and fetch).

`ws` finds the project by walking from the current directory up to
`.ws/config.yaml`.

---

## Install

```
uv tool install -e <path-to-this-repo>
```

Installs an editable `ws` on `PATH` (typically `~/.local/bin`).
Alternatively run `uv run --project <path-to-this-repo> ws …` from
anywhere.

Requires Python ≥ 3.11, `git`, and a filesystem that supports
symlinks and `flock`.

---

## Concepts

| Term | Meaning |
| --- | --- |
| **Project** | Directory containing `.ws/config.yaml`. |
| **Repo** | A registered bare clone at `.ws/repos/<name>.git`. |
| **Workspace** | Directory `wt/<name>/` for one human or agent. |
| **Checkout** | Named view of a repo inside a workspace, under `repo/<name>/`. |
| **Readonly** | Symlink to a shared detached worktree. Convention: do not edit, do not run mutating git. |
| **Readwrite** | Git worktree on branch `ws/<workspace>/<checkout>`. Ordinary git is allowed. |
| **Shared tree** | One detached worktree per `(repo, ref)` at `.ws/shared/<repo>/<ref>/`. |

There is no demote (readwrite → readonly). Isolation is convention
plus a generated `wt/<name>/CLAUDE.md`. There is no daemon.

---

## On-disk layout

```
<project>/
  docs/
  data/
  tmp/ws/<workspace>/
  wt/<workspace>/
    CLAUDE.md
    docs -> ../../docs
    data -> ../../data
    tmp  -> ../../tmp/ws/<workspace>
    repo/<checkout>/
  .ws/
    lock
    config.yaml
    state.yaml
    .gitignore
    repos/<name>.git/
    shared/<repo>/<ref as dirs>/
```

| Object | Path |
| --- | --- |
| Config | `.ws/config.yaml` |
| Runtime state | `.ws/state.yaml` |
| Lock | `.ws/lock` |
| Bare repo | `.ws/repos/<name>.git` |
| Shared tree | `.ws/shared/<repo>/<ref>/` (`origin/main` → `origin/main/`) |
| Workspace | `wt/<name>/` |
| Checkout | `wt/<name>/repo/<checkout>/` |
| Scratch | `tmp/ws/<name>/` |

`init` creates `wt/`, `docs/`, `data/`, `tmp/`, `.ws/`, and
`.ws/repos/`. It does not create or overwrite a project-root
`CLAUDE.md`.

`.ws/.gitignore` ignores `lock`, `state.yaml`, `shared/`, and
`repos/`. `config.yaml` is meant to be committable.

---

## Names and refs

Workspace, repo, and checkout names: `[A-Za-z0-9._-]+`.

Refs: non-empty, no leading or trailing `/`, no `.` or `..` path
segment. Typical values: `origin/main`, `origin/master`, a commit
SHA.

Readwrite branch name is always `ws/<workspace>/<checkout>`. That
branch must not already exist.

Default checkout ref and mode come from `config.yaml` `defaults`
(`origin/main`, `readonly`) when omitted on the command line.

---

## Workspace inference

If the current directory is under `wt/<name>/` and `<name>` is a
known workspace, checkout commands may omit the workspace argument.

If the first positional token is a known workspace name, it is
treated as the workspace even when cwd is inside another one.

Otherwise the workspace name is required.

---

## Commands

### `ws init [path]`

Create a project at `path` (default: `.`). Fails if
`.ws/config.yaml` already exists. Prints the resolved project root.

### `ws repo add <source> [--name NAME]`

Bare-clone `source` into `.ws/repos/<name>.git` and register it.

- `source` is a git URL (`git@`, `ssh://`, `https://`, `http://`,
  `file://`, or a non-existent `*.git` path) or an existing local
  repo (working tree or bare).
- `--name` defaults to the URL/path basename with a trailing `.git`
  stripped.
- Fetch is configured as `+refs/heads/*:refs/remotes/origin/*` so
  `git fetch` updates `origin/*` and does not move `ws/…` branches.
- If `source` is a local repo, `remote` in config is that repo’s
  `origin` URL when present, otherwise `source`.

Fails if the name is already registered or the destination exists.

Prints `NAME<TAB>PATH`.

### `ws repo ls`

Prints `NAME<TAB>PATH` for each registered repo. Empty if none.

### `ws add <name>`

Create `wt/<name>/` with `repo/`, generated `CLAUDE.md`, and
symlinks `docs`, `data`, `tmp`. Creates project `docs/` and `data/`
if missing, and `tmp/ws/<name>/`.

Fails if the workspace already exists in state or on disk. Prints
the workspace path.

### `ws ls`

Prints `NAME<TAB>CHECKOUTS` (comma-separated checkout names, or
`-`). Empty if none.

### `ws rm <name> [--force]`

Remove every checkout in the workspace (`git worktree remove` for
readwrite), then delete `wt/<name>/` and `tmp/ws/<name>/`.

Fails if a readwrite checkout is dirty unless `--force`. Shared
trees and bare clones are kept.

### `ws checkout add [workspace] <repo> [ref] [--name NAME] [--mode MODE]`

Attach a checkout.

- `repo` must already be registered.
- `ref` defaults to `defaults.ref`.
- `--name` defaults to the repo name.
- `--mode` is `readonly` or `readwrite`, default `defaults.mode`.

**Readonly.** Ensure a shared detached worktree at
`.ws/shared/<repo>/<ref>/` (fetch + `worktree add --detach` on first
use). Symlink `wt/<ws>/repo/<name>` to it.

**Readwrite.** Fetch, then `worktree add -b ws/<ws>/<name>` at that
path, starting at `ref`.

Rewrites the workspace `CLAUDE.md`. Prints
`NAME<TAB>REPO<TAB>REF<TAB>MODE`.

Fails if the checkout name exists, the destination path exists, the
mode is invalid, or git refuses the worktree (for example the branch
is already checked out).

### `ws checkout ls [workspace]`

Prints `NAME<TAB>REPO<TAB>REF<TAB>MODE<TAB>BRANCH`. Branch is `-`
for readonly. Empty if the workspace has no checkouts.

### `ws checkout rm [workspace] <name> [--force]`

Remove one checkout. Readwrite: refuse if dirty unless `--force`,
then `git worktree remove`. Readonly: unlink the symlink. Does not
delete the shared tree. Rewrites `CLAUDE.md`.

### `ws checkout promote [workspace] <name>`

Readonly → readwrite only. Unlink the symlink, `worktree add -b
ws/<ws>/<name>` at the current `HEAD`. Fails if the checkout is not
readonly or is not a symlink.

Prints `NAME<TAB>MODE<TAB>BRANCH`.

### `ws sync [repo]`

For each recorded shared tree (optionally filtered by `repo`):
fetch the bare clone, then `git reset --hard <ref>` in the shared
worktree. Live readonly workspaces see the new files.

Prints `REPO<TAB>REF` for each tree synced. No output if none match.

---

## `config.yaml`

User-edited. Written by `init` and `repo add`.

```yaml
defaults:
  ref: origin/main
  mode: readonly

repos:
  - name: Jasper
    path: .ws/repos/Jasper.git
    remote: git@github.com:SebastianMestre/Jasper.git

shared:
  - repo: Jasper
    ref: origin/main
    retain: true
```

| Key | Role |
| --- | --- |
| `defaults.ref` | Used when `checkout add` omits `ref`. |
| `defaults.mode` | Used when `checkout add` omits `--mode`. |
| `repos[].name` | CLI name. |
| `repos[].path` | Bare clone, relative to the project root unless absolute. |
| `repos[].remote` | Recorded URL; not re-read for fetch (git `origin` on the bare repo is). |
| `shared[].retain` | Reserved for future GC. v1 never collects shared trees. |

`shared:` in config is not populated by `checkout add`. Shared
trees that exist are listed in `state.yaml`.

---

## `state.yaml`

Written by `ws`. Do not edit while commands run.

```yaml
workspaces:
  - name: tutorial
    checkouts:
      - name: Jasper
        repo: Jasper
        ref: origin/master
        mode: readwrite
        branch: ws/tutorial/Jasper
      - name: bytecode
        repo: bytecode
        ref: origin/trunk
        mode: readonly
        branch: null
shared:
  - repo: Jasper
    ref: origin/master
```

---

## Git behaviour

- Bare clones are the only object store. All worktrees hang off
  `.ws/repos/<name>.git`.
- Shared trees are detached at `ref` (usually `origin/<branch>`).
- Two workspaces can share one readonly tree. Two readwrite
  checkouts cannot use the same branch (git rule). `ws` always
  creates a unique `ws/…` branch.
- `sync` is in-place `reset --hard`. It does not snapshot old tips.
- `ws` does not push, merge, rebase, or open PRs.
- Agents run ordinary `git` in readwrite checkouts. There is no
  `ws git` wrapper.

---

## Generated `CLAUDE.md`

`wt/<name>/CLAUDE.md` is rewritten on workspace create and on every
checkout add/rm/promote. It lists checkouts and states the readonly
rules. The project-root `CLAUDE.md` (if any) is never modified.

---

## Not in v1

Daemon, demote, GC of unused shared trees, `ws run`, `ws git`,
land/rebase helpers, hard filesystem isolation, migrate/adopt of
older on-disk layouts, Windows.
