# ADR-001 — Azure Functions Shared Architecture Standard

| | |
|---|---|
| **Status** | Accepted |
| **Date** | April 2026 |
| **Last revised** | 2026-08-02 |
| **Deciders** | Engineering team |
| **Scope** | All Azure Function applications owned by the team |
| **Supersedes** | N/A (first formal ADR for Azure Functions) |

---

## Writing style

Write all prose in ASD-STE100 (Simplified Technical English) style: short sentences,
one instruction per sentence, active voice, "must"/"must not"/"can" instead of
"should"/"may", consistent terminology. This rule covers every kind of prose you
write — instructions, documents, responses, messages to other agents, and code
comments. Only code syntax and literal commands are exempt.

## 1. Context

The team builds and operates several Azure Function applications in C# on the
isolated worker model. Teams built these applications independently. The applications
diverged in structure, testability, and operational maturity. Some applications were
flat single-project scripts with logic bound directly to trigger entry points. Other
applications were fully layered.

Five non-functional requirements apply to every Azure Function application the team
owns: Clean Architecture, resilience, unit testing, telemetry, and operational
alerting. This ADR fixes the target architecture as a standard. New applications must
start aligned with this standard. Existing applications can migrate against this
standard as a clear reference.

This document describes patterns, not products. It must not name individual
applications. A rule that depends on a specific repo existing has a short shelf life.

## 2. Decision

All Azure Function applications must follow the structure and patterns below.
Deviations are permitted where the application's shape demands them. Each deviation
must carry justification in a code comment at the point of deviation.

Rules marked **[Orchestrated]** apply only to applications that use Durable
Functions. Rules marked **[Scheduled]** apply only to timer-triggered applications.
Everything else applies universally, including to plain HTTP-triggered functions.

## 3. Architecture Standard

### 3.1 Project structure

Every solution has four source projects plus tests. The projects reflect Clean
Architecture layers:

```
src/
  <App>.Domain/          Entities, enums, interfaces. Zero NuGet dependencies.
  <App>.Application/     Use cases. References Domain only.
  <App>.Infrastructure/  Azure SDK, HTTP clients, notifications, resilience, DI wiring.
  <App>.Functions/       Trigger entry points and Program.cs only.
tests/
  Unit/                  xUnit + NSubstitute. Mirrors src/ layout.
  Integration/           Optional. [Trait("Category","Integration")], skipped by default.
```

The dependency rule is enforced by project references:

| Project | References |
|---|---|
| Domain | nothing |
| Application | Domain, `Microsoft.Extensions.Logging.Abstractions` |
| Infrastructure | Domain, Application, Azure SDKs, Polly, third-party packages |
| Functions | Application, Infrastructure, Functions worker SDK |

Infrastructure references Application, not only Domain, because `AddInfrastructure()`
is the single composition root. It registers use cases alongside their dependencies.
This design is intentional: it keeps the Functions project free of registration logic.

Naming inside each project follows role-based folders: `UseCases/`, `Options/`,
`Notifications/`, `Resilience/`, `Extensions/`, `Triggers/`, and (**[Orchestrated]**)
`Orchestrators/` and `Activities/`.

**Naming convention.** Projects, assemblies, and root namespaces use a short
PascalCase application name as the prefix, for example `PaymentGateway.Domain` and
`PaymentGateway.Tests.Unit`. Do not use a fully-qualified organizational path. Long
prefixes push project paths past the point of readability. They also make
test-project names unwieldy without adding information the repo name doesn't
already carry.

### 3.2 Common build properties

Every `.csproj` in the solution sets:

```xml
<TargetFramework>net10.0</TargetFramework>
<Nullable>enable</Nullable>
<ImplicitUsings>enable</ImplicitUsings>
<TreatWarningsAsErrors>true</TreatWarningsAsErrors>
<LangVersion>latest</LangVersion>
<RootNamespace><!-- matches the project name --></RootNamespace>
```

`TreatWarningsAsErrors` is non-negotiable. Nullable-reference warnings are the main
defence against the null-deref failures these applications are prone to.

Target the current LTS-or-later runtime uniformly across all projects in a solution.
Never mix target frameworks within one solution.

**Package versions are centrally managed.** Each repo has a `Directory.Packages.props`
at the root with `<ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>`
and one `<PackageVersion>` entry per package; individual `.csproj` files carry
`<PackageReference Include="..." />` with no `Version` attribute:

