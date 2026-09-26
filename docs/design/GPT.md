<!-- ai-authored -->

# Yard — independent design (GPT 5.6 Sol)

Generated with empty context; did not see the `ws` design. Model: gpt-5.6-sol-medium.

---

# Yard: Task-Scoped Workspaces for Coding Agents

## Summary

Yard is a small CLI that creates isolated, task-specific directories for coding subagents while preserving a top-level project directory for the human and coordinating Claude.

Each Yard workspace contains:

- Dedicated Git worktrees for repositories the subagent may edit.
- Detached checkouts for repositories used only as references.
- Project instructions and documentation.
- Shared access to large datasets.
- Private scratch storage.
- A machine-readable manifest describing its permissions and Git state.

Yard v1 is intentionally daemonless. It uses normal directories, Git worktrees, manifests, and short-lived file locks.

## Problem

A project may contain several repositories, shared documentation, large datasets, and scratch storage:

```text
project/
├── CLAUDE.md
├── .claude/
├── docs/
├── data/
├── repo/
│   ├── frontend/
│   ├── backend/
│   └── schemas/
├── tmp -> /scratch/project/tmp
└── wt/
```

The coordinating Claude runs from `project/`. Subagents need smaller, explicit environments, but today those environments are assembled through prompts and conventions.

This creates several risks:

- A subagent may edit the canonical checkout.
- “Reference-only” repositories are not clearly distinguished.
- Two agents may contend for the same branch.
- A workspace may accidentally share temporary files with another agent.
- It is difficult to determine which task owns a worktree.
- Cleanup can lose uncommitted work or leave stale Git worktrees.
- Multi-repository tasks have no unified status view.

Yard makes workspace construction and ownership explicit without replacing Git or requiring containers.

## Intended workflow

### Coordinating agent

The main Claude continues to run at the project root. It:

1. Decides which repositories a task may edit.
2. Selects any additional reference repositories.
3. Creates a named Yard workspace.
4. Launches a subagent inside it.
5. Inspects changes across all repositories.
6. Requests rebases or resolves integration conflicts.
7. Integrates completed branches.
8. Tears down the workspace.

Example:

```sh
yard create fix-auth \
  --edit backend \
  --edit frontend \
  --ref schemas \
  --from main

yard run fix-auth -- claude
yard inspect fix-auth
yard diff fix-auth
yard integrate fix-auth
yard destroy fix-auth
```

### Subagent

The subagent starts with its working directory set to:

```text
project/wt/fix-auth/
```

It sees a project-shaped environment containing only the declared repositories and shared resources. Its instructions identify:

- The task and workspace name.
- Which repositories are editable.
- Which repositories are references.
- The branches and base revisions.
- The requirement to remain inside the workspace.
- The expected completion procedure.

The subagent uses ordinary Git commands inside editable repositories. It does not need to understand Yard internals.

## Design principles

1. **Explicit access roles:** Every included repository is declared as editable or reference-only.
2. **Dedicated working trees:** No agent edits a canonical checkout under `repo/`.
3. **Visible mechanics:** Workspaces remain understandable with ordinary filesystem and Git tools.
4. **Safe defaults:** Unique branches, pinned references, and guarded deletion are defaults.
5. **No daemon:** Commands modify durable state and exit.
6. **Incremental adoption:** Existing project directories remain valid.
7. **Honest isolation:** Prompt-level boundaries are not described as security boundaries.

## Concepts and object model

### Project

A directory containing `CLAUDE.md`, project resources, canonical repository checkouts, and managed workspaces.

Project configuration lives in:

```text
.yard/project.toml
```

Example:

```toml
version = 1
workspace_root = "wt"
scratch_root = "/scratch/acme/yard"

[repos.frontend]
path = "repo/frontend"
default_base = "main"

[repos.backend]
path = "repo/backend"
default_base = "main"

[repos.schemas]
path = "repo/schemas"
default_base = "main"

[shared]
docs = "docs"
data = "data"
claude_config = ".claude"
```

Repositories are explicitly registered. Yard does not recursively treat every Git directory as part of the project.

### Workspace

A named, task-scoped directory under `wt/`. It has:

- A stable workspace ID.
- A human-readable name.
- Creation time and owner metadata.
- A lifecycle state.
- Repository bindings.
- A private scratch directory.
- Generated agent instructions.

Workspace states are:

```text
creating → ready → running → completed → integrated → removed
                     └──────→ abandoned
```

`running` records an active process but is not required to use the workspace manually.

### Repository binding

A repository included in a workspace with one of two roles:

- **edit:** Dedicated Git worktree on a unique task branch.
- **reference:** Detached worktree pinned to a specific commit.

Each binding records:

- Logical repository name.
- Source repository under `repo/`.
- Role.
- Base ref and resolved base commit.
- Workspace branch, if editable.
- Current commit.
- Dirty state.

### Workspace branch

Each editable repository receives its own branch. The default naming scheme is:

```text
yard/<workspace-name>/<repo-name>
```

For example:

```text
yard/fix-auth/backend
yard/fix-auth/frontend
```

Branch names can be overridden, but Yard never silently reuses a branch already checked out elsewhere.

### Manifest

Each workspace contains `.yard/workspace.json`. This is the authoritative description of how the workspace was created.

It stores resolved commits rather than only symbolic names, making the initial state reproducible.

The project also stores lightweight indexes and locks under `.yard/state/`. The workspace manifest remains sufficient to inspect or recover an orphaned workspace.

## On-disk layout

After initialization:

```text
project/
├── CLAUDE.md
├── .claude/
├── .yard/
│   ├── project.toml
│   ├── state/
│   │   ├── workspaces.json
│   │   └── locks/
│   └── templates/
│       └── AGENT.md
├── docs/
├── data/
├── repo/
│   ├── frontend/
│   ├── backend/
│   └── schemas/
├── tmp -> /scratch/project/tmp
└── wt/
    └── fix-auth/
        ├── CLAUDE.md
        ├── AGENT.md
        ├── .yard/
        │   └── workspace.json
        ├── docs -> ../../docs
        ├── data -> ../../data
        ├── repo/
        │   ├── frontend/
        │   ├── backend/
        │   └── schemas/
        └── tmp -> /scratch/acme/yard/<workspace-id>/tmp
```

### Project resources

- `CLAUDE.md` remains the source project instruction file.
- Workspace `CLAUDE.md` is generated from a snapshot of the project file plus a clearly marked Yard section describing workspace boundaries.
- `AGENT.md` contains the task prompt and repository role table.
- `.claude/` may be linked into the workspace when configured. Yard warns that writable shared configuration can cause cross-agent interference.
- `docs/` is linked to the project documentation by default.
- `data/` is linked to the project data directory, preserving existing links to large datasets.
- `tmp/` is workspace-private and points into configured scratch storage.
- `repo/` preserves the familiar project structure but contains only repositories selected for this task.
- `wt/` is reserved for Yard-managed workspaces.

A workspace does not contain its own nested `wt/` directory.

### Scratch fallback

If `scratch_root` is configured, workspace temporary storage is created there. Otherwise Yard uses:

```text
wt/<name>/tmp/
```

Yard reports which location it selected. It never assumes `/scratch` exists.

## CLI

### Project setup

```sh
yard init
yard repo add frontend repo/frontend
yard repo add backend repo/backend --base main
yard repo add schemas repo/schemas --base main
yard config show
yard doctor
```

`yard init` creates `.yard/`, ensures `wt/` exists, and may offer to register immediate children of `repo/`. Discovery is presented for confirmation rather than silently persisted.

`yard doctor` checks:

- Registered repository paths.
- Git worktree support.
- Missing or moved workspaces.
- Stale locks.
- Scratch availability.
- Reference checkouts with modifications.
- Git worktree metadata consistency.

### Create

```sh
yard create NAME [options]
```

Common options:

```text
--edit REPO              Include an editable repository; repeatable
--ref REPO               Include a reference repository; repeatable
--from REF               Default base for editable repositories
--repo-from REPO=REF     Per-repository base override
--at REPO=REF            Pin a reference repository
--branch REPO=BRANCH     Override generated branch
--prompt TEXT            Record a short task prompt
--prompt-file PATH       Read a task prompt
--no-fetch               Do not update remote refs
--json                   Emit machine-readable output
```

