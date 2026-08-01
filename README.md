# Agentic Coding Workflow Setup

A working set of [Claude Code](https://claude.com/claude-code) customizations — agents, skills,
architecture decision records, and a coding-standard doc — built up over real project work and
refined as the rough edges showed up. Sharing it in case the patterns are useful to others setting
up their own agentic coding workflow.

## What's here

- **`agents/`** — paired implementer/reviewer subagent definitions (`model`/`effort` tuned
  per role) for a few common stacks: Azure Functions, a .NET web app architecture, dbt data
  models, and Azure Data Factory pipelines. Each implementer encodes the standard's non-obvious
  gotchas up front rather than relying on the model to re-derive them; each reviewer works from
  the same standard plus a few review-specific checks (downstream impact, silently-bent rules,
  re-derivation risk).
- **`adr/`** — two example Architecture Decision Records the Azure Functions and .NET web agents
  are built against, showing the kind of standing document an implementer/reviewer pair is meant
  to enforce.
- **`skills/`** — Claude Code skills for scaffolding a new project in each stack, including
  checklists and an `AGENTS.md` template to seed a new repo's own agent instructions.
- **`standards/`** — a general coding-conventions reference.
- **`commands/work-backlog.md`** — a `/work-backlog` command that drives a markdown checklist of
  tasks through an implement → review loop automatically: it spawns the implementer agent, spawns
  the reviewer agent against the real diff, relays findings back into the next implementer pass
  (capped at 3 round-trips per task to avoid burning cycles on something that isn't converging),
  and commits each task once the reviewer is clean — no copy-pasting feedback between agents by
  hand.

## Why implementer/reviewer pairs

The core idea across all of these: a single agent asked to "implement and then check your own
work" tends to rubber-stamp itself. Splitting the role into two subagents — one that writes code
against a standard, one that reviews the actual diff against the same standard from a blank
context — catches more, especially violations that are individually plausible but wrong in
aggregate (e.g. a model quietly recomputing something an upstream layer already computes). The
reviewer is deliberately given only read tools; it reports findings, it doesn't fix them.

## Adapting this

None of this is meant to be used verbatim — the agents assume specific stacks and repo layouts
that won't match yours. The reusable part is the shape: pair an implementer with a reviewer, point
both at the same standing standard (an ADR, a style guide, a `CLAUDE.md`), give the reviewer
narrower tools and a mandate to trace real files rather than trust the implementer's own account,
and use a command like `/work-backlog` to drive the loop across a task list without needing to
babysit the hand-off between them.
