# Document a Data Pipeline in Confluence

Generate a Confluence page documenting a data pipeline from its source definition
(an ADF pipeline JSON, or an equivalent orchestration file).

## How to invoke

```
/adf-document-pipeline <path-to-pipeline-json> [parent-page-id]
```

- `path-to-pipeline-json`: path to the pipeline definition.
- `parent-page-id` *(optional)*: Confluence page to create under. If omitted, ask.

The Confluence cloudId and space are **not** hard-coded here. Get them with
`getAccessibleAtlassianResources` and `getConfluenceSpaces`, or read them from the
project's `AGENTS.md` if it records them. Ask which space if it is ambiguous — do not
guess, since a page created in the wrong space is visible to the wrong audience.

## What to extract

Read the pipeline definition and pull out: name, description, folder; every activity with
its type, `dependsOn` and dependency conditions, and type properties; parameters with types
and defaults; annotations; referenced datasets and linked services; global parameters
(`@pipeline().globalParameters.*`); and any notification pipelines invoked, with the
arguments passed to them.

Anything project-specific — which global parameters exist and what they mean, the parameter
contract of the notification pipelines, connector quirks — belongs in that project's
`AGENTS.md`, not in this command. Read it from there.

## Confluence API traps

These are confirmed by experiment, not documented. They cost a session each to rediscover.

**Two-column layouts do not work through the API.** The REST API silently converts
`layoutSection` nodes to `ac:type="fixed-width"` regardless of the `layoutType` or `width`
attributes you specify, so the result always renders as a single column. The interactive
editor handles it; the API path does not. Build a flat, single-column document — no
`layoutSection` wrapper — and put a TOC macro inline at the top instead:

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
Bold is `"marks": [{"type": "strong"}]`, inline code is `{"type": "code"}`. Header cells are
`tableHeader`, data cells `tableCell`, and **every cell must contain at least one paragraph
node** — an empty cell is a malformed document, not a blank cell. Use `colwidth` to keep
two-column property tables readable (roughly `[200]` label, `[670]` value). Set
`"enableStaging": false`; do not invent fields the ADF editor does not emit.

## Page structure

Title is the pipeline name. Content is flat: TOC macro, then a summary table, then sections.

The summary table is two columns (bold label, value): pipeline name as inline code, folder,
schedule, source, destination, status.

Then only the sections that actually apply — skip a section rather than emitting it empty.
Typically: Overview, Business Purpose, Key Features, Pipeline Architecture, Activity Details
(one H2 per activity, each with a property/value table), Configuration (parameters, global
parameters, datasets, linked services, notifications), Error Handling, and Change History
populated from `git log --oneline -- <pipeline-file>`.

H1 for sections, H2 for subsections, with a `{"type": "rule"}` divider before each H1 except
the first.

## Diagrams

Always [D2](https://d2lang.com). Never Mermaid, PlantUML, or ASCII art. Emit it as a
`codeBlock` node with `attrs.language = "d2"`.

Show source system → each activity → destination as nodes, arrows labelled with the activity
name, and notification branches labelled with their condition (`Succeeded` / `Failed`). One
node per logical step, not per dataset or linked service. Cylinders for data stores,
rectangles for activities.

## Getting a large body into the tool call

`createConfluencePage` takes the body as a parameter, so the JSON has to be in context. A
generated page body runs tens of KB on one line, which is more than a single `Read` returns.

Build the document with a Python script (helper functions for paragraph, heading, marks,
bullet list, table/row/cell, the TOC macro, and the rule node) and write it to a file. Then
validate and check the size before doing anything else:

```python
output = json.dumps(doc, ensure_ascii=False)
json.loads(output)          # fails loudly here rather than at the API
print("VALID -", len(output), "bytes")
```

If it fits in one `Read`, read it and pass it. If it does not, split it into chunks, read
them in parallel, and concatenate them in order as the `body` argument — the chunks are raw
substrings, so concatenation reconstructs the exact JSON, and tool call arguments have no
size limit.

**Measure the cap rather than trusting a number written here.** As of 2026-08-01 a single
`Read` of a one-line file returned ~43 KB before truncating, and the truncation notice states
the real limit in both characters and tokens. Split on what that notice tells you, with
margin. An earlier version of this command hard-coded a "10 KB Read limit" and 8 KB chunks,
which was wrong by more than 4x and produced eight pointless round-trips for a body that
needed two.

Prefer not needing this at all: if the body is very large, consider creating the page with
its first sections and appending the rest with `updateConfluencePage`.
