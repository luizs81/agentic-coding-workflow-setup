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

## Writing style

Write all prose in ASD-STE100 (Simplified Technical English) style: short sentences,
one instruction per sentence, active voice, "must"/"must not"/"can" instead of
"should"/"may", consistent terminology. This rule covers every kind of prose you
write — instructions, documents, responses, messages to other agents, and code
comments. Only code syntax and literal commands are exempt.

This skill encodes the architecture standard for every Azure Function application in
this team. The authoritative source is
[ADR-001](../../adr/ADR-001-azure-functions-shared-architecture.md). This file is the
operational how-to for scaffolding. The ADR explains why each rule exists and what to
revisit. **If the two disagree, the ADR wins.** Flag the mismatch. Do not silently pick
one.

Before you write any code, read `references/checklist.md`. For the rationale behind
each rule, read `references/standards.md`.

Rules below marked **[Orchestrated]** apply only to apps that use Durable Functions.
Rules marked **[Scheduled]** apply only to timer-triggered apps. Everything else is
universal, including plain HTTP-triggered functions.

---

## What to do when this skill triggers

1. **Clarify the function's purpose and shape.** What does it load, transform, or
   produce? Which trigger does it use (timer, HTTP, queue, blob)? Does it need a
   Durable orchestrator, or is a single trigger enough? What consumes the output?

2. **Identify the external systems.** List every data source and every output sink
   (Blob Storage, SQL, SharePoint, an internal API, a downstream queue). Each becomes
   a Domain interface with one Infrastructure implementation. Do not assume a report
   shape. Some apps only receive an event and write a record.

3. **Run the pre-flight checklist.** Read `references/checklist.md` and tick every
   box before you generate project files.

4. **Scaffold the project.** Follow the four-layer structure below. Never put
   infrastructure code in the Functions project. Never put Azure SDK references in
   Domain or Application.

5. **Generate all five pillars.** All five must be present in every new project, even
   if some are stubs.

6. **Seed `AGENTS.md`.** Generate the project's `AGENTS.md` from
   `references/agents-md-template.md`. Fill it in with this project's actual specifics
   (app name, trigger shape, output sink, external dependencies, notification scope).
   The `azure-function-implementer` and `azure-function-reviewer` subagents treat this
   file as authoritative on every later task in this repo. Do not leave placeholder
   text in it. A half-filled `AGENTS.md` is worse than none, because a subagent trusts
   it as-is.

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
`PaymentGateway.Tests.Unit`. Do not use a fully-qualified organizational path.

---

## Common build properties

Every `.csproj` sets `net10.0` (or current LTS-or-later, uniform across the solution),
`<Nullable>enable</Nullable>`, `<ImplicitUsings>enable</ImplicitUsings>`,
`<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`, `<LangVersion>latest</LangVersion>`.

**Package versions are centrally managed.** Generate a `Directory.Packages.props` at
the repo root. Set `<ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>`
and add one `<PackageVersion>` per package. Individual `.csproj` files carry
`<PackageReference Include="..." />` with **no** `Version` attribute.

---

## The five required pillars

### 1. Clean Architecture

Domain knows nothing. Application knows only Domain. Infrastructure knows Domain and
Application. Functions knows Application and Infrastructure. Never add an Azure SDK
reference to Domain or Application.

Domain references no NuGet packages beyond the runtime. Application references only
`Microsoft.Extensions.Logging.Abstractions`. Infrastructure references Application, not
just Domain, because `AddInfrastructure()` is the single composition root. It registers
use cases alongside their dependencies.

All domain interfaces live in `Domain/Interfaces/`. Add one interface per external
system the app talks to, plus `INotificationService`. Report-style apps typically need
a loader/builder/uploader triple. Event-driven apps often need only a validator and a
writer. Derive the interfaces from step 2. Do not impose a fixed set.

### 2. Polly resilience pipeline