Creation is transactional where practical. Yard first validates every requested binding, branch, path, and commit. It then creates the worktrees. If a later step fails, it removes worktrees created by that invocation and reports anything requiring manual recovery.

Example machine-readable result:

```json
{
  "name": "fix-auth",
  "path": "/work/acme/wt/fix-auth",
  "state": "ready",
  "editable": ["backend", "frontend"],
  "reference": ["schemas"]
}
```

### Run

```sh
yard run fix-auth -- claude
yard run fix-auth -- claude --continue
yard shell fix-auth
```

`yard run`:

- Changes to the workspace root.
- Sets environment variables such as `YARD_WORKSPACE`, `YARD_WORKSPACE_ID`, and `YARD_PROJECT_ROOT`.
- Records the child PID and start time.
- Forwards signals and returns the child exit status.
- Clears active-process state when the process exits.

Yard does not daemonize the subagent.

### Inspect

```sh
yard list
yard status fix-auth
yard inspect fix-auth
yard diff fix-auth
yard diff fix-auth --repo backend
yard path fix-auth
yard prompt fix-auth
```

`yard inspect` summarizes all bindings:

```text
WORKSPACE  fix-auth
STATE      ready

REPOSITORY  ROLE       BRANCH                         BASE       STATUS
backend     edit       yard/fix-auth/backend          a83d2c1    3 commits
frontend    edit       yard/fix-auth/frontend         e109cb4    dirty
schemas     reference  detached at 6fbd820            6fbd820    clean
```

`yard diff` shows repository-separated diffs and never combines them into a synthetic cross-repository patch.

### Maintenance and integration

```sh
yard check fix-auth
yard rebase fix-auth
yard rebase fix-auth --repo backend --onto origin/main
yard complete fix-auth
yard integrate fix-auth
yard destroy fix-auth
yard gc
```

`yard check` fails if:

- A reference checkout is dirty.
- An editable repository has unresolved conflicts.
- A branch has unexpectedly moved outside its worktree.
- The manifest and Git worktree registrations disagree.

`yard complete` marks the workspace ready for review but does not alter Git history.

## Multi-repository checkout behavior

### Editable repository

For an editable binding, Yard:

1. Resolves the requested base ref to a commit.
2. Creates a unique workspace branch.
3. Adds a Git worktree at `wt/<name>/repo/<repo>`.
4. Records the base commit and branch in the manifest.

Conceptually:

```sh
git -C repo/backend worktree add \
  -b yard/fix-auth/backend \
  wt/fix-auth/repo/backend \
  <resolved-base>
```

The canonical checkout under `repo/backend` is not changed.

### Reference repository

For a reference binding, Yard creates a detached worktree pinned to the resolved commit:

```sh
git -C repo/schemas worktree add \
  --detach \
  wt/fix-auth/repo/schemas \
  <resolved-commit>
```

This is preferable to linking directly to the canonical checkout:

- The subagent gets a stable snapshot.
- Changes in the canonical checkout do not alter its view.
- Accidental edits do not damage the canonical working tree.
- Yard can detect and discard local reference changes during teardown.

The files are still writable at the operating-system level in v1. “Reference-only” is therefore a policy with detection, not a hard security boundary.

### Repositories not declared

Undeclared repositories do not appear under the workspace’s `repo/` directory. They remain reachable through absolute paths or `..` unless stronger isolation is enabled in a later version.

### Multi-repository completion

Git cannot make commits across repositories atomic. Yard therefore treats completion as a set of repository results:

```text
backend:  branch yard/fix-auth/backend, 3 commits
frontend: branch yard/fix-auth/frontend, 1 commit
schemas:  unchanged reference
```

The manifest records each repository independently. Integrators can merge, rebase, or abandon one result without corrupting the others.

## Git and branch policy

### Unique branches by default

Every editable repository gets a unique branch. This prevents two worktrees from checking out the same local branch and avoids ambiguous ownership.

If the generated branch already exists, creation fails unless the user explicitly chooses one of:

```sh
yard create fix-auth-2 --branch backend=yard/fix-auth/backend-v2
yard adopt fix-auth --branch backend=existing-branch
```

`adopt` requires that the branch is not currently checked out in another worktree.

