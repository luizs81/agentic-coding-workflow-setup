---
name: azure-functions
description: >
  Scaffold new Azure Function applications against the team's architecture standard
  (ADR-001). Use this skill any time someone asks to create, scaffold, or start a new
  Azure Function app or project — even if they don't mention the standards explicitly.
  It covers every trigger shape: timer, HTTP, queue, blob, and Durable orchestrations.
  The skill ensures the five architecture pillars are applied — Clean Architecture
  layers, Polly resilience, unit tests, structured telemetry, and Teams notifications —
  and seeds a project AGENTS.md so the azure-function-implementer and
  azure-function-reviewer subagents have established conventions to work against
  afterward. Trigger on phrases like "build a new Azure Function", "create a function
  app", "scaffold a new function", "add an Azure Function for X", or any request to
  start a new Functions-based service from scratch. Do NOT use this for adding a
  feature to an existing Function app — that's ordinary implementation work for
  azure-function-implementer, not scaffolding.
---

# Azure Functions — Architecture Standard

This skill encodes the architecture standard every Azure Function application in this
team must satisfy. The authoritative source is
[ADR-001](../../adr/ADR-001-azure-functions-shared-architecture.md) — this file is the
operational how-to for scaffolding; the ADR explains why each rule exists and what to
revisit. **If the two disagree, the ADR wins.** Flag the mismatch rather than silently
picking one.

Before writing a single line of code, read `references/checklist.md`. For the rationale
behind each rule, read `references/standards.md`.

Rules below marked **[Orchestrated]** apply only to apps using Durable Functions;
**[Scheduled]** only to timer-triggered apps. Everything else is universal, including
plain HTTP-triggered functions.

---

## What to do when this skill triggers

1. **Clarify the function's purpose and shape** — what does it load, transform, or
   produce? Which trigger (timer, HTTP, queue, blob)? Does it need a Durable
   orchestrator, or is a single trigger enough? What consumes the output?

2. **Identify the external systems** — every data source and every output sink (Blob
   Storage, SQL, SharePoint, an internal API, a downstream queue). Each becomes a
   Domain interface with one Infrastructure implementation. Don't assume a report
   shape; some apps only receive an event and write a record.

3. **Run the pre-flight checklist** — read `references/checklist.md` and tick every
   box before generating project files.

4. **Scaffold the project** — follow the four-layer structure below. Never put
   infrastructure code in the Functions project, and never put Azure SDK references
   in Domain or Application.

5. **Generate all five pillars** — all must be present in every new project, even if
   some are stubs.

6. **Seed `AGENTS.md`** — generate the project's `AGENTS.md` from
   `references/agents-md-template.md`, filled in with this project's actual specifics
   (app name, trigger shape, output sink, external dependencies, notification scope).
   This is what the `azure-function-implementer` / `azure-function-reviewer` subagents
   treat as authoritative on every subsequent task in this repo. Don't leave
   placeholder text in it — a half-filled `AGENTS.md` is worse than none, since a
   subagent will trust it as-is.

---

## Project structure

```
<AppName>/
├── Directory.Packages.props            # Central package versions — see below
├── azure-pipelines.yml
├── dev-start.sh
├── README.md
├── AGENTS.md
├── src/
│   ├── <AppName>.Domain/               # Zero external NuGet dependencies
│   │   ├── Entities/                   # Sealed records or classes
│   │   ├── Enums/
│   │   └── Interfaces/                 # One per external system + INotificationService
│   ├── <AppName>.Application/          # Depends on Domain only
│   │   └── UseCases/                   # One use case per workflow
│   ├── <AppName>.Infrastructure/       # Depends on Domain + Application
│   │   ├── <Role>/                     # Implementations, one folder per role
│   │   ├── Notifications/              # INotificationService (Teams)
│   │   ├── Resilience/                 # PollyResiliencePipeline
│   │   ├── Options/                    # Strongly-typed config classes
│   │   └── Extensions/                 # ServiceCollectionExtensions.AddInfrastructure()
│   └── <AppName>.Functions/            # Entry points only — depends on App + Infra
│       ├── Triggers/
│       ├── Orchestrators/              # [Orchestrated]
│       ├── Activities/                 # [Orchestrated]
│       ├── Program.cs
│       ├── host.json
│       └── local.settings.json.template
└── tests/
    ├── Unit/                           # Mirrors src/ layout
    └── Integration/                     # Optional; [Trait("Category","Integration")]
```

**Naming.** Use a short PascalCase app name as the prefix — `PaymentGateway.Domain`,
`PaymentGateway.Tests.Unit` — not a fully-qualified organizational path.

---

## Common build properties

Every `.csproj` sets `net10.0` (or current LTS-or-later, uniform across the solution),
`<Nullable>enable</Nullable>`, `<ImplicitUsings>enable</ImplicitUsings>`,
`<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`, `<LangVersion>latest</LangVersion>`.

