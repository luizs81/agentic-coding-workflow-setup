---
name: dotnet-web
description: >
  Scaffold new internal .NET web applications (Blazor Web App, ASP.NET Core) against the
  team's architecture standard (ADR-002). Use this skill any time someone asks to create,
  scaffold, or start a new .NET web app or Blazor project from scratch — even if they
  don't mention the standards explicitly. It covers Clean Architecture layering, the
  module rule and its architecture tests, Entra ID auth with a global fallback policy,
  configuration and secrets, localization, the design-token system, and the UAT-swap
  pipeline. It also seeds a project AGENTS.md so the dotnet-web-implementer and
  dotnet-web-reviewer subagents have established conventions to work against afterward.
  Trigger on phrases like "build a new web app", "create a Blazor app", "scaffold a new
  .NET web project", "start a new internal tool", or any request to start a new .NET web
  application from scratch. Do NOT use this for adding a feature to an existing web app —
  that's ordinary implementation work for dotnet-web-implementer, not scaffolding.
  Consider first whether the request should be a new **module** in an existing platform
  rather than a new application at all.
---

# .NET Web — Project Scaffold

## Writing style

Write all prose in ASD-STE100 (Simplified Technical English) style: short sentences,
one instruction per sentence, active voice, "must"/"must not"/"can" instead of
"should"/"may", consistent terminology. This rule covers every kind of prose you
write — instructions, documents, responses, messages to other agents, and code
comments. Only code syntax and literal commands are exempt.

This skill scaffolds internal web applications against
[ADR-002](../../adr/ADR-002-web-application-shared-architecture.md), the authoritative
source. This file is the operational how-to. The ADR explains why each rule exists and
what to revisit. **If the two disagree, the ADR wins.** Flag the mismatch. Do not
silently pick one.

Before you write any files, read `references/checklist.md`.

Rules marked **[Multi-module]** apply only to applications that host more than one
operational module. Rules marked **[External-write]** apply only to applications that
write to a system of record outside their own database. Everything else is universal.

---

## Before scaffolding anything: should this be a new application?

ADR-002's core decision is that a new operational request should become a **module in
an existing platform**, not the next standalone app. The failure mode this replaces is
one app per request, each with its own sign-in, shell, deployment, and language
handling.

So the first question is not "how do I scaffold this." It is "does a platform already
exist that this belongs in?" If yes, this skill is the wrong tool: adding a module is
ordinary implementation work. Scaffold a new application only when the capability
genuinely has a different audience, lifecycle, or deployment story. State which of
those applies.

---

## What to do when this skill triggers

1. **Name the operational pain.** What does an operator do today, across which
   systems, and what breaks? Write it down before any code. It drives every decision
   below, in particular whether the app needs the failure-matrix apparatus. If there is
   no clear answer, the work is not ready to start.

2. **Clarify purpose and dependencies.** Identify what the app does, who uses it, and
   what it talks to (SQL, Snowflake, an internal API, an external system of record).
   Each external system becomes a port in Application with an adapter in
   Infrastructure.

3. **Confirm the auth scope.** Identify which Entra ID app registration and tenant to
   use, and who the admins are. Do not create a registration yourself. Confirm it
   exists, or ask the user to create one, then wire config against it.

4. **Decide bilingual-or-not, now.** Retrofitting localization means touching every
   user-facing string, including validation messages that originate in Domain rules.

5. **Run the pre-flight checklist.** Work through `references/checklist.md`, every box.

6. **Scaffold** the structure below. Never put Entra ID or an Azure SDK reference in
   Domain or Application. Never put business logic in a Razor component.

7. **Seed `AGENTS.md`** from `references/agents-md-template.md`, filled with this
   project's actual specifics. The `dotnet-web-implementer` and `dotnet-web-reviewer`
   subagents treat this file as authoritative afterward. Do not leave placeholder text.
   A half-filled `AGENTS.md` is worse than none, because a subagent trusts it as-is.

8. **Set up `docs/specs/`** with the index and spec template. Specs are the source of
   truth, so shape the repo that way from commit one.

---

## Project structure

