# Getting started

This tutorial walks you through one project: install `ws`, register two
repos, open a workspace, attach checkouts, and throw it away. By the
end you will have used every command you need day to day.

You need `git`, [uv](https://docs.astral.sh/uv/), and a clone of this
repository. Commands assume `ws` is on your `PATH`.

## 1. Install the CLI

From the `ws` checkout:

```
uv tool install -e .
```

Check that it worked:

```
ws --help
```

You should see subcommands `init`, `repo`, `add`, `ls`, `rm`,
`checkout`, and `sync`.

## 2. Create a project

```
mkdir ~/ws-tutorial
ws init ~/ws-tutorial
cd ~/ws-tutorial
```

`ws init` prints the project path. The directory now has `wt/`,
`docs/`, `data/`, `tmp/`, and `.ws/`. You will work in `wt/`. Do not
edit `.ws/` by hand in this tutorial.

## 3. Register two remotes

Any two git remotes you can clone will do. These two are public and
were used while writing `ws`:

```
ws repo add git@github.com:SebastianMestre/Jasper.git --name Jasper
ws repo add git@github.com:SebastianMestre/bytecode.git --name bytecode
ws repo ls
```

You should see both names and paths under `.ws/repos/`. Those
directories are bare clones. There is nothing to `cd` into yet.

The default checkout ref is `origin/main`. These two remotes do not
use that name. Look up theirs:

```
git -C .ws/repos/Jasper.git symbolic-ref refs/remotes/origin/HEAD
git -C .ws/repos/bytecode.git symbolic-ref refs/remotes/origin/HEAD
```

Expect `origin/master` and `origin/trunk`. You will pass those refs
below.

## 4. Open a workspace

```
ws add tutorial
ls wt/tutorial
```

You should see `CLAUDE.md`, `docs`, `data`, `tmp`, and `repo/`.
`docs` and `data` are links back to the project. `tmp` is private
scratch for this workspace.

## 5. Attach a readonly checkout

Still in the project root:

```
ws checkout add tutorial Jasper origin/master
ls -l wt/tutorial/repo
```

`wt/tutorial/repo/Jasper` is a symlink to a shared tree. Open a file
in it if you want; treat it as read-only.

## 6. Work from inside the workspace

```
cd wt/tutorial
ws checkout add bytecode origin/trunk
ws checkout ls
```

Inside `wt/<name>/` you can omit the workspace name. `checkout ls`
should show Jasper and bytecode, both `readonly`.

## 7. Promote one checkout so you can edit

```
ws checkout promote Jasper
ws checkout ls
```

Jasper’s mode is now `readwrite` and it sits on branch
`ws/tutorial/Jasper`. Edit a file and run `git status` in
`repo/Jasper` — ordinary git.

Leave bytecode readonly. Do not run `git checkout` or `git commit` in
a readonly tree.

## 8. Sync a shared tree (optional)

From the project root, after someone else has pushed to bytecode:

```
cd ~/ws-tutorial
ws sync bytecode
```

Readonly views of `origin/trunk` jump to the new tip. That can change
files under a live workspace. For this tutorial it is enough that the
command runs without error (it is a no-op if nothing changed).

## 9. Tear down

```
ws rm tutorial --force
ws ls
```

`--force` is required if Jasper still has uncommitted edits. The
workspace directory is gone. The bare clones stay; you can `ws add`
again without re-cloning.

You now have a project you can keep, or delete with
`rm -rf ~/ws-tutorial`.

## What to read next

- [Reference](reference.md) — every command, flag, and file
- [Design notes](design/INDEX.md) — why the tree looks like this
