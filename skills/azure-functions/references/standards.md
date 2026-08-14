# Azure Functions — Rationale for the specific numbers

The decision record lives at
[`../../../adr/ADR-001-azure-functions-shared-architecture.md`](../../../adr/ADR-001-azure-functions-shared-architecture.md).
It covers context, options considered, trade-offs, and consequences. **Read that
first** to learn why the architecture is shaped this way at all: why Clean
Architecture is used over a flat project, why the layering is worth the setup cost, and
what to revisit as apps grow.

This file covers only what the ADR states as a rule without justifying the specific
value. It covers the magic numbers and the two "why not the obvious alternative"
questions that come up most in review. If this file and the ADR ever disagree, the ADR
wins. Flag the mismatch. Do not silently pick one.

## Why 3 retries, 2s initial, and those circuit breaker numbers

3 retries with exponential backoff plus jitter are enough to ride out typical
transient Azure service blips, without extending a run so long that it risks the
function's timeout. The circuit breaker (100% failure ratio, min 5 requests, 30s
sampling/break) exists so a genuinely down dependency fails fast. Without it, every
subsequent call would queue up its own 3-retry sequence, multiplying the outage's
blast radius on your own compute.

The 100% failure ratio is deliberate. These apps make few enough calls per run that a
partial ratio would trip on normal noise. The breaker opens only when a dependency is
unambiguously down.

## Why the retry predicate matters, not just the count

An unfiltered retry, the Polly default, treats every exception the same. That means it
treats "the connection blipped" and "the login failed" the same way. The second case
will not succeed on attempt two or three. The credentials do not fix themselves between
retries. An unfiltered retry only buys roughly 14 seconds of added latency (2s + 4s +
8s at the default backoff) and three warning-level log lines before the failure
surfaces anyway. Under load, it also triples the calls against a dependency that is
already rejecting them.

Scope the retry to faults that plausibly resolve on their own (timeouts, resets,
throttling). Let everything else fail on the first attempt. This keeps the fast path
fast without giving up the genuine benefit of retrying a transient blip.

## Why Polly *and* the Durable retry, not just one

Durable's `RetryPolicy` operates at the activity level. If an entire activity throws,
Durable retries the whole activity from scratch. That is too coarse for a transient
failure inside a single SDK call (a momentary Blob 503, a connection hiccup), because
retrying the whole activity discards any partial work already done earlier in it. Polly
wraps the individual call, so a transient failure three calls into an activity does not
force redoing the first two. The Durable retry stays as the backstop for the case Polly
cannot catch: the worker crashing mid-activity.

## Why `ILogger<T>` only — the correlation argument

The ADR gives the double-initialization reason. The subtler reason: `ILogger<T>` is
what the Functions Application Insights integration is wired to pick up automatically,
via `ConfigureFunctionsApplicationInsights()`. A static logger or a separate framework
either duplicates that pipeline or bypasses it. This produces logs that do not land in
the same trace as the rest of the invocation and cannot be correlated by invocation ID.
That defeats the `BeginScope()` discipline the standard requires everywhere else.

## Why 500 characters on Teams error messages

Adaptive Cards have practical rendering limits. A full .NET stack trace pasted into a
Teams message is unreadable anyway. The truncated message tells an on-call person
*what* failed and gives them enough to start searching in Application Insights. It is a
pointer, not the full diagnostic.
