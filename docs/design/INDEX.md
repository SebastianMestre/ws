<!-- ai-authored -->

# Design notes

Working notes from the v1 design, not user docs. Start with
[Getting started](../getting-started.md) or the
[reference](../reference.md) if you want to *use* `ws`.

| Page | What it is |
| --- | --- |
| [INITIAL.md](INITIAL.md) | First model (repo store + workspaces), CLI sketch, and the discussion that dropped the daemon, kept lockfiles, and settled `retain`. |
| [LAYOUT.md](LAYOUT.md) | Current on-disk tree: bare clones under `.ws/repos/`, shared trees, `wt/`, `docs/`/`data/` links, YAML config, v1 command list. |
| [DOGFOOD.md](DOGFOOD.md) | Concrete commands used to stand up `example/` with Jasper and bytecode, plus the friction (default branches, no one-shot create). |
| [COMPARE.md](COMPARE.md) | Independent designs vs ours: what to steal (`wt/` + prompt overlay + private tmp) and what we already had (shared `origin/*` pool). |
| [GROK.md](GROK.md) | Independent design (`booth`), Grok 4.7. Did not see this repo. |
| [OPUS.md](OPUS.md) | Independent design (`bay`), Claude Opus 5.5. Did not see this repo. |
| [GPT.md](GPT.md) | Independent design (`Yard`), GPT 5.6 Sol. Did not see this repo. |
