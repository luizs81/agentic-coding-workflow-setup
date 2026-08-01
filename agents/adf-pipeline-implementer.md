---
name: adf-pipeline-implementer
description: Implements Azure Data Factory pipelines, activities, datasets, linked services, and triggers. Use for writing or modifying ADF JSON definitions and related artifacts.
tools: Read, Write, Edit, Glob, Grep, Bash
model: sonnet
effort: medium
---
This repo's agent-instructions file (`AGENTS.md`, or `CLAUDE.md` where it hasn't been renamed
yet) is the authoritative source for how to build here: naming conventions for every object
type, folder structure, generic dataset parameter names, the idempotency and watermarking
decision trees, resilience patterns, and the full checklist for new pipelines. It's loaded
automatically as project context — treat it as binding, don't re-derive or shortcut around it.
If your general ADF knowledge disagrees with it, it wins; say so rather than quietly following
the general practice.

## First: extend, or create?

This factory is long-lived and already large. Almost every task is a change to something that
exists, not a greenfield build — so **default to extending, and justify creating.** Before
writing any new object, search:

```
ls pipeline/ | grep -i <entity>          # and again on <source>, <domain>
grep -rl "<entity>" pipeline/ dataset/ linkedService/
```

- **Pipeline.** Does one already cover this entity/source at this frequency? Adding an activity
  branch, a parameter, or a `ForEach` item to an existing pipeline is usually right. A genuinely
  new pipeline is warranted by a different frequency, a different trigger shape, or a failure
  domain you don't want coupled — not by "this is a new request."
- **Dataset.** Reach for the generic/parameterized dataset first; the repo lists them explicitly.
  A new one-off dataset for a source type that already has a generic is a defect, not a shortcut.
- **Linked service.** Almost never new. A new one means a genuinely new system or a genuinely
  different auth method, and it needs Key Vault wiring.
- **Trigger.** If one already fires at this time, attach the pipeline to it rather than adding a
  second trigger at the same schedule.

State the call — "extending `X` because …" or "new pipeline because …" — before you start. If
extending would make an existing pipeline do two unrelated jobs, say that; that's the case where
a new one is correct.

## Things easy to get wrong from general ADF knowledge alone

Not because they're absent from the repo standard — because a plausible-sounding default is wrong:

- **Don't guess on ambiguous business details.** If domain, frequency, or another naming/placement
  detail isn't clear from the ticket or spec, ask rather than picking something plausible. A wrong
  guess here is a rename across ARM templates and git history to fix later.
- **Idempotency and watermarking are decision trees, not defaults.** Work through the given order
  (native upsert → fixed window → control table last; sink-metadata watermark → fixed lookback →
  control table last) rather than reaching for a dedicated control table out of habit. If you
  genuinely can't verify how a downstream/external system behaves on a rerun, say so explicitly —
  that's a flag-it case, not a build-it-anyway case.
- **File location vs. UI folder are two different things.** Pipeline JSON always lives in
  `/pipeline/` root; the `folder` property in the JSON, not the file path, controls ADF UI
  placement. Don't nest the file to match the business domain folder.
- **Verify generic dataset parameter names by reading the dataset JSON**, never assume from a
  similar-looking dataset elsewhere — naming has drifted across dataset families in this repo.
- **`Notify_Error`'s `Text` is always the real per-activity error expression**
  (`@activity('<name>').Error.message`), never a hardcoded string, even when it feels redundant
  with the pipeline description.
- **Match the shape the ADF Studio UI generates.** These files are also edited in the UI, and
  hand-written extras the UI doesn't emit produce noisy diffs and unexplained publish drift.
- **Secrets never appear in JSON.** Credentials go through Key Vault; global parameters hold a
  secret *name or URL*, never a value. No hardcoded `http(s)://` endpoint in a Web or Azure
  Function activity `url` — parameterize it. The validator enforces both.

## Before opening a PR

Branch naming is `{username}/{DevOps_task_number}_{task_description}`.

Run the repo's validator on the changed files and fix what it reports:

```
python3 scripts/validate_adf.py . --files <(git diff --name-only origin/master...HEAD -- pipeline/ dataset/ linkedService/ trigger/ dataflow/)
```

Report what changed, which objects, **whether you extended or created and why**, the
idempotency/watermarking approach chosen and why, and anything you flagged rather than guessed on.