Every external call (SQL, Blob Storage, HTTP, Key Vault) goes through a shared sealed
`PollyResiliencePipeline`. Register it as a singleton and inject it into every
infrastructure class that makes external calls. Consume Polly via
`Microsoft.Extensions.Resilience`. Use `Microsoft.Extensions.Http.Resilience` for
`HttpClient`-specific pipelines.

Default: 3 retry attempts, exponential backoff (2s initial, 2x multiplier, jitter),
plus a count-based circuit breaker (100% failure ratio, min 5 requests, 30s sampling,
30s break). **Source of truth: ADR-001 §3.5.** If that table changes, update this
mirror in the same commit.

Retry count is the one value you can tune per app. Lower it when an attempt is
expensive or slow (browser automation, large report generation), so a failing run
surfaces quickly instead of multiplying cost. Record the reason at the call site.

**Filter the retry to transient faults. Do not retry on the base `Exception` type.**
Give the retry strategy a `ShouldHandle` predicate. Retry timeouts, connection resets,
throttling, and 429/503 errors. Let auth and permission failures (401/403, expired
credentials), missing objects, and malformed requests throw on the first attempt. A
second attempt cannot fix those. It only delays the failure and burns the backoff
budget. The exact exception types differ per SDK. Pick them at the call site and
comment why.

**[Orchestrated]** The Durable `RetryPolicy` stays at the activity level as a coarse
backstop. It does not replace Polly. Polly handles individual SDK call failures.
Durable handles activity-level crashes.

### 3. Unit tests

Every project ships `tests/Unit/` using xUnit and NSubstitute, mirroring the `src/`
layout. Cover at minimum, before merging:

- **Every use case** — happy path, primary dependency failure, secondary dependency
  failure, and non-blocking notification failure.
- **Notification card builders** — field presence per status the app emits, long error
  message truncation (500 chars), schema compliance.
- **Pure transformation logic** — parsing, pivots, date-range and schedule maths,
  signature validation. Use parameterized tests for boundary conditions.

The unit test project references Domain, Application, **and** Infrastructure. Card
builders, validators, and parsers are real infrastructure code, so test them directly.
Keep those members `internal` and expose them with `InternalsVisibleTo` on the
Infrastructure project. Do not widen them to public.

Always substitute Azure SDK clients and outbound HTTP. Tests must pass in CI with no
network access and no Azure credentials.

### 4. Telemetry

Application Insights needs **both** halves. `host.json` alone is not enough. In
`Program.cs`, add `AddApplicationInsightsTelemetryWorkerService()` and
`ConfigureFunctionsApplicationInsights()`. In `host.json`, enable sampling with
`"excludedTypes": "Request"`, and set `enableLiveMetricsFilters`. If you omit the
worker-service registration, you silently lose worker-emitted telemetry.

Use `ILogger<T>` exclusively. Do not use Serilog (it double-initializes under the
isolated worker) or a static logger. Follow these required patterns:

- At every trigger and activity entry point, call `LogInformation` with a summary of
  input and context. Wrap it in a `BeginScope()` that carries the invocation or
  orchestration instance ID, so all lines in that invocation correlate.
- For exceptions caught at use case level, call `LogError(ex, ...)` with structured
  properties (operation name, duration, entity IDs).
- Use `LogWarning` for non-fatal conditions: a retry attempt, a webhook non-200
  response, missing optional config, or a timer firing past due.
- Use named placeholders in message templates (`{InstanceId}`). Never use
  interpolation.
- Never let an exception propagate silently. If you catch it, log it.

### 5. Teams notifications

Applications must report run outcomes to a Teams channel via an Incoming Webhook,
using Adaptive Cards schema v1.5.

The contract is a single `INotificationService` in `Domain/Interfaces/`, implemented
in `Infrastructure/Notifications/`. Method and result-type names follow the
application's own domain language. There is no fixed signature.

**Which events notify:**

- **[Scheduled]** Notify on both success and failure. A silent scheduled job is
  indistinguishable from a broken one.
- **Event-driven / high-frequency triggers** — notify on failures only. A card per
  inbound event trains the channel to be ignored. Success is observed through the
  downstream artifact. Document the suppression at the implementation.