```xml
<!-- Directory.Packages.props -->
<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
  </PropertyGroup>
  <ItemGroup>
    <PackageVersion Include="Azure.Storage.Blobs" Version="12.27.0" />
    <PackageVersion Include="Microsoft.Extensions.Options" Version="10.0.5" />
  </ItemGroup>
</Project>
```

Without this, the same package drifts to different versions across projects in a
single solution. The build resolves the version by nearest-wins. This produces
runtime behaviour that does not match what any one `.csproj` declares.

### 3.3 Composition root

A single `ServiceCollectionExtensions.AddInfrastructure(this IServiceCollection, IConfiguration)`
in the Infrastructure project registers all options, infrastructure services, and use
cases, in that order, with section comments. `Program.cs` contains only host
construction:

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

Place process-wide setup that must run before the host exists (for example
registering `CodePagesEncodingProvider` for Shift-JIS input) above the builder, with
a comment that explains why.

**Lifetimes:** register infrastructure services as `AddSingleton`. They are
stateless and hold expensive clients. Register use cases as `AddTransient` so each
invocation gets a fresh instance. Always obtain `HttpClient` from a named
`IHttpClientFactory` client (`services.AddHttpClient("Teams")`). Never construct it
directly.

Where an implementation is selected at runtime, register each concrete type and
resolve it through a factory delegate registered in the same method.

### 3.4 Configuration and secrets

All configuration is bound via the Options pattern. Each Options class is `sealed`,
lives in `Infrastructure/Options/`, exposes `public const string SectionName`, and
gives every property a safe default:

```csharp
public sealed class BlobLandingOptions
{
    public const string SectionName = "BlobLanding";
    public string? ConnectionString { get; set; }   // local only
    public string AccountUri { get; set; } = "";    // managed identity
    public string ContainerName { get; set; } = "";
}
```

Read configuration via `IConfiguration` inside `AddInfrastructure()`, or via
`IOptions<T>` at the consumer. Never use `Environment.GetEnvironmentVariable()`
anywhere in the application.

**Secrets** are stored in Azure Key Vault. The app surfaces them as Key Vault
references in app settings (`@Microsoft.KeyVault(...)`). The Function's
system-assigned managed identity resolves these references, and this identity
requires the **Key Vault Secrets User** role on the vault. This is the default
approach: it keeps `Azure.Security.KeyVault.Secrets` out of the dependency graph
entirely. Instantiate `SecretClient` directly only when a secret must be fetched or
rotated at runtime rather than at startup.

**Identity:** reach Azure resources with `DefaultAzureCredential` against a resource
URI. Accept a connection string only as a fallback for local development against
Azurite:

```csharp
var client = !string.IsNullOrWhiteSpace(opts.ConnectionString)
    ? new BlobServiceClient(opts.ConnectionString)
    : new BlobServiceClient(new Uri(opts.AccountUri), new DefaultAzureCredential());
```

### 3.5 Resilience

Wrap calls to external systems (SQL, Blob Storage, HTTP, Key Vault) in a shared
`PollyResiliencePipeline`. This is a sealed Infrastructure class registered as a
singleton, and it exposes `ExecuteAsync` overloads with and without a return value.
Consume Polly through `Microsoft.Extensions.Resilience`. Use
`Microsoft.Extensions.Http.Resilience` for `HttpClient`-specific pipelines.

Default configuration. **This table is the single source of truth for these numbers.**
`skills/azure-functions/SKILL.md` and `skills/dotnet-web/SKILL.md` both mirror this
table so scaffolding does not need an extra file read. If you change a value here,
update both mirrors in the same commit — an unchanged mirror silently reintroduces the
old default the next time either skill scaffolds a project.

| Setting | Retry | Circuit breaker |
|---|---|---|
| Strategy | Exponential backoff with jitter | Count-based |
| Threshold | 3 attempts | 100% failure ratio, min 5 requests |
| Timing | 2s initial delay, 2× multiplier | 30s sampling, 30s break |
| Events | Log `Warning` with attempt, delay, exception type | Log state changes: `Error` on open, `Information` on close/half-open |

Retry count is the one value that applications can tune. Lower it when an attempt is
expensive or slow (browser automation, large report generation), so a failing run
surfaces quickly instead of multiplying cost. Record the reason at the call site.

**Retry only faults that a second attempt can plausibly fix.** The retry strategy
must carry a `ShouldHandle` predicate. By default, Polly applies an unfiltered retry
to any exception. This treats "the network blipped" and "the credentials are wrong"
identically, and spends the full backoff budget on a failure that a later attempt
cannot fix any better than the first. Split failures into two classes:

- **Transient — retry.** The call failed for a reason that plausibly resolves on its
  own: timeouts, connection resets, throttling, a 429/503, a momentary DNS failure.
- **Non-transient — fail fast.** The call failed for a reason a retry cannot fix,
  because it needs a human: expired or invalid credentials, permission/authorization
  errors (401/403), a missing object, a malformed request, a schema mismatch. Let
  these throw on the first attempt.

The specific exception types or error codes in each bucket differ per SDK. Snowflake,
SQL Server, Blob Storage, and an HTTP client each surface auth/permission failures
differently. Pick them at the call site and record the mapping in a code comment. Do
not retry on the base `Exception` type. When a new failure mode shows up in
production that is not yet classified, treat it as transient until proven otherwise
(the safe default), but add it to the predicate rather than leaving the gap for next
time.

**The retried delegate must be side-effect-free.** Polly re-invokes the delegate
passed to `ExecuteAsync` from the beginning, but it cannot undo what a failed attempt
already did. Anything the delegate mutates outside its own scope — a caller-owned
collection, a cache, a counter, a field — carries the partial results of every failed
attempt into the successful one. A reader that throws partway through a result set is
the ordinary case, not an exotic one.

Build results into a local variable. Hand them back through the return value, and
let the caller merge after `ExecuteAsync` returns:

```csharp
// Wrong: rows read before the failure survive the retry.
await _pipeline.ExecuteAsync(async ct => {
    await using var reader = await cmd.ExecuteReaderAsync(ct);
    while (await reader.ReadAsync(ct)) sharedSet.Add(reader.GetString(0));
});

// Right: the delegate owns its state; the caller merges once, on success.
var rows = await _pipeline.ExecuteAsync(async ct => {
    var local = new List<string>();
    await using var reader = await cmd.ExecuteReaderAsync(ct);
    while (await reader.ReadAsync(ct)) local.Add(reader.GetString(0));
    return local;
});
foreach (var row in rows) sharedSet.Add(row);
```

Severity depends on the accumulator. A set is the *forgiving* case: re-adding a
duplicate key to a `HashSet` or `Dictionary` is idempotent, so the corruption stays
latent. An additive accumulator — a summing `Dictionary<string, int>`, a `List`, a
running total, `+=` on any field — silently double-counts instead, and produces a
plausible wrong number rather than an error. Treat the pattern as a defect wherever
it appears, not only where it currently happens to be survivable.

**[Orchestrated]** The Durable `RetryPolicy` stays at the activity level as a coarse
backstop. It does not replace Polly. Polly absorbs transient SDK-level errors, so a
single timeout does not trigger a full Durable backoff. The Durable retry covers
activity-level crashes.

### 3.6 Unit testing

Cover business logic with unit tests before merging to main. Minimum coverage:

- **Every use case** — happy path, primary dependency failure (loader/validator throws),
  and secondary dependency failure (uploader/writer throws).
- **Notification card builders** — field presence for each status the app emits,
  plus edge cases such as long error messages being truncated.
- **Pure transformation logic** — CSV parsing, pivots, schedule and date-range
  calculations, signature validation: parameterized tests for boundary conditions.

The unit test project references Domain, Application, **and** Infrastructure,
because notification builders, validators, and parsers are real infrastructure code
worth asserting on directly. Members tested this way stay `internal`, exposed via
`InternalsVisibleTo` on the Infrastructure project rather than widened to public.

Always substitute Azure SDK clients and outbound HTTP with NSubstitute. Tests must
pass in CI with no network access and no Azure credentials.

### 3.7 Telemetry

Application Insights requires **both** halves — `host.json` alone is not enough:

```json
"logging": {
  "applicationInsights": {
    "samplingSettings": { "isEnabled": true, "excludedTypes": "Request" },
    "enableLiveMetricsFilters": true
  }
}
```

plus `AddApplicationInsightsTelemetryWorkerService()` and
`ConfigureFunctionsApplicationInsights()` in `Program.cs` (§3.3). Omitting the
worker-service registration silently loses worker-emitted telemetry.

`ILogger<T>` is the only logging abstraction. Serilog and other frameworks are not
permitted, because they double-initialize under the isolated worker. Structured
logging rules:

- Every trigger and activity entry point logs at `Information` with a summary of its
  input and context (invocation ID, instance ID, blob name).
- Entry points open a `BeginScope()` carrying the invocation or orchestration
  instance ID and relevant entity IDs, so every message in that invocation is correlated.
