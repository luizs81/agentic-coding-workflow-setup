# ADR-002 — Internal Web Application Shared Architecture Standard

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-01 |
| **Last revised** | 2026-08-01 |
| **Deciders** | Engineering team |
| **Scope** | All internal ASP.NET Core / Blazor web applications owned by the team |
| **Supersedes** | N/A (first formal ADR for web applications) |
| **Related** | ADR-001 (Azure Functions Shared Architecture) |

---

## Writing style

Write all prose in this document in ASD-STE100 (Simplified Technical English) style:
short sentences, one instruction per sentence, active voice, "must"/"must not"/"can"
instead of "should"/"may", consistent terminology. This includes code comments. Only
code syntax and literal commands are exempt.

## 1. Context

The team builds internal web applications for back-office operations. The
generation being replaced shares a failure pattern that is not primarily about code
quality. An operator's task spans several systems. Each app covers one of them. People
fill the gaps between the apps. Work moves between a web app, a BI report, a shared
spreadsheet, a public website, and a printer. No system holds the whole task, and no
system records an attempt that failed halfway.

Two failure modes follow from that. This standard exists to prevent them:

1. **Partial writes with no compensation.** An external system is written, the local
   audit record is never confirmed, and nothing can detect or reconcile the gap
   afterwards. The operator sees an error and does not know whether to retry.
2. **One app per request.** Each new operational need becomes another standalone
   application with its own sign-in, shell, deployment, and language handling. The
   marginal cost of the fifth tool is the same as the first, and the operator gains
   another bookmark rather than fewer.

This ADR fixes the target architecture for these applications. New applications must
start aligned with this standard. Existing applications can migrate against this
standard as a clear reference.

This document describes patterns, not products. It must not name individual
applications. A rule that depends on a specific repo existing has a short shelf life.

## 2. Decision

All internal web applications must follow the structure and patterns below. Deviations
are permitted where the application's shape demands them. Each deviation must carry
justification in a code comment at the point of deviation **and** be recorded in the
repository's `AGENTS.md`.

Rules marked **[Multi-module]** apply only to applications hosting more than one
operational module. Rules marked **[External-write]** apply only to applications that
write to a system of record outside their own database. Everything else applies
universally.

Where this standard and ADR-001 differ, the difference is deliberate, and this document
notes it. Where they agree, they agree on purpose. An engineer moving between a
Function app and a web app must not have to relearn configuration, logging, or
resilience.

## 3. Architecture Standard

### 3.1 Project structure and the module rule

Four source projects, plus one test project per layer:

```
src/
  <App>.Domain/          Entities, value objects, domain rules. No framework deps, no I/O.
  <App>.Application/     Ports (interfaces), one handler per use case, cross-cutting pipelines.
  <App>.Infrastructure/  Adapters implementing the ports. No business logic.
  <App>.Web/             Thin over Application use cases. No business logic in components.
tests/
  <App>.Domain.Tests/         <App>.Application.Tests/
  <App>.Infrastructure.Tests/ <App>.Web.Tests/
```

Dependency direction is `Web → Application → Domain` and
`Infrastructure → Application → Domain`. Infrastructure translates. It does not decide.

**Modules are folders and namespaces, not projects.** Inside each of the four projects,
code divides into:

```
<App>.<Layer>/
  Platform/            Sign-in, shell, language, config, notifications, shared persistence.
  Modules/<Name>/      One operational capability.
```

A type under `Modules.X` can reference `Platform` and its own module. It must
**never** reference a sibling module. Anything two modules both need belongs in
`Platform`.

This is the central decision of this ADR. It is a deliberate departure from ADR-001,
where each concern gets its own project. The reasoning: a new operational request must
become a module in an existing application rather than the next standalone app.
Project-per-module would mean four new `.csproj` files per capability. Folders make the
marginal cost of a module small enough that adding one is the path of least resistance.
That is the behaviour the standard aims to produce.

**[Multi-module]** The cost of folders over projects is that the compiler no longer
enforces the boundary. Architecture tests must buy the enforcement back (§3.8). A
module boundary that is only a naming convention erodes on the first deadline.

A single-module application is a conforming instance of this layout, not an exception.
It has a `Platform/` and one entry under `Modules/`. Starting there means the second
module costs a folder rather than a refactor.

### 3.2 Common build properties

Shared MSBuild properties live in a `Directory.Build.props` at the repo root so a new
project cannot quietly drift:

