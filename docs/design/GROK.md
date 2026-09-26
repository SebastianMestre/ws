<!-- ai-authored -->

# booth — independent design (Grok 4.7)

Generated with empty context; did not see the `ws` design. Model: grok-4.7-high-fast.

---

# booth — Subagent Workspace Manager

## 1. Problem and intended workflow

### Today
A developer runs Claude Code at a project root that looks like:

```
CLAUDE.md
.claude/
docs/
repo/          # one or more git checkouts
data/          # symlinks to large datasets
tmp/           # symlink to /scratch (or similar)
wt/            # ad-hoc agent worktrees
```

The main agent creates directories under `wt/`, prompts subagents to stay there, and hopes they do. Multiple repos live under `repo/`; edit vs reference is also prompt-only. Shared layout means accidental cross-writes, branch collisions, and unclear teardown.

### Intended workflow
1. **Human or main Claude** works at the project root (unchanged: `CLAUDE.md`, docs, overview of all repos).
2. When a task needs a sandboxed subagent, the main agent calls **`booth`** to create a named workspace under `wt/`.
3. `booth` materializes a **directory the subagent should treat as its cwd**, with only the repos it needs — writable checkouts for edit targets, read-only views for reference.
4. The main agent launches Claude Code (or another agent) with cwd = that booth path and a short prompt that says “stay in this booth.”
5. When done, `booth teardown` removes worktrees / cleans state; the main agent can inspect status anytime via `booth list` / `booth show`.

**Main agent** = orchestrator at project root; owns planning and `booth` CLI.  
**Subagent** = worker inside one booth; does not call `booth create` for siblings (v1 convention); may call `booth status` / `booth tip` for self-info.

---

## 2. Concepts / object model

| Concept | Meaning |
|--------|---------|
| **Project** | Directory containing `CLAUDE.md` (or `.booth/project.toml`). Root of main agent. |
| **Booth** | Named, isolated workspace for one subagent run. Lives under `wt/<name>/`. |
| **Mount** | How one git repo appears inside a booth: **edit** or **ref**. |
| **Edit mount** | Dedicated git worktree (or clone) the subagent may commit in. |
| **Ref mount** | Read-only view of an existing checkout (symlink or bind); for reading only. |
| **Shared volume** | Project-level `data/` and `tmp/` — visible in every booth by default (same paths). |
| **Manifest** | `.booth/booth.toml` + per-booth `wt/<name>/.booth/manifest.json` describing mounts and lifecycle. |

**Identity:** booth names are slug-like (`fix-auth-timeout`, `explore-billing`). Unique within the project while active.

**Session (soft):** optional label linking a booth to a chat/task id for humans; not a daemon session.

---

## 3. On-disk layout

Evolve the existing tree; do not invent a parallel universe.

```
<project>/
  CLAUDE.md
  .claude/
  docs/
  repo/
    api/                 # primary checkouts (human + main agent)
    web/
    shared-lib/
  data/                  # unchanged; large datasets via symlink
  tmp/                   # unchanged; scratch via symlink
  wt/
    <booth-name>/
      .booth/
        manifest.json    # mounts, branch map, created_at, state
        prompt.md        # optional seed prompt copied at create
      CLAUDE.md          # thin overlay: “you are in booth X; stay here”
      docs -> ../../docs # symlink (read)
      data -> ../../data
      tmp  -> ../../tmp
      repo/
        api/             # edit: git worktree OR ref: symlink RO
        web/             # ...
      # no sibling booths visible
  .booth/
    project.toml         # registered repos, defaults
    lock/                # flock files per repo/branch
    log/                 # create/teardown events
```

### Evolution rules
- Keep `repo/` as the **canonical** checkouts for humans and the main agent.
- Keep `wt/` as the **only** place booths live (formalize what was ad-hoc).
- `data/` and `tmp/` stay project-global; booths always get the same symlinks so agents do not copy terabytes.
- Add `.booth/` at project root for tool state; do not put large blobs there.
- Optional: if `wt/` already has hand-made dirs, `booth adopt <name>` can wrap them once.

### `project.toml` (example)

```toml
name = "payments-monorepo"

[[repos]]
id = "api"
path = "repo/api"
default_branch = "main"

[[repos]]
id = "web"
path = "repo/web"

[[repos]]
id = "shared-lib"
path = "repo/shared-lib"

[defaults]
# ref mounts: "symlink" (fast) or "copy-sparse" (rare)
ref_mode = "symlink"
# edit mounts always use git worktree from path above
edit_mode = "worktree"
shared = ["docs", "data", "tmp"]
```

Repos are discovered from `repo/*` on first `booth init` if the file is missing; human can edit afterward.

---

## 4. CLI

Binary name: **`booth`**. Runnable by humans and the top-level agent. No daemon in v1.

```
booth init                          # create .booth/project.toml from repo/*
booth create <name> [flags]
booth list [--all]
booth show <name>
booth tip <name>                    # one-liner + env hints for launching a subagent
booth teardown <name> [--keep-branch]
booth adopt <name>                  # wrap existing wt/<name>
booth doctor                        # broken symlinks, stale worktrees, lock files
```

