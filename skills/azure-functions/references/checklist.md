# Pre-flight checklist — new Azure Function project

Work through this before generating any files. Don't guess on an unclear item — ask.

Items tagged **[Orchestrated]** apply only to Durable Functions apps, **[Scheduled]**
only to timer-triggered apps.

## Purpose and shape
- [ ] Function's purpose is clear: what does it load, transform, or produce?
- [ ] Trigger type identified (timer, HTTP, queue, blob)
- [ ] Durable orchestrator vs. single trigger decided
- [ ] Every external system named — each data source and each output sink
- [ ] One Domain interface identified per external system, derived from the above
      rather than assumed from a template

## Structure
- [ ] Project names use a short PascalCase app prefix: `<AppName>.Domain` /
      `.Application` / `.Infrastructure` / `.Functions` — not a long org path
- [ ] No Azure SDK references in Domain or Application `.csproj`
- [ ] Infrastructure references Application, not just Domain
- [ ] Test project references Domain + Application + Infrastructure, with
      `InternalsVisibleTo` on Infrastructure
- [ ] `Directory.Packages.props` at repo root; no `Version` attributes in `.csproj`
- [ ] Uniform target framework across the solution; `TreatWarningsAsErrors` set

## The five pillars — all present, even as stubs
- [ ] Clean Architecture layering respected
- [ ] `PollyResiliencePipeline` registered singleton and injected into every
      infrastructure class making external calls
- [ ] Retry count either left at the default 3 or tuned with the reason at the call site
- [ ] Retry strategy has a `ShouldHandle` predicate scoped to transient faults — no
      retry on the base `Exception` type; auth/permission/malformed-request failures
      fail on the first attempt
- [ ] **[Orchestrated]** Durable `RetryPolicy` present at activity level as a backstop
- [ ] Unit test project scaffolded with the minimum coverage in pillar 3
- [ ] App Insights configured in **both** `host.json` and `Program.cs`
- [ ] `functionTimeout` set explicitly in `host.json`, matched to the hosting plan — not
      left to the plan default, especially where the work being ported has any history of
      timing out
- [ ] `ILogger<T>` used exclusively; entry points open a `BeginScope()`
- [ ] `INotificationService` implemented, non-blocking on failure
- [ ] Notification scope matches the trigger shape: **[Scheduled]** both success and
      failure; event-driven / high-frequency, failures only with the suppression
      documented at the implementation

## Configuration
- [ ] Every Options class `sealed`, in `Infrastructure/Options/`, with a
      `public const string SectionName` and safe defaults on all properties
- [ ] No `Environment.GetEnvironmentVariable()` anywhere, including `Program.cs`
- [ ] Secrets reach the app as Key Vault references in app settings, not via a
      `SecretClient` — unless runtime fetch/rotation is genuinely required
- [ ] `DefaultAzureCredential` against a resource URI; connection string only as the
      local Azurite fallback
- [ ] `FUNCTIONS_WORKER_RUNTIME` set to `"dotnet-isolated"` in
      `local.settings.json.template`, every key present, all secrets blank

## Repo scaffolding
- [ ] `dev-start.sh` at repo root
- [ ] `azure-pipelines.yml` with Build & Test plus an environment-bound deployment job
- [ ] `README.md` with a section linking to ADR-001
- [ ] `local.settings.json` git-ignored

## AGENTS.md
- [ ] `references/agents-md-template.md` copied into the new repo root as `AGENTS.md`
- [ ] Every placeholder filled with this project's actual specifics — app name, trigger
      shape, output sink, external dependencies, notification scope
- [ ] No leftover placeholder text — a half-filled `AGENTS.md` is worse than none,
      since a subagent will trust it as authoritative