**Package versions are centrally managed.** Generate a `Directory.Packages.props` at
the repo root with `<ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>`
and one `<PackageVersion>` per package. Individual `.csproj` files carry
`<PackageReference Include="..." />` with **no** `Version` attribute.

---

## The five required pillars

### 1. Clean Architecture

Domain knows nothing. Application knows only Domain. Infrastructure knows Domain +
Application. Functions knows Application + Infrastructure. Never add an Azure SDK
reference to Domain or Application.

Domain references no NuGet packages beyond the runtime. Application references only
`Microsoft.Extensions.Logging.Abstractions`. Infrastructure references Application (not
just Domain) because `AddInfrastructure()` is the single composition root and registers
use cases alongside their dependencies.

All domain interfaces live in `Domain/Interfaces/` — one per external system the app
talks to, plus `INotificationService`. Report-style apps typically land on a
loader/builder/uploader triple; event-driven apps often need only a validator and a
writer. Derive the interfaces from step 2, don't impose a fixed set.

### 2. Polly resilience pipeline

Every external call (SQL, Blob Storage, HTTP, Key Vault) goes through a shared sealed
`PollyResiliencePipeline`, registered singleton and injected into every infrastructure
class making external calls. Consume Polly via `Microsoft.Extensions.Resilience`; use
`Microsoft.Extensions.Http.Resilience` for `HttpClient`-specific pipelines.

Default: 3 retry attempts, exponential backoff (2s initial, 2× multiplier, jitter),
plus a count-based circuit breaker (100% failure ratio, min 5 requests, 30s sampling,
30s break).

Retry count is the one value expected to be tuned per app — lower it when an attempt is
expensive or slow (browser automation, large report generation) so a failing run
surfaces quickly instead of multiplying cost. Record the reason at the call site.

**Filter the retry to transient faults — don't retry on the base `Exception` type.**
Give the retry strategy a `ShouldHandle` predicate: retry timeouts, connection resets,
throttling, and 429/503s; let auth/permission failures (401/403, expired credentials),
missing objects, and malformed requests throw on the first attempt — a second attempt
can't fix those, it just delays the failure and burns the backoff budget. The exact
exception types differ per SDK; pick them at the call site and comment why.

**[Orchestrated]** The Durable `RetryPolicy` stays at the activity level as a coarse
backstop; it does not replace Polly. Polly handles individual SDK call failures,
Durable handles activity-level crashes.

### 3. Unit tests

Every project ships `tests/Unit/` using xUnit and NSubstitute, mirroring the `src/`
layout. Minimum coverage before merging:

- **Every use case** — happy path, primary dependency failure, secondary dependency
  failure, and notification-failure-is-non-blocking.
- **Notification card builders** — field presence per status the app emits, long error
  message truncation (500 chars), schema compliance.
- **Pure transformation logic** — parsing, pivots, date-range and schedule maths,
  signature validation: parameterized tests for boundary conditions.

The unit test project references Domain, Application, **and** Infrastructure — card
builders, validators, and parsers are real infrastructure code worth asserting on
directly. Keep those members `internal` and expose them with `InternalsVisibleTo` on
the Infrastructure project rather than widening to public.

Azure SDK clients and outbound HTTP are always substituted. Tests must pass in CI with
no network access and no Azure credentials.

### 4. Telemetry

Application Insights needs **both** halves — `host.json` alone is not enough. In
`Program.cs`: `AddApplicationInsightsTelemetryWorkerService()` and
`ConfigureFunctionsApplicationInsights()`. In `host.json`: sampling enabled with
`"excludedTypes": "Request"`, and `enableLiveMetricsFilters`. Omitting the
worker-service registration silently loses worker-emitted telemetry.

Use `ILogger<T>` exclusively — no Serilog (it double-initializes under the isolated
worker), no static logger. Required patterns:

- Every trigger and activity entry point: `LogInformation` with a summary of input and
  context, wrapped in a `BeginScope()` carrying the invocation or orchestration
  instance ID so all lines in that invocation correlate.
- Exceptions caught at use case level: `LogError(ex, ...)` with structured properties
  (operation name, duration, entity IDs).
- `LogWarning` for non-fatal conditions: retry attempt, webhook non-200, optional
  config missing, timer firing past due.
- Message templates use named placeholders (`{InstanceId}`), never interpolation.
- Never let an exception propagate silently — if it's caught, log it.

### 5. Teams notifications

Applications report run outcomes to a Teams channel via an Incoming Webhook using
Adaptive Cards schema v1.5.

The contract is a single `INotificationService` in `Domain/Interfaces/`, implemented in
`Infrastructure/Notifications/`. Method and result-type names follow the application's
own domain language — there is no fixed signature.

**Which events notify:**

- **[Scheduled]** Both success and failure. A silent scheduled job is
  indistinguishable from a broken one.
- **Event-driven / high-frequency triggers** — failures only. A card per inbound event
  trains the channel to be ignored; success is observed through the downstream
  artifact. Document the suppression at the implementation.

