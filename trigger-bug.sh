#!/usr/bin/env bash
set -euo pipefail

# Simulate a Datadog/Sentry production alert hitting the self-healing pipeline.
# Fires a repository_dispatch event to the control plane, which triggers
# handle-telemetry.yml → handle-telemetry.py → bug spec in features/active/.

GH_REPO="ChristianJensen/tasks-control-plane"

echo "Simulating production alert..."
echo ""
echo "  Error:    TypeError: Cannot read properties of undefined (reading 'id')"
echo "  Service:  api"
echo "  Severity: critical"
echo "  Impact:   Task creation and listing failing for all users"
echo ""

gh api "repos/${GH_REPO}/dispatches" \
  --method POST \
  --input - <<'JSON'
{
  "event_type": "telemetry_alert",
  "client_payload": {
    "error_message": "TypeError: Cannot read properties of undefined (reading id)",
    "file": "src/app.js",
    "service": "api",
    "severity": "critical",
    "user_impact": "Task creation and listing failing for all users — 47 errors in last 15 minutes",
    "stack_trace": "TypeError: Cannot read properties of undefined (reading id)\n    at taskWithCount (src/app.js:34:30)\n    at GET /tasks (src/app.js:109:25)"
  }
}
JSON

echo "Alert dispatched to ${GH_REPO}."
echo "Watch pipeline: https://github.com/${GH_REPO}/actions"