```xml
<Project>
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
```

Target the current LTS-or-later runtime uniformly. Never mix target frameworks within a
solution.

**Package versions are centrally managed** in a `Directory.Packages.props` with
`<ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>` and one
`<PackageVersion>` per package. `.csproj` files carry `<PackageReference>` with no
`Version` attribute. Without this, the same package drifts to different versions across
projects in one solution. The build resolves the version at build time by
nearest-wins, and produces runtime behaviour matching no single `.csproj`. UI and
identity packages drift fastest, because they appear in both the Web project and its
test project.

### 3.3 Application layer — ports and use cases

The Application layer defines **ports** — interfaces the outer layers implement — and
one handler per use case. It performs no I/O itself.

Validation is a cross-cutting pipeline that **aggregates** failures rather than
throwing on the first one. An operator filling a form needs every problem at once.
Returning them one per round trip is the difference between one correction pass and
six.

### 3.4 Configuration and secrets

Configuration binds through `IOptions<T>`. Do not write bespoke secret-loading code.
Never use `Environment.GetEnvironmentVariable()`.

- **Never put secrets in source control** — not even as `appsettings.json`
  placeholders with a "just for dev" justification. Use empty-string placeholders so
  the file doubles as a documented template of every key the application expects.
- **Use user-secrets in development and Key Vault in UAT and production**, bound
  through the standard configuration system. Production configuration comes from the
  platform's own config store (App Service settings, Key Vault references). This is
  one-time infra setup, not something the pipeline manages per run.
- **Fail fast at startup** on missing required configuration, with a message naming
  the missing key. Do not let it surface as a confusing exception deep inside first
  use. Do this from day one. Retrofitting it is the kind of task that gets deferred
  permanently.
- **If a predecessor application committed real credentials, rotate every one of
  them.** The credentials were compromised the moment they entered git history.
  Deleting them in a later commit does not undo that.

### 3.5 Authentication and admin access

- Use enterprise SSO (Entra ID / OIDC) with a **global fallback policy**: every route
  requires a signed-in user by default, and routes opt *out* individually. Opt-in
  authorization fails open — the route someone forgets to annotate becomes public.
- Two roles are usually enough: **General** (any signed-in user) and **Admin**.
- **Admin membership is a small allowlist of identities (email/UPN) in
  configuration** — not a directory group, not a group-claim lookup. Keep this
  deliberately low-ceremony: a handful of named admins does not justify provisioning
  and maintaining a directory group. Enforce it in one policy handler and gate it onto
  the pages that need it — seeing all records versus your own, admin CRUD screens,
  manually-triggered operational actions.
- Document the allowlist config key in the configuration spec, so each environment's
  admins are visibly declared rather than tribal knowledge.

### 3.6 [External-write] The attempt-record and failure-matrix pattern

Any flow that writes to a system of record outside the application's own database must
follow this pattern. It is the specific answer to failure mode 1 in §1.

1. **Name every attempt.** One operational table (`<Thing>Attempt`) records:
   idempotency key, normalized-payload hash, actor, external-system identifier when
   known, status enum, failure step and detail, retry state, timestamps.
2. **Write the attempt record before the first external write**, and update it as the
   flow progresses. If nothing else survives a crash, this row must.
3. **Draw the failure matrix as a table before writing code.** For each step —
   validation, external write, local audit write, duplicate submission — specify what
   the user sees, what state the external system is left in, what the audit record
   says, whether retry is safe, and whether it alerts. This table is the feature's
   contract. Put it in the spec.
4. **The idempotency key is a hash of the normalized request payload**, not a
   client-generated nonce. It is stateless, so retries and double-clicks converge on
   one result instead of creating duplicates.
5. **Multi-entity external writes are multi-phase, not one changeset**, unless the
   external system can atomically roll back a parent when a child fails. Verify that
   against the real API rather than assuming changeset semantics hold. Identify which
   phase-two failures are therefore *routine* rather than exceptional, and give them a
   first-class recovery path: a reconciliation job or screen, not a TODO.
6. **The audit source of truth is the operational table plus the telemetry platform.**
   Chat notifications are alerting only. They are never part of the record.

### 3.7 Resilience on outbound calls

Every call leaving the application — SQL, an external system of record, an analytics
warehouse, an internal API, a chat webhook — must go through a resilience pipeline
built with `Microsoft.Extensions.Resilience`, or `Microsoft.Extensions.Http.Resilience`
for `HttpClient`. Register it in Infrastructure and inject it into the adapters. No
adapter can implement its own retry loop.

