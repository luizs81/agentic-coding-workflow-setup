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

## 1. Context

The team builds and operates several Azure Function applications in C# on the
isolated worker model. Built independently, they diverged in structure, testability,
and operational maturity — some were flat single-project scripts with logic bound
directly to trigger entry points, others were fully layered.

Five non-functional requirements apply to every Azure Function application we own:
Clean Architecture, resilience, unit testing, telemetry, and operational alerting.
This ADR fixes the target architecture as a standard so new applications start
aligned and existing ones can be migrated against a clear reference.

This document describes patterns, not products. It must not name individual
applications — a rule that depends on a specific repo existing has a shelf life.

## 2. Decision

All Azure Function applications must follow the structure and patterns below.
Deviations are permitted where the application's shape demands it, but must be
justified in a code comment at the point of deviation.

Rules marked **[Orchestrated]** apply only to applications that use Durable
Functions. Rules marked **[Scheduled]** apply only to timer-triggered applications.
Everything else applies universally, including to plain HTTP-triggered functions.

## 3. Architecture Standard

### 3.1 Project structure

Four source projects plus tests, reflecting Clean Architecture layers:

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

Infrastructure references Application (not only Domain) because `AddInfrastructure()`
is the single composition root and registers use cases alongside their dependencies.
This is intentional: the Functions project stays free of registration logic.

Naming inside each project follows role-based folders — `UseCases/`, `Options/`,
`Notifications/`, `Resilience/`, `Extensions/`, `Triggers/`, and (**[Orchestrated]**)
`Orchestrators/` and `Activities/`.

**Naming convention.** Projects, assemblies, and root namespaces use a short
PascalCase application name as the prefix — `PaymentGateway.Domain`,
`PaymentGateway.Tests.Unit` — not a fully-qualified organizational path. Long
prefixes push project paths past the point of readability and make test-project
names unwieldy without adding information the repo name doesn't already carry.

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

`TreatWarningsAsErrors` is non-negotiable — nullable-reference warnings are the
main defence against the null-deref failures these applications are prone to.

Target the current LTS-or-later runtime uniformly across all projects in a solution;
never mix target frameworks within one solution.

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
single solution — which resolves at build time by nearest-wins and produces
runtime behaviour that does not match what any one `.csproj` declares.

### 3.3 Composition root

A single `ServiceCollectionExtensions.AddInfrastructure(this IServiceCollection, IConfiguration)`
in the Infrastructure project registers all options, infrastructure services, and use cases,
in that order, with section comments. `Program.cs` contains only host construction:

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

Process-wide setup that must run before the host exists (for example registering
`CodePagesEncodingProvider` for Shift-JIS input) goes above the builder with a
comment explaining why.

**Lifetimes:** infrastructure services are `AddSingleton` — they are stateless and
hold expensive clients. Use cases are `AddTransient` so each invocation gets a fresh
instance. `HttpClient` is always obtained from a named `IHttpClientFactory` client
(`services.AddHttpClient("Teams")`), never constructed directly.

Where an implementation is selected at runtime, register each concrete type and
resolve through a factory delegate registered in the same method.

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

Configuration is read via `IConfiguration` inside `AddInfrastructure()` or via
`IOptions<T>` at the consumer. `Environment.GetEnvironmentVariable()` is not used
anywhere in the application.

**Secrets** are stored in Azure Key Vault and surfaced to the app as Key Vault
references in app settings (`@Microsoft.KeyVault(...)`), resolved by the Function's
system-assigned managed identity, which requires the **Key Vault Secrets User** role
on the vault. This is the default: it keeps `Azure.Security.KeyVault.Secrets` out of
the dependency graph entirely. Instantiate `SecretClient` directly only when a secret
must be fetched or rotated at runtime rather than at startup.

**Identity:** Azure resources are reached with `DefaultAzureCredential` against a
resource URI. A connection string is accepted only as a fallback for local
development against Azurite:

```csharp
var client = !string.IsNullOrWhiteSpace(opts.ConnectionString)
    ? new BlobServiceClient(opts.ConnectionString)
    : new BlobServiceClient(new Uri(opts.AccountUri), new DefaultAzureCredential());
```

### 3.5 Resilience