```
<AppName>/
├── Directory.Build.props           # TFM, nullable, implicit usings
├── Directory.Packages.props        # Central package versions
├── azure-pipelines.yml
├── scripts/dev-db.sh
├── README.md
├── AGENTS.md
├── docs/specs/README.md            # Spec index + north star
├── src/
│   ├── <AppName>.Domain/           # No framework deps, no I/O
│   │   ├── Platform/
│   │   └── Modules/<Name>/
│   ├── <AppName>.Application/      # Ports, one handler per use case, pipelines
│   │   ├── Platform/{Auth,Admin,Notifications}/
│   │   └── Modules/<Name>/
│   ├── <AppName>.Infrastructure/   # Adapters. No business logic.
│   │   ├── Platform/{Auth,Admin,Configuration,Notifications,Persistence}/
│   │   └── Modules/<Name>/
│   └── <AppName>.Web/              # Thin over Application use cases
│       ├── Components/Platform/{Layout,Pages}/
│       ├── Components/Modules/<Name>/
│       ├── Resources/
│       ├── wwwroot/
│       └── Program.cs
└── tests/
    ├── <AppName>.Domain.Tests/
    ├── <AppName>.Application.Tests/     # Architecture tests live here
    ├── <AppName>.Infrastructure.Tests/
    └── <AppName>.Web.Tests/             # bUnit
```

Dependency direction: `Web → Application → Domain`, `Infrastructure → Application →
Domain`. Infrastructure translates. It does not decide.

**Modules are folders and namespaces, not projects.** A type under `Modules.X` can
reference `Platform` and its own module. It must never reference a sibling module.
Anything two modules both need belongs in `Platform`.

Scaffold `Platform/` and one `Modules/<Name>/` even for a single-capability app. A
single-module application is a conforming instance, not an exception. The second
module then costs a folder, not a refactor.

**Naming.** Use a short PascalCase app name as prefix — `<AppName>.Domain`. Do not use
a fully-qualified organizational path.

---

## Build properties and packages

`Directory.Build.props` at the root carries `net10.0` (or current LTS-or-later, uniform
across the solution), `<Nullable>enable</Nullable>`, `<ImplicitUsings>enable</ImplicitUsings>`.

`Directory.Packages.props` carries `<ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>`
and one `<PackageVersion>` per package. `.csproj` files use `<PackageReference>` with no
`Version`. UI and identity packages drift fastest, because they appear in both the Web
project and its test project. Generate this file at scaffold time, not later.

---

## Architecture tests — generate these, don't defer them

**[Multi-module]** Folders buy cheap modules at the cost of compiler enforcement. Buy
it back in `<AppName>.Application.Tests/`:

- `ModuleBoundaryTests` — confirms no type under `*.Modules.X` references a sibling
  module. Scan the Domain, Application, and Infrastructure assemblies by reflection.
- `NamespaceMatchesFolderTests` — confirms namespaces track folders, so the boundary
  scan cannot be fooled by a misfiled type.

**Confirm they bite.** Add a cross-module reference, watch the test fail, then revert
it. A test that passes vacuously is worse than no test, because it produces false
confidence. Put that instruction in a comment at the top of the test. Repeat it
whenever the scanning logic changes.

---

## Authentication and admin access

- Use `Microsoft.Identity.Web`, configured in `Program.cs` from the `AzureAd` config
  section. Never hardcode it.
- **Global fallback policy: every route requires a signed-in user by default, and
  routes opt *out* individually.** Do not use per-route opt-in. A route someone forgets
  to annotate becomes public, so opt-in fails open.
- Define an `ICurrentUser` port in Application, implemented in
  `Infrastructure/Platform/Auth/`. Use cases depend on `ICurrentUser`, never on
  `HttpContext` or a claims principal directly. This is what keeps Application
  testable without a real auth context.
- **Admin is an allowlist of email/UPN identities in configuration.** It is not a
  directory group and not a Graph group-claim lookup. Two roles are usually enough:
  General (any signed-in user) and Admin. Enforce this in one policy handler. Gate it
  onto the pages that need it: seeing all records vs. your own, admin CRUD, and
  manually-triggered operational actions.
- Document the allowlist config key in the config spec, so each environment's admins
  are visibly declared rather than tribal knowledge.
- State in `AGENTS.md` whether local dev uses a real dev-tenant registration or a stub
  `ICurrentUser`. This is the first thing that breaks for a new contributor.

---

