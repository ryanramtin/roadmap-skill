---
name: roadmap
description: Build a living, AI-era roadmap of how Ryan's apps and projects have progressed — derived from claude-mem, shiplog and git history instead of a hand-written plan. Produces a self-updating local dashboard (Gantt lanes, momentum, ships, explore-vs-execute, agent mix, decisions) plus a director-level 16:9 deck view (print to PDF). Use when the user says "roadmap", "gantt", "portfolio review", "exec deck of my projects", "how have my projects progressed", "project timeline", "director deck", or invokes /roadmap. Not for a quick status check (that's `minimize`).
---

# Roadmap — the derived, self-updating kind

Old roadmaps were **declared**: someone drew bars and then the work drifted away from them.
With agents doing the building, the record of what happened already exists. Every
observation, ship, decision and commit is logged. So this roadmap is **derived** from that record:

- **Lanes** = real activity spans (git commits where a repo exists, claude-mem otherwise).
- **Milestones** = `feature`/`decision` observations; **ships** = shiplog entries (shipped vs held).
- **Next** = the agents' own `next_steps` from session summaries, which in effect is the backlog.
- **How it got built** = explore-vs-execute ratio (discoveries vs build work), agent mix (claude/opencode/codex), and the decision log.
- **Honesty**: the page shows the share of activity it couldn't attribute to a project and flags suspected backfill bursts.

Data stays computed (scripts). Opus adds only the **director narrative**: takeaway titles, now/next/risks.

## Files
```
~/.claude/skills/roadmap/
  aliases.json        project canonicalization + repo paths + junk buckets (edit freely)
  scripts/collect.py  claude-mem (read-only SQL) + shiplog + git → roadmap.json + digest.md (redacts private text)
  scripts/render.py   roadmap.json (+ narrative.json) → index.html (Dashboard + Deck views, self-contained)
  scripts/serve.py    127.0.0.1-only live server; rebuilds only when sources changed (cheap fingerprint check every N s, default 900), /refresh forces; page polls /roadmap.json
  scripts/build.sh    collect + render in one go
```

## Workflow

1. **Build the data** (default window 180d; pass `--since 90d` etc.):
   ```bash
   OUT=~/.roadmap   # durable default; or a scratchpad dir for one-offs
   bash ~/.claude/skills/roadmap/scripts/build.sh "$OUT"
   ```
2. **Read `$OUT/digest.md`** (compact, bounded). Don't read roadmap.json raw unless you need to.
3. **Write `$OUT/narrative.json`** as the director (Opus does this, not a sub-agent):
   ```json
   {"headline": "…one sentence, the takeaway…",
    "exec_bullets": ["…", "…", "…"],
    "projects": {"Ok Stewie": {"headline": "…", "now": "…", "next": "…", "risks": ["…"]}},
    "closing": {"decisions": ["…"], "next": ["…"]}}
   ```
   Rules: slide titles state a **takeaway**, never a label ("NxtSteps went quiet after the v2 cutover", not "NxtSteps"). Be specific, use the numbers, and don't invent anything not in the digest. If a project is unclear, leave it out and let the fallback text stand. render.py works without this file.
4. **Render**: `python3 ~/.claude/skills/roadmap/scripts/render.py --out "$OUT"` → `$OUT/index.html`.
5. **Look at it.** Screenshot both views (headless Chrome: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --screenshot=… --window-size=1600,1000 file://…`, or the playwright skill). Check Gantt overlap, label overflow, empty lanes. Fix, then re-render.
6. **Live mode** (the "dashboard that updates itself"):
   ```bash
   python3 ~/.claude/skills/roadmap/scripts/serve.py --out "$OUT" --port 8797 --interval 900
   # open http://127.0.0.1:8797  (Deck view: toggle top-right, or #deck)
   ```
   Run it in the background (`run_in_background`) if the user wants it up. For always-on, offer a launchd agent and only install it if they say yes. The narrative stays from the last time Opus wrote it, and the numbers keep refreshing.
7. **Sharing**: the deck prints to PDF (one slide per page, landscape). Offer an Artifact publish in one line. **Don't auto-publish**, since this is personal cross-project data.

## Hard rules
- **Privacy:** collect.py drops SAM / companion / private-mode text by default (denylist constant `REDACT_DENYLIST` / `DENY_RE` in collect.py; redacted items still count in every total, only their text is withheld), and masks emails, phones and tokens. Never pass `--no-redact` when the output will be published. SAM content never goes into Artifacts.
- **Read-only:** the claude-mem DB opens with `mode=ro` and git is `log` only. Never write to repos, ATTIC or the mem DB.
- **Bounded:** at most 14 Gantt lanes (the rest roll into "Other") and at most 8 project slides.
- If attribution coverage is low, say so in the exec summary. Don't hide it. Improve it by adding `keywords` and `exact` names to aliases.json.
- Voice to Ryan: punk-stoner. Deck copy stays crisp and executive.