Default configuration, consistent with ADR-001 §3.5:

| Setting | Retry | Circuit breaker |
|---|---|---|
| Strategy | Exponential backoff with jitter | Count-based |
| Threshold | 3 attempts | 100% failure ratio, min 5 requests |
| Timing | 2s initial delay, 2× multiplier | 30s sampling, 30s break |
| Events | Log `Warning` with attempt, delay, exception type | Log state changes: `Error` on open, `Information` on close/half-open |

Two rules are specific to an interactive application and do not carry over from
ADR-001, where nobody is waiting:

- **A user-facing request has a total time budget, and the retry policy must live
  inside it.** Three attempts with backoff on a call that already takes four seconds
  produces a twenty-second page load. The operator will abandon it and retry manually,
  turning one slow request into several concurrent ones. Set an overall timeout on the
  pipeline and prefer fewer attempts on the interactive path. Background and
  reconciliation work, where no one is blocked, keeps the full default.
- **Retries must not silently duplicate a write.** Retry is safe by default only for
  reads and for operations that are idempotent by construction. **[External-write]** A
  write to an external system of record can be retried only through the attempt
  record in §3.6, whose idempotency key is what makes a second attempt converge
  rather than duplicate. A bare retry policy wrapped around a non-idempotent write is
  a defect, not a resilience measure.

Distinguish a failure the operator can act on from one they cannot. Show the operator
a validation rejection from an external system as a message. Retry a timeout or a 503,
and if it exhausts, show an error that names the operation and tells the operator
whether the work was recorded — which is what §3.6's attempt row exists to answer.

Never retry chat notification delivery into the critical path. It is non-blocking by
§3.10 regardless of the pipeline's configuration.

### 3.7a EF Core `DbContext` lifetime and concurrency

`AddDbContext<T>` registers the context as **scoped**. In a Blazor Web App running
InteractiveServer, the scope is the **circuit**: one instance per connected user, not
per request. Every component and adapter on that circuit shares the same `DbContext`
instance for as long as the user stays on the page.

`DbContext` is not thread-safe. It does not allow overlapping operations on one
instance. Two UI events firing close together (a fast double-click, a timer tick
landing next to a user action, two components independently refreshing on
`OnInitializedAsync`) can each start a query on the shared context before the first
finishes. EF Core detects this and throws — typically `InvalidOperationException: A
second operation was started on this context instance before a previous operation
completed`. It sometimes surfaces instead as an `ObjectDisposedException` if the
first operation's context was disposed mid-flight. Either way, it is not a transient
fault, and retrying the operation without fixing the lifetime issue reproduces it.

- **Register `AddDbContextFactory<T>`, not `AddDbContext<T>`, for any context reachable
  from Blazor Server/InteractiveServer components.** Inject `IDbContextFactory<T>` into
  adapters and call `CreateDbContextAsync` per operation. Dispose it (`await using`)
  when the operation completes. This gives each call its own short-lived context
  instead of sharing one across the circuit's lifetime.
- This rule also applies to MVC/Web API contexts if a handler kicks off concurrent
  operations on the same injected context (for example `Task.WhenAll` over adapters
  that all take the scoped instance). The factory pattern is the general answer, not
  Blazor-specific, even though Blazor's per-circuit scope makes the failure far more
  likely to occur in practice.
- A UI-side race can compound this problem. A component that re-fires an async
  refresh on stale input (rapid form edits, a debounce racing a page transition) can
  call an adapter method concurrently with itself even with the factory fix in place.
  This produces wrong or flickering results rather than an exception. Guard
  re-entrant refreshes with a generation counter or a cancellation token per
  invocation, so a stale call's result is discarded rather than applied after a newer
  one.
- `AddDbContextFactory<T>` also registers `T` itself as a scoped service (EF Core
  6.0+), so existing code resolving the context directly via DI keeps working. The
  factory is additive, not a breaking change to callers outside the
  concurrency-prone path.

### 3.8 Testing

Each layer has its own test project. Coverage expectations:

- **Domain** — rules and value objects directly, including boundary and encoding cases.
- **Application** — each use case: happy path, each dependency-failure mode, and the
  aggregating behaviour of the validation pipeline.
- **Infrastructure** — adapter translation logic and persistence constraints. Assert
  database constraints against the real engine, not an in-memory provider, because an
  in-memory provider does not enforce them.