- Exceptions are caught at the use case level and logged with `LogError(ex, ...)`
  including structured properties (operation name, duration, entity IDs).
- `Warning` covers non-fatal conditions: a retry attempt, a webhook returning
  non-200, optional configuration missing, a timer firing past due.
- Message templates use named placeholders (`{InstanceId}`), never string interpolation.

### 3.8 Operational notifications

Applications must report run outcomes to a Microsoft Teams channel through an
Incoming Webhook using Adaptive Cards (schema v1.5).

The contract is a single `INotificationService` declared in `Domain/Interfaces/` and
implemented in `Infrastructure/Notifications/`. Callers in the Application layer see
only the interface. Method and result-type names must follow the application's own
domain language rather than a fixed signature.

**Which events notify:**

- **[Scheduled]** Notify on both success and failure. A silent scheduled job is
  indistinguishable from a broken one.
- **Event-driven / high-frequency triggers** — notify on failure only. A card per
  inbound event is noise that trains the channel to be ignored. Operators can observe
  success through the downstream artifact instead. Document the suppression at the
  implementation.

**Minimum card content:** status, the artifact identifier (output filename, blob
path, or event reference), duration, and on failure the error type, the error
message truncated to 500 characters, and a local-timezone timestamp.

Bind the webhook URL through `IOptions<TeamsOptions>` from app settings. Never
hardcode it. When it is absent, log a `Warning` and return.

**Delivery is always non-blocking.** The service must catch every exception, log a
`Warning`, and return. A Teams outage must never fail a run or block a pipeline.

### 3.9 Local development

- Git-ignore `local.settings.json`. Commit a `local.settings.json.template` with all
  keys present and secrets blanked.
- Provide a `dev-start.sh` at the repo root that brings up the full local stack in
  one command: reset and start Azurite, build, then `func start`, tearing down
  Azurite on exit.
- Start the Functions host from within the Functions project directory. The SDK
  resolves its working directory from the shell's cwd, not from `--project`.
- Use connection strings against Azurite for local Azure access (§3.4). Never use
  real production credentials.

### 3.10 CI/CD

Each repo has an `azure-pipelines.yml` triggered on `main` with at minimum:

1. **Build & Test** — pinned SDK version, `restore`, `build`, then `test` against
   the unit test project. Integration tests stay excluded by trait.
2. **Deploy to Production** — a `deployment` job bound to an `environment`, so
   approval gating is configured in Azure DevOps rather than in YAML.

Either zip deploy of the published Functions project or a container image pushed to
ACR is acceptable. Choose per application and keep the choice consistent within a
repo. Secrets must reach the pipeline through variable groups, never inline.

### 3.11 Repository documentation

Every repo carries a `README.md` (what the app does, how to run it) with a section
linking to this ADR, and an `AGENTS.md` (solution layout, configuration table,
build/test commands, known local-dev gotchas).

## 4. Options considered

**Option A — flat single-project structure.** Minimal setup and fast iteration. But
it is untestable without interfaces, allows no reuse, and violates
single-responsibility at the file level.

**Option B — Clean Architecture with separate projects (chosen).** Full testability,
enforced dependency boundaries, and consistency across the estate. It costs more
setup and more files for simple functions, mitigated by scaffolding from an existing
conforming repo.

## 5. Trade-off analysis

The trade-off is initial velocity against long-term maintainability. For a
genuinely throwaway script, Option A is defensible. For recurring, business-critical
functions — report feeds people make decisions from, payment events that cannot be
replayed — the operational risk of untestable code with silent failure modes
outweighs the setup cost by a wide margin. The applications are similar enough in
shape that a shared standard is both feasible and valuable. It has held across
orchestrated, scheduled, and plain HTTP-triggered applications.

## 6. Consequences

**Easier:** unit testing, onboarding, adding new output targets, debugging via
correlated structured logs and Teams alerts, and moving engineers between
applications.

**Harder:** initial setup for a new function, mitigated by scaffolding from any
conforming repo.

**Must revisit:** whether four separate assemblies remain right versus
vertical-slice-per-feature, if applications grow well beyond a handful of use cases.
At current scale, layered is appropriate.

## 7. Action items

Link this ADR from each repo's README. Add a PR template checklist item ("Does this
change follow ADR-001?"). Introduce `Directory.Packages.props` in each existing repo
and strip `Version` attributes from `.csproj` files (§3.2). Scaffold new
applications from an existing conforming repo rather than from scratch. Review this
ADR annually, or whenever a new application cannot be built within this standard,
whichever comes first.