Calls to external systems (SQL, Blob Storage, HTTP, Key Vault) are wrapped in a
shared `PollyResiliencePipeline` — a sealed Infrastructure class registered as a
singleton, exposing `ExecuteAsync` overloads with and without a return value.
Polly is consumed through `Microsoft.Extensions.Resilience`; use
`Microsoft.Extensions.Http.Resilience` for `HttpClient`-specific pipelines.

Default configuration:

| Setting | Retry | Circuit breaker |
|---|---|---|
| Strategy | Exponential backoff with jitter | Count-based |
| Threshold | 3 attempts | 100% failure ratio, min 5 requests |
| Timing | 2s initial delay, 2× multiplier | 30s sampling, 30s break |
| Events | Log `Warning` with attempt, delay, exception type | Log state changes: `Error` on open, `Information` on close/half-open |

Retry count is the one value expected to be tuned per application. Lower it when an
attempt is expensive or slow (browser automation, large report generation) so a
failing run surfaces quickly instead of multiplying cost. Record the reason at the
call site.

**Retry only faults that a second attempt can plausibly fix.** The retry strategy must
carry a `ShouldHandle` predicate — an unfiltered retry, which Polly applies to any
exception by default, treats "the network blipped" and "the credentials are wrong"
identically, spending the full backoff budget on a failure a later attempt cannot fix
any better than the first. Split failures into two classes:

- **Transient — retry.** The call failed for a reason that plausibly resolves on its
  own: timeouts, connection resets, throttling, a 429/503, a momentary DNS failure.
- **Non-transient — fail fast.** The call failed for a reason a retry cannot fix
  because it needs a human: expired or invalid credentials, permission/authorization
  errors (401/403), a missing object, a malformed request, a schema mismatch. Let these
  throw on the first attempt.

The specific exception types or error codes in each bucket differ per SDK (Snowflake,
SQL Server, Blob Storage, and an HTTP client each surface auth/permission failures
differently) — pick them at the call site and record the mapping in a code comment,
rather than retrying on the base `Exception` type. When a new failure mode shows up in
production that isn't yet classified, treat it as transient until proven otherwise (the
safe default), but add it to the predicate rather than leaving the gap for next time.

**The retried delegate must be side-effect-free.** Polly re-invokes the delegate passed
to `ExecuteAsync` from the beginning, but it cannot undo what a failed attempt already
did. Anything the delegate mutates outside its own scope — a caller-owned collection, a
cache, a counter, a field — carries the partial results of every failed attempt into the
successful one. A reader that throws partway through a result set is the ordinary case,
not an exotic one.

Build results into a local, then hand them back through the return value and let the
caller merge after `ExecuteAsync` returns:

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

Severity depends on the accumulator, and a set is the *forgiving* case: re-adding a
duplicate key to a `HashSet` or `Dictionary` is idempotent, so the corruption stays
latent. An additive accumulator — a summing `Dictionary<string, int>`, a `List`, a
running total, `+=` on any field — silently double-counts instead, producing a plausible
wrong number rather than an error. Treat the pattern as a defect wherever it appears, not
only where it currently happens to be survivable.

**[Orchestrated]** The Durable `RetryPolicy` stays at the activity level as a coarse
backstop; it does not replace Polly. Polly absorbs transient SDK-level errors so a
single timeout doesn't trigger a full Durable backoff; the Durable retry covers
activity-level crashes.

### 3.6 Unit testing

Business logic is covered by unit tests before merging to main. Minimum coverage:

- **Every use case** — happy path, primary dependency failure (loader/validator throws),
  and secondary dependency failure (uploader/writer throws).
- **Notification card builders** — field presence for each status the app emits,
  plus edge cases such as long error messages being truncated.
- **Pure transformation logic** — CSV parsing, pivots, schedule and date-range
  calculations, signature validation: parameterized tests for boundary conditions.

The unit test project references Domain, Application, **and** Infrastructure, because
notification builders, validators, and parsers are real infrastructure code worth
asserting on directly. Members tested this way stay `internal`, exposed via
`InternalsVisibleTo` on the Infrastructure project rather than being widened to public.