- **[External-write]** Every row of the failure matrix in §3.6 must have a
  corresponding test. A matrix without tests is only a diagram.
- **[Multi-module]** Architecture tests enforce what the compiler no longer can: no
  type references a sibling module, and namespaces match folders. Whenever the
  scanning logic changes, confirm such a test actually bites rather than passing
  vacuously — introduce a violation, watch it fail, then revert.

Give localization resource keys a **missing-key check** as a test or build step, so one
language cannot silently drift behind the other.

### 3.9 Localization

Decide bilingual-or-not up front. Retrofitting it means touching every user-facing
string. If the application is bilingual, **every** user-facing string must come from
resource files through the framework's localizer, including validation and error
messages originating in Domain rules. Initial culture comes from the request
(`Accept-Language`). A user can override it with an explicit switch, and the system
must persist the choice so it survives across requests.

### 3.10 Telemetry and notifications

Consistent with ADR-001 §3.7–3.8:

- **One logging abstraction** — `ILogger<T>`. Do not layer in a second logging library.
- Use-case handlers must open a `BeginScope()` carrying correlation and entity
  identifiers, so every line in an invocation is traceable together. Log
  `Information` at entry. Log `Error` with structured properties at the use-case
  boundary. Log `Warning` for non-fatal conditions. Use named placeholders in message
  templates, never string interpolation.
- Chat notifications go through an `INotificationService` port in Application, with
  the Infrastructure adapter posting to a pre-existing webhook or flow where the
  organization already has one. Reuse the proven payload shape rather than inventing
  a new one. The URL comes from configuration and must never be hardcoded.
- **Delivery is non-blocking.** A non-success response logs a `Warning` and returns.
  A notification call must never throw, and it is never treated as part of the record.
- Message content: status, identifier, duration, timestamp. On failure, also include
  the error type, a **truncated** message (enforce the cap in the domain entity, not
  ad hoc at each call site), and which specific sub-item failed.

### 3.11 Visual design system

- Use a small set of CSS custom properties as **design tokens** in one theme file
  (`--app-primary`, `--app-page-bg`, `--app-card-bg`, text scale, and semantic
  danger/warning/info triads for background, border, and text). Override the
  component library's own theme variables from those tokens. Never hand-style
  individual component instances.
- Use a standard shell: brand-colored sidebar, top bar with application name,
  right-aligned user avatar with initials fallback, and a dropdown carrying name,
  culture switch, and sign-out.
- Use reusable page primitives as a handful of small CSS classes rather than per-page
  bespoke styling: card container, eyebrow label for section headers, labeled-field
  wrapper, responsive grid helper, actions row, banner variants with icon and text,
  and a monospace class reserved for **copy-paste-critical identifiers** — support
  references, external order numbers — which must never be truncated or reformatted.
- State in the token file's header comment that it is purely presentational. Keep a
  visual redesign and a markup or behaviour change as separate concerns. Do not
  bundle them.

### 3.12 Local development tooling

- For any external integration behind SSO/MFA that is tedious to click through
  repeatedly, build a **thin read-only CLI probe** that calls the Application read
  ports directly, reusing the main application's DI wiring and user-secrets. Keep it
  read-only by construction: it must never reference the write ports, unless a
  specific write command is explicitly needed and labelled as hitting the real
  external system.
- Where no local instance of an external dependency exists, run the application's own
  database in a local container **matching the production engine**, not a different
  local engine. Dialect and constraint behaviour must be identical between dev and
  prod, which is the whole reason §3.8 asserts constraints against a real database.

### 3.13 CI/CD

Use a three-stage pipeline: **Build & Test** → **deploy to a UAT slot** → **swap UAT
into production**. Gate the swap with a manual-approval `environment` rather than
running it automatically. Swapping validates the exact bits that were tested, rather
than performing a second independent production deploy and hoping it matches.

While iterating on a feature branch pre-merge, prefer a manual pipeline run against
that branch over editing the pipeline's trigger configuration. This keeps the shared
trigger definition untouched and avoids leaving a stale branch name behind after
merge. Watch the promote-to-production approval gate when doing this. Do not approve
it for a pre-merge branch.

Secrets must reach the pipeline through variable groups, never inline.

### 3.14 Repository documentation

Every repo carries:

- `README.md` — what the application does and how to run it, linking to this ADR.
- `AGENTS.md` — solution layout, module list, configuration table, build and test
  commands, local-dev gotchas, and any deviation from this ADR with its reason.
