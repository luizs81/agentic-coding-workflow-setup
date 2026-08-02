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
- **Every date, time, and number formatted or parsed for a machine-readable output pins
  `CultureInfo.InvariantCulture`** — file contents, filenames, export columns, API payloads,
  keys. Only text a human reads uses the ambient culture. Reason: `ja-JP` and `en-US`
  (the only ambient cultures this environment runs under) format separators and date order
  differently, and machine-readable output must be consistent regardless of host culture.
  A culture test can pin `CurrentCulture` to either of these two and assert the
  invariant-formatted output ignores it. Do not reason about other cultures, calendars, or
  test-culture choices beyond this — out of scope for this environment, not worth the
  tokens.
- No secrets in code, in config committed to git, or in logs. No hard-coded user-facing
  strings — see the applicable ADR for where they belong instead.
- Follow existing project conventions (naming, DI patterns, folder structure) over
  introducing new ones. Check an existing file in the same layer before writing a new one.

## Comments are terse, not derivations

A comment justifying a non-obvious choice (a culture pick, a retry scope, a deviation from
an ADR) states the constraint in 1-2 lines and stops. It does not re-derive the reasoning
from scratch, walk through the alternatives considered, or restate what the referenced
ADR/standard already says. If the file the reader needs to trust the comment is this
standard or an ADR, name it and move on — don't inline a copy of its argument.

- Bad: a paragraph explaining why a culture was chosen for a test, what alternatives would
  have failed to catch, and why the assertion format proves the point.
- Good: `// ja-JP ambient, asserts InvariantCulture output unaffected (see
  dotnet-conventions.md).`

This applies every time a comment is written or rewritten — a long comment surviving from a
previous pass is not grandfathered in; tighten it when touched.

## Doc comments are contract, not narration

An XML doc comment on a type or interface is read by the next implementer as a statement
of fact about behaviour. Treat it with the same weight as the signature it sits on.

- **Before implementing against an existing interface, re-read its doc comment and honour
  it.** If the implementation must deviate, change the interface's comment in the same
  commit. (Not: implement the deviation and leave the comment. A contract that says errors
  are captured as data, paired with an implementation that throws, is a defect in both.)
- **Any change to behaviour an existing type's doc comment describes updates that comment
  in the same commit.** This is the rule already applied to `docs/` files, extended to the
  comments on the types themselves — those go stale silently, since nothing compiles
  against them.
- This bites hardest when interfaces and their implementations land in *different* tasks.
  The gap between the two is exactly where the drift happens, so the re-read is not
  optional there.

## Testing

The testing approach — framework, substitution strategy, which layers get their own test
project, what minimum coverage means — is set by the applicable ADR, because it differs
between the two stacks. These rules hold everywhere:

- **New logic ships with tests in the same commit.** Tests assert behaviour, not "runs
  without throwing."
- **A test must fail against the implementation you're worried about.** Before writing the
  assertion, name the wrong implementation it's meant to catch, then check the test would
  actually distinguish the two. A composite key needs each component varied independently,
  or an implementation keyed on one of them passes. A field deliberately *excluded* from a
  key needs a test that varies it and asserts nothing changed, or nothing pins the exclusion
  and the next refactor absorbs it.
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
- Every doc comment describing behaviour you changed is updated in the same commit.
