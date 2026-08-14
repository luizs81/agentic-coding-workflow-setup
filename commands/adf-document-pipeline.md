# Document a Data Pipeline in Confluence

Generate a Confluence page that documents a data pipeline. Use the pipeline's source
definition (an ADF pipeline JSON file, or an equivalent orchestration file) as input.

## Writing style

Write all prose in ASD-STE100 (Simplified Technical English) style: short sentences,
one instruction per sentence, active voice, "must"/"must not"/"can" instead of
"should"/"may", consistent terminology. This rule covers every kind of prose you
write — instructions, documents, responses, messages to other agents, and code
comments. Only code syntax and literal commands are exempt.

## How to invoke

```
/adf-document-pipeline <path-to-pipeline-json> [parent-page-id]
```

- `path-to-pipeline-json`: path to the pipeline definition.
- `parent-page-id` *(optional)*: Confluence page to create under. If omitted, ask the user.

The Confluence cloudId and space are **not** hard-coded here. Get them with
`getAccessibleAtlassianResources` and `getConfluenceSpaces`. Alternatively, read them from
the project's `AGENTS.md` if it records them. If the space is ambiguous, ask which space to
use. Do not guess — a page created in the wrong space is visible to the wrong audience.

## What to extract

Read the pipeline definition. Pull out the following: name, description, and folder; every
activity with its type, `dependsOn`, dependency conditions, and type properties; parameters
with types and defaults; annotations; referenced datasets and linked services; global
parameters (`@pipeline().globalParameters.*`); and any notification pipelines invoked, with
the arguments passed to them.

Some information is project-specific: which global parameters exist and what they mean, the
parameter contract of the notification pipelines, and connector quirks. This information
belongs in that project's `AGENTS.md`, not in this command. Read it from there.

## Confluence API traps

Experiments confirmed these traps. They are not documented elsewhere. Each one costs a
session to rediscover.

**Two-column layouts do not work through the API.** The REST API silently converts
`layoutSection` nodes to `ac:type="fixed-width"`. This happens regardless of the
`layoutType` or `width` attributes you specify. The result always renders as a single
column. The interactive editor handles two-column layouts; the API path does not. Build a
flat, single-column document instead — do not use a `layoutSection` wrapper. Put a TOC
macro inline at the top instead:

```json
{
  "type": "extension",
  "attrs": {
    "layout": "default",
    "extensionType": "com.atlassian.confluence.macro.core",
    "extensionKey": "toc",
    "parameters": {
      "macroParams": {
        "minLevel": { "value": "1" }, "maxLevel": { "value": "2" },
        "outline": { "value": "false" }, "style": { "value": "none" },
        "type": { "value": "list" }, "printable": { "value": "true" }
      },
      "macroMetadata": {
        "macroId": { "value": "<uuid>" }, "schemaVersion": { "value": "1" },
        "title": "Table of Contents"
      }
    },
    "localId": "<uuid>"
  }
}
```

**ADF node conventions.** Every node needs a unique `localId` (generate with `uuid.uuid4()`).
Bold uses `"marks": [{"type": "strong"}]`. Inline code uses `{"type": "code"}`. Header cells
use `tableHeader`. Data cells use `tableCell`. **Every cell must contain at least one
paragraph node** — an empty cell makes a malformed document, not a blank cell. Use
`colwidth` to keep two-column property tables readable (roughly `[200]` for the label,
`[670]` for the value). Set `"enableStaging": false`. Do not invent fields that the ADF
editor does not emit.

## Page structure

Use the pipeline name as the title. Keep the content flat: TOC macro, then a summary table,
then sections.

The summary table has two columns (bold label, value): pipeline name as inline code, folder,
schedule, source, destination, and status.

Include only the sections that apply. Skip a section rather than emit it empty. Typical
sections are: Overview, Business Purpose, Key Features, Pipeline Architecture, Activity
Details (one H2 per activity, each with a property/value table), Configuration (parameters,
global parameters, datasets, linked services, notifications), Error Handling, and Change
History. Populate Change History from `git log --oneline -- <pipeline-file>`.

Use H1 for sections and H2 for subsections. Add a `{"type": "rule"}` divider before each H1
except the first.

## Diagrams

Always use [D2](https://d2lang.com). Never use Mermaid, PlantUML, or ASCII art. Emit the
diagram as a `codeBlock` node with `attrs.language = "d2"`.

Show source system, each activity, and destination as nodes. Label arrows with the activity
name. Label notification branches with their condition (`Succeeded` / `Failed`). Use one
node per logical step, not one per dataset or linked service. Use cylinders for data stores
and rectangles for activities.

## Getting a large body into the tool call

`createConfluencePage` takes the body as a parameter, so the JSON must be in context. A
generated page body can run tens of KB on one line, more than a single `Read` returns.

Build the document with a Python script. Write helper functions for paragraph, heading,
marks, bullet list, table/row/cell, the TOC macro, and the rule node, and write the output
to a file. Then validate the output and check its size before doing anything else:

```python
output = json.dumps(doc, ensure_ascii=False)
json.loads(output)          # fails loudly here rather than at the API
print("VALID -", len(output), "bytes")
```

If the output fits in one `Read`, read it and pass it. If it does not fit, split it into
chunks and read them in parallel. Concatenate the chunks in order as the `body` argument.
The chunks are raw substrings, so concatenation reconstructs the exact JSON. Tool call
arguments have no size limit.

**Measure the cap. Do not trust a number written here.** As of 2026-08-01, a single `Read`
of a one-line file returned about 43 KB before truncating. The truncation notice states the
real limit in both characters and tokens. Split according to what that notice tells you, and
leave margin. An earlier version of this command hard-coded a "10 KB Read limit" and 8 KB
chunks. That number was wrong by more than 4x and produced eight pointless round-trips for a
body that needed two.

Avoid this problem where possible. If the body is very large, create the page with its first
sections, then append the rest with `updateConfluencePage`.