**Minimum card content:** status, the artifact identifier (output filename, blob path,
or event reference), duration, and, on failure, the error type, the error message
truncated to 500 characters, and a timestamp.

Bind the webhook URL through `IOptions<TeamsOptions>`. Never hardcode it. When the URL
is absent, log a `Warning` and return. **Delivery is always non-blocking.** The service
catches every exception, logs a `Warning`, and returns. A Teams outage must never fail
a run.

---

## Options pattern and configuration

Never use `Environment.GetEnvironmentVariable()` anywhere in the application, not even
in `Program.cs`. Bind all config via the Options pattern, registered in
`AddInfrastructure()`. Make each Options class `sealed`. Place it in
`Infrastructure/Options/`. Expose `public const string SectionName`. Give every
property a safe default.

Create one Options class per external system the app actually talks to, plus
`TeamsOptions`. Do not scaffold options for systems the app does not use.

**Secrets** live in Azure Key Vault and reach the app as Key Vault *references* in app
settings (`@Microsoft.KeyVault(...)`), resolved by the Function's system-assigned
managed identity. That identity needs the **Key Vault Secrets User** role. This is the
default. It keeps `Azure.Security.KeyVault.Secrets` out of the dependency graph.
Instantiate `SecretClient` directly only when a secret must be fetched or rotated at
runtime.

**Identity:** reach Azure resources with `DefaultAzureCredential` against a resource
URI. Use a connection string only as a fallback for local Azurite development:

```csharp
var client = !string.IsNullOrWhiteSpace(opts.ConnectionString)
    ? new BlobServiceClient(opts.ConnectionString)
    : new BlobServiceClient(new Uri(opts.AccountUri), new DefaultAzureCredential());
```

In `local.settings.json.template`, set `FUNCTIONS_WORKER_RUNTIME` to `"dotnet-isolated"`.
Do not use `"python"` or `"dotnet"`. Include every key the app reads. Blank all
secrets.

---

## DI registration pattern

Put all registration in one method,
`ServiceCollectionExtensions.AddInfrastructure(this IServiceCollection, IConfiguration)`.
Register options first, then infrastructure services, then use cases. Add section
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

Place process-wide setup that must run before the host exists (for example,
registering `CodePagesEncodingProvider` for Shift-JIS input) above the builder, with a
comment explaining why.

**Lifetimes:** use singleton for all infrastructure classes (loaders, builders,
uploaders, notification service, resilience pipeline). Use transient for use cases.
`HttpClient` always comes from a named `IHttpClientFactory` client
(`services.AddHttpClient("Teams")`). Never construct it directly. Where the app chooses
an implementation at runtime, register each concrete type and resolve through a
factory delegate in the same method.

---

## Local development and CI/CD

- Git-ignore `local.settings.json`. Commit the `.template` file.
- Generate a `dev-start.sh` at the repo root that brings up the local stack in one
  command: reset and start Azurite, build, run `func start`, and tear down Azurite on
  exit.
- Start the Functions host from *within* the Functions project directory. The SDK
  resolves its working directory from the shell's cwd, not from `--project`.
- Generate an `azure-pipelines.yml` triggered on `main`. Include at minimum a Build &
  Test stage (pinned SDK, restore/build/test, integration tests excluded by trait) and
  a Deploy stage as a `deployment` job bound to an `environment`, so approval gating
  lives in Azure DevOps rather than YAML. Zip deploy and an ACR container image are
  both acceptable. Pick one per app and keep it consistent. Pass secrets to the
  pipeline through variable groups. Never put them inline.
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
  project, with placeholders filled from steps 1-2
- [`../../adr/ADR-001-azure-functions-shared-architecture.md`](../../adr/ADR-001-azure-functions-shared-architecture.md) —
  the formal decision record behind this skill. It governs every Azure Function project
  across the team, not just one repo, so it lives alongside the skill. Read it when you
  need the full context, options considered, or history behind a rule, not just what to
  do.
