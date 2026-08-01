# Shared .NET conventions

Lives at `~/.claude/standards/dotnet-conventions.md`, alongside `~/.claude/adr/`. Not a
subagent, not a skill — a plain reference file read explicitly by the implementer and
reviewer agents for both stacks, and by the `azure-functions` and `dotnet-web` skills.

**Scope:** language-level and security non-negotiables that hold regardless of what is
being built, plus how to behave when a task is unclear. Architecture — layering, testing
approach, configuration, telemetry, resilience — is **not** here. That lives in the
applicable ADR:

| Building | Standard |
|---|---|
| Azure Functions | `~/.claude/adr/ADR-001-azure-functions-shared-architecture.md` |
| Internal web applications | `~/.claude/adr/ADR-002-web-application-shared-architecture.md` |

**Precedence:** project `AGENTS.md` > the applicable ADR > this file. Most specific wins.

---

## Non-negotiables

- `async Task`, never `async void`, on every handler.
- No `SELECT *`. No string-concatenated SQL. Parameterized queries only.
- **Sort keys and column names coming from a client are allowlisted**, never passed
  through to SQL or an OData query. An ordering parameter is an injection vector that
  parameterized queries do not protect, because the column name isn't a parameter.
- No secrets in code, in config committed to git, or in logs. No hard-coded user-facing
  strings — see the applicable ADR for where they belong instead.
- Follow existing project conventions (naming, DI patterns, folder structure) over
  introducing new ones. Check an existing file in the same layer before writing a new one.

## Testing

The testing approach — framework, substitution strategy, which layers get their own test
project, what minimum coverage means — is set by the applicable ADR, because it differs
between the two stacks. Two rules hold everywhere:

- **New logic ships with tests in the same commit.** Tests assert behaviour, not "runs
  without throwing."
- **Do not assert against a substitute where the real thing is what's under test.** An
  in-memory database provider does not enforce the constraints a real engine does, so a
  test using one proves nothing about them.

## When a task is blocked or ambiguous

Stop and report back — do not guess, do not proceed — if:

- The task is explicitly marked blocked, needing a human decision, or needing a design
  decision ("not a lookup") in whatever backlog or ticket you're working from.
- A prerequisite task this one depends on isn't actually complete yet.
- A spec, if one exists, appears wrong or incomplete. Propose the fix in your report; do
  not commit a spec change unilaterally.
- You'd need to invent a value that should come from somewhere else — a timestamp, a
  config value, a business rule. Flag it, don't invent it.

## Definition of done

- Behaviour matches the spec or ticket, if one exists.
- Tests added per the rules above and the applicable ADR.
- No secrets, no hard-coded user-facing strings, no `SELECT *`, no string-concatenated
  SQL, no unallowlisted sort key.
- `async Task`, not `async void`.
- Build and tests pass. Where warnings are errors, a warning is a failure.
- If the project has a resource-key parity convention (e.g. JA/EN keys), both are added.
- Any deviation from the applicable ADR is justified in a code comment at the point of
  deviation **and** recorded in the project's `AGENTS.md`.
