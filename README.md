# ws

Manage multi-repo workspaces for agentic workflows. Bare clones live
under `.ws/repos/`, shared readonly trees under `.ws/shared/`, and
work happens in `wt/`.

```
ws init
ws repo add git@github.com:org/foo.git
ws add fix-auth
ws checkout add fix-auth foo --mode readonly
ws checkout promote fix-auth foo
ws rm fix-auth
```

See `docs/design/LAYOUT.md` for the v1 layout.
