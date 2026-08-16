# Work a Backlog: Implement → Review Loop

Drive a backlog of tasks to completion. Alternate an implementer subagent and a reviewer
subagent, task by task. Do not ask the user to relay feedback between them.

## Writing style

Write all prose in ASD-STE100 (Simplified Technical English) style. Four rules are
mechanical, and a script checks them:

1. Do not use "should", "may", or "might". Use "must", "must not", or "can".
2. Keep every sentence to 25 words or fewer.
3. Keep every paragraph to 4 sentences or fewer.
4. Do not use an em-dash aside. Write two sentences instead.

Check any markdown file you write or edit before you report done:

```
python3 ~/.claude/standards/check-style.py <changed .md files>
```

Fix every ERROR. Fix each WARN unless splitting the sentence loses meaning.

The script cannot check the rest of the style. Also write in active voice. Also put one
instruction in each sentence. Also use the same term for the same thing every time.

This rule covers every kind of prose you write. It covers instructions, documents,
responses, messages to other agents, and code comments. Only code syntax and literal
commands are exempt.

## How to invoke

```
/work-backlog <path-to-backlog.md> <implementer-agent-name> <reviewer-agent-name>
```

- `path-to-backlog.md`: a markdown file with tasks as `- [ ]` / `- [x]` checkbox items.
- `implementer-agent-name`: e.g. `dotnet-web-implementer`, `adf-pipeline-implementer`,
  `dbt-data-engineer-implementer`.
- `reviewer-agent-name`: e.g. `dotnet-web-reviewer`, `adf-pipeline-reviewer`,
  `dbt-data-engineer-reviewer`.

If any argument is missing, ask for it. Do not guess — picking the wrong agent pair runs the
loop against the wrong standard.

## The loop

For each unchecked `- [ ]` task in the backlog, top to bottom:

1. **Implement.** Spawn the implementer agent (`Agent` tool, `subagent_type` = the given
   implementer name, `run_in_background: false` — the next step needs its result). Prompt it
   with the task's full text, plus enough surrounding context from the backlog file (section
   heading, adjacent notes) that it does not have to guess intent. On the first pass for a
   task, do not include reviewer feedback. There is none yet.

   Include these two items in that first prompt whenever they apply:

   - **Verify the task's premise before building to it.** The task's stated purpose can
     depend on fixture, log, or export data — for example "validate against the real run",
     "golden file", or "replay production output". In that case the implementer must
     confirm the data actually contains the *values* the task needs. Confirming that the
     files exist and have the right shape is not enough. If the data does not contain the
     needed values, the task is blocked: stop and report. Do not deliver a test whose name
     claims more than it can do.
   - **Report overlap with other tasks.** Implementing this task can also deliver something
     a later backlog task lists. If so, the implementer must say so explicitly instead of
     silently absorbing it. This lets you amend the later task instead of letting it
     re-derive work that already exists.

2. **Gate on the code actually running.** Before you spawn the reviewer, confirm the change
   compiles or builds. Use whatever command fits the stack (`dbt compile --select <model>`,
   `dotnet build`, and so on). A task does not reach review until this gate passes.

   Always truncate the build command's output — for example
   `dotnet build 2>&1 | tail -30`. A passing build's log is worthless the moment the gate
   passes, but it stays in your context for the rest of the run and is re-sent on every
   later turn. If the tail does not show the cause of a failure, re-run and grep for the
   error instead of dropping the whole log into context.

   Do not treat the implementer's report as evidence of this. An implementer can report
   success on code that was never parsed. This gate exists because that happened once: a
   dbt model was written, reviewed clean, checked off, and committed, and it did not
   compile. No reviewer catches that, because reviewers read files instead of running them.

   If the gate fails, return to step 1 with the error. Do not count this as a review round.

