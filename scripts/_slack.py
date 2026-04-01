"""Slack Block Kit messaging for Relay notifications.

Pure functions for building messages + one fire-and-forget sender.
Zero external dependencies — uses urllib.request only.
"""

import json
import urllib.request
import urllib.error


def send_slack_message(webhook_url, blocks, text_fallback):
    """POST a Block Kit message to a Slack incoming webhook.

    Returns True on success, False on failure. Never raises.
    """
    payload = json.dumps({"blocks": blocks, "text": text_fallback}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            return True
    except (urllib.error.URLError, OSError):
        return False


def build_pr_ready_message(repo, pr_url, pr_title, feature=None, acceptance_criteria=None):
    """Build a rich Block Kit message for a PR ready for review.

    Returns (blocks, text_fallback).
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "PR Ready for Review", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Repo:*\n{repo}"},
                {"type": "mrkdwn", "text": f"*Feature:*\n{feature or '—'}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*<{pr_url}|{pr_title}>*"},
        },
    ]

    if acceptance_criteria:
        # Replace markdown checkboxes with checkmark emoji for cleaner Slack rendering
        formatted_ac = acceptance_criteria.replace("- [ ] ", ":white_check_mark: ").replace("- [x] ", ":white_check_mark: ")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Acceptance Criteria:*\n{formatted_ac[:2000]}",
            },
        })

    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Review PR", "emoji": True},
                "url": pr_url,
                "style": "primary",
            }
        ],
    })

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "Relay | Agent completed task"}],
    })

    fallback = f"[{repo}] PR ready for review: {pr_title} — {pr_url}"
    return blocks, fallback


def build_task_event_message(repo, task, event, detail=None):
    """Build a Block Kit message for a task lifecycle event.

    Returns (blocks, text_fallback).
    """
    emoji = {
        "CLAIMED": ":hourglass_flowing_sand:",
        "COMPLETED": ":white_check_mark:",
        "BLOCKED": ":x:",
        "STARTED": ":rocket:",
    }.get(event.upper(), ":information_source:")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{event.upper()}* — `{task}`",
            },
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Relay | {repo}"}],
        },
    ]

    if detail:
        blocks.insert(1, {
            "type": "section",
            "text": {"type": "mrkdwn", "text": detail[:2000]},
        })

    fallback = f"[{repo}] {event}: {task}"
    return blocks, fallback
