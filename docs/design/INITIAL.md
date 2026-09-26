# WS — initial design

A project is usually several git repos. A task often needs more than one of
them checked out: some to edit, some only as reference. When spawning
subagents we want an isolated workspace with the right checkouts, then run
the agent in that workspace.

`ws` manages repos and checkouts for that project.

This note restates the model already sketched in `src/ws/workspace.py` and
the CLI in `src/ws/main.py`, then records the design discussion around
isolation, refs, lifecycle, and shared-checkout GC.

**Bias: keep v1 small.** Isolation and a daemon are optional later, not
load-bearing. Shared checkouts are a convenience and a convention;
agents are told not to edit them. Concurrent `ws` commands can be
serialized with a lockfile. Readwrite checkouts are normal git
worktrees; agents run git there.

---

## Core model

A project has two stores:

1. **Repo store** — bare clones, plus shared checkout trees for some
   `(repo, ref)` pairs.
2. **Workspace store** — one directory per workspace.

A workspace contains a `repo/` directory of named checkouts.

| Mode | Where the tree lives | How it appears in the workspace |
| --- | --- | --- |
| `readonly` | repo store (shared) | linked into `repo/<name>` |
| `readwrite` | the workspace itself | a git worktree |

Readonly sharing is the point: many workspaces can see the same `main`
tree without duplicating it. Not editing that tree is a convention.

### Objects

```
Repo                id, name, remote
SharedCheckout      id, repo_id, ref, retain=false
RepoStore           repos, shared_checkouts

WorkspaceCheckout   name, repo_id, ref, mode   # mode: readonly | readwrite
Workspace           name, checkouts
                    path = <project_root>/wt/<name>

Project             root, workspaces, repos, shared trees
```

Shared checkout `ref` is a remote-tracking name (`origin/main`), not a
local branch. Repos are bare clones under `.ws/repos/`. Shared trees
are detached worktrees of those. Sync updates them in place.
No demote. Workspaces symlink project `docs/` and `data/`, and get a
private `tmp/`.

On-disk layout: see [LAYOUT.md](LAYOUT.md).

---

## CLI (as sketched)

```
ws init [project_root]

ws repo ls
ws repo add [remote] --name [name]

ws ls
ws add [workspace_name]
ws rm [workspace_name]

ws checkout add <workspace_name> <repo_name> [ref] --name [name] --mode [mode]
ws checkout rm <workspace_name> <name>
ws checkout promote <workspace_name> <name>   # readonly → readwrite only
```

Later, maybe: pin/unpin, retain/GC controls, `ws run`, `ws git`. Not v1.

---

## Isolation and a daemon

**v1: skip both.** Readonly is a prompt/convention (“do not edit shared
checkouts”). That is not airtight, but it matches how agent harnesses
actually run (same OS user as the human). Hard isolation is a later
upgrade if agents misbehave enough to justify it.

### How Docker does the CLI ↔ daemon split

