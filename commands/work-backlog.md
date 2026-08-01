# Work a Backlog: Implement → Review Loop

Drive a backlog of tasks to completion by alternating an implementer subagent and a
reviewer subagent, task by task, without asking the user to relay feedback between them.

## How to invoke

```
/work-backlog <path-to-backlog.md> <implementer-agent-name> <reviewer-agent-name>
```

- `path-to-backlog.md`: a markdown file with tasks as `- [ ]` / `- [x]` checkbox items.
- `implementer-agent-name`: e.g. `dotnet-web-implementer`, `adf-pipeline-implementer`,
  `dbt-data-engineer-implementer`.
- `reviewer-agent-name`: e.g. `dotnet-web-reviewer`, `adf-pipeline-reviewer`,
  `dbt-data-engineer-reviewer`.

If any argument is missing, ask for it rather than guessing — picking the wrong agent pair
runs the loop against the wrong standard.

## The loop

For each unchecked `- [ ]` task in the backlog, top to bottom:

1. **Implement.** Spawn the implementer agent (`Agent` tool, `subagent_type` = the given
   implementer name, `run_in_background: false` — the next step needs its result). Prompt
   it with the task's full text plus enough surrounding context from the backlog file
   (section heading, adjacent notes) that it doesn't have to guess intent. On the first
   pass for a task, do not include reviewer feedback — there isn't any yet.

2. **Review.** Spawn the reviewer agent (`Agent` tool, `subagent_type` = the given reviewer
   name, `run_in_background: false`) with a prompt describing what was just implemented and
   asking it to review the current diff/working tree state against its standard. Do not
   summarize or filter the implementer's own claims into the reviewer's prompt — let the
   reviewer inspect the actual files itself.

3. **Relay, don't ask.** Take the reviewer's returned findings and feed them directly into
   the next implementer prompt yourself — this is the whole point of the loop, the user
   should not be copy-pasting between agents. Only Critical and Major findings block
   progress; Minor findings are worth noting in the final report but don't loop.

4. **Repeat 1→3** for this task until the reviewer returns with no Critical or Major
   findings. Cap this at 3 implement/review round-trips per task — if it's still not clean
   after 3 tries, stop looping and escalate to the user with the task, the diff, and the
   last review, rather than burning further cycles on something that isn't converging.

5. **Check off the task** — edit the backlog file, flipping `- [ ]` to `- [x]` for that
   item — once the reviewer is clean.

6. **Commit.** Once a task is checked off, stage and commit the changes for that task alone
   (one commit per task, not one at the end) following the repo's normal commit conventions
   and the standing git-safety rules — review what's staged, never `git add -A`, never
   `--no-verify`. Use the task's own text as the basis for the commit message.

7. **Move to the next unchecked task** and repeat from step 1.

## Between tasks

- Don't batch multiple tasks into one implement/review pair — each task gets its own full
  loop, so the reviewer's Critical/Major findings map to exactly the change that produced
  them.
- If a task's own text says it depends on a later or earlier task, or the implementer flags
  a blocking ambiguity mid-task, stop and ask the user rather than guessing — this mirrors
  the "don't guess on ambiguous business details, ask" rule already in the ADF/dbt agents.

## When the backlog is exhausted

Report a summary: which tasks were completed, how many review round-trips each took, any
task escalated to the user without converging, and any Minor findings left un-addressed
across the run (grouped, not one at a time).

## Notes

- This command intentionally does not use agent teams or the `TaskCompleted`/`TeammateIdle`
  hooks — those require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and are built for teammates
  that coordinate with each other directly. Here the main session is the sole coordinator,
  which is simpler and sufficient: implementer and reviewer never need to know about each
  other, only about the current task and the current findings.
- Both subagent calls must run in the foreground (not `run_in_background: true`). The loop
  cannot decide whether to continue or move on without each result in hand first.
