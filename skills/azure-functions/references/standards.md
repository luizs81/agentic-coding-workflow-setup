# Azure Functions — Rationale for the specific numbers

The decision record — context, options considered, trade-offs, consequences — lives at
[`../../../adr/ADR-001-azure-functions-shared-architecture.md`](../../../adr/ADR-001-azure-functions-shared-architecture.md).
**Read that first** for why the architecture is shaped this way at all: why Clean
Architecture over a flat project, why the layering is worth the setup cost, what to
revisit as apps grow.

This file covers only what the ADR states as a rule without justifying the specific
value — the magic numbers and the two "why not the obvious alternative" questions that
come up most in review. If this file and the ADR ever disagree, the ADR wins; flag the
mismatch rather than silently picking one.

## Why 3 retries, 2s initial, and those circuit breaker numbers

3 retries with exponential backoff plus jitter is enough to ride out typical transient
Azure service blips without extending a run so long it risks the function's timeout.
The circuit breaker (100% failure ratio, min 5 requests, 30s sampling/break) exists so a
genuinely down dependency fails fast instead of every subsequent call queuing up its own
3-retry sequence and multiplying the outage's blast radius on your own compute.

The 100% failure ratio is deliberate: these apps make few enough calls per run that a
partial ratio would trip on normal noise. It opens only when a dependency is
unambiguously down.

## Why the retry predicate matters, not just the count

An unfiltered retry — the Polly default — treats every exception the same, which means
it treats "the connection blipped" and "the login failed" the same. The second case
isn't going to succeed on attempt two or three; the credentials don't fix themselves
between retries. All an unfiltered retry buys you there is roughly 14 seconds of added
latency (2s + 4s + 8s at the default backoff) and three warning-level log lines before
the failure surfaces anyway — plus, under load, three times the calls against a
dependency that's already rejecting them. Scoping the retry to faults that plausibly
resolve on their own (timeouts, resets, throttling) and letting everything else fail on
the first attempt keeps the fast path fast without giving up the genuine benefit of
retrying a transient blip.

## Why Polly *and* the Durable retry, not just one

Durable's `RetryPolicy` operates at the activity level — if an entire activity throws,
Durable retries the whole activity from scratch. That's too coarse for a transient
failure inside a single SDK call (a momentary Blob 503, a connection hiccup): retrying
the whole activity discards any partial work already done earlier in it. Polly wraps the
individual call, so a transient failure three calls into an activity doesn't force
redoing the first two. The Durable retry stays as the backstop for the case Polly can't
catch — the worker crashing mid-activity.

## Why `ILogger<T>` only — the correlation argument

The ADR gives the double-initialization reason. The subtler one: `ILogger<T>` is what
the Functions Application Insights integration is wired to pick up automatically via
`ConfigureFunctionsApplicationInsights()`. A static logger or a separate framework
either duplicates that pipeline or bypasses it, producing logs that don't land in the
same trace as the rest of the invocation and can't be correlated by invocation ID —
which defeats the `BeginScope()` discipline the standard requires everywhere else.

## Why 500 characters on Teams error messages

Adaptive Cards have practical rendering limits, and a full .NET stack trace pasted into
a Teams message is unreadable anyway. The truncated message tells an on-call person
*what* failed and gives them enough to start searching in Application Insights — it's a
pointer, not the full diagnostic.