- `docs/specs/` — one file per feature, the source of truth for behaviour, with an
  index. A feature's acceptance criteria must be checkable, ideally one-to-one with a
  test. Each spec carries an **append-only** decisions log: mark a resolved entry
  `RESOLVED (date, evidence)` and keep it; mark a reversed entry `SUPERSEDED (date,
  evidence)` with a pointer to its replacement. Never delete an entry. The reasoning
  behind a reversal is usually worth more than the reversal.

## 4. Options considered

**Option A — one application per operational request**

| Dimension | Assessment |
|---|---|
| Time to first release | Fastest; nothing shared to negotiate |
| Marginal cost of capability N | Unchanged from capability 1 — full sign-in, shell, deploy, i18n each time |
| Operator experience | Degrades with each addition: another bookmark, another login, another idiom |
| Cross-capability work | Not possible without integration work between apps |

This is the status quo being replaced. Operators bear its cost rather than engineering,
which is why it persisted. The decisive evidence was a single routine task that
spanned a web app, a BI report, a spreadsheet, a public website, and a word processor,
with a human as the integration layer.

**Option B — one application, capabilities as separate projects**

| Dimension | Assessment |
|---|---|
| Boundary enforcement | Strongest; the compiler rejects a cross-capability reference |
| Marginal cost of capability N | Four new `.csproj` files and their wiring |
| Risk | High enough friction that the next capability becomes a standalone app again |

Rejected on that last row. The enforcement is genuinely better, but a standard that
makes the desired behaviour expensive does not produce the desired behaviour.

**Option C — one application, capabilities as folders and namespaces, boundaries
enforced by architecture tests (chosen)**

| Dimension | Assessment |
|---|---|
| Boundary enforcement | Test-time rather than compile-time; requires the tests to exist and to bite |
| Marginal cost of capability N | A folder in each of four projects |
| Platform reuse | Sign-in, shell, language, deployment built once and inherited |

Pros: adding a capability is cheap enough to be the default choice, the platform is
built once, and one deployment serves one operator-facing application. Cons: the
boundary is only as real as the architecture tests, and a failing-open test is worse
than no test because it produces false confidence. Section 3.8's requirement to
verify the test actually fails on a real violation mitigates this risk.

## 5. Trade-off analysis

The trade-off is enforcement strength against the cost of adding a capability. It
resolves differently here than in ADR-001, because the failure modes differ. A
Function app is one job. Its risk is that its layers blur, and project separation is
cheap because there is no per-capability multiplier. A web platform's risk is that
the fifth capability becomes a sixth application, and project separation directly
feeds that risk.

Accepting test-time enforcement is therefore not a compromise on rigour but a
relocation of it. The boundary must be *tested* rather than *assumed*. This is a
higher standard than the convention it replaces and a lower one than the compiler.
That is the correct place to sit given what it buys.

The second trade-off is the failure-matrix pattern's overhead. An attempt table, a
payload hash, and a reconciliation path are substantial work for a flow that usually
succeeds. It is justified only where a partial write leaves an external system of
record inconsistent and a human unable to tell whether to retry. That is why §3.6 is
tagged rather than universal.

## 6. Consequences

| | |
|---|---|
| **Easier** | Adding an operational capability; reusing sign-in, shell, language, and deployment; onboarding, since every module has the same shape; answering "why does the code do X" from the specs' decision logs; diagnosing a half-completed write. |
| **Harder** | Initial platform setup, which front-loads sign-in, shell, tokens, and pipeline before the first capability ships. Boundary discipline now depends on tests that engineers must maintain and verify rather than on the compiler. |
| **Must revisit** | Whether a module needs to graduate to its own project or deployment if it grows a genuinely independent lifecycle, scaling need, or release cadence. The module rule assumes capabilities that ship and scale together. |

## 7. Action items

1. Link this ADR from each repo's README.
2. Add a PR template checklist item: *"Does this change follow ADR-002?"*
3. Introduce `Directory.Packages.props` in each existing repo and strip `Version`
   attributes from the `.csproj` files (§3.2). Reconcile drifted versions upward as
   part of the migration.
4. Confirm the architecture tests fail on a real violation before relying on them
   (§3.8). Repeat that check whenever their scanning logic changes.
5. Scaffold new applications from an existing conforming repo rather than from scratch.
6. Review this ADR annually, or whenever a new application cannot be built within this
   standard — the second case is the more informative signal.