### `booth create`

```
booth create fix-timeout \
  --edit api \
  --ref web \
  --ref shared-lib \
  --branch agent/fix-timeout \
  --base origin/main \
  --prompt-file /tmp/task.md
```

Flags:
- `--edit <repo-id>` (repeatable) — writable worktree.
- `--ref <repo-id>` (repeatable) — read-only mount of `repo/<id>`.
- `--branch <name>` — branch for **all** edit mounts (default: `booth/<name>`).
- `--branch <repo-id>:<name>` — per-repo branch override.
- `--base <ref>` — starting point for new branches (default: repo `default_branch` / current HEAD of canonical checkout).
- `--from-worktree` — if branch already has a worktree elsewhere, fail clearly (see §6).
- `--prompt` / `--prompt-file` — write `wt/<name>/.booth/prompt.md` and a short `CLAUDE.md` overlay.

Exit 0 prints machine-friendly summary (path + tip). `--json` for agents.

### `booth tip <name>`

Prints something the main agent can paste:

```
cd /path/to/wt/fix-timeout
# Launch subagent here. Edit mounts: repo/api (branch booth/fix-timeout).
# Ref only: repo/web, repo/shared-lib. Do not write outside this directory.
```

### Exit codes
- `0` ok  
- `2` usage / validation  
- `3` git conflict / lock held  
- `4` missing repo registration  

---

## 5. Multi-repo checkouts: edit vs reference

### Registration
Every git root under `repo/` gets an `id` (directory name by default). Booths never invent repos outside `project.toml` in v1.

### Edit mount
For repo `api` in booth `fix-timeout`:

1. Ensure branch `booth/fix-timeout` (or override) exists, based on `--base`.
2. Create a **git worktree** at `wt/fix-timeout/repo/api` linked to `repo/api`’s object database.
3. Subagent cwd sees a normal checkout; `git status` / commit / push work as usual (push policy is human/remote concern).

### Ref mount
For `web`:

1. Symlink `wt/fix-timeout/repo/web` → `../../repo/web` (resolved absolute).
2. Mark intent in manifest as `"mode": "ref"`.
3. **Enforcement (v1, light):** on Linux, prefer `ln -s` plus documenting RO; optional `--strict-ref` uses a read-only bind mount when the user has permissions (`mount --bind` + `remount,ro`) — off by default because it needs privileges. Without privileges: convention + `CLAUDE.md` overlay + `chmod -R a-w` on the symlink target is **wrong** (would affect canonical repo). So v1 **does not** chmod the target; ref = symlink + prompt + `booth doctor` warnings if the subagent’s git writes dirty the shared checkout.

**Practical v1 rule:** Prefer **edit worktrees even for “mostly read”** when the agent might run formatters. Use **ref** only for truly reference-only large repos. Document that clearly in `booth create` help.

### Path stability
Inside a booth, paths mirror the project: `repo/<id>/...`, `docs/`, `data/`, `tmp/`. Subagent instructions and tools that assume `repo/api` keep working. The booth root is a **miniature project root**, not a flat worktree dump.

### Main agent access
Main agent keeps using `repo/` and `docs/` at the real project root. It should not edit the same files via both `repo/api` and `wt/.../repo/api` without coordinating branches (see §6).

---

## 6. Git / branches / worktrees

### Model
- Canonical clone: `repo/<id>`.
- Each edit mount: `git worktree add` from that clone.
- Default branch naming: `booth/<booth-name>` (one branch name across edit repos unless overridden).

### Conflicts and races

| Situation | v1 behavior |
|-----------|-------------|
| Two booths want edit mounts on the **same branch** | **Reject** create (or second mount). One branch → one worktree (git rule). |
| Two booths, **different branches**, same repo | Allowed; separate worktrees. |
| Branch already checked out in `repo/<id>` (main working tree) | `worktree add` fails if that branch is already checked out — booth creates a **new** branch from `--base` by default so the main tree can stay on `main`. |
| Stale worktree after crash | `booth doctor` / `teardown` runs `git worktree prune` and removes booth dir. |
| Rebase of booth branch while agent runs | Not prevented; `booth show` notes dirty state. Human/main agent responsibility. |
| Merge back | Out of scope for `booth`; human or main agent merges from the booth branch into mainline using normal git at `repo/` or inside the booth. |

### Locking
`.booth/lock/<repo-id>.lock` with `flock` during create/teardown only (not for the whole agent run). Prevents two concurrent `booth create` calls from fighting over the same worktree path/branch.

### Two agents on the same branch
**Disallowed** for edit mounts in v1. If the main agent needs parallel reviews of one branch, use one booth and multiple read-only observers, or two branches.

### Push / remote
`booth` does not push. Subagent may push if credentials exist; document risk. Optional later: `booth create --no-push` note in overlay CLAUDE.md.

