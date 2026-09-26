<!-- ai-authored -->

# Introduction

`ws` is a CLI for multi-repo workspaces in agentic workflows. Bare clones
are under `.ws/repos/`, shared readonly trees under `.ws/shared/`, and
work happens in `wt/`.

User docs are [Getting started](docs/getting-started.md) and
[Reference](docs/reference.md). Design notes are under
[docs/design/](docs/design/INDEX.md). Bundled agent templates are
`src/ws/templates/ws-project.md` and `src/ws/templates/ws-workspace.md`.

# Code style

Python 3.11 or newer. Format with Black, target version `py311`.

The package is `src/ws/`. Keep one concept per module (`Project`,
`Workspace`, `Checkout`, `Repo`, `SharedCheckout`, `Overlay`, `Config`,
`State`). YAML records are dataclasses with explicit `load`, `save`, and
`to_dict`. The CLI is argparse plus `cmd_*` functions in `cli.py`. Call
git through `gitutil.GitRepo`.

Raise `WsError` for anything the user should see. `main` prints
`ws: <message>` on stderr and returns 1.

Read and write YAML with `yaml.safe_load` and
`yaml.safe_dump(..., sort_keys=False, default_flow_style=False)`. Keep
the key order the existing `to_dict` methods emit. `config.yaml` is
user-edited; `state.yaml` is written by `ws`.

# PR / CI workflow

Default branch is `trunk`. CI runs on every push to `trunk` and on every
pull request. The two jobs are `format`
(`uv run black --check --diff --target-version py311 .`) and `test`
(`uv run pytest`); both must pass.

# Development instructions

An AI-authored file under `docs/design/` starts with `<!-- ai-authored -->`.

```
uv sync --group dev
uv run black .
uv run pytest
```

Install the CLI for dogfooding:

```
uv tool install -e .
```

When the agent-facing interface changes, update
`src/ws/templates/ws-project.md` and/or
`src/ws/templates/ws-workspace.md` in the same change. Update those
templates when any of the following change:

- Commands and flags (new/renamed/removed verbs, argument order, cwd
  inference, `--mode`, `--force`)
- Concept names (project, repo, workspace, checkout, readonly,
  readwrite)
- Paths agents are told to use (`wt/`, `.ws/`, `repo/<checkout>/`,
  `tmp/`, `docs/`, `data/`)
- Promises in the prose (default ref `origin/main`, no demote, `sync`
  rewriting live readonly trees, readonly not enforced, dirty `rm`
  needing `--force`, readwrite branch `ws/<workspace>/<checkout>`)
- The main-agent loop (create workspace, attach checkouts, set subagent
  cwd, tear down)

Do not update the templates for lockfile or YAML internals, git
plumbing, bugfixes that do not change the CLI or layout, tests, CI, or
extra commands agents are not told to run.

The short generated project and workspace `CLAUDE.md` snippets change
only if the link target or one-line contract changes: renaming
`docs/ws-*.md`, breaking the `docs/` symlink, or dropping "stay in this
directory".
