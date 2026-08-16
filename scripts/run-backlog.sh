#!/usr/bin/env bash
# Run one work-backlog task per Claude session, so context never carries between tasks.
# State passes between tasks through the backlog checkboxes and git commits, not context.
set -uo pipefail

usage() {
  cat <<'USAGE'
usage: run-backlog.sh <backlog.md> <implementer-agent> <reviewer-agent> [max-tasks]

Runs one fresh `claude -p` session per unchecked task. Stops when the backlog is
empty, when max-tasks is reached, or when a session makes no progress.

env:
  PERMISSION_MODE  passed to --permission-mode (default: acceptEdits).
                   acceptEdits still prompts on Bash, so builds and commits block.
                   Use bypassPermissions only in a sandbox or a throwaway checkout.
  SKIP_FINAL_PASS  set to 1 to skip the standards feedback pass at the end.
USAGE
  exit 2
}

[ $# -lt 3 ] && usage
BACKLOG=$1
IMPL=$2
REV=$3
MAX=${4:-20}
PERMISSION_MODE=${PERMISSION_MODE:-acceptEdits}

[ -f "$BACKLOG" ] || { echo "no such backlog file: $BACKLOG" >&2; exit 2; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "not a git repo" >&2; exit 2; }

# A findings log left over from an unfinished run is not a dirty working tree.
if [ -n "$(git status --porcelain | grep -v '\.work-backlog-findings\.md$')" ]; then
  echo "Working tree is dirty. Commit or stash first." >&2
  exit 2
fi

FINDINGS="$(cd "$(dirname "$BACKLOG")" && pwd)/.work-backlog-findings.md"
[ -f "$FINDINGS" ] || printf '# Findings log\n\nOne line per Critical/Major finding.\n' > "$FINDINGS"

remaining() { grep -c '^[[:space:]]*- \[ \]' "$BACKLOG" 2>/dev/null || true; }

run_claude() {
  claude -p "$1" --permission-mode "$PERMISSION_MODE" --output-format text
}

for ((i = 1; i <= MAX; i++)); do
  before=$(remaining)
  if [ "$before" -eq 0 ]; then
    echo "Backlog complete."
    break
  fi

  head_before=$(git rev-parse HEAD)
  echo "=== session $i, $before task(s) unchecked ==="

  run_claude "/work-backlog $BACKLOG $IMPL $REV

Single-task mode. Work exactly ONE task: the first unchecked item. Run its full
loop through the commit, then stop. Do not start the next task. Do not run the
standards feedback pass. Append every Critical and Major finding raised for this
task to $FINDINGS, one line each, before you commit." | tail -40

  if [ "$(remaining)" -ge "$before" ] && [ "$(git rev-parse HEAD)" = "$head_before" ]; then
    echo "Session $i checked off no task and made no commit. Stopping." >&2
    echo "Read the session output above. The task needs a decision from you." >&2
    exit 1
  fi
done

if [ "$(remaining)" -eq 0 ] && [ "${SKIP_FINAL_PASS:-0}" != "1" ]; then
  echo "=== standards feedback pass ==="
  run_claude "Read $FINDINGS. It logs every Critical and Major finding from a
completed backlog run. Run the 'feed findings back into the standard' step of
~/.claude/commands/work-backlog.md against it. Propose edits. Do not apply them."
fi
