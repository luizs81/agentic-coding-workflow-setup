# <AppName> — Coding Standards

Scaffolded from the `azure-functions` skill on <date>. This file is the authoritative
source for how to work in this repo. The `azure-function-implementer` and
`azure-function-reviewer` subagents treat it as binding. Update it as real conventions
emerge or diverge from what's here. Do not let it go stale.

The team-wide standard is ADR-001 (Azure Functions Shared Architecture). This file
records **this project's** instantiation of it and any deviation from it. It does not
record the general rule.

## Writing style

Write all prose in ASD-STE100 (Simplified Technical English) style: short sentences,
one instruction per sentence, active voice, "must"/"must not"/"can" instead of
"should"/"may", consistent terminology. This rule covers every kind of prose you
write — instructions, documents, responses, messages to other agents, and code
comments. Only code syntax and literal commands are exempt.

## What this function does

<one or two sentences: what it loads/transforms/produces, trigger type (timer/HTTP/
queue/blob), whether it uses a Durable orchestrator, who consumes the output>

## Architecture

Clean Architecture, four projects: `<AppName>.Domain` → `<AppName>.Application` →
`<AppName>.Infrastructure` → `<AppName>.Functions`. The dependency direction runs
one-way, outward from Domain. Infrastructure references Application because
`AddInfrastructure()` is the single composition root.

## Domain interfaces

<list the interfaces in Domain/Interfaces/ and their Infrastructure implementations —
one per external system, plus INotificationService>

## External dependencies

<list: Blob Storage, SQL Server, Snowflake, SharePoint, internal APIs — whatever this
function actually talks to. For each one, state where its config lives (Key Vault
reference, app setting, local.settings.json locally)>

## Configuration

| Options class | Section | Notes |
|---|---|---|
| `TeamsOptions` | `Teams` | <webhook config key as actually used> |
| <...> | | |

## Teams notifications

Notify on: <both success and failure / failure only — state which. If failures only,
state why success is suppressed and where that is documented in code>.

## Build and test

```
dotnet build
dotnet test --filter "Category!=Integration"
./dev-start.sh          # Azurite + func start
```

## Deviations from ADR-001

<any rule this project intentionally departs from, with the reason. Empty is a valid
answer. But if the code deviates and this section is empty, the code is wrong.>

## Known gaps / TODOs

<anything deliberately deferred at scaffold time: a stubbed implementation, an
unconfirmed output sink, or a "figure this out before first real run" item>

## Open questions log

<append-only. If a decision made here later turns out wrong, add a
`RESOLVED (date, evidence)` line. Do not delete the original entry.>