## Configuration and secrets

- Bind through `IOptions<T>`. Do not use `Environment.GetEnvironmentVariable()`
  anywhere, including `Program.cs`. Do not write bespoke secret-loading code.
- **Never put secrets in source control** — not even as `appsettings.json`
  placeholders with a "just for dev" justification. Use empty-string placeholders, so
  the file doubles as a documented template of every key the app expects.
- Use user-secrets in dev and Key Vault in UAT and production.
- **Generate startup config validation** that fails fast on a missing required key,
  with a message naming the key. Do this at scaffold time. Retrofitting it is exactly
  the task that gets deferred permanently.
- If a predecessor app committed real credentials, **rotate every one of them.** They
  were compromised the moment they entered git history.

---

## DI and lifetimes

Put all registration in one
`ServiceCollectionExtensions.AddInfrastructure(IServiceCollection, IConfiguration)`.
`Program.cs` calls that, plus the Blazor and auth registrations
(`AddRazorComponents().AddInteractiveServerComponents()`,
`AddMicrosoftIdentityWebAppAuthentication()`).

- **Scoped:** `DbContext`, use cases, and anything holding per-request or per-circuit
  state.
- **Singleton:** stateless clients — `IHttpClientFactory`-provided `HttpClient`,
  resilience pipelines.
- **Never register `DbContext` as singleton.** Interactive server circuits are
  long-lived. A singleton context leaks connections and state across users.

---

## [External-write] The attempt-record and failure-matrix pattern

Apply this pattern to any flow that writes to a system of record outside the app's own
database. It is the specific answer to partial writes with no compensation. See
ADR-002 §3.6 for the full pattern.

1. Create one `<Thing>Attempt` table: idempotency key, normalized-payload hash, actor,
   external identifier when known, status enum, failure step and detail, retry state,
   timestamps.
2. **Write the attempt row before the first external write.** If nothing else survives
   a crash, this row does.
3. **Draw the failure matrix as a table before you write code.** For each step, record
   what the user sees, the external system's state, what the audit record says,
   whether retry is safe, and whether it alerts. Paste it into the feature spec. It is
   the contract.
4. Set the idempotency key to a hash of the normalized payload, not a
   client-generated nonce.
5. Treat multi-entity external writes as multi-phase, unless the external API
   genuinely rolls back atomically — verify this against the real API. Give routine
   phase-two failures a first-class recovery path (a reconciliation job or screen), not
   a TODO.
6. Treat the attempt table plus telemetry as the audit source of truth. Chat
   notifications are for alerting only.

---

## Resilience on outbound calls

Every call leaving the app (SQL, an external system of record, an analytics warehouse,
an internal API) must go through a resilience pipeline built with
`Microsoft.Extensions.Resilience`, or `Microsoft.Extensions.Http.Resilience` for
`HttpClient`. Register it in Infrastructure and inject it into the adapters. No adapter
writes its own retry loop.

Defaults match ADR-001: 3 attempts, exponential backoff with jitter (2s initial, 2x),
count-based circuit breaker (100% failure ratio, min 5 requests, 30s sampling and
break).

Two things differ from a Function app, because here someone is waiting:

- **The interactive path has a time budget, and the retry policy lives inside it.**
  Three backed-off attempts on an already-slow call produce a page load the operator
  abandons and retries by hand. This turns one slow request into several concurrent
  ones. Set an overall pipeline timeout and use fewer attempts on user-facing calls.
  Background and reconciliation work keeps the full default.
- **Never wrap a bare retry around a non-idempotent write.** Retry is safe by default
  only for reads and naturally idempotent operations. **[External-write]** external
  writes retry through the attempt record's idempotency key (above). This is what
  makes the second attempt converge instead of duplicating. A retry policy around an
  unprotected write is a defect wearing a resilience costume.

Surface failures the operator can act on (a validation rejection from the external
system) differently from ones they cannot act on (a timeout). When retries exhaust,
the error must name the operation and state whether the work was recorded.

---

## Localization

If the app is bilingual, **every** user-facing string must come from resource files
through the framework's localizer, including validation and error messages that
originate in Domain rules. Derive culture from `Accept-Language`. Let an explicit
switch override it, and persist the choice so it survives across requests. Generate a
**missing-key check** as a test or build step, so one language cannot silently drift
behind the other.

