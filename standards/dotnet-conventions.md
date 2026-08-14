# Shared .NET conventions

This file lives at `~/.claude/standards/dotnet-conventions.md`, alongside `~/.claude/adr/`.
It is not a subagent and not a skill. It is a plain reference file. The implementer and
reviewer agents for both stacks read it explicitly. The `azure-functions` and `dotnet-web`
skills read it too.

**Scope:** This file lists language-level and security rules. These rules apply
regardless of what you build. This file also states how to act when a task is unclear.
Architecture topics — layering, the testing approach, configuration, telemetry,
resilience — are **not** here. Find those in the applicable ADR:

| Building | Standard |
|---|---|
| Azure Functions | `~/.claude/adr/ADR-001-azure-functions-shared-architecture.md` |
| Internal web applications | `~/.claude/adr/ADR-002-web-application-shared-architecture.md` |

**Precedence:** project `AGENTS.md` > the applicable ADR > this file. Most specific wins.

## Writing style

Write all prose in this document — and all prose agents and skills produce when they
reference it — in ASD-STE100 (Simplified Technical English) style: short sentences, one
instruction per sentence, active voice, "must"/"must not"/"can" instead of
"should"/"may", consistent terminology. This includes code comments. Only code syntax
and literal commands are exempt.

---

## Non-negotiables

- Use `async Task` on every handler. Never use `async void`.
- Do not use `SELECT *`. Do not build SQL by concatenating strings. Use parameterized
  queries only.
- **Allowlist sort keys and column names that come from a client.** Never pass them
  through to SQL or an OData query. An ordering parameter is an injection vector.
  Parameterized queries do not protect against it, because the column name is not a
  parameter.
- **Pin `CultureInfo.InvariantCulture` for every date, time, and number in
  machine-readable output.** This covers file contents, filenames, export columns, API
  payloads, and keys. Use the ambient culture only for text a human reads. Reason: this
  environment runs under two ambient cultures, `ja-JP` and `en-US`. These two cultures
  format separators and date order differently. Machine-readable output must stay
  consistent regardless of the host culture. A culture test can pin `CurrentCulture` to
  either of these two cultures. The test then asserts that invariant-formatted output
  ignores the pinned culture. Do not reason about other cultures, calendars, or
  test-culture choices beyond this. That is out of scope for this environment.
- **Treat a shared input value with multiple independent consumers as more than one
  thing to fix.** A clock reading, a config default, or a computed value passed to more
  than one caller can carry more than one meaning, even as a single variable. Before you
  correct such a value for one consumer — or split it into a "fixed" and "not yet fixed"
  variant — audit every other consumer. Otherwise a fix for one consumer silently changes
  behavior the task never touched. (Seen in production: a fix that made a `now` value
  stay host-local, per a blocked business decision, also broke an unrelated, already
  correct JST-formatted fragment derived from the same variable. The fix and the
  regression sat one line apart.)
- Do not put secrets in code, in config committed to git, or in logs. Do not hard-code
  user-facing strings. See the applicable ADR for where user-facing strings belong.
- Follow existing project conventions — naming, DI patterns, folder structure — instead
  of introducing new ones. Check an existing file in the same layer before you write a
  new one.

## Comments are terse, not derivations

Write a comment that justifies a non-obvious choice — a culture pick, a retry scope, a
deviation from an ADR — in 1-2 lines. Stop there. Do not re-derive the reasoning from
scratch. Do not walk through the alternatives you considered. Do not restate what the
referenced ADR or standard already says. If the reader needs this standard or an ADR to
trust the comment, name that file and move on. Do not inline a copy of its argument.

- Bad: a paragraph that explains why a culture was chosen for a test, what alternatives
  would have failed to catch, and why the assertion format proves the point.
- Good: `// ja-JP ambient, asserts InvariantCulture output unaffected (see
  dotnet-conventions.md).`

Apply this rule every time you write or rewrite a comment. A long comment that survives
from a previous pass is not exempt. Tighten it when you touch it.

**State a non-obvious fact once, at the site closest to where it matters. Do not state it
at every site that touches it.** A class doc comment, an inline comment above the call,
and the called method's own doc comment can end up explaining the same thing — for
example, "why these three values must stay separate." That is the same paragraph paid
for three times. A human would write it once. Pick the one site a reader would check
first — usually the narrowest scope, such as the method that computes the values, not
the class that calls it. At every other site, add a half-line reference instead
(`// see ComputeClockValues' doc comment`). Do not restate the fact there. This is the
terse-comments rule above, applied across a file's comment sites instead of within one.

## Doc comments are contract, not narration

The next implementer reads an XML doc comment on a type or interface as a statement of
fact about behavior. Treat it with the same weight as the signature it sits on.

- **Before you implement against an existing interface, re-read its doc comment and
  follow it.** If the implementation must deviate, change the interface's comment in the
  same commit. Do not implement the deviation and leave the comment as is. A contract
  that says errors are captured as data, paired with an implementation that throws, is a
  defect in both.
- **When you change behavior a type's doc comment describes, update that comment in the
  same commit.** This is the rule already applied to `docs/` files. It extends to the
  comments on the types themselves, because those go stale silently — nothing compiles
  against them.
- This rule bites hardest when an interface and its implementation land in *different*
  tasks. The gap between the two is exactly where drift happens. The re-read is not
  optional there.

## Testing

The applicable ADR sets the testing approach — the framework, the substitution strategy,
which layers get their own test project, and what minimum coverage means. It differs
between the two stacks. These rules hold everywhere:

- **Ship new logic with tests in the same commit.** Write tests that assert behavior, not
  tests that only check the code runs without throwing.
- **Write a test that fails against the implementation you are worried about.** Before you
  write the assertion, name the wrong implementation it must catch. Then check the test
  actually distinguishes the two. A composite key needs each component varied
  independently, or an implementation keyed on only one component still passes. A field
  deliberately *excluded* from a key needs a test that varies it and asserts nothing
  changed — otherwise nothing pins the exclusion, and the next refactor absorbs it.
- **Do not assert against a substitute when the real thing is under test.** An in-memory
  database provider does not enforce the constraints a real engine does. A test that uses
  one proves nothing about those constraints.

## When a task is blocked or ambiguous

Stop and report back. Do not guess. Do not proceed. Stop when:

- The backlog or ticket marks the task blocked, or marks it as needing a human decision
  or a design decision ("not a lookup").
- A prerequisite task this one depends on is not actually complete yet.
- A spec, if one exists, appears wrong or incomplete. Propose the fix in your report. Do
  not commit a spec change on your own.
- You would need to invent a value that must come from somewhere else — a timestamp, a
  config value, a business rule. Flag it. Do not invent it.

## Definition of done

- Behavior matches the spec or ticket, if one exists.
- Tests are added per the rules above and the applicable ADR.
- Code has no secrets, no hard-coded user-facing strings, no `SELECT *`, no
  string-concatenated SQL, and no unallowlisted sort key.
- Every handler uses `async Task`, not `async void`.
- Build and tests pass. Where warnings are errors, treat a warning as a failure.
- If the project has a resource-key parity convention (for example, JA/EN keys), add
  both keys.
- Justify any deviation from the applicable ADR in a code comment at the point of
  deviation, **and** record it in the project's `AGENTS.md`.
- Update every doc comment that describes behavior you changed, in the same commit.
