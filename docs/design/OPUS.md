# bay — independent design (Claude Opus 5.5)

Generated with empty context; did not see the `ws` design. Model: claude-opus-5-5-medium (no high-effort 5.5 slug available).

---

# `bay`: per-agent workspaces for multi-repo Claude Code projects

## 1. Problem

The developer runs Claude Code at the root of a project directory:

```
project/
  CLAUDE.md
  .claude/
  docs/      markdown project knowledge
  repo/      git checkouts (several repos), plus ad-hoc extra worktrees
  data/      symlinks to large datasets
  tmp/       symlink to big scratch storage (/scratch/...)
  wt/        agent worktrees, created ad hoc by the main agent
```

When the main agent needs to fan out, it runs `git worktree add` under `wt/`, picks a name, and writes a prompt that says "stay in `wt/foo`". This mostly works, but it has several problems:

- **No structure.** `wt/foo` is a single worktree of a single repo. A task that edits two repos and reads a third ends up with a mix of worktrees and bare paths into `repo/`. Each prompt describes it differently.
- **No record.** Nothing says which worktree belongs to which task, what branch it is on, or what it was based on. You can't easily tell whether it is finished or safe to delete.
- **Easy to escape.** A subagent that needs a file from repo B reads `repo/B` directly. That is the human's live checkout, which may be on some other branch or be edited by accident.
- **Shared scratch.** Build outputs, caches, and temp files collide in `tmp/` or land on the small OS disk.
- **Manual cleanup.** Stale worktrees, `bay/*`-style branches, and scratch dirs pile up.

`bay` is a small CLI that makes a workspace a first-class, self-describing directory. The main agent (or the human) creates, inspects, integrates, and removes workspaces with it. Subagents work inside one.

Non-goals for v1: no daemon, no containers, and no replacement for Claude Code's own subagent mechanism.

## 2. Intended workflow

### Main agent (runs at project root)

1. Plans the work and splits it into tasks.
2. For each task, runs:
   ```
   bay new fix-parser --edit core,cli --ref schema --task - <<'EOF'
   Fix the tokenizer bug in core (issue #412) and update the cli flag handling.
   EOF
   ```
3. Runs `bay prompt fix-parser` and passes the output verbatim as the subagent's prompt (Task tool). Alternatively, it runs `bay run fix-parser` to launch a separate headless Claude process in the workspace (see §8).
4. While subagents run: `bay ls`, `bay show fix-parser`, `bay diff fix-parser`.
5. When a subagent reports done: it reviews `REPORT.md` and the diff, then runs `bay sync` (rebase onto the latest base) and `bay land` (fast-forward into the target branch), or leaves the branch for a PR.
6. Runs `bay rm fix-parser`.

### Subagent (lives in `wt/<name>/`)

1. Reads `wt/<name>/CLAUDE.md`, which is generated and describes the task, layout, rules, and repos.
2. Edits only under `edit/`, reads `ref/`, `docs/`, and `data/`, and writes scratch to `tmp/`.
3. Commits on its workspace branch(es) and doesn't push, rebase, or switch branches.
4. Writes `REPORT.md` (what changed, how it was verified, open questions) and stops.

### Human

Uses the same CLI. `bay ls` shows the state of every agent's workspace at a glance, and `cd wt/fix-parser/edit/core` is a normal git worktree to inspect or take over.

## 3. Concepts / object model

