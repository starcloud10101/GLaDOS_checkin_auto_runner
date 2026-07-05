#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

REPO="starcloud10101/GLaDOS_checkin_auto_runner"
WORKFLOW_NAME="开始每日签到"
WORKFLOW_FILE="runGladosAction.yml"

cd "/Users/nebula/GLaDOS_checkin_auto"

runs_json="$(gh run list \
  --repo "$REPO" \
  --workflow "$WORKFLOW_NAME" \
  --limit 20 \
  --json status,conclusion,createdAt,event)"
export RUNS_JSON="$runs_json"

if /usr/bin/python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone, timedelta

tz = timezone(timedelta(hours=8))
today = datetime.now(tz).date()
runs = json.loads(os.environ.get("RUNS_JSON", "[]"))

for run in runs:
    created = run.get("createdAt")
    if not created:
        continue
    created_at = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(tz)
    if created_at.date() != today:
        continue
    if run.get("conclusion") == "success" or run.get("status") in {"queued", "in_progress"}:
        sys.exit(0)

sys.exit(1)
PY
then
  echo "$(date '+%Y-%m-%d %H:%M:%S') Already checked in or running today; skipping fallback trigger."
  exit 0
fi

gh workflow run "$WORKFLOW_FILE" --repo "$REPO" --ref master
echo "$(date '+%Y-%m-%d %H:%M:%S') Triggered $WORKFLOW_FILE in $REPO."
