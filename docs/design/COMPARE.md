<!-- ai-authored -->

# Independent designs vs `ws`

Three agents designed from the same workflow prompt and did not see
`ws`. Docs: [GROK.md](GROK.md) (`booth`), [OPUS.md](OPUS.md) (`bay`),
[GPT.md](GPT.md) (`Yard`).

## What all three did that we did not

They **evolved the existing tree** (`CLAUDE.md`, `repo/`, `wt/`, `data/`,
`tmp/`, `docs/`). We designed a greenfield `.ws/` + `workspaces/`
layout. Given how this tool will actually be used, that is the bigger
miss.

They treat `repo/<name>` as the **human’s primary checkout** and
`git worktree add` from it. We put bare clones in a hidden store. Their
path is incremental (no migrate-to-bare). Ours is cleaner if the
project is `ws`-first. For this workflow, theirs fits better.

They all generate a **per-workspace prompt overlay** (`CLAUDE.md` /
`AGENT.md` / `booth tip`) and give the main agent `--json` / `prompt` /
`tip`. We had “put it in AGENTS.md” but not the launch artifact.

They all **symlink `docs/` and `data/`** into the workspace so the
subagent does not walk up to the project root. We did not.

They all want **private scratch** (`tmp/bay/<ws>` or a scratch_root).
We shared `tmp` implicitly. On a 20GB boot disk this matters.

## Where we are ahead

**Shared detached trees tracking `origin/main`.** All three either
symlink refs to the live `repo/` checkout (Grok — cheap, dirty, follows
the human’s branch) or make a **per-workspace** detached worktree
(Opus, GPT — stable, disk-heavy). Opus even deferred “a shared
read-only snapshot pool.” That pool is our repo store. Keep it.

**In-place sync of shared refs is OK.** They default to pinning. We
want `origin/main` to move. Compatible with a shared pool: one detached
tree per `(repo, origin/<branch>)`, many workspaces link to it.

**Promote, no demote.** Opus has two-way `mount`; we already cut demote.

## Steal list (worth taking)

1. **Sit on `wt/` + `repo/` + `data/` + `tmp/`**, not `workspaces/`.
   Hidden metadata as `.ws/` next to those, not a new project shape.
2. **Workspace is a mini project root:** `repo/`, `docs` →, `data` →,
   private `tmp` → `/scratch/.../<ws>`. Subagent never needs `../../repo`.
3. **`--edit` / `--ref` at create**, plus `--ref-all`.
4. **`ws prompt` / `ws tip`** for in-session Task-tool subagents (they
   inherit the main cwd; a generated prompt is the actual sandbox).
5. **Unique workspace branch** (`ws/<name>` or `ws/<name>/<repo>`).
   Never check out the human’s `main`.
6. **Do not mutate `repo/` working trees** except maybe a later
   explicit land/ff.
7. **`doctor`, `adopt`, `gc`** — you already have leftover `wt/` dirs.
8. **`--from <workspace>` stacking** (Opus) — cheap and useful.
9. **Archive patches on rm** (Opus) — `format-patch` before teardown.
10. **Guarded destroy** — refuse dirty / unmerged unless
    `--keep-branches` / `--discard`.
11. **Warn about linking `.claude/`** (GPT) — shared writable settings
    leak across agents.
12. **Prefer an edit worktree if a formatter might run** (Grok) —
    “mostly ref” is a trap.

## Do not steal for v1

Opus’s `land` / `sync` / `merge-tree` conflict matrix, claims/PIDs,
port blocks, PreToolUse guard hook, `chmod a-w` on refs. GPT’s
integrate/rebase suite. All good later; they are how these docs got
long. Our v1 stays create / ls / checkout / promote / rm + lockfile +
shared `origin/*` trees.

## Layout sketch after this (proposal)

```
<project>/
  CLAUDE.md
  .claude/
  docs/
  repo/<name>/              # human primary checkouts (not bare)
  data/                     # unchanged
  tmp -> /scratch/...
    ws/<workspace>/         # private scratch
  wt/<workspace>/           # subagent cwd
    CLAUDE.md               # generated overlay
    docs -> ../../docs
    data -> ../../data
    tmp  -> ../../tmp/ws/<workspace>
    repo/<name>/            # symlink to shared, or RW worktree
  .ws/
    lock
    config.toml
    shared/<repo>/origin/main/   # detached, retain-able
```

Bare-clone store is optional. Worktrees can hang off `repo/<name>`
the same way they do today. Shared trees still earn their keep for
hot `origin/main` refs.
