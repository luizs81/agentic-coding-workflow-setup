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

## 1. Context

The team builds internal web applications for back-office operations. The
generation being replaced shares a failure pattern that is not primarily about code
quality: an operator's task spans several systems, each app covers one of them, and the
gaps between them are filled by people. Work moves between a web app, a BI report, a
shared spreadsheet, a public website, and a printer, with no system holding the whole
task and no record of an attempt that failed halfway.

Two failure modes follow from that, and they are the ones this standard exists to
prevent:

1. **Partial writes with no compensation.** An external system is written, the local
   audit record is never confirmed, and nothing can detect or reconcile the gap
   afterwards. The operator sees an error and does not know whether to retry.
2. **One app per request.** Each new operational need becomes another standalone
   application with its own sign-in, shell, deployment, and language handling — so the
   marginal cost of the fifth tool is the same as the first, and the operator gains
   another bookmark rather than fewer.

This ADR fixes the target architecture for these applications so new ones start aligned
and existing ones can be migrated against a clear reference.

This document describes patterns, not products. It must not name individual
applications — a rule that depends on a specific repo existing has a shelf life.

## 2. Decision

All internal web applications must follow the structure and patterns below. Deviations
are permitted where the application's shape demands it, but must be justified in a code
comment at the point of deviation **and** recorded in the repository's `AGENTS.md`.

Rules marked **[Multi-module]** apply only to applications hosting more than one
operational module. Rules marked **[External-write]** apply only to applications that
write to a system of record outside their own database. Everything else applies
universally.

Where this standard and ADR-001 differ, the difference is deliberate and noted; where
they agree, they agree on purpose — an engineer moving between a Function app and a web
app should not have to relearn configuration, logging, or resilience.

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
`Infrastructure → Application → Domain`. Infrastructure translates; it does not decide.

**Modules are folders and namespaces, not projects.** Inside each of the four projects,
code is divided into:

```
<App>.<Layer>/
  Platform/            Sign-in, shell, language, config, notifications, shared persistence.
  Modules/<Name>/      One operational capability.
```

A type under `Modules.X` may reference `Platform` and its own module. It may **never**
reference a sibling module. Anything two modules both need belongs in `Platform`.

This is the central decision of this ADR, and it is a deliberate departure from ADR-001,
where each concern gets its own project. The reasoning: a new operational request should
become a module in an existing application rather than the next standalone app, and
project-per-module would mean four new `.csproj` files per capability. Folders make the
marginal cost of a module small enough that adding one is the path of least resistance —
which is the behaviour the standard is trying to produce.

**[Multi-module]** The cost of folders over projects is that the compiler no longer
enforces the boundary, so it must be bought back with architecture tests (§3.8). A
module boundary that is only a naming convention erodes on the first deadline.

A single-module application is a conforming instance of this layout, not an exception —
it has a `Platform/` and one entry under `Modules/`. Starting there means the second
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

Target the current LTS-or-later runtime uniformly; never mix target frameworks within a
solution.

**Package versions are centrally managed** in a `Directory.Packages.props` with
`<ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>` and one
`<PackageVersion>` per package; `.csproj` files carry `<PackageReference>` with no
`Version` attribute. Without this, the same package drifts to different versions across
projects in one solution, resolves at build time by nearest-wins, and produces runtime
behaviour matching no single `.csproj`. UI and identity packages drift fastest because
they appear in both the Web project and its test project.

### 3.3 Application layer — ports and use cases

The Application layer defines **ports** — interfaces the outer layers implement — and
one handler per use case. It performs no I/O itself.

Validation is a cross-cutting pipeline that **aggregates** failures rather than throwing
on the first one. An operator filling a form needs every problem at once; returning them
one per round trip is the difference between one correction pass and six.

### 3.4 Configuration and secrets

Configuration binds through `IOptions<T>`. No bespoke secret-loading code, and no
`Environment.GetEnvironmentVariable()`.

- **No secrets in source control, ever** — not even as `appsettings.json` placeholders
  with a "just for dev" justification. Use empty-string placeholders so the file doubles
  as a documented template of every key the application expects.
- **User-secrets in development, Key Vault in UAT and production**, bound through the
  standard configuration system. Production configuration comes from the platform's own
  config store (App Service settings, Key Vault references); this is one-time infra
  setup, not something the pipeline manages per run.
- **Fail fast at startup** on missing required configuration, with a message naming the
  missing key — not a confusing exception deep inside first use. Do this from day one;
  retrofitting it is the kind of task that gets deferred permanently.