---

## 7. Lifecycle

```
init → create → (run subagent outside booth CLI) → show/list → teardown
```

### Create
1. Validate name, repos, locks.
2. Create `wt/<name>/` skeleton + shared symlinks.
3. Add edit worktrees; add ref symlinks.
4. Write overlay `CLAUDE.md` + manifest.
5. Release locks; print `tip`.

### Run
`booth` does **not** spawn Claude Code in v1. The main agent (or human) does:

```bash
booth create ... 
cd "$(booth show fix-timeout --path)" && claude   # or whatever launcher
```

This keeps booth a small filesystem/git tool, not an agent runner.

### Teardown
```
booth teardown fix-timeout
booth teardown fix-timeout --keep-branch
```

1. Lock repos involved.
2. Fail if worktree has **uncommitted** changes unless `--force` (destructive) or `--stash`.
3. `git worktree remove` for each edit mount.
4. Delete `wt/<name>/` (symlinks only for refs — canonical `repo/` untouched).
5. Optionally delete local branch (`--keep-branch` preserves it for later merge).
6. Append log line under `.booth/log/`.

### States in manifest
`creating` | `ready` | `tearing_down` | (absent = gone)

---

## 8. Isolation: convention vs enforced

| Boundary | v1 |
|----------|----|
| Cwd / “stay in booth” | **Convention** + overlay `CLAUDE.md` + `booth tip` |
| Cannot see other booths | **Mostly enforced** by not linking `wt/` siblings; agent can still `cd ../other` if it tries — prompt discourages |
| Edit vs ref | Edit = own worktree (**enforced** by git). Ref = symlink (**convention** not to write; optional strict bind-mount later) |
| `data/` / `tmp/` | **Shared by design** (same symlink targets); isolation is not for datasets |
| Network / secrets | **Not enforced** (same user environment) |
| Writing to `repo/` canonical trees | Ref mounts make it easy to slip — mitigated by preferring edit mounts; doctor can scan ref targets for unexpected dirt during booth lifetime |
| Process sandbox (namespaces, containers) | **Deferred** |

v1 thesis: **correct git worktrees + mirrored paths + clear manifests** beat heavy isolation for this workflow. Enforcement focuses on what git already guarantees (one worktree per branch) and on lifecycle hygiene.

---

## 9. Concurrency

- Multiple booths in parallel: **yes**, different branches.
- Concurrent `booth create` / `teardown`: serialized per repo via flock.
- Main agent + subagent: main uses `repo/` on shared branches carefully; recommended pattern is main stays on `main`/`master` and only merges booth branches, while subagents only touch `booth/*` branches.
- `booth list` is read-only and lock-free (may be slightly stale).
- No global mutex on `data/` or `tmp/`; agents must use task-specific subdirs under `tmp/<booth-name>/` (create suggests this in overlay CLAUDE.md).

---

## 10. What to defer

1. **Daemon / always-on supervisor** — unnecessary for create/list/teardown.
2. **Spawning / supervising Claude Code** — launcher integration later (`booth run` wrapping a command).
3. **True RO mounts / containers / user namespaces** — only if convention fails in practice.
4. **Automatic PR creation / merge queues** — stay a workspace tool.
5. **Cross-host booths** or remote executors.
6. **File-level allowlists** (only `src/foo` writable) — too sharp for v1.
7. **Adopting arbitrary nested git layouts** outside `repo/`.
8. **Windows** — document Unix-first (Linux/macOS); worktrees + symlinks are the hard part.
9. **Billing / multi-tenant isolation** — single trusted user on a workstation.
10. **Syncing booth CLAUDE.md with root CLAUDE.md** beyond a short generated overlay.

---

## 11. Minimal v1 acceptance checklist

- [ ] `booth init` scans `repo/*` into `.booth/project.toml`
- [ ] `booth create` builds `wt/<name>/` with mirrored `repo/`, plus `docs`/`data`/`tmp` links
- [ ] Edit mounts are real git worktrees on `booth/<name>` (or overrides)
- [ ] Second booth cannot attach an edit mount to an already-checked-out branch
- [ ] `booth tip` / `--json` usable by the root Claude agent
- [ ] `booth teardown` removes worktrees without deleting canonical `repo/` data
- [ ] `booth doctor` finds pruned/missing worktrees and orphan `wt/` dirs

---

## 12. Example main-agent playbook (prompt fragment)

```text
When you need a subagent:
1. booth create <task-slug> --edit <repos-to-change> --ref <repos-to-read>
2. Read booth tip <task-slug> and start the subagent with that cwd.
3. Subagent must stay inside wt/<task-slug> and only commit on booth branches.
4. When finished, review the branch from the project root, then booth teardown <task-slug>
   (use --keep-branch if you still need to merge).
```

That is the whole product surface for v1: a thin, boring CLI that turns an ad-hoc `wt/` convention into explicit mounts, git-safe edit sandboxes, and a teardown story the top-level agent can drive without leaving the project root.
