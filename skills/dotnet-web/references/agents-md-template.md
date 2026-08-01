# <AppName> — working conventions

Scaffolded from the `dotnet-web` skill on <date>. Authoritative for how to work in this
repo — the `dotnet-web-implementer` and `dotnet-web-reviewer` subagents treat it as
binding. Update it as real conventions emerge; don't let it go stale.

The team-wide standard is **ADR-002 — Internal Web Application Shared Architecture**.
This file covers the process, this project's instantiation of the standard, and any
deviation from it. Precedence: this file > ADR-002.

## 0. Ground rule

The operational pain this app exists to fix:

<what an operator does today, across which systems, and what breaks. This is the north
star for every architectural decision — in particular whether a flow needs the
failure-matrix apparatus (ADR-002 §3.6). If this is vague, the work isn't ready.>

## 1. Spec-first process

- `docs/specs/` is the source of truth. **Read or extend the spec before coding a
  feature** — never the other way around.
- One markdown file per feature:

  ```
  # <Feature>
  ## Context / problem
  ## Requirements (numbered, testable)
  ## Acceptance criteria (Given / When / Then)
  ## Out of scope
  ## Open questions / decisions
  ```

- **Open questions / decisions is append-only.** A resolved entry is marked
  `RESOLVED (date, evidence)` and kept; a reversed one `SUPERSEDED (date, evidence)` with
  a pointer to its replacement. Never delete — this is what answers "why does the code do
  X" in six months without archaeology through git blame.
- Acceptance criteria should be checkable, ideally one-to-one with a test.
- If a spec turns out wrong, **update it in the same commit as the code**.

## 2. This project's shape

Four projects with modules as folders and namespaces under `Platform/` and
`Modules/<Name>/`, per ADR-002 §3.1.

| Module | Route | What it does |
|---|---|---|
| <Name> | `/<route>` | <one line> |

The boundary rule — a `Modules.X` type may reference `Platform` and its own module,
never a sibling — is enforced by `ModuleBoundaryTests` and `NamespaceMatchesFolderTests`
in `tests/<AppName>.Application.Tests/`. **Before relying on either, confirm it bites:**
add a cross-module reference, watch it fail, revert. Repeat whenever the scanning logic
changes.

Anything two modules both need belongs in `Platform`.

## 3. Auth

- Entra ID via `Microsoft.Identity.Web`. Tenant: <tenant, or "TBD — placeholder in
  appsettings.json, replace before first deploy">.
- Global fallback policy: every route requires a signed-in user; routes opt *out*.
- Admin allowlist config key: `<key>`. Current admins: <identities, or where declared>.
- Local dev auth: <"real dev-tenant registration" OR "stub `ICurrentUser` registered in
  Development only — see `Infrastructure/Platform/Auth/`">.

## 4. External dependencies

<list: SQL, Snowflake, internal APIs, external system of record — what this app actually
talks to, the port that fronts each one, and where its config lives (Key Vault,
appsettings, user-secrets locally)>

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
valid state — but if the code deviates and this section is empty, the code is wrong.>

## 7. Known gaps / TODOs

<anything deliberately deferred at scaffold time — a stubbed adapter, an unconfirmed
auth detail, a "figure this out before the first real feature" item>
