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

   Two things belong in that first prompt whenever they apply:

   - **Verify the task's premise before building to it.** If the task's stated purpose
     depends on fixture, log, or export data — "validate against the real run", "golden
     file", "replay production output" — the implementer must confirm the data actually
     contains the *values* the task needs, not merely that the files exist and are the
     right shape. If it doesn't, that's a blocked task: stop and report, rather than
     delivering a test whose name claims more than it can do.
   - **Report overlap with other tasks.** If implementing this task also delivers
     something a later backlog task lists, the implementer says so explicitly instead of
     silently absorbing it, so you can amend the later task rather than let it re-derive
     work that already exists.

2. **Review.** Spawn the reviewer agent (`Agent` tool, `subagent_type` = the given reviewer
   name, `run_in_background: false`) and ask it to review the current diff/working tree
   state against its standard.

   The reviewer's prompt contains only: the task's text and acceptance criteria, the
   changed file paths (`git diff --name-only`), and an instruction to read those files
   itself. Never paste implementer narrative or file contents into it — the reviewer must
   inspect the actual files rather than review a summary of them.

3. **Relay, don't ask.** Take the reviewer's returned findings and feed them directly into
   the next implementer prompt yourself — this is the whole point of the loop, the user
   should not be copy-pasting between agents. Only Critical and Major findings block
   progress; Minor findings are worth noting in the final report but don't loop.

   When you relay a finding, tell the implementer to fix the class of defect, not the
   instance the reviewer happened to cite. A reviewer reports the example it found, not an
   inventory — so search for every other site with the same shape and fix those in the same
   pass, and say in your report which sites you checked. Sibling functions are the usual
   miss: the one that was reported gets fixed and the one beside it doing the same thing
   doesn't.

4. **Repeat 1→3** for this task until the reviewer returns with no Critical or Major
   findings. Cap this at 3 implement/review round-trips per task — if it's still not clean
   after 3 tries, stop looping and escalate to the user with the task, the diff, and the
   last review, rather than burning further cycles on something that isn't converging.

   **Self-fix trailing single-issue findings instead of spawning another round.** If a
   review round comes back with exactly one Critical/Major finding left and it's contained
   — a doc comment, a wrong constant, a one-line assertion, anything fixable by reading the
   finding and editing the file directly, with no design ambiguity and no multi-file
   fan-out — fix it yourself with `Edit` rather than spawning another implementer/reviewer
   round-trip. Verify with a build/test run appropriate to the stack afterward, and record
   it as a self-fix (not a subagent round) in the final report. Fall back to a full subagent
   round only when the finding is non-trivial: touches multiple files, requires re-deriving
   a design decision, or you're not confident the fix is correct without a second pair of
   eyes.

5. **Check off the task** — edit the backlog file, flipping `- [ ]` to `- [x]` for that
   item — once the reviewer is clean.

   Before checking off, sweep whatever documentation the task's behaviour change
   invalidated — design docs describing the changed mechanism, open-question entries the
   task resolved, blocker entries it cleared, and any in-code description of behaviour
   that moved (the applicable standard defines what that means for this stack). These go
   in the *same* commit as the change, and are named in the reviewer's prompt so they're
   in scope for review, not just for you.

   This matters because the backlog and its design docs are what the *next* task is
   briefed from. One that still lists a resolved blocker, or describes a mechanism that
   has since changed, doesn't just read as stale — it gets built on.

6. **Commit.** Once a task is checked off, stage and commit the changes for that task alone
   (one commit per task, not one at the end) following the repo's normal commit conventions
   and the standing git-safety rules — review what's staged, never `git add -A`, never
   `--no-verify`. Use the task's own text as the basis for the commit message.

   End the commit message with a trailer recording how the task converged, so review
   round-trips are queryable later without archaeology through commit prose:
   `Review-rounds: N` where N counts full implement/review round-trips this task took
   (1 if the reviewer was clean on the first pass), plus `Self-fixed: yes` if step 4's
   self-fix path was used for the trailing finding instead of spawning another round.

7. **Move to the next unchecked task** and repeat from step 1.

## Between tasks

- Don't batch multiple tasks into one implement/review pair — each task gets its own full
  loop, so the reviewer's Critical/Major findings map to exactly the change that produced
  them.
- If a task's own text says it depends on a later or earlier task, or the implementer flags
  a blocking ambiguity mid-task, stop and ask the user rather than guessing — this mirrors
  the "don't guess on ambiguous business details, ask" rule already in the ADF/dbt agents.

## Lightweight path for low-risk tasks

Not every task needs the full implementer→reviewer ceremony. Before starting step 1 for a
task, judge whether it qualifies as low-risk:

- Small, additive, and mechanically simple — a new config/options class, a constant, a
  small pure helper, a doc/comment sweep, wiring an existing type into DI — not new business
  logic, not a change to an existing code path, not anything touching resilience, auth,
  money, dates/timezones, or external I/O.
- Fully scoped by the task text itself, with no ambiguity to resolve.
- Low blast radius: a mistake here is cheap to spot and cheap to fix.

If a task qualifies, skip the implementer subagent and write it yourself directly (Read/
Edit/Write), then still send it to the reviewer subagent once (step 2) before checking it
off — the reviewer pass stays mandatory, only the implementer round is skipped. If the
reviewer comes back with a Critical/Major finding, escalate to the full implementer/
reviewer loop from that point rather than continuing to self-fix — a real finding on a task
you judged "low-risk" means the judgment call was wrong, not that the fix should stay
informal.

When in doubt, don't take the shortcut — the full loop is the default, this is the
exception.

## When the backlog is exhausted

Report a summary: which tasks were completed, how many review round-trips each took, any
task escalated to the user without converging, and any Minor findings left un-addressed
across the run (grouped, not one at a time).

## After the backlog is exhausted: feed findings back into the standard

Look back across every Critical/Major finding raised during the run (not just the final
task's). If the same class of issue was flagged on more than one task, or is the kind of
mistake likely to recur on future backlogs, that's a gap in the standard or in the
implementer's own instructions, not just a diff to fix and move past.

For each recurring finding:

- If it's a rule the implementer got wrong or missed entirely, propose an edit to the
  ADR/standard file itself (not the agent file) — both implementer and reviewer read the
  same standard, so one edit closes the gap for both roles. Phrase it as a direct rule with
  its rationale, e.g. "Do X. (Not Y — Y causes Z.)", not a narrative about what happened.
- If it's specific to how this implementer tends to fail (a shortcut it defaults to, a check
  it skips even though the standard already covers it), propose the edit to the implementer
  agent's own file instead, in whatever section already lists gotchas or common mistakes.

Present these as proposed edits with the specific file and wording, and apply them once the
user confirms — don't silently rewrite the standard files without approval, since they're
shared across every future run, not just this backlog.

## Notes

- This command intentionally does not use agent teams or the `TaskCompleted`/`TeammateIdle`
  hooks — those require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and are built for teammates
  that coordinate with each other directly. Here the main session is the sole coordinator,
  which is simpler and sufficient: implementer and reviewer never need to know about each
  other, only about the current task and the current findings.
- Both subagent calls must run in the foreground (not `run_in_background: true`). The loop
  cannot decide whether to continue or move on without each result in hand first.