### Two agents working on the same logical branch

Yard does not allow two workspaces to check out the same branch. Each receives a separate branch:

```text
yard/auth-attempt-a/backend
yard/auth-attempt-b/backend
```

The coordinating agent chooses one result or integrates commits between them. This avoids shared-index and branch-tip races.

Supporting a shared writable branch would provide little benefit: Git worktrees prohibit normal concurrent checkout of one branch, and bypassing that protection makes branch ownership unclear.

### Rebasing

`yard rebase NAME` rebases each editable branch onto its configured upstream. Repositories are processed independently in deterministic name order.

If one repository conflicts:

- Yard stops rebasing that repository.
- It does not begin further repositories by default.
- The workspace remains intact.
- Status reports the exact repository and rebase state.
- The user or agent may resolve normally and run `yard rebase --continue`.

Already-rebased repositories are not rolled back automatically. Cross-repository rollback would be surprising and potentially destructive.

### Integration

`yard integrate` is conservative in v1. For each editable repository it:

1. Requires a clean worktree.
2. Verifies no rebase or merge is in progress.
3. Reports commits relative to the recorded base.
4. Checks whether the configured destination can accept a fast-forward.
5. Performs only explicitly requested integration.

Examples:

```sh
yard integrate fix-auth --strategy ff-only
yard integrate fix-auth --strategy merge
yard integrate fix-auth --repo backend --strategy cherry-pick
```

The default is dry-run reporting. A human or main agent must provide `--apply`.

No all-repository atomicity is claimed. If integration succeeds in one repository and fails in another, Yard reports the partial result and retains the workspace.

### Conflicts with canonical worktrees

Git may reject worktree operations when:

- A requested branch is already checked out.
- Worktree metadata is stale.
- A destination branch is checked out in the canonical tree.
- The canonical repository is mid-rebase or mid-merge.

Yard surfaces these conditions and does not bypass Git protections with force flags by default.

## Lifecycle

### Create

1. Acquire the project state lock.
2. Validate the name and configuration.
3. Resolve every requested Git ref.
4. Reserve the workspace ID and paths.
5. Create scratch storage.
6. Create reference and editable worktrees.
7. Link shared resources.
8. Generate instructions and manifest.
9. Mark the workspace `ready`.
10. Release the lock.

### Run

The main agent may launch through `yard run` or manually change into the workspace. Launching through Yard improves observability but is not mandatory.

Only one managed process is allowed per workspace by default. `--allow-multiple` permits additional processes and records each PID.

### Complete and inspect

The subagent may run:

```sh
yard complete .
```

This runs checks and marks the workspace completed. It does not commit changes automatically. The coordinating agent then uses `yard inspect` and `yard diff`.

### Teardown

```sh
yard destroy fix-auth
```

Destruction refuses when:

- An associated process is still running.
- An editable worktree has uncommitted changes.
- Commits exist only on a workspace branch without an explicit retention choice.
- A rebase or merge is in progress.
- A reference checkout is dirty.

The user must select a disposition:

```sh
yard destroy fix-auth --keep-branches
yard destroy fix-auth --delete-merged-branches
yard destroy fix-auth --discard
```

`--discard` requires an additional confirmation interactively or `--yes` in automation.

Yard removes worktrees through Git before deleting directories. Scratch deletion is separate and reported explicitly.

### Garbage collection

`yard gc` identifies:

- Manifests whose directories are missing.
- Directories without registered manifests.
- Stale process records.
- Prunable Git worktree metadata.
- Scratch directories belonging to removed workspaces.
- Merged Yard branches eligible for deletion.

It reports planned actions first; mutation requires `--apply`.

## Isolation model

### Enforced in v1

Yard enforces:

- Separate directories for each workspace.
- Separate editable Git worktrees.
- Unique writable branches.
- Detached, pinned reference worktrees.
- Workspace-private temporary storage.
- Explicit repository membership in the workspace layout.
- Lifecycle locks and guarded deletion.
- Dirty-reference detection.
- No implicit force removal or branch reuse.

### Convention and prompt in v1

Yard does not prevent a process from:

