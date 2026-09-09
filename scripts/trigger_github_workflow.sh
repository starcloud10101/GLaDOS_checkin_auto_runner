#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

REPO="starcloud10101/GLaDOS_checkin_auto_runner"
WORKFLOW_FILE="runGladosAction.yml"
GH_BIN="${GLADOS_GH_BIN:-/opt/homebrew/bin/gh}"
WORKFLOW_API="repos/$REPO/actions/workflows/$WORKFLOW_FILE"

log() {
  print -r -- "$(TZ=Asia/Taipei date '+%Y-%m-%d %H:%M:%S') $*" >&2
}

if [[ "${1:-}" == "--scheduled" && "$(TZ=Asia/Taipei date '+%H%M')" < "0930" ]]; then
  log "Before the daily check-in window; waiting until 09:30 Taipei time."
  exit 0
fi

# Retry reads and the idempotent enable operation, not dispatch POSTs.
api_retry() {
  local attempt result
  for attempt in 1 2 3; do
    if result="$("$GH_BIN" api "$@" 2>&1)"; then
      print -r -- "$result"
      return 0
    fi
    log "GitHub API attempt $attempt/3 failed: $result"
    if (( attempt < 3 )); then
      sleep $((attempt * 2))
    fi
  done
  return 1
}

workflow_state="$(api_retry "$WORKFLOW_API" --jq .state)" || exit 1
case "$workflow_state" in
  disabled_inactivity)
    log "Workflow disabled due to inactivity; restoring it."
    api_retry --method PUT "$WORKFLOW_API/enable" >/dev/null || exit 1
    workflow_state="$(api_retry "$WORKFLOW_API" --jq .state)" || exit 1
    ;;
esac
if [[ "$workflow_state" != active ]]; then
  log "Workflow state is $workflow_state; no dispatch or automatic override."
  exit 1
fi

runs_json="$(api_retry "$WORKFLOW_API/runs?per_page=100" \
  --jq '{workflow_runs: [.workflow_runs[] | {created_at, status, conclusion}]}')" || exit 1

if RUNS_JSON="$runs_json" /usr/bin/python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone, timedelta

tz = timezone(timedelta(hours=8))
today = datetime.now(tz).date()
try:
    runs = json.loads(os.environ["RUNS_JSON"])["workflow_runs"]
    if not isinstance(runs, list):
        raise ValueError("workflow_runs must be a list")
except (KeyError, ValueError, TypeError):
    sys.exit(2)

try:
    attempts_today = 0
    for run in runs:
        created = run["created_at"]
        created_at = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(tz)
        if created_at.date() != today:
            continue
        attempts_today += 1
        if run.get("conclusion") == "success" or run.get("status") in {
            "queued", "in_progress", "requested", "waiting", "pending"
        }:
            sys.exit(0)
except (KeyError, ValueError, TypeError, AttributeError):
    sys.exit(2)

if attempts_today >= 6:
    sys.exit(3)
sys.exit(1)
PY
then
  log "Today's workflow succeeded or is pending; skipping fallback trigger."
  exit 0
else
  decision=$?
  if (( decision == 3 )); then
    log "Six runs attempted today without confirmation; human or Codex review is needed."
    exit 1
  fi
  if (( decision != 1 )); then
    log "Cannot validate workflow run data; refusing to guess."
    exit 1
  fi
fi

if "$GH_BIN" api --method POST "$WORKFLOW_API/dispatches" -f ref=master; then
  log "Triggered $WORKFLOW_FILE in $REPO; completion still needs verification."
else
  log "Dispatch failed or its result is unknown; check GitHub runs before retrying."
  exit 1
fi