Azure SDK clients and outbound HTTP are always substituted with NSubstitute. Tests
must pass in CI with no network access and no Azure credentials.

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
permitted — they double-initialize under the isolated worker. Structured logging rules:

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

Applications report run outcomes to a Microsoft Teams channel through an Incoming
Webhook using Adaptive Cards (schema v1.5).

The contract is a single `INotificationService` declared in `Domain/Interfaces/` and
implemented in `Infrastructure/Notifications/`. Callers in the Application layer see
only the interface. Method and result-type names follow the application's own domain
language rather than a fixed signature.

**Which events notify:**

- **[Scheduled]** Both success and failure. A silent scheduled job is
  indistinguishable from a broken one.
- **Event-driven / high-frequency triggers** — failures only. A card per inbound
  event is noise that trains the channel to be ignored; success is observed through
  the downstream artifact instead. Document the suppression at the implementation.

**Minimum card content:** status, the artifact identifier (output filename, blob
path, or event reference), duration, and on failure the error type, the error
message truncated to 500 characters, and a local-timezone timestamp.

The webhook URL is bound through `IOptions<TeamsOptions>` from app settings and is
never hardcoded. When it is absent, log a `Warning` and return.

**Delivery is always non-blocking.** The service catches every exception, logs a
`Warning`, and returns. A Teams outage must never fail a run or block a pipeline.

### 3.9 Local development

- `local.settings.json` is git-ignored; a `local.settings.json.template` with all
  keys present and secrets blanked is committed.
- A `dev-start.sh` at the repo root brings up the full local stack in one command:
  reset and start Azurite, build, then `func start`, tearing down Azurite on exit.
- The Functions host must be started from within the Functions project directory —
  the SDK resolves its working directory from the shell's cwd, not from `--project`.
- Local Azure access uses connection strings against Azurite (§3.4); never real
  production credentials.

### 3.10 CI/CD

Each repo has an `azure-pipelines.yml` triggered on `main` with at minimum:

1. **Build & Test** — pinned SDK version, `restore`, `build`, then `test` against
   the unit test project. Integration tests stay excluded by trait.
2. **Deploy to Production** — a `deployment` job bound to an `environment`, so
   approval gating is configured in Azure DevOps rather than in YAML.

Either zip deploy of the published Functions project or a container image pushed to
ACR is acceptable; choose per application and keep the choice consistent within a repo.
Secrets reach the pipeline through variable groups, never inline.

### 3.11 Repository documentation

Every repo carries a `README.md` (what the app does, how to run it) with section linking to this ADR and a `AGENTS.md`
(solution layout, configuration table, build/test commands, known local-dev
gotchas).

## 4. Options considered

**Option A — flat single-project structure.** Minimal setup, fast iteration; but
untestable without interfaces, no reuse, single-responsibility violated at the file
level.

**Option B — Clean Architecture with separate projects (chosen).** Full testability,
enforced dependency boundaries, consistency across the estate; costs more setup and
more files for simple functions — mitigated by scaffolding from an existing
conforming repo.

## 5. Trade-off analysis

Initial velocity against long-term maintainability. For a genuinely throwaway
script, Option A is defensible. For recurring, business-critical functions — report
feeds people make decisions from, payment events that cannot be replayed — the
operational risk of untestable code with silent failure modes outweighs the setup
cost by a wide margin. The applications are similar enough in shape that a shared
standard is both feasible and valuable, and it has held across orchestrated,
scheduled, and plain HTTP-triggered applications.

## 6. Consequences

Easier: unit testing, onboarding, adding new output targets, debugging via
correlated structured logs and Teams alerts, moving engineers between applications.
Harder: initial setup for a new function, mitigated by scaffolding from any
conforming repo. Must revisit: whether four separate assemblies remain right versus
vertical-slice-per-feature, if applications grow well beyond a handful of use cases —
at current scale, layered is appropriate.

## 7. Action items

Link this ADR from each repo's README; add a PR template checklist item ("Does this
change follow ADR-001?"); introduce `Directory.Packages.props` in each existing repo
and strip `Version` attributes from `.csproj` files (§3.2); scaffold new applications
from an existing conforming repo rather than from scratch; review annually or
whenever a new application cannot be built within this standard, whichever comes
first.