**Minimum card content:** status, the artifact identifier (output filename, blob path,
or event reference), duration, and on failure the error type, the error message
truncated to 500 characters, and a timestamp.

The webhook URL is bound through `IOptions<TeamsOptions>` and never hardcoded. When
absent, log a `Warning` and return. **Delivery is always non-blocking** — the service
catches every exception, logs a `Warning`, and returns. A Teams outage must never fail
a run.

---

## Options pattern and configuration

`Environment.GetEnvironmentVariable()` is not used anywhere in the application — not
even in `Program.cs`. All config binds via the Options pattern, registered in
`AddInfrastructure()`. Each Options class is `sealed`, lives in `Infrastructure/Options/`,
exposes `public const string SectionName`, and gives every property a safe default.

Create one Options class per external system the app actually talks to, plus
`TeamsOptions`. Don't scaffold options for systems the app doesn't use.

**Secrets** live in Azure Key Vault and reach the app as Key Vault *references* in app
settings (`@Microsoft.KeyVault(...)`), resolved by the Function's system-assigned
managed identity, which needs the **Key Vault Secrets User** role. This is the default —
it keeps `Azure.Security.KeyVault.Secrets` out of the dependency graph. Instantiate
`SecretClient` directly only when a secret must be fetched or rotated at runtime.

**Identity:** reach Azure resources with `DefaultAzureCredential` against a resource
URI. A connection string is a fallback for local Azurite development only:

```csharp
var client = !string.IsNullOrWhiteSpace(opts.ConnectionString)
    ? new BlobServiceClient(opts.ConnectionString)
    : new BlobServiceClient(new Uri(opts.AccountUri), new DefaultAzureCredential());
```

In `local.settings.json.template`, set `FUNCTIONS_WORKER_RUNTIME` to `"dotnet-isolated"`
(not `"python"` or `"dotnet"`), include every key the app reads, and blank all secrets.

---

## DI registration pattern

All registration goes in one method,
`ServiceCollectionExtensions.AddInfrastructure(this IServiceCollection, IConfiguration)`,
registering options, then infrastructure services, then use cases, with section
comments. `Program.cs` contains only host construction:

```csharp
var host = new HostBuilder()
    .ConfigureFunctionsWorkerDefaults()
    .ConfigureServices((context, services) =>
    {
        services.AddApplicationInsightsTelemetryWorkerService();
        services.ConfigureFunctionsApplicationInsights();
        services.AddInfrastructure(context.Configuration);
    })
    .Build();

await host.RunAsync();
```

Process-wide setup that must run before the host exists (e.g. registering
`CodePagesEncodingProvider` for Shift-JIS input) goes above the builder with a comment
explaining why.

**Lifetimes:** singleton for all infrastructure classes (loaders, builders, uploaders,
notification service, resilience pipeline); transient for use cases. `HttpClient` always
comes from a named `IHttpClientFactory` client (`services.AddHttpClient("Teams")`),
never constructed directly. Where an implementation is chosen at runtime, register each
concrete type and resolve through a factory delegate in the same method.

---

## Local development and CI/CD

- `local.settings.json` is git-ignored; the `.template` is committed.
- Generate a `dev-start.sh` at the repo root that brings up the local stack in one
  command: reset and start Azurite, build, `func start`, tear down Azurite on exit.
- The Functions host must be started from *within* the Functions project directory —
  the SDK resolves its working directory from the shell's cwd, not from `--project`.
- Generate an `azure-pipelines.yml` triggered on `main` with at minimum a Build & Test
  stage (pinned SDK, restore/build/test, integration tests excluded by trait) and a
  Deploy stage as a `deployment` job bound to an `environment`, so approval gating
  lives in Azure DevOps rather than YAML. Zip deploy or an ACR container image are both
  acceptable — pick one per app and keep it consistent. Secrets reach the pipeline
  through variable groups, never inline.
- Generate a `README.md` covering what the app does and how to run it, with a section
  linking to ADR-001.

---

## Reference files

- `references/checklist.md` — pre-flight checklist, run before generating any files
- `references/standards.md` — rationale behind each pillar, for judgment calls
- [`../../standards/dotnet-conventions.md`](../../standards/dotnet-conventions.md) —
  language-level and security non-negotiables that hold regardless of stack (`async Task`,
  parameterized SQL, allowlisted sort keys), plus blocked-task handling and definition of
  done. Generated code must satisfy these too.
- `references/agents-md-template.md` — the AGENTS.md template to seed into the new
  project, with placeholders filled from steps 1–2
- [`../../adr/ADR-001-azure-functions-shared-architecture.md`](../../adr/ADR-001-azure-functions-shared-architecture.md) —
  the formal decision record behind this skill. It governs every Azure Function project
  across the team rather than any single repo, so it lives alongside the skill. Read it
  when you need the full context, options considered, or history behind a rule — not
  just what to do.