`docker` does not write container state itself. `dockerd` does. The CLI
is an HTTP client for the [Docker Engine API](https://docs.docker.com/reference/api/engine/):
ordinary REST (`GET /containers/json`, etc.), usually over the Unix
socket `/var/run/docker.sock` (TCP/TLS if you point `DOCKER_HOST` at
it). Same idea we want if we ever grow a daemon: control-plane RPCs
only, trees stay on disk.

```
curl --unix-socket /var/run/docker.sock \
  http://localhost/v1.45/containers/json
```

Docker has a daemon because containers need a privileged supervisor
(cgroups, mounts, image store). `ws` does not, unless we want a
dedicated-uid store.

### How expensive is a daemon?

Two different products, often mixed together:

| | Same-user helper (serialize ops) | Dedicated `ws` user (real readonly) |
| --- | --- | --- |
| Why | single writer, no races | agent cannot write shared trees |
| Code | socket + HTTP/JSON handlers, or just extract a library and put a thin server in front | all of that, plus uid, chown of worktrees, socket group |
| Install | optional systemd user unit, or CLI auto-starts a process | `useradd`, packaging, permissions; `uv`/`pip` install is no longer enough |
| Dev/test | start a server or mock it | fixtures with two uids |
| Need it? | **No.** `flock` on a project lockfile is enough. | Only if we stop trusting prompts. |

A Docker-shaped daemon is weeks of productization, not an afternoon.
A lockfile is an afternoon. v1 should be a library + CLI that takes the
lock and does the git work in-process.

If we add a daemon later, copy Docker’s shape: CLI talks REST (or
JSON-RPC) over a Unix socket; it does not proxy file I/O.

---

## Refs, pinning, and git

Branch names as refs are intentional so shared `main` can stay current.
Pinning (freeze to a commit) is still useful, but the harder part is
**history that is not a fast-forward**: rebase, someone else pushed,
merge conflicts.

Readonly / shared trees should only move through `ws` (fetch, retarget
the shared pointer). Do not rebase a tree other workspaces are reading.

Readwrite checkouts are different. Agents **need real git** there:
rebase, merge, conflict markers, `add`/`commit`, push. A closed `ws`
verb set will not cover that.

v1: a readwrite checkout is a normal worktree. The agent runs `git` in
that directory. No wrapper.

Later, optional `ws git <workspace> <checkout> -- <git command>` so we
have a chokepoint to log or (eventually) allowlist. Roadmap item; do
not block on a safety parser. For a while it can be a pass-through.

Pinning / sync still matters for *shared* trees:

- **Tracking** — ref is a branch; sync moves the shared pointer.
- **Pinned** — frozen to a commit.

Sync must not `reset --hard` a shared tree that live workspaces have
linked. Retarget a pointer; drop the old tree when unused (see GC).

Open questions (can wait):

- Is sync explicit (`ws sync`) or opportunistic on `checkout add`?
- Can a workspace pin its view of `main` while the store still tracks tip?

---

## Workspace lifecycle

Three layers, not one:

| Layer | What it can do | What it cannot |
| --- | --- | --- |
| `AGENTS.md` / `CLAUDE.md` | Tell an agent already in a workspace how to add checkouts, what not to touch | Guarantee create/teardown; agents ignore prompts |
| Skill | Same, but easier to discover | Same |
| Harness / `ws run` | Create workspace, attach checkouts, launch agent, tear down on exit | Teach an in-flight agent project conventions |

A later `ws run` (or a tiny harness) can own spawn/teardown:

1. create the workspace
2. attach the requested checkouts
3. launch the agent with that workspace as cwd / project root
4. on agent exit, tear down — or keep on failure, or keep if asked

Prompts and skills are still useful **inside** a workspace: how to request
another checkout, the difference between readonly and readwrite, do not
`rm -rf` the store. They are not a substitute for spawn/teardown.

Open questions:

- Keep-vs-delete policy on success, failure, and debug (“leave it”).
- Whether an interactive human workspace has the same lifecycle as a
  subagent workspace, or only subagents go through `ws run`.

---

## Shared checkout GC

Shared trees that no workspace references should not live forever.

Two policies at once:

1. **Idle GC** — a shared checkout with no workspace users for some time
   is a collection candidate.
2. **Retain** — some refs are expected to be used constantly (`main`,
   release branches). Those trees should stay warm even at zero users, so
   the next workspace does not pay a cold checkout.

A boolean on `SharedCheckout`:

- `retain: bool = false` — eligible for idle GC.
- `retain: true` — keep even with no users (e.g. `main`).

GC must never delete a tree still linked into a workspace, and should
respect the “no in-place update under live users” rule above.

Open questions:

- TTL / last-used clock.
- Whether `retain` is per `(repo, ref)`, or a project-level “well-known
  branches” list.

---

## Review (inconsistencies and holes)

### Real tensions

**Git will not check out the same branch in two worktrees.** The bare
repo cannot have a shared `main` worktree *and* a readwrite `main`
worktree, nor two RW workspaces both on `main`. Shared trees should be
detached (`git worktree add --detach` at the tip, or a plain tree with
`GIT_DIR` elsewhere). RW checkouts need their own branch name (or a
detached HEAD plus a branch the agent creates). This has to be decided
before `checkout add` works.

**“Keep `main` current” vs “don’t change files under live users” vs
“one symlink to one shared tree.”** All three cannot be true. Simple
v1: one shared tree per `(repo, moving ref)`, updated in place on
fetch/sync. Live readonly workspaces will see files change. The
retarget-and-GC-generations story is the complicated one; drop it until
we need it.

**A readonly link is still a git checkout.** If the shared tree has a
`.git` pointing at the bare repo, `git commit` / `git checkout` there
mutates shared refs and the tree for everyone. The prompt has to say
“don’t edit *and* don’t run mutating git in readonly checkouts,” not
just “don’t edit files.” Alternative: readonly is a tree of files with
no `.git` (history only via `ws` or the bare repo). Agents lose
`git log` / blame unless we expose it another way.

**Mode flip is underspecified.** Readonly → readwrite: unlink the
shared path, `git worktree add` there (path must be empty; branch
uniqueness applies). Readwrite → readonly: what happens to uncommitted
work and a unique local branch? Promote is in the CLI; demote is the
hard direction.

**This doc still mixes v1 and later.** Lifecycle-as-harness, pinning,
generation-based sync, and hard isolation are later. v1 is lockfile +
CLI + convention.

### Clearly missing for a first implementation

- **On-disk layout** — where the bare repos, shared trees, lockfile,
  and project state live relative to `ws/<name>/`.
- **Project / workspace discovery** — walk-up from cwd, a marker file,
  env var. Today every command takes `<workspace_name>`; agents will
  get that wrong unless cwd implies the workspace.
- **Fetch** — no `ws fetch` / `ws sync`. “Main stays current” needs a
  primitive, even if it is just “fetch on `checkout add`.”
- **Defaults** — omitted `ref`? omitted `--mode`?
- **`ws rm` must `git worktree remove`**, not only delete the
  directory, or the bare repo’s worktree list rots.
- **The agent contract** — a short AGENTS.md (readonly vs RW, don’t
  mutate shared git, how to add a checkout) is part of the product, not
  polish.
- **Auth** — clone/fetch/push use the user’s existing git credentials.
  Fine, but it is the whole remote story; there isn’t another one.

### Fine to leave

Wire format, GC TTL, `ws run`, `ws git`, real isolation, multi-machine.

---

## Deferred

- Daemon / dedicated user / hard isolation.
- `ws git` allowlisting.
- Wire format for project state (toml, sqlite, …).
- How a readonly checkout is linked (symlink is the obvious v1).
- Multi-machine / remote repo store.
- How this sits next to Cursor / Claude Code beyond “launch with this cwd.”
