# <AppName> — working conventions

Scaffolded from the `dotnet-web` skill on <date>. This file is authoritative for how to
work in this repo. The `dotnet-web-implementer` and `dotnet-web-reviewer` subagents
treat it as binding. Update it as real conventions emerge. Do not let it go stale.

The team-wide standard is **ADR-002 — Internal Web Application Shared Architecture**.
This file covers the process, this project's instantiation of the standard, and any
deviation from it. Precedence: this file over ADR-002.

## Writing style

Write all prose in ASD-STE100 (Simplified Technical English) style: short sentences,
one instruction per sentence, active voice, "must"/"must not"/"can" instead of
"should"/"may", consistent terminology. This rule covers every kind of prose you
write — instructions, documents, responses, messages to other agents, and code
comments. Only code syntax and literal commands are exempt.

## 0. Ground rule

The operational pain this app exists to fix:

<what an operator does today, across which systems, and what breaks. This is the north
star for every architectural decision, in particular whether a flow needs the
failure-matrix apparatus (ADR-002 §3.6). If this is vague, the work is not ready.>

## 1. Spec-first process

- `docs/specs/` is the source of truth. **Read or extend the spec before you code a
  feature.** Never do it the other way around.
- Use one markdown file per feature:

  ```
  # <Feature>
  ## Context / problem
  ## Requirements (numbered, testable)
  ## Acceptance criteria (Given / When / Then)
  ## Out of scope
  ## Open questions / decisions
  ```

- **Open questions / decisions is append-only.** Mark a resolved entry
  `RESOLVED (date, evidence)` and keep it. Mark a reversed entry
  `SUPERSEDED (date, evidence)` with a pointer to its replacement. Never delete an
  entry. This is what answers "why does the code do X" in six months, without
  archaeology through git blame.
- Make acceptance criteria checkable. Aim for one-to-one with a test.
- If a spec turns out wrong, **update it in the same commit as the code**.

## 2. This project's shape

Four projects with modules as folders and namespaces under `Platform/` and
`Modules/<Name>/`, per ADR-002 §3.1.

| Module | Route | What it does |
|---|---|---|
| <Name> | `/<route>` | <one line> |

The boundary rule states that a `Modules.X` type can reference `Platform` and its own
module, and must never reference a sibling module. `ModuleBoundaryTests` and
`NamespaceMatchesFolderTests` in `tests/<AppName>.Application.Tests/` enforce this rule.
**Before you rely on either test, confirm it bites:** add a cross-module reference,
watch the test fail, then revert the change. Repeat this whenever the scanning logic
changes.

Anything two modules both need belongs in `Platform`.

## 3. Auth

- Entra ID via `Microsoft.Identity.Web`. Tenant: <tenant, or "TBD — placeholder in
  appsettings.json, replace before first deploy">.
- Global fallback policy: every route requires a signed-in user. Routes opt *out*.
- Admin allowlist config key: `<key>`. Current admins: <identities, or where declared>.
- Local dev auth: <"real dev-tenant registration" OR "stub `ICurrentUser` registered in
  Development only — see `Infrastructure/Platform/Auth/`">.

## 4. External dependencies

<list: SQL, Snowflake, internal APIs, external system of record — what this app
actually talks to. For each one, name the port that fronts it and where its config
lives (Key Vault, appsettings, user-secrets locally)>

## 5. Commands

```bash
dotnet build
dotnet test
dotnet run --project src/<AppName>.Web      # needs user-secrets
./scripts/dev-db.sh                          # local DB container matching prod engine
```

<note any test that skips unless an env var is set — e.g. DB constraint tests>

## 6. Deviations from ADR-002

<any rule this project intentionally departs from, with the reason. An empty list is a
valid state. But if the code deviates and this section is empty, the code is wrong.>

## 7. Known gaps / TODOs

<anything deliberately deferred at scaffold time: a stubbed adapter, an unconfirmed
auth detail, or a "figure this out before the first real feature" item>