3. **Review.** Spawn the reviewer agent (`Agent` tool, `subagent_type` = the given reviewer
   name, `run_in_background: false`). Ask it to review the current diff/working tree state
   against its standard.

   The reviewer's prompt must contain only: the task's text and acceptance criteria, the
   changed file paths (`git diff --name-only`), and an instruction to read those files
   itself. Never paste implementer narrative or file contents into it. The reviewer must
   inspect the actual files instead of reviewing a summary of them.

4. **Relay, don't ask.** Take the reviewer's returned findings and feed them directly into
   the next implementer prompt yourself. This is the whole point of the loop — the user must
   not copy-paste between agents. Only Critical and Major findings block progress. Note
   Minor findings in the final report, but do not loop on them.

   When you relay a finding, tell the implementer to fix the class of defect, not just the
   instance the reviewer cited. A reviewer reports the example it found, not a full
   inventory. Search for every other site with the same shape and fix those in the same
   pass. State in your report which sites you checked. Sibling functions are the usual miss:
   the reported one gets fixed, and the one beside it doing the same thing does not.

5. **Repeat 1→4** for this task until the reviewer returns with no Critical or Major
   findings. Cap this at 3 implement/review round-trips per task. If the task is still not
   clean after 3 tries, stop looping. Escalate to the user with the task, the diff, and the
   last review. Do not burn further cycles on something that is not converging.

   **Self-fix trailing single-issue findings instead of spawning another round.** A review
   round can come back with exactly one Critical/Major finding left, and that finding can be
   contained — for example a doc comment, a wrong constant, or a one-line assertion. If the
   finding is fixable by reading it and editing the file directly, with no design ambiguity
   and no multi-file fan-out, fix it yourself with `Edit` instead of spawning another
   implementer/reviewer round-trip. Verify the fix afterward with a build/test run
   appropriate to the stack. Record it as a self-fix (not a subagent round) in the final
   report. Fall back to a full subagent round only when the finding is non-trivial: it
   touches multiple files, it requires re-deriving a design decision, or you are not
   confident the fix is correct without a second pair of eyes.

6. **Check off the task.** Once the reviewer is clean, edit the backlog file and flip
   `- [ ]` to `- [x]` for that item.

   Before checking off, sweep whatever documentation the task's behavior change
   invalidated: design docs describing the changed mechanism, open-question entries the
   task resolved, blocker entries it cleared, and any in-code description of behavior that
   moved (the applicable standard defines what that means for this stack). Put these
   updates in the *same* commit as the change. Name them in the reviewer's prompt so they
   stay in scope for review, not just for you.

   This matters because the backlog and its design docs brief the *next* task. A backlog
   that still lists a resolved blocker, or describes a mechanism that has since changed,
   does not just read as stale — later work gets built on it.

7. **Commit.** Once a task is checked off, stage and commit the changes for that task alone.
   Use one commit per task, not one commit at the end. Follow the repo's normal commit
   conventions and the standing git-safety rules: review what is staged, never use
   `git add -A`, and never use `--no-verify`. Base the commit message on the task's own
   text.

   End the commit message with a trailer that records how the task converged, so review
   round-trips are queryable later without archaeology through commit prose. Add
   `Review-rounds: N`, where N counts full implement/review round-trips the task took (use 1
   if the reviewer was clean on the first pass). Add `Self-fixed: yes` if step 5's self-fix
   path was used for the trailing finding instead of spawning another round.

8. **Log the findings.** Append every Critical and Major finding this task raised to the
   findings log, one line each: `<task name> | SEVERITY | file | the finding`. The log
   lives at `.work-backlog-findings.md`, beside the backlog file. Create it if it is
   absent.

   The final step of this command looks across every finding in the run. Your own context
   is not a safe place to keep them. A long run can compact, and single-task mode starts
   each task in a new session. The log is the only durable record.

9. **Move to the next unchecked task** and repeat from step 1.

## Single-task mode

A caller can ask you to work exactly one task and then stop. The driver script
`scripts/run-backlog.sh` does this, so each task gets a clean context.

