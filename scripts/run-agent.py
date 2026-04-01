#!/usr/bin/env python3
"""Generic agent runner for Relay.

Loads an agent definition from process/agents/<type>.md and runs it as an
isolated headless process. Results are optionally posted to a callback URL.

Usage:
    python3 run-agent.py --agent-type triage --context '{"title":"..."}' \
        --cp-dir /path/to/control-plane \
        [--callback-url http://localhost:7433/api/inbox/1/triage-result] \
        [--budget 1.00]

This script is a thin CLI surface over AgentRuntime. All tool execution
and conversation management lives in _agent_runtime.py.
"""

import argparse
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from _agent_runtime import (
    AgentRuntime, load_agent_def, parse_service_catalog, resolve_api_key,
)
import _workflow as wf


# ── Result extraction and delivery ───────────────────────────────

def extract_json_report(text):
    """Extract a JSON code block from the agent's response."""
    match = re.search(r'```json\s*\n(\{.*?\})\s*\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def post_callback(url, payload):
    """POST a JSON payload to a callback URL."""
    import urllib.request
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"  Callback: {resp.status} {resp.reason}")
    except Exception as e:
        print(f"  Callback failed: {e}")


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Relay generic agent runner")
    parser.add_argument("--agent-type", required=True, help="Agent type (e.g. triage)")
    parser.add_argument("--context", required=True, help="Context JSON or plain text for the agent")
    parser.add_argument("--cp-dir", required=True, help="Control plane directory")
    parser.add_argument("--callback-url", help="URL to POST results to on completion")
    parser.add_argument("--budget", type=float, help="Max budget in USD")
    args = parser.parse_args()

    cp_dir = os.path.abspath(args.cp_dir)
    relay_dir = None

    # Resolve RELAY_DIR: check .relay-config for relay-path, or fall back to parent of scripts dir
    config_path = os.path.join(cp_dir, ".relay-config")
    if os.path.exists(config_path):
        with open(config_path) as f:
            for line in f:
                m = re.match(r"^relay-path:\s*(.+)", line)
                if m:
                    relay_dir = m.group(1).strip()
                    break
    if not relay_dir:
        relay_dir = os.path.dirname(os.path.dirname(SCRIPT_DIR))

    agent_def = load_agent_def(args.agent_type, relay_dir)
    repo_paths, _ = parse_service_catalog(cp_dir)

    api_key = resolve_api_key(cp_dir)
    if not api_key:
        print("Error: No Anthropic API key found.")
        sys.exit(1)

    # Parse context — try JSON, fall back to plain text
    try:
        context_obj = json.loads(args.context)
        context_text = json.dumps(context_obj, indent=2)
    except (json.JSONDecodeError, TypeError):
        context_text = args.context

    print(f"{'─' * 60}")
    print(f"  Relay Agent Runner")
    print(f"{'─' * 60}")
    print(f"  Agent: {agent_def['name']}")
    print(f"  Tools: {agent_def['tools']}")
    print()

    model = wf.resolve_model(cp_dir, role="implementer")
    runtime = AgentRuntime(agent_def, cp_dir, repo_paths, api_key, model=model)
    start_time = time.time()
    result_text, input_tokens, output_tokens = runtime.run_headless(context_text)
    duration = time.time() - start_time

    # Print agent output
    for line in result_text.strip().split("\n"):
        print(f"  {line}")

    print()
    print(f"  Done in {duration:.1f}s | {input_tokens} in / {output_tokens} out tokens")

    # Extract structured output if agent produces JSON
    if agent_def["output"] == "json":
        report = extract_json_report(result_text)
        if report and args.callback_url:
            print()
            post_callback(args.callback_url, report)
        elif report:
            print()
            print("  Report (no callback URL provided):")
            print(f"  {json.dumps(report, indent=2)}")
        else:
            print()
            print("  Warning: Agent did not produce a valid JSON report.")
            if args.callback_url:
                post_callback(args.callback_url, {"error": "no_json_report", "raw_text": result_text[-2000:]})
    elif args.callback_url:
        post_callback(args.callback_url, {"text": result_text})

    print(f"{'─' * 60}")


if __name__ == "__main__":
    main()
