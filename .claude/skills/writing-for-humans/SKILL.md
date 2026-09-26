---
name: writing-for-humans
description: >-
  Draft and revise human-facing prose so it reads as a person writing, not a
  model polishing. Use when writing or editing articles, README, tutorials,
  how-tos, design notes, CLAUDE.md, AGENTS.md, PR descriptions, user-facing
  explanations, or any text that will carry a person's name. Do not use for
  code, configs, logs, or raw data dumps.
---

# Writing for humans

The reader can smell model prose. When they do, they skim faster, trust less, and remember the author as the person who published it. The name on the piece is still the human's. Write so they are in it.

This skill applies to **prose people will read as writing**. It does not apply to code.

Sources: [Claudisms](https://claudisms.ai/), [About](https://claudisms.ai/about/), [Your Name Is Still on It](https://wespomeroy.substack.com/p/your-name-is-still-on-it). The catalog is CC0; use it as a kill list, not as style to imitate.

## Before a word

If this text will carry the user's name, their thinking has to be in it.

1. **Ideas first.** Pull claims, decisions, and examples from the conversation, the repo, or what they actually did. Do not invent a lived story, a recurring observation, or a ranking they never made.
2. **Could they go deeper?** If asked about a specific point, could they defend it from experience or reasoning that did not make the cut? If you cannot point to that source, cut the point or mark it as yours to confirm.
3. **Could they write it without you?** You are speeding a writer, not ghostwriting a voice that is not there. If there is no perspective to amplify, write short, factual, and small. Do not add polish to hide the hollow.

Do not ask the model what would resonate. Stay with their friction, their layout, their call.

## How to draft

1. Get their points on the table before shaping sentences. If they are verbose, stay there. The draft is only as good as the thinking that went in.
2. Write the thing. Do not announce that you are about to write it.
3. Scrub against [claudisms.md](claudisms.md) before showing the draft.
4. Read it as if you are hearing them talk. Cut anything they would not say. Correct assumptions the model filled in.
5. Verify every citation, statistic, quote, and link yourself. A wrong source stays wrong in public.

A first pass is a distillation, not a finish. Revision is where authorship happens.

## Write the thing, not the search

This applies to every piece of human-facing prose, including design notes.

Put down the fact. Do not put down how you learned it, what you looked for, what you discussed, or what you discarded. A reader should not be able to reconstruct the chat or the exploration from the page.

Do not list status-quo absences. “There is no daemon” is what you learn by hunting a daemon. The default for a CLI is no daemon, so the sentence brings in a thing the reader never needed to hear about. That includes omitted features, postponed ideas, platforms you did not target, and tools you did not add.

Name an absence only when a careful reader would wrongly assume the thing exists. Then state what is true instead. “This graph database has no graph type; edges are rows in `link` and queries are recursive SQL.” What replaces the missing piece is the point. A bare “there is no X” still drags X into the room.

An action rule is different. “Dirty `rm` needs `--force`” tells someone what to do.

## Demonstrate, don't announce

The root rule: never tell the reader what to think of something. Cool people do not need to tell people they are cool.

| Instead of | Do |
|---|---|
| This matters / worth noting / the useful part | State the fact. Let them decide. |
| Here's where it gets interesting | Start the interesting part. |
| The whole game / the only thing that matters | Say what it does, at its real size. |
| The one that surprised me most | Give the example. Skip the crown. |
| I'm going to make three points | Make them. |
| It's not X, it's Y | Lead with what is true. Contrast later, once, if it adds information. |

These all label value, drama, or cleverness: "worth \_\_\_", "the right \_\_\_", "quietly", "settled", "honestly" on your own claim, "what I want you to see", "the tell". Cut the label.

## Plain English

Prefer the verb that names the event. Model prose reaches for writerly metaphors when "is", "does", or "shows up" would do.

Banned textures (metaphorical use):

- Placement and motion: *lives, sits with, shape of, holds, carries, moves, points, rides along, hands you, reaching for*
- Grandeur: *physics of, the engine, load-bearing, names the move, throughline*
- Corporate: *leverage, unpack, lean into, surface (verb), double-click, foster, harness, navigate the landscape*
- Hype: *transformative, groundbreaking, robust, seamless, pivotal, delve, shed light, pave the way*

If a reader cannot picture what the sentence claims is happening, rewrite it until they can.

Match verbs to what actually happened. A small effect did not wreck anything. A change did not "quietly" hide itself unless someone failed to notice.

## Voice and evidence

- Do not invent a population ("most teams", "everyone I've watched") unless the observation is in the source.
- Do not invent a discovery arc ("I didn't set out to…", "the question I keep coming back to"). State the observation.
- Do not invent a feeling ("hit a nerve", "stuck with me", "the thing that got me"). Name the actual reaction, or drop it.
- Do not grade the current state as immature, or a future state as more mature. Say what changes.
- Do not use "real" as a compliment. It implies the alternative is fake.
- Do not claim a question was settled, or that nobody has settled it, unless that history is documented.

## Shape of the page

- **Em dashes (—) are out.** Use a spaced hyphen (` - `) for an aside. One per sentence, not a stack.
- **No emojis** in articles, docs, headlines, or share text.
- **No `---` horizontal rules** as section dividers. Use headings.
- Mix sentence length. Four short declaratives in a row is a tic.
- Do not end by restating the thesis in a neat one-liner. Sometimes it just ends.
- Do not open with "In today's rapidly evolving…".
- Do not answer a question by restating the question.
- Lists: write the item, then the sentence. Do not use `**Bold term:** explanation`.
- Signposts ("Let's explore", "Now let's turn to", "This is where X comes in") are lecture-hall filler. Cut them.

Negative parallelism is the most recognizable machine tell. Do not write "It's not just X, it's Y", "This isn't about X. It's about Y", or "No X. No Y. Just Z."

Open with what is true or what to do. Contrast only if it earns its keep.

## After the draft

Copy and use:

```
Scrub:
- [ ] Every claim traces to the user, the repo, or a checked source
- [ ] Facts only; no chat or exploration on the page
- [ ] No status-quo absence unless a reader would wrongly assume the thing exists
- [ ] No invented noticing, ranking, or emotion
- [ ] Value is shown, not labeled (no "worth", "matters", "useful part")
- [ ] No "it's not X, it's Y" / "not only X but Y"
- [ ] No em dashes, emojis, or --- dividers
- [ ] Metaphors named the event, or were cut
- [ ] Superlatives have a reason, or were cut
- [ ] Citations opened and checked
```

If a phrase is on [claudisms.md](claudisms.md), rewrite in plainer English before showing the draft. When a new tic keeps turning up, add it there.