In that mode:

- Work only the first unchecked task. Run its full loop, steps 1 through 8.
- Stop after the commit. Do not start the next task.
- Do not run the standards feedback pass. The driver runs it once at the end.
- Report in under 200 words. Name the task, the review round count, and any escalation.

Everything the next session needs is already on disk. The checkbox records what is done.
The commit records the change. The findings log records what review caught.

Do not write a handoff note.

## Between tasks

- Do not batch multiple tasks into one implement/review pair. Each task gets its own full
  loop, so the reviewer's Critical/Major findings map to exactly the change that produced
  them.
- A task's own text can say it depends on a later or earlier task, or the implementer can
  flag a blocking ambiguity mid-task. In either case, stop and ask the user. Do not guess.
  This mirrors the "don't guess on ambiguous business details, ask" rule already in the
  ADF/dbt agents.

## Lightweight path for low-risk tasks

Not every task needs the full implementer→reviewer ceremony. Before you start step 1 for a
task, judge whether it qualifies as low-risk:

- Small, additive, and mechanically simple: a new config/options class, a constant, a small
  pure helper, a doc/comment sweep, or wiring an existing type into DI. It must not be new
  business logic, a change to an existing code path, or anything touching resilience, auth,
  money, dates/timezones, or external I/O.
- Fully scoped by the task text itself, with no ambiguity to resolve.
- Low blast radius: a mistake here is cheap to spot and cheap to fix.

If a task qualifies, skip the implementer subagent and write it yourself directly (Read/
Edit/Write). Then run the step 2 build gate and send it to the reviewer subagent once (step
3) before checking it off. The build gate and the reviewer pass both stay mandatory; only
the implementer round is skipped. If the reviewer comes back with a Critical/Major finding,
escalate to the full implementer/reviewer loop from that point. Do not continue to
self-fix — a real finding on a task you judged "low-risk" means the judgment call was
wrong, not that the fix should stay informal.

When in doubt, do not take the shortcut. The full loop is the default; this is the
exception.

## When the backlog is exhausted

Report a summary: which tasks were completed, how many review round-trips each took, any
task escalated to the user without converging, and any Minor findings left un-addressed
across the run (grouped, not listed one at a time).

## After the backlog is exhausted: feed findings back into the standard

Read `.work-backlog-findings.md`. Step 8 logged every Critical and Major finding there.

Use the log, not your memory of the run. The log is complete. Your context is not.

Look across every finding in the log, not just the final task's. The same class of issue
can be flagged on more than one task. It can also be the kind of mistake likely to recur
on future backlogs. Either case is a gap in the standard or in the implementer's own
instructions, not just a diff to fix and move past.

Delete the log once the user accepts or rejects your proposed edits.

For each recurring finding:

- If the implementer got a rule wrong or missed it entirely, propose an edit to the
  ADR/standard file itself, not the agent file. Both implementer and reviewer read the same
  standard, so one edit closes the gap for both roles. Phrase it as a direct rule with its
  rationale, for example "Do X. (Not Y — Y causes Z.)", not a narrative about what happened.
- If the finding is specific to how this implementer tends to fail — a shortcut it defaults
  to, or a check it skips even though the standard already covers it — propose the edit to
  the implementer agent's own file instead, in whatever section already lists gotchas or
  common mistakes.

Present these as proposed edits with the specific file and wording. Apply them once the user
confirms. Do not silently rewrite the standard files without approval — they are shared
across every future run, not just this backlog.

## Notes

- This command intentionally does not use agent teams or the `TaskCompleted`/`TeammateIdle`
  hooks. Those require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and are built for teammates
  that coordinate with each other directly. Here the main session is the sole coordinator.
  This is simpler and sufficient: implementer and reviewer never need to know about each
  other, only about the current task and the current findings.
- Both subagent calls must run in the foreground (not `run_in_background: true`). The loop
  cannot decide whether to continue or move to the next task without each result in hand
  first.
