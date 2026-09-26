# `ws` for a workspace agent

Stay inside this workspace. Do not `cd` to the project root or into
another workspace.

```
ws repo ls
ws checkout ls
ws checkout add <repo> [ref] [--mode readonly|readwrite]
ws checkout promote <name> # turns shared readonly into a local readwrite checkout
```

`checkout ls` is the live list of checkouts.

Readonly checkouts are not locked by `ws`. Do not edit those files
and do not run mutating git (`commit`, `checkout`, `rebase`, `reset`,
`push`). If you need to change a repo, `promote` it or add it
`--mode readwrite`.

Write build output and temp files under `tmp/`. `docs/` and `data/`
are project-wide (symlinks).
