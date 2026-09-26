# ws

CLI for multi-repo workspaces in agentic workflows. Bare clones live
under `.ws/repos/`, shared readonly trees under `.ws/shared/`, and
all work happens in `wt/`.

Documentation follows the [Diátaxis](https://diataxis.fr/) four
types:

| Need | Doc |
| --- | --- |
| Learn | [Getting started](docs/getting-started.md) |
| Look up | [Reference](docs/reference.md) |
| Understand | [Design notes](docs/design/INDEX.md) |

How-to guides are not written yet; use the reference for specific
flags and the tutorial for a first successful run.

```
uv tool install -e .
ws init ~/my-project
```
