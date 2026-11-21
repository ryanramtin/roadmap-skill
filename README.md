# roadmap

A living, derived roadmap for people who build with AI agents — instead of a hand-drawn plan that drifts.

It reads what already happened: your agent memory (claude-mem), your ship log, and your git history. Then it renders a local dashboard with Gantt lanes, momentum, ships vs held, explore-vs-execute ratio, agent mix, and the decision log, plus a director-level 16:9 deck view you can print to PDF.

## Install

```bash
git clone --depth 1 https://github.com/ryanramtin/roadmap-skill.git ~/.claude/skills/roadmap
```

Then ask your agent:

```
roadmap
```

or `portfolio review`, `exec deck of my projects`, `project timeline`.

## What it produces

- **Lanes** — real activity spans from git and agent memory, per project.
- **Milestones and ships** — features, decisions, and shipped/held work.
- **Next** — the agents' own next steps, which is effectively your live backlog.
- **How it got built** — explore vs execute, agent mix, decision log.
- **Honesty panel** — the share of activity it could not attribute, and any suspected backfill bursts.

## Requirements

- Python 3 (standard library only)
- Optional: [shiplog](https://github.com/ryanramtin/shiplog) for ship data
- Optional: a claude-mem database for agent memory

Everything runs locally. Nothing is uploaded. Private text is redacted before it reaches the page.

MIT licensed. Use it, change it, ship it.
