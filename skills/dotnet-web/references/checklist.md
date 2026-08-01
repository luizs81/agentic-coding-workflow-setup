# Pre-flight checklist — new .NET web project

Work through this before generating any files. Don't guess on an unclear item — ask.

Items tagged **[Multi-module]** apply to apps hosting more than one module,
**[External-write]** to apps writing to a system of record outside their own database.

## Should this exist at all?
- [ ] Checked whether an existing platform should absorb this as a **module** instead —
      a new app is the exception, not the default
- [ ] If a new app: stated which of audience, lifecycle, or deployment story genuinely
      differs

## Purpose and scope
- [ ] The operational pain is written down: what an operator does today, across which
      systems, and what breaks
- [ ] App's purpose is clear: what it does, for whom
- [ ] Every external dependency named (SQL, Snowflake, internal APIs, external system of
      record) — each becomes a port in Application
- [ ] Whether the app writes to an external system of record is decided (drives
      **[External-write]** below)
- [ ] Bilingual-or-not decided — retrofitting means touching every user-facing string

## Auth
- [ ] Entra ID app registration exists, or the user has confirmed they'll create one
- [ ] Tenant and client ID known, or explicitly deferred with a placeholder marked as
      such in `appsettings.json` and `AGENTS.md`
- [ ] Admin allowlist identities known and the config key named
- [ ] Global fallback policy planned — routes opt *out*, never opt *in*
- [ ] Local dev auth approach decided (real dev-tenant registration vs. stub
      `ICurrentUser`) and will be stated in `AGENTS.md`

## Structure
- [ ] Project names use a short PascalCase app prefix: `<AppName>.Domain` /
      `.Application` / `.Infrastructure` / `.Web`
- [ ] `Platform/` and at least one `Modules/<Name>/` present in each layer, even for a
      single-capability app
- [ ] No Entra ID, EF Core, or Azure SDK reference in Domain or Application `.csproj`
- [ ] One test project per layer — not a flat `tests/Unit/`
- [ ] `Directory.Build.props` and `Directory.Packages.props` both at the repo root; no
      `Version` attributes in `.csproj`

## Architecture tests
- [ ] **[Multi-module]** `ModuleBoundaryTests` and `NamespaceMatchesFolderTests`
      generated in `<AppName>.Application.Tests`
- [ ] Both verified to actually fail on a real violation, not pass vacuously
- [ ] The "confirm it bites" instruction is in a comment at the top of the test

## Configuration and secrets
- [ ] Everything binds via `IOptions<T>`; no `Environment.GetEnvironmentVariable()`
      anywhere, including `Program.cs`
- [ ] `appsettings.json` has empty-string placeholders for every key the app expects,
      and no real values
- [ ] User-secrets wired for dev; Key Vault for UAT/prod
- [ ] Startup validation fails fast on a missing required key, naming the key
- [ ] If a predecessor app committed credentials, rotation is flagged as a task

## [External-write]
- [ ] `<Thing>Attempt` table designed: idempotency key, payload hash, actor, external id,
      status, failure step, retry state, timestamps
- [ ] Failure matrix drawn as a table and pasted into the feature spec **before** coding
- [ ] Idempotency key is a normalized-payload hash, not a client nonce
- [ ] Recovery path for routine phase-two failures identified — a job or screen, not a TODO

## Resilience
- [ ] Resilience pipeline registered in Infrastructure and injected into adapters — no
      hand-rolled retry loops
- [ ] Interactive-path calls have an overall timeout and a reduced attempt count; the
      full default is reserved for background work
- [ ] No retry policy wraps a non-idempotent write. **[External-write]** external writes
      retry through the attempt record's idempotency key, not a bare retry

## Cross-cutting
- [ ] `ILogger<T>` only; handlers open a `BeginScope()` with correlation and entity IDs
- [ ] `INotificationService` port in Application; delivery non-blocking, never throws
- [ ] Design-token theme file generated; component library theme overridden from tokens
- [ ] `DbContext` registered Scoped — never Singleton
- [ ] Localization missing-key check exists as a test or build step (if bilingual)

## Repo scaffolding
- [ ] `docs/specs/README.md` with the north star and spec template
- [ ] `scripts/dev-db.sh` running a container matching the production DB engine
- [ ] `azure-pipelines.yml`: Build & Test → UAT slot → approval-gated swap to prod
- [ ] `README.md` linking to ADR-002

## AGENTS.md
- [ ] `references/agents-md-template.md` copied into the new repo root as `AGENTS.md`
- [ ] Every placeholder filled with this project's actual specifics — app name, modules,
      auth scope, local dev decision, external dependencies
- [ ] Deviations section either lists real deviations with reasons, or is empty because
      there are none
- [ ] No leftover placeholder text — a half-filled `AGENTS.md` is worse than none, since
      a subagent will trust it as authoritative