- **If a predecessor application committed real credentials, rotate every one of them.**
  They were compromised the moment they entered git history; deleting them in a later
  commit does not undo that.

### 3.5 Authentication and admin access

- Enterprise SSO (Entra ID / OIDC) with a **global fallback policy**: every route
  requires a signed-in user by default, and routes opt *out* individually. Opt-in
  authorization fails open — the route someone forgets to annotate is public.
- Two roles is usually enough: **General** (any signed-in user) and **Admin**.
- **Admin membership is a small allowlist of identities (email/UPN) in configuration** —
  not a directory group, not a group-claim lookup. Deliberately low-ceremony: a handful
  of named admins does not justify provisioning and maintaining a directory group.
  Enforce it in one policy handler and gate it onto the pages that need it — seeing all
  records versus your own, admin CRUD screens, manually-triggered operational actions.
- Document the allowlist config key in the configuration spec so each environment's
  admins are visibly declared rather than tribal knowledge.

### 3.6 [External-write] The attempt-record and failure-matrix pattern

Any flow that writes to a system of record outside the application's own database
follows this pattern. It is the specific answer to failure mode 1 in §1.

1. **Name every attempt.** One operational table (`<Thing>Attempt`) records: idempotency
   key, normalized-payload hash, actor, external-system identifier when known, status
   enum, failure step and detail, retry state, timestamps.
2. **Write the attempt record before the first external write**, and update it as the
   flow progresses. If nothing else survives a crash, this row does.
3. **Draw the failure matrix as a table before writing code.** For each step —
   validation, external write, local audit write, duplicate submission — specify what
   the user sees, what state the external system is left in, what the audit record says,
   whether retry is safe, and whether it alerts. This table is the feature's contract;
   put it in the spec.
4. **The idempotency key is a hash of the normalized request payload**, not a
   client-generated nonce. Stateless, so retries and double-clicks converge on one
   result instead of creating duplicates.
5. **Multi-entity external writes are multi-phase, not one changeset**, unless the
   external system can atomically roll back a parent when a child fails — verify that
   against the real API rather than assuming changeset semantics hold. Identify which
   phase-two failures are therefore *routine* rather than exceptional, and give them a
   first-class recovery path: a reconciliation job or screen, not a TODO.
6. **The audit source of truth is the operational table plus the telemetry platform.**
   Chat notifications are alerting only and are never part of the record.

### 3.7 Resilience on outbound calls

Every call leaving the application — SQL, an external system of record, an analytics
warehouse, an internal API, a chat webhook — goes through a resilience pipeline built
with `Microsoft.Extensions.Resilience`, or `Microsoft.Extensions.Http.Resilience` for
`HttpClient`. Register it in Infrastructure and inject it into the adapters; no adapter
implements its own retry loop.

Default configuration, consistent with ADR-001 §3.5:

| Setting | Retry | Circuit breaker |
|---|---|---|
| Strategy | Exponential backoff with jitter | Count-based |
| Threshold | 3 attempts | 100% failure ratio, min 5 requests |
| Timing | 2s initial delay, 2× multiplier | 30s sampling, 30s break |
| Events | Log `Warning` with attempt, delay, exception type | Log state changes: `Error` on open, `Information` on close/half-open |

Two rules are specific to an interactive application and do not carry over from ADR-001,
where nobody is waiting:

- **A user-facing request has a total time budget, and the retry policy lives inside
  it.** Three attempts with backoff on a call that already takes four seconds is a
  twenty-second page load, which the operator will abandon and retry manually — turning
  one slow request into several concurrent ones. Set an overall timeout on the pipeline
  and prefer fewer attempts on the interactive path. Background and reconciliation work,
  where no one is blocked, keeps the full default.
- **Retries must not silently duplicate a write.** Retry is safe by default only for
  reads and for operations that are idempotent by construction. **[External-write]** A
  write to an external system of record is retried only through the attempt record in
  §3.6, whose idempotency key is what makes a second attempt converge rather than
  duplicate. A bare retry policy wrapped around a non-idempotent write is a defect, not
  a resilience measure.

Distinguish a failure the operator can act on from one they cannot. A validation
rejection from an external system is a message to show them; a timeout or a 503 is a
retry, and if it exhausts, an error that names the operation and tells them whether the
work was recorded — which is what §3.6's attempt row exists to answer.

Chat notification delivery is never retried into the critical path; it is non-blocking
by §3.10 regardless of the pipeline's configuration.

### 3.8 Testing

Each layer has its own test project. Coverage expectations:

- **Domain** — rules and value objects directly, including boundary and encoding cases.
- **Application** — each use case: happy path, each dependency-failure mode, and the
  aggregating behaviour of the validation pipeline.
- **Infrastructure** — adapter translation logic and persistence constraints. Database
  constraints are asserted against the real engine, not an in-memory provider, which
  does not enforce them.
- **[External-write]** Every row of the failure matrix in §3.6 has a corresponding test.
  A matrix without tests is a diagram.
- **[Multi-module]** Architecture tests enforce what the compiler no longer can:
  no type references a sibling module, and namespaces match folders. Confirm such a test
  actually bites rather than passing vacuously — introduce a violation, watch it fail,
  revert — whenever the scanning logic changes.

Localization resource keys have a **missing-key check** as a test or build step, so one
language cannot silently drift behind the other.

### 3.9 Localization

Decide bilingual-or-not up front; retrofitting it means touching every user-facing
string. If bilingual, **every** user-facing string comes from resource files through the
framework's localizer — including validation and error messages originating in Domain
rules. Initial culture comes from the request (`Accept-Language`), is overridable by an
explicit user switch, and is persisted so it survives across requests.

### 3.10 Telemetry and notifications

Consistent with ADR-001 §3.7–3.8:

- **One logging abstraction** — `ILogger<T>`. No second logging library layered in.
- Use-case handlers open a `BeginScope()` carrying correlation and entity identifiers so
  every line in an invocation is traceable together. `Information` at entry, `Error`
  with structured properties at the use-case boundary, `Warning` for non-fatal
  conditions. Named placeholders in message templates, never string interpolation.
- Chat notifications go through an `INotificationService` port in Application, with the
  Infrastructure adapter posting to a pre-existing webhook or flow where the
  organization already has one — reuse the proven payload shape rather than inventing a
  new one. The URL comes from configuration and is never hardcoded.
- **Delivery is non-blocking.** A non-success response logs a `Warning` and returns.
  A notification call never throws and is never treated as part of the record.
- Message content: status, identifier, duration, timestamp; on failure also the error
  type, a **truncated** message — enforce the cap in the domain entity, not ad hoc at
  each call site — and which specific sub-item failed.

### 3.11 Visual design system

- A small set of CSS custom properties as **design tokens** in one theme file
  (`--app-primary`, `--app-page-bg`, `--app-card-bg`, text scale, and semantic
  danger/warning/info triads for background, border, and text). Override the component
  library's own theme variables from those tokens. Never hand-style individual component
  instances.
- A standard shell: brand-colored sidebar, top bar with application name, right-aligned
  user avatar with initials fallback and a dropdown carrying name, culture switch, and
  sign-out.
- Reusable page primitives as a handful of small CSS classes rather than per-page
  bespoke styling: card container, eyebrow label for section headers, labeled-field
  wrapper, responsive grid helper, actions row, banner variants with icon and text, and
  a monospace class reserved for **copy-paste-critical identifiers** — support
  references, external order numbers — which must never be truncated or reformatted.
- The token file's header comment states that it is purely presentational. A visual
  redesign and a markup or behaviour change are separate concerns and are not bundled.

### 3.12 Local development tooling

- For any external integration behind SSO/MFA that is tedious to click through
  repeatedly, build a **thin read-only CLI probe** that calls the Application read ports
  directly, reusing the main application's DI wiring and user-secrets. Keep it read-only
  by construction — it never references the write ports — unless a specific write command
  is explicitly needed and labelled as hitting the real external system.
- Where no local instance of an external dependency exists, run the application's own
  database in a local container **matching the production engine**, not a different local
  engine. Dialect and constraint behaviour must be identical between dev and prod, which
  is the whole reason §3.8 asserts constraints against a real database.

### 3.13 CI/CD

A three-stage pipeline: **Build & Test** → **deploy to a UAT slot** → **swap UAT into
production**, the swap gated by a manual-approval `environment` rather than running
automatically. Swapping validates the exact bits that were tested, rather than
performing a second independent production deploy and hoping it matches.

While iterating on a feature branch pre-merge, prefer a manual pipeline run against that
branch over editing the pipeline's trigger configuration — that keeps the shared trigger
definition untouched and avoids leaving a stale branch name behind after merge. Watch
the promote-to-production approval gate when doing this; do not approve it for a
pre-merge branch.

Secrets reach the pipeline through variable groups, never inline.

### 3.14 Repository documentation

Every repo carries:

- `README.md` — what the application does and how to run it, linking to this ADR.
- `AGENTS.md` — solution layout, module list, configuration table, build and test
  commands, local-dev gotchas, and any deviation from this ADR with its reason.
- `docs/specs/` — one file per feature, the source of truth for behaviour, with an
  index. A feature's acceptance criteria should be checkable, ideally one-to-one with a
  test. Each spec carries an **append-only** decisions log: a resolved entry is marked
  `RESOLVED (date, evidence)` and kept, a reversed one `SUPERSEDED (date, evidence)`
  with a pointer to its replacement. Never delete — the reasoning behind a reversal is
  usually worth more than the reversal.

## 4. Options considered

**Option A — one application per operational request**

| Dimension | Assessment |
|---|---|
| Time to first release | Fastest; nothing shared to negotiate |
| Marginal cost of capability N | Unchanged from capability 1 — full sign-in, shell, deploy, i18n each time |
| Operator experience | Degrades with each addition: another bookmark, another login, another idiom |
| Cross-capability work | Not possible without integration work between apps |

This is the status quo being replaced, and its cost is borne by operators rather than by
engineering — which is why it persisted. The decisive evidence was a single routine task
that spanned a web app, a BI report, a spreadsheet, a public website, and a word
processor, with a human as the integration layer.

**Option B — one application, capabilities as separate projects**

| Dimension | Assessment |
|---|---|
| Boundary enforcement | Strongest; the compiler rejects a cross-capability reference |
| Marginal cost of capability N | Four new `.csproj` files and their wiring |
| Risk | High enough friction that the next capability becomes a standalone app again |

Rejected on that last row. The enforcement is genuinely better, but a standard that makes
the desired behaviour expensive does not produce the desired behaviour.

**Option C — one application, capabilities as folders and namespaces, boundaries
enforced by architecture tests (chosen)**

| Dimension | Assessment |
|---|---|
| Boundary enforcement | Test-time rather than compile-time; requires the tests to exist and to bite |
| Marginal cost of capability N | A folder in each of four projects |
| Platform reuse | Sign-in, shell, language, deployment built once and inherited |

Pros: adding a capability is cheap enough to be the default choice; the platform is
built once; one deployment and one operator-facing application. Cons: the boundary is
only as real as the architecture tests, and a failing-open test is worse than no test
because it produces false confidence — mitigated by §3.8's requirement to verify the
test actually fails on a real violation.

## 5. Trade-off analysis

The trade-off is enforcement strength against the cost of adding a capability, and it
resolves differently here than in ADR-001 because the failure modes differ. A Function
app is one job; the risk is that its layers blur, and project separation is cheap
because there is no per-capability multiplier. A web platform's risk is that the fifth
capability becomes a sixth application, and project separation directly feeds that risk.

Accepting test-time enforcement is therefore not a compromise on rigour but a
relocation of it: the boundary must be *tested* rather than *assumed*, which is a higher
standard than the convention it replaces and a lower one than the compiler. That is the
correct place to sit given what it buys.

The second trade-off is the failure-matrix pattern's overhead. An attempt table, a
payload hash, and a reconciliation path are substantial work for a flow that usually
succeeds. It is justified only where a partial write leaves an external system of record
inconsistent and a human unable to tell whether to retry — which is why §3.6 is tagged
rather than universal.

## 6. Consequences

| | |
|---|---|
| **Easier** | Adding an operational capability; reusing sign-in, shell, language, and deployment; onboarding, since every module has the same shape; answering "why does the code do X" from the specs' decision logs; diagnosing a half-completed write. |
| **Harder** | Initial platform setup, which front-loads sign-in, shell, tokens, and pipeline before the first capability ships. Boundary discipline now depends on tests that must be maintained and verified rather than on the compiler. |
| **Must revisit** | Whether a module should graduate to its own project or deployment if it grows a genuinely independent lifecycle, scaling need, or release cadence. The module rule assumes capabilities that ship and scale together. |

## 7. Action items

1. Link this ADR from each repo's README.
2. Add a PR template checklist item: *"Does this change follow ADR-002?"*
3. Introduce `Directory.Packages.props` in each existing repo and strip `Version`
   attributes from the `.csproj` files (§3.2), reconciling drifted versions upward as
   part of the migration.
4. Confirm the architecture tests fail on a real violation before relying on them
   (§3.8), and repeat that check whenever their scanning logic changes.
5. Scaffold new applications from an existing conforming repo rather than from scratch.
6. Review annually, or whenever a new application cannot be built within this standard —
   the second case is the more informative signal.