---

## Telemetry and notifications

This follows the Functions standard: `ILogger<T>` only, no second logging library.
Use-case handlers open a `BeginScope()` carrying correlation and entity IDs. Use named
placeholders in message templates. Never use interpolation.

Chat notifications go through an `INotificationService` port in Application. The
Infrastructure adapter posts to a pre-existing org webhook or flow where one exists.
Reuse the proven payload shape. Read the URL from config. Never hardcode it.
**Delivery is non-blocking**: on non-success, log a `Warning` and return. Never throw,
and never treat delivery as part of the record. Enforce message truncation in the
domain entity, not ad hoc at each call site.

---

## Design system

Generate a single theme file of CSS custom properties as design tokens:
`--app-primary`, `--app-page-bg`, `--app-card-bg`, a text scale, and semantic
danger/warning/info triads for background, border, and text. Override the component
library's own theme variables from those tokens. **Never hand-style individual
component instances.**

Standard shell: brand-colored sidebar, top bar with app name, right-aligned user
avatar with initials fallback, and a dropdown carrying name, culture switch, and
sign-out.

Build page primitives as a handful of small CSS classes, not per-page bespoke
styling: card container, eyebrow label, labeled-field wrapper, responsive grid
helper, actions row, banner variants, and a monospace class reserved for
copy-paste-critical identifiers that must never be truncated or reformatted.

State in the token file's header comment that it is purely presentational. A
redesign and a markup change are separate concerns. Do not bundle them.

---

## Testing

Use one test project per layer, not a flat `Unit/`:

- **Domain.Tests** — test rules and value objects directly, including boundary and
  encoding cases.
- **Application.Tests** — test each use case (happy path plus each dependency-failure
  mode), the validation pipeline's aggregating behavior, and the architecture tests.
- **Infrastructure.Tests** — test adapter translation and persistence constraints
  **against the real engine**. An in-memory provider does not enforce constraints, so a
  test that uses one proves nothing about them.
- **Web.Tests** — use bUnit. Interactive components have failure modes unit tests
  cannot reach: list mutation, `@key`-based rendering, optimistic UI state. Scaffold
  this from the start, even if it begins as one smoke test. Retrofitting it after
  several screens exist is expensive.

**[External-write]** Give every row of the failure matrix a test. A matrix without
tests is a diagram.

---

## Local development and CI/CD

- Generate `scripts/dev-db.sh` to run the app's own database in a container
  **matching the production engine**, not a different local engine. Dialect and
  constraint behavior must be identical. This is the whole reason Infrastructure tests
  assert against a real database.
- For an external integration behind SSO/MFA that is tedious to click through
  repeatedly, build a **thin read-only CLI probe** that calls the Application read
  ports directly, reusing the app's DI wiring and user-secrets. Make it read-only by
  construction. It must never reference the write ports.
- Use a three-stage `azure-pipelines.yml`: **Build & Test**, then **deploy to UAT
  slot**, then **swap UAT into production**, with the swap gated by a
  manual-approval `environment`. Swapping validates the exact bits that were tested,
  instead of doing a second independent prod deploy. Pass secrets via variable
  groups. Never put them inline.

---

## Reference files

- `references/checklist.md` — pre-flight checklist, run before generating any files
- `references/agents-md-template.md` — the AGENTS.md template to seed into the new project
- [`../../standards/dotnet-conventions.md`](../../standards/dotnet-conventions.md) —
  language-level and security non-negotiables that hold regardless of stack (`async Task`,
  parameterized SQL, allowlisted sort keys), plus blocked-task handling and definition of
  done. Generated code must satisfy these too. The allowlisted-sort-key rule in
  particular applies to every grid or table this skill scaffolds.
- [`../../adr/ADR-002-web-application-shared-architecture.md`](../../adr/ADR-002-web-application-shared-architecture.md) —
  the decision record: context, options considered, trade-offs, consequences. Read it
  when you need the reasoning behind a rule, not just what to do.
- [`../../adr/ADR-001-azure-functions-shared-architecture.md`](../../adr/ADR-001-azure-functions-shared-architecture.md) —
  the Functions standard. Where the two agree, they agree on purpose. Check it before
  inventing a different convention for configuration, logging, or resilience.
