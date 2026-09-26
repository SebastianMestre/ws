# Dogfood: `example/` with Jasper and bytecode

What it actually took to stand up a project and two workspaces, 2026-09-26.
The repos are [SebastianMestre/Jasper](https://github.com/SebastianMestre/Jasper)
and [SebastianMestre/bytecode](https://github.com/SebastianMestre/bytecode).

## 1. Empty project dir

`example/` already existed and was empty.

`ws` is not on `PATH`; every command was run from the `ws` checkout with
`uv run`. After `cd example`, that becomes:

```
uv run --project /home/seba/code/ws ws <command>
```

## 2. Init

```
uv run ws init /home/seba/code/ws/example
```

Created `.ws/`, `repo/`, `wt/`, `docs/`, `data/`, `tmp/`. Default
config is `ref: origin/main`, `mode: readonly`.

## 3. Clone the two remotes

`gh` is logged in as `SebastianMestre`, git protocol SSH.

```
cd /home/seba/code/ws/example
uv run --project /home/seba/code/ws ws repo add \
  git@github.com:SebastianMestre/Jasper.git --name Jasper
uv run --project /home/seba/code/ws ws repo add \
  git@github.com:SebastianMestre/bytecode.git --name bytecode
```

`--name` was required for Jasper if we wanted that capital J (basename
of the URL is already `Jasper` / `bytecode`, so it was optional).

Result: `repo/Jasper`, `repo/bytecode`, registered in `.ws/config.yaml`.

## 4. Default branches are not `origin/main`

`checkout add` without a ref uses `defaults.ref` (`origin/main`).
Neither repo has that:

```
git -C repo/Jasper symbolic-ref refs/remotes/origin/HEAD
# refs/remotes/origin/master

git -C repo/bytecode symbolic-ref refs/remotes/origin/HEAD
# refs/remotes/origin/trunk
```

Had to look that up with raw git. `ws` has no “show default remote
branch” and does not take `origin/HEAD`.

## 5. Two workspaces

```
uv run --project /home/seba/code/ws ws add readonly
uv run --project /home/seba/code/ws ws checkout add readonly Jasper origin/master
uv run --project /home/seba/code/ws ws checkout add readonly bytecode origin/trunk

uv run --project /home/seba/code/ws ws add jasper-rw
uv run --project /home/seba/code/ws ws checkout add jasper-rw bytecode origin/trunk
uv run --project /home/seba/code/ws ws checkout add jasper-rw Jasper origin/master \
  --mode readwrite
```

Readonly is the default mode; only the last add needed `--mode`.

## Result

| Workspace | Checkout | Mode | On disk |
| --- | --- | --- | --- |
| `wt/readonly` | Jasper @ `origin/master` | readonly | symlink → `.ws/shared/Jasper/origin/master` |
| `wt/readonly` | bytecode @ `origin/trunk` | readonly | symlink → `.ws/shared/bytecode/origin/trunk` |
| `wt/jasper-rw` | bytecode @ `origin/trunk` | readonly | same shared symlink |
| `wt/jasper-rw` | Jasper @ `origin/master` | readwrite | worktree on `ws/jasper-rw/Jasper` |

Both workspaces also have `docs/`, `data/`, and a private `tmp/` as
designed.

## Friction to remember

1. **`uv run --project …`** every time you are inside the example
   project, not the tool repo.
2. **Default ref is wrong** for any repo whose primary branch is not
   `main`. Creating a workspace meant a side trip through `git
   symbolic-ref`. Per-repo default in config, or resolving
   `origin/HEAD`, would have skipped that.
3. **No “create workspace with these mounts” one-liner.** Six commands
   for two workspaces, four checkouts.
4. **`--name` on `repo add`** is easy to forget if you care about
   casing; here the GitHub names already matched.