| Concept | Definition |
|---|---|
| **Project** | A directory with `.bay/config.toml` at its root. There is one per project directory. |
| **Repo** | A registered git checkout under `repo/<name>`. It has a name, a path, and a default base branch (for example `main`). `repo/<name>` is the **primary checkout** and belongs to the human. |
| **Workspace** | A directory `wt/<ws>/` owned by bay. It has a name, a task, a set of mounts, a state, and an optional parent workspace. |
| **Mount** | One repo inside a workspace, in a mode:<br>• `edit`: a git worktree on a workspace-owned branch.<br>• `ref`: a read-only snapshot at a pinned commit. |
| **Workspace branch** | `bay/<ws>` in each edited repo. The name is the same across repos so cross-repo changes line up. |
| **Base** | For each edit mount, the branch it forked from (`main`, or another workspace's branch) and the exact commit, recorded at creation. |
| **Target** | Where `bay land` integrates. Defaults to the base branch. |
| **Report** | `wt/<ws>/REPORT.md`, the subagent's hand-off. |

Workspace state is mostly **derived** from what is on disk and in git; very little is stored:

- **`created`**: the workspace exists and no commits have been made yet.
- **`active`**: commits exist or the worktree is dirty.
- **`done`**: `REPORT.md` exists or `bay done` was run.
- **`landed`**: every edit branch is an ancestor of its target.
- **`stale`**: the workspace references a worktree or branch that no longer exists.

The only stored lifecycle fields are `done_at`, `landed_at`, and the `claim` (§10).

## 4. On-disk layout

### Project root (evolved)

```
project/
  CLAUDE.md                  # human-written; bay init appends a marked "Workspaces" section
  .claude/
    settings.json            # bay init adds a PreToolUse guard hook (§8)
    commands/bay.md          # optional slash command: "/bay new ..." cheat-sheet
  .bay/
    config.toml              # repos, defaults, hooks (human-edited, committed if project is versioned)
    locks/                   # flock files: project.lock, repo-<name>.lock
    archive/<ws>-<date>/     # patches + reports from removed workspaces
    log.jsonl                # append-only log of bay mutations (who, what, when)
  docs/                      # unchanged; the shared knowledge base
  repo/
    core/                    # primary checkouts: human's, agents never edit here
    cli/
    schema/
  data/                      # unchanged
  tmp -> /scratch/seba/project/
         └── bay/<ws>/       # per-workspace scratch, created and deleted by bay
  wt/                        # bay-owned. Every subdir with .bay/ws.json is a workspace
    fix-parser/
    ...
```

What changes compared with today:

- `repo/` holds **only primary checkouts**. The "extra worktrees" that used to live there move under `wt/`, either as human workspaces (`bay new --human`) or adopted with `bay adopt`.
- `wt/` is managed by bay. Directories without `.bay/ws.json` are left alone and reported by `bay doctor` as unmanaged.
- Per-workspace scratch lives on the big disk under `tmp/bay/<ws>`, never on the OS disk.

### Workspace directory

```
wt/fix-parser/
  CLAUDE.md             # generated: task, layout, rules, mounts, conventions
  TASK.md               # the task text as given to bay new (source of truth for the brief)
  REPORT.md             # written by the subagent at the end
  .claude/settings.json # generated: permissions for `bay run` mode (§8)
  .bay/
    ws.json             # metadata (below)
    env                 # sourceable: BAY_WS, BAY_ROOT, TMPDIR, BAY_PORT_BASE, ...
  edit/
    core/               # git worktree, branch bay/fix-parser, based on main@a1b2c3
    cli/                # git worktree, branch bay/fix-parser, based on main@9f8e7d
  ref/
    schema/             # detached worktree at main@5e6f70, files chmod a-w
  docs -> ../../docs    # symlink, read by convention
  data -> ../../data    # symlink (or data/<only selected> with --data a,b)
  tmp  -> ../../tmp/bay/fix-parser
  notes/                # subagent's free-form working notes (kept in archive)
```

Everything a subagent needs is under one root, so "stay inside `wt/fix-parser/`" is a complete rule. The subagent never needs a path into `repo/`.

### `ws.json`

```json
{
  "name": "fix-parser",
  "created_at": "2026-09-26T12:30:00-03:00",
  "created_by": "agent:main",
  "parent": null,
  "mounts": [
    {"repo": "core",   "mode": "edit", "branch": "bay/fix-parser",
     "base_ref": "main", "base_commit": "a1b2c3...", "target": "main"},
    {"repo": "cli",    "mode": "edit", "branch": "bay/fix-parser",
     "base_ref": "main", "base_commit": "9f8e7d...", "target": "main"},
    {"repo": "schema", "mode": "ref",  "commit": "5e6f70...", "ref": "main"}
  ],
  "port_base": 41200,
  "claim": {"session": "claude-7c1e", "pid": 31337, "host": "ws-01", "since": "..."},
  "done_at": null,
  "landed_at": null
}
```

Each workspace carries its own metadata, and there is no central index. `bay ls` scans `wt/*/.bay/ws.json`, so a deleted directory or a copied workspace can't leave an index out of sync.

### `.bay/config.toml`

```toml
[defaults]
branch_prefix = "bay/"
ref_mode      = "worktree"       # worktree | symlink (see §5)
land_strategy = "ff"             # ff | merge | squash
port_block    = 20

[repo.core]
path = "repo/core"
base = "main"

[repo.cli]
path = "repo/cli"
base = "main"

[repo.schema]
path     = "repo/schema"
base     = "main"
ref_only = true                  # bay refuses --edit schema without --force

[hooks]
post_create = "scripts/bay-setup.sh"   # run in workspace root: venvs, npm ci, etc.
pre_remove  = ""
```

## 5. Checkouts with multiple repos: edit vs reference

### Edit mounts

- Run `git -C repo/<r> worktree add wt/<ws>/edit/<r> -b bay/<ws> <base_commit>`.
- The base defaults to the repo's configured base branch, as currently known locally. Pass `--fetch` to update it from the remote first.
- Worktrees share the object store with `repo/<r>`, so creating one is fast and disk-cheap. Only the checkout's working files cost disk.
- For large repos, `--sparse core=src/tokenizer,tests` uses `git sparse-checkout` for that mount.

### Reference mounts

A reference mount is a read-only view of another repo at a known commit. There are three options:

| Option | Pros | Cons |
|---|---|---|
| Symlink to `repo/<r>` | Free, always current | Shows the human's live checkout, which can change branch mid-task. It is also writable, which is the current failure mode. |
| Detached worktree at a pinned commit, files `chmod a-w` (**default**) | Stable, reproducible, recorded, hard to edit by accident | Costs working-tree disk; can go stale |
| `git archive` export | Fully decoupled | Loses git history, which is useful for reading `git log` and blame |

The default is a detached worktree. `ref_mode = "symlink"` is available per repo for huge repos where a checkout is too expensive. In that case bay warns that the mount is live and unpinned.

`bay ref update <ws> <repo> [--to <ref>]` re-pins a reference mount by restoring write permission, checking out the new commit, and removing write permission again.

### Choosing modes

- Specify them explicitly with `--edit a,b --ref c`.
- `--ref-all` adds every other registered repo as a reference. This is convenient because it gives the subagent a complete, self-contained view.
- A repo can be switched between modes later with `bay mount <ws> --edit c` or `--ref c`. Going from reference to edit converts the detached worktree into a branch at the pinned commit. Going from edit to reference is refused if there are commits.

### Cross-repo consistency

Every edited repo uses the same branch name `bay/<ws>`, so the main agent and the human can find all parts of one change. `bay show` and `bay land` operate on the whole set.

## 6. Git: branches, worktrees, conflicts

### One writer per branch

Git refuses to check out the same branch in two worktrees. bay relies on this as its main enforced invariant: **each workspace branch has exactly one working tree, so it has exactly one writer.**

### Two agents on the "same branch"

This isn't supported directly, by design. The alternatives are:

- **Parallel.** Give each agent its own workspace off the same base (`bay new a --edit core`, `bay new b --edit core`). The main agent integrates them one after the other with `bay land` or `bay sync`.
- **Stacked.** Base one workspace on another: `bay new b --from a` bases `b`'s edit mounts on `bay/a`, and its target defaults to `bay/a`. Use this when B depends on A's work.
- **Hand-off.** Run `bay rm a --keep-branches`, then `bay new b --branch core=bay/a`. The new workspace takes over the existing branch once the old worktree is gone.

`--branch core=feature/x` checks out an existing branch in an edit mount. Git fails if that branch is checked out anywhere else, including `repo/core`. bay reports which location has it: "feature/x is checked out in repo/core; use --from-branch to fork from it instead."

### Human's primary checkout

bay never runs a mutating command in `repo/<r>`'s working tree. It reads refs from it and adds worktrees through it, and that's all.

### Rebasing: `bay sync <ws> [--onto <ref>] [--fetch]`

- Rebases each edit mount onto the latest of its base (or `--onto`).
- It runs mount by mount. On the first conflict it stops and leaves that worktree mid-rebase, then prints the conflicted files and the next steps (`git rebase --continue` / `--abort` in `wt/<ws>/edit/<r>`).
- bay never auto-resolves. The main agent can resolve the conflict itself or send the subagent back with "resolve the rebase in edit/core".
- It refuses to run if the workspace is claimed by a live session (§10), unless you pass `--force`. Rebasing under a running agent confuses it.

### Conflict prediction

`bay show` and `bay ls --conflicts` run `git merge-tree --write-tree <target> bay/<ws>`, which leaves both worktrees untouched. They also do this pairwise between active workspaces that edit the same repo, and report overlaps early, for example: "fix-parser and add-flag both touch core/src/lexer.rs".

### Landing: `bay land <ws> [--strategy ff|merge|squash] [--into <branch>]`

1. Checks that every edit mount is clean and has commits.
2. **ff** (default): every `bay/<ws>` must be a descendant of its target. If one isn't, bay suggests `bay sync` first.
3. Updates the target ref in each repo:
   - If the target branch is checked out in some worktree (usually `repo/<r>`), bay requires that worktree to be clean and runs `git merge --ff-only` there. Otherwise it refuses.
   - If it isn't checked out anywhere, bay runs `git update-ref` with the expected old value, which acts as a compare-and-swap.
   - **merge / squash**: bay creates a temporary worktree of the target under `tmp/bay/.land/`, does the merge there, and fast-forwards the target. If the merge conflicts, bay aborts and reports without leaving anything half done.
4. Multiple repos: bay checks every repo before updating any refs. If a ref update fails partway (a race), it reports exactly which repos landed. No hidden rollback in v1.
5. `--push` pushes the target afterwards. `bay push <ws>` pushes the `bay/<ws>` branches for PR-based flows. Creating PRs is deferred.

### Commits

The generated workspace `CLAUDE.md` tells subagents to commit early and often on their branch with a descriptive message, and never to run `push`, `rebase`, `reset --hard` on commits they didn't create, `checkout <other branch>`, or `worktree` commands. The main agent owns history operations through bay.

### Housekeeping

- `bay rm` uses `git worktree remove` and deletes the branch only if it has landed (or with `--delete-branches`).
- `bay gc` runs `git worktree prune`, lists orphaned `bay/*` branches that have no workspace, and deletes orphaned `tmp/bay/*` directories.

## 7. Lifecycle

### Create: `bay new`

The steps run in order. If any step fails, bay rolls back the earlier ones.

1. Validate the name (`[a-z0-9-]+`, unique) and resolve repos, bases, and commits (with `--fetch` if asked).
2. Take the project lock, then each repo lock in sorted name order.
3. Create `wt/<ws>/`, then the edit worktrees, then the reference worktrees (chmod), then the symlinks.
4. Create `tmp/bay/<ws>/`.
5. Allocate a port block (lowest free multiple of `port_block` above 41000, scanned from all `ws.json` files).
6. Write `ws.json`, `.bay/env`, `TASK.md`, `CLAUDE.md`, and `.claude/settings.json`.
7. Run the `post_create` hook with `BAY_*` in the environment. If it fails, the workspace is kept but marked, and the hook output goes to `.bay/hook.log`.
8. Print the path and the next command (`bay prompt <ws>`).

### Run

bay doesn't supervise agents in v1. The main agent launches them in one of two ways:

- **In-session subagent (default).** `bay prompt <ws>` prints a prompt block:
  ```
  You are working in the bay workspace at /abs/project/wt/fix-parser.
  First: read /abs/project/wt/fix-parser/CLAUDE.md and TASK.md.
  All file edits must be under /abs/project/wt/fix-parser/edit/.
  Use absolute paths or `cd /abs/project/wt/fix-parser` at the start of every shell command.
  Source .bay/env in shell commands that build or run things (sets TMPDIR, ports).
  When finished, write REPORT.md and reply with a 3-line summary.
  ```
  The prompt matters because Task-tool subagents share the main session's working directory and settings. They don't automatically pick up the workspace's `CLAUDE.md` or `.claude/`, so the prompt points them to it.
- **Separate process.** `bay run <ws> [--bg]` runs `claude -p "$(bay prompt <ws>)"` with the workspace as its working directory. This session loads the workspace's own `CLAUDE.md` and `.claude/settings.json`, so the stricter permissions apply (§8). Output goes to `wt/<ws>/.bay/run.log`. Use it for long or untrusted tasks, or when you want real permission scoping.

`bay claim` / `bay release` record which session is working in a workspace. `bay run` claims automatically. For in-session subagents, the prompt tells the subagent to run `bay claim` first. This is advisory, and §10 explains what it is used for.

### Done

The subagent writes `REPORT.md`, and optionally runs `bay done`, which sets `done_at`. `bay ls` shows `done` either way.

### Inspect

- `bay ls [--json]`: one line per workspace with name, state, repos (edit/ref), commits ahead, dirty flag, claim, age, and predicted conflicts.
- `bay show <ws> [--json]`: mounts, base/target, ahead/behind counts, commit log, dirty files, report excerpt, scratch usage (`du` on `tmp/bay/<ws>`).
- `bay diff <ws> [repo] [--stat]`: `git diff <base_commit>...bay/<ws>` for each edit mount.
- `bay path <ws> [repo]`: prints the absolute path, for `cd $(bay path x core)`.

### Teardown: `bay rm <ws>`

- Refuses if any edit mount is dirty, has commits that haven't landed, or the claim is live. `--force` overrides all three.
- It always archives first to `.bay/archive/<ws>-<date>/`:
  - `TASK.md`, `REPORT.md`, `notes/`, `ws.json`
  - one `git format-patch <base>..bay/<ws>` per edit mount
  - a `git diff` of any uncommitted changes
  
  A forced removal therefore loses almost nothing.
- Then it runs the `pre_remove` hook, removes the worktrees (restoring write permission on reference mounts first) and `tmp/bay/<ws>`, and deletes branches that have landed (`--keep-branches` keeps them all).
- `bay rm --landed` removes every workspace in the `landed` state. This is the usual end-of-day cleanup.

## 8. Isolation: convention vs enforcement

The design avoids pretending prompts are security. Each isolation measure is listed with how strongly it holds:

| Measure | Strength | Mechanism |
|---|---|---|
| Separate working directory per task | Enforced | A separate git worktree and directory |
| One writer per branch | Enforced | git's worktree branch exclusivity |
| History of the human's checkout not rewritten by bay | Enforced | bay never mutates `repo/*` working trees except for an ff-only land into a clean tree |
| Reference repos not editable | Enforced against accidents, bypassable on purpose | `chmod a-w` on the files, plus the guard hook below |
| Per-workspace scratch and temp | Mostly enforced | `tmp` symlink and `TMPDIR` in `.bay/env`; tools that ignore `TMPDIR` escape it |
| Port collisions avoided | Convention | `BAY_PORT_BASE` in env; the project's scripts must use it |
| Edit tools stay inside the workspace (in-session subagents) | Enforced for Edit/Write tools, not for Bash | Top-level PreToolUse guard hook (below) |
| Edit tools stay inside the workspace (`bay run`) | Enforced by Claude Code permissions | Workspace `.claude/settings.json` |
| Bash commands stay inside the workspace | Convention | The prompt and `CLAUDE.md` say so; Bash isn't parsed reliably |
| No reading other workspaces or the network | Not addressed | Deferred (§11) |

### Guard hook (`bay guard`)

`bay init` installs a PreToolUse hook in the root `.claude/settings.json` for Edit/Write-style tools. It gets the target path and blocks when:

- the path is under `repo/**` (the primary checkouts). Set `allow_primary_edits = true` if the human wants the main agent to edit there,
- the path is under `wt/*/ref/**`, `data/**`, or `docs/**`, for example because `docs` symlinks through from inside a workspace. docs can be allowlisted.

It does not need to know which agent is calling. These paths are off-limits to every agent, and edits inside `wt/<ws>/edit/` are allowed. It can't stop subagent A from editing workspace B, because in-session subagents are indistinguishable to the hook. Separate branches make that mistake visible in `bay show`, and `bay run` mode prevents it.

### `bay run` settings

The generated workspace settings allow Edit/Write only under `./edit/**`, `./notes/**`, `./REPORT.md`, and `./tmp/**`. They deny git `push`, `rebase`, `reset`, `checkout`, and `worktree` subcommands, plus `bay land`, `bay rm`, and `bay sync`, through Bash permission patterns. Bash patterns are best-effort, which the doc says outright.

### Why no stronger isolation in v1

Containers, bubblewrap, or Landlock would enforce the filesystem boundary for Bash too. They would also cut agents off from the machine's toolchains, GPUs, datasets under `data/`, and caches, and each project would need image or bind-mount setup. The failures the developer actually sees are accidental edits in the wrong place and collisions. The measures above cover those at almost no cost. Kernel sandboxing is the first thing to add if deliberate escapes turn out to matter (§11).

## 9. CLI reference (v1)

```
bay init                       # create .bay/, discover repo/*, add CLAUDE.md section + guard hook
bay repo add <name> [--path P] [--base B] [--ref-only]
bay repo ls

bay new <ws> [--edit r1,r2] [--ref r3 | --ref-all] [--base r=ref] [--branch r=existing]
             [--from <ws>] [--sparse r=paths] [--data d1,d2] [--fetch]
             [--task FILE|-] [--human]
bay mount <ws> (--edit r | --ref r)
bay ref update <ws> <repo> [--to ref]

bay prompt <ws>                # print subagent prompt
bay run <ws> [--bg] [-- claude args]
bay claim <ws> / bay release <ws>
bay done <ws>
bay exec <ws> -- <cmd...>      # run in workspace root with .bay/env loaded

bay ls [--json] [--conflicts] [--state S]
bay show <ws> [--json]
bay diff <ws> [repo] [--stat]
bay path <ws> [repo]

bay sync <ws> [--onto ref] [--fetch] [--force]
bay land <ws> [--strategy ff|merge|squash] [--into branch] [--push]
bay push <ws>

bay rm <ws> [--force] [--keep-branches|--delete-branches]
bay rm --landed
bay adopt <path> [--name ws]   # wrap an existing ad-hoc worktree under wt/ into a workspace
bay gc [--dry-run]
bay doctor                     # unmanaged dirs in wt/, stale worktrees, dead claims, broken symlinks
```

Conventions:

- Every read command supports `--json`, which is what the main agent should use.
- Exit code 0 means success, 1 means an error, and 2 means refused for safety (dirty tree, live claim, not fast-forwardable). The message always names the override flag.
- bay finds the project root by walking up to `.bay/config.toml`, so it works from inside a workspace too. `bay ls` run from a workspace still lists them all.
- Mutating commands append to `.bay/log.jsonl` with `BAY_ACTOR`, which the prompt sets to `agent:<ws>`, and `agent:main` or `human` otherwise.

### `CLAUDE.md` section added by `bay init`

```md
<!-- bay:begin -->
## Workspaces (bay)
- Never edit files under repo/ directly. For any code change, create a workspace:
  `bay new <task-name> --edit <repos> --ref-all --task -`
- Launch subagents with the exact output of `bay prompt <task-name>`.
- Check progress with `bay ls --json`; review with `bay diff`; integrate with `bay sync` then `bay land`.
- Remove finished workspaces with `bay rm`. Do not run `git worktree` yourself.
<!-- bay:end -->
```

## 10. Concurrency

The main agent may launch several subagents at once, and each of them, as well as the main agent, may call bay at the same time.

- **bay's own state.** Mutating commands take `flock` on `.bay/locks/project.lock` for the short critical section: choosing names and ports, and writing `ws.json`. Git work runs under per-repo locks (`repo-<name>.lock`), always acquired in sorted order so there are no deadlocks. Parallel `bay new` calls that touch different repos run in parallel.
- **Git.** Worktrees have separate index files, so commits in different workspaces don't contend. Shared-metadata operations (worktree add/remove, fetch, ref updates in `land`) are serialized by the per-repo lock. `land` uses compare-and-swap ref updates, so a concurrent land shows up as an error instead of lost commits. bay sets `gc.auto=0` for bay-driven commands and leaves repacking to the human or `bay gc --repack`, so auto-gc doesn't start in the middle of heavy parallel work.
- **Workspace access.** A workspace should have one agent at a time. The claim in `ws.json` records session, PID, and host. It is advisory: nothing prevents a second agent from working in the directory. It does protect the destructive commands. `sync`, `land`, and `rm` refuse on a live claim, where live means the PID exists on the same host. Claims whose PID is gone are treated as stale and shown by `bay doctor`.
- **Resources.** Workspaces get separate `TMPDIR` and scratch dirs, and disjoint port blocks. Build caches that are safe to share (ccache, the pip/npm cache) stay shared through the environment. Unsafe ones, such as in-tree `target/` or `node_modules/`, are per worktree by construction.
- **Datasets.** `data/` is shared and read-only by convention. Outputs go to `tmp/`.
- **No daemon.** All state is on disk and derived on demand, so a crashed bay command leaves at most a partial workspace. `bay doctor` finds it, and `bay rm --force` cleans it up.

## 11. Deferred

The following are not in v1:

- **Kernel-level sandboxing.** bubblewrap or Landlock profiles for `bay run` would bind-mount the workspace read-write, `repo/`, `data/`, and `docs/` read-only, and deny other workspaces. This is the first addition if escapes matter.
- **Shared-branch collaboration.** Two live agents on one branch would need locking at the file or hunk level, which is not worth building. Stacking and hand-off cover the need.
- **Merge queue / automatic integration.** Ordering lands, re-running tests after rebase, and landing automatically. The main agent does this by hand for now.
- **PR creation and CI integration.** For example `bay pr <ws>` through `gh`. `bay push` is enough to start.
- **Agent supervision.** Process management, restarts, token or cost tracking, or a TUI dashboard beyond `bay ls`.
- **Per-agent identity in the guard hook.** Telling in-session subagents apart, so the hook could stop A from writing to B.
- **Cheaper reference mounts.** Copy-on-write clones (reflink, overlayfs), sparse reference mounts by default, or a shared read-only snapshot pool when several workspaces pin the same commit.
- **Remote or multi-machine workspaces.** Claims are host-local in v1.
- **Automatic dependency setup.** Language-aware environment setup; v1 has only the `post_create` hook.
- **Submodules and LFS.** v1 runs `git submodule update --init` in edit mounts only if the config asks for it. Otherwise it is documented as unsupported.
- **Generating task text.** Creating `TASK.md` from issues or tickets.

## 12. Implementation notes

- **Language.** A single-file Python script that uses only the standard library (`tomllib`, `json`, `fcntl`, `subprocess` calling `git`), installed with `uv tool install` or dropped on `PATH`. It is fast to change while the workflow settles. A Go rewrite is an option once the design is stable.
- **Size.** About 1,500 lines. Most of the logic is careful git plumbing, with safety checks before every destructive step.
- **Tests.** Build scratch projects with 2–3 local repos, then run scripted scenarios: parallel `new`, stacked workspaces, a conflicted `sync`, a racing `land`, and a forced `rm` restored from the archive.
- **Rollout.**
  1. Run `bay init` in one project and `bay adopt` the existing `wt/*` directories.
  2. Add the `CLAUDE.md` section.
  3. Use in-session subagents with `bay prompt` for a week.
  4. Then try `bay run` for long tasks.
