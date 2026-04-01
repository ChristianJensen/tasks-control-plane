#!/usr/bin/env python3
"""CLI wrapper for Relay Slack notifications.

Usage:
  slack_notify.py pr-ready --webhook-url URL --repo REPO --pr-url URL --pr-title TITLE [--feature F] [--acceptance A] [--dry-run]
  slack_notify.py task-event --webhook-url URL --repo REPO --task TASK --event EVENT [--detail D] [--dry-run]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _slack


def main():
    parser = argparse.ArgumentParser(description="Send Relay Slack notifications")
    sub = parser.add_subparsers(dest="command", required=True)

    # pr-ready
    pr = sub.add_parser("pr-ready", help="Notify that a PR is ready for review")
    pr.add_argument("--webhook-url", required=True)
    pr.add_argument("--repo", required=True)
    pr.add_argument("--pr-url", required=True)
    pr.add_argument("--pr-title", required=True)
    pr.add_argument("--feature", default=None)
    pr.add_argument("--acceptance", default=None)
    pr.add_argument("--dry-run", action="store_true", help="Print Block Kit JSON instead of sending")

    # task-event
    te = sub.add_parser("task-event", help="Notify a task lifecycle event")
    te.add_argument("--webhook-url", required=True)
    te.add_argument("--repo", required=True)
    te.add_argument("--task", required=True)
    te.add_argument("--event", required=True)
    te.add_argument("--detail", default=None)
    te.add_argument("--dry-run", action="store_true", help="Print Block Kit JSON instead of sending")

    args = parser.parse_args()

    if args.command == "pr-ready":
        blocks, fallback = _slack.build_pr_ready_message(
            repo=args.repo,
            pr_url=args.pr_url,
            pr_title=args.pr_title,
            feature=args.feature,
            acceptance_criteria=args.acceptance,
        )
    elif args.command == "task-event":
        blocks, fallback = _slack.build_task_event_message(
            repo=args.repo,
            task=args.task,
            event=args.event,
            detail=args.detail,
        )

    if args.dry_run:
        print(json.dumps({"blocks": blocks, "text": fallback}, indent=2))
        return

    ok = _slack.send_slack_message(args.webhook_url, blocks, fallback)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