- Navigating to `../../repo/`.
- Editing a reference checkout and changing its permissions.
- Following `docs/` or `data/` links outside the workspace.
- Reading arbitrary user files.
- Accessing the network.
- Starting unmanaged child processes.
- Invoking Git against another checkout by absolute path.

Generated instructions clearly state these boundaries. Yard detects several violations during inspection, but detection is not containment.

### Optional future enforcement

A later `yard run --sandbox` could use platform-specific facilities:

- Linux mount namespaces with the workspace writable and references read-only.
- Read-only mounts for `docs/` and selected datasets.
- Explicit writable mounts for workspace repositories and scratch.
- Optional network restrictions.
- Process cleanup through cgroups.

This should remain an optional execution backend. Containers or namespace tooling would increase portability and debugging costs and are unnecessary for the core v1 workflow.

## Concurrency

Yard uses filesystem locks under `.yard/state/locks/` for short critical sections.

Lock scopes are:

- One project-state lock for workspace registration.
- One lock per source repository for worktree creation, removal, and branch operations.
- One lock per workspace for lifecycle transitions.

Locks are acquired in sorted repository-name order to avoid deadlocks.

Long-running agents do not hold locks. Their presence is represented by PID records and workspace state.

Concurrent operations behave as follows:

- Different workspaces using different repositories proceed independently.
- Creating worktrees from the same source repository serializes only Git metadata updates.
- Inspection is lock-free where possible and tolerates state changing during output.
- Destruction refuses while a managed process is active.
- Two creators requesting the same workspace name cannot both succeed.
- Two agents cannot receive the same editable branch through normal Yard commands.

Locks contain PID, host, command, and start time. Yard may clear a stale lock only after verifying that its process no longer exists on the same host. Cross-host shared filesystem coordination is not supported in v1.

## Agent-facing instructions

Generated `AGENT.md` should be short and operational:

```markdown
# Task

Repair authentication refresh behavior.

## Workspace

You are in Yard workspace `fix-auth`.

Editable repositories:

- `repo/backend`
- `repo/frontend`

Reference repositories:

- `repo/schemas`

Only editable repositories should be modified. Reference checkouts are pinned
snapshots and are checked for changes during completion.

Keep temporary output under `tmp/`. Do not access the parent project directory.

When finished:

1. Commit or clearly report uncommitted work.
2. Run `yard check .`.
3. Run `yard complete .`.
```

The manifest is also available for agents that prefer structured input:

```sh
yard inspect . --json
```

## Error handling and recovery

Yard favors recoverable failure:

- A partially created workspace is marked `creating-failed`.
- Successfully created worktrees are listed in the error report.
- Cleanup never deletes dirty trees automatically.
- Missing project indexes can be rebuilt from workspace manifests.
- Missing manifests can be partially reconstructed from Git worktree metadata.
- Unknown directories under `wt/` are treated as user-owned unless explicitly adopted.

Commands support `--json`, with stable error codes such as:

```text
BRANCH_IN_USE
WORKTREE_DIRTY
REFERENCE_MODIFIED
PROCESS_ACTIVE
INTEGRATION_PARTIAL
STALE_METADATA
```

## What v1 deliberately defers

- Strong filesystem, process, network, or secret isolation.
- Containers, virtual machines, and remote execution.
- A background daemon or web interface.
- Cross-machine workspace coordination.
- Atomic commits or rollbacks across repositories.
- Automatic pull-request creation.
- Automatic conflict resolution.
- Automatic dependency installation.
- Repository-specific build orchestration.
- Copy-on-write datasets.
- Shared writable branches.
- Nested Yard projects.
- Sophisticated workspace snapshots or caching.
- Automatic interpretation of arbitrary existing worktree layouts.

These can be added after the basic workspace and ownership model proves useful.

## V1 implementation boundary

A practical first release needs only:

1. Project configuration and repository registration.
2. Workspace creation with edit and reference bindings.
3. Generated instructions and manifests.
4. `run`, `list`, `inspect`, `diff`, and `check`.
5. Rebase helpers using normal Git operations.
6. Guarded teardown and garbage collection.
7. JSON output for coordinating agents.

This delivers the central improvement: every subagent receives an explicit, inspectable, task-scoped workspace, while the top-level Claude retains control from the familiar project root.
