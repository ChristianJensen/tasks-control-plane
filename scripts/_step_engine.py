"""Generic deterministic step engine for orchestrated agentic workflows.

Walks through a WorkflowDef's ordered steps, injecting a complete_step tool
for interactive phases and detecting write_file for autonomous phases.
Both CLI and web consume this identically.

Usage:
    from _step_engine import StepDef, WorkflowDef, StepEngine

    steps = [
        StepDef(id="interview", label="Interview", type="interactive",
                prompt="...", kickoff="Begin the interview."),
        StepDef(id="draft", label="Write Draft", type="autonomous",
                prompt="...", kickoff="Write the draft now."),
        StepDef(id="finalize", label="Finalize", type="no-ai",
                prompt="", kickoff=""),
    ]
    workflow = WorkflowDef(name="My Workflow", steps=steps)
    engine = StepEngine(workflow, config={"idea": "...", "slug": "..."})
"""

from dataclasses import dataclass, field
import logging
import re

logger = logging.getLogger(__name__)


# ── Data model ───────────────────────────────────────────────────

@dataclass
class StepDef:
    """A single step in a workflow.

    Attributes:
        id:      Unique identifier, e.g. "interview", "refine-3"
        label:   Human-readable label, e.g. "Refine: Scope Boundaries"
        type:    "interactive" | "autonomous" | "no-ai"
        prompt:  System prompt template (may contain {placeholders})
        kickoff: Initial user message to start the step (may contain {placeholders})
    """
    id: str
    label: str
    type: str       # "interactive" | "autonomous" | "no-ai"
    prompt: str
    kickoff: str


@dataclass
class WorkflowDef:
    """An ordered sequence of steps that define a workflow.

    Attributes:
        name:  Human-readable workflow name, e.g. "Feature Specification"
        steps: Ordered list of StepDefs — executed exactly in this order
    """
    name: str
    steps: list = field(default_factory=list)


# ── Tool definition ──────────────────────────────────────────────

COMPLETE_STEP_TOOL = {
    "name": "complete_step",
    "description": (
        "Signal that the current workflow step is complete. "
        "Call this ONLY after you have finished all work for this step."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of what was accomplished in this step",
            }
        },
        "required": ["summary"],
    },
}

COMPLETE_STEP_INSTRUCTION = (
    "\n\nWhen you have completed all work for this step, call the "
    "`complete_step` tool with a brief summary of what was accomplished."
)


# ── Engine ───────────────────────────────────────────────────────

class StepEngine:
    """Generic deterministic step orchestrator.

    Walks through a WorkflowDef's steps in order.
    Provides complete_step tool injection and completion detection.
    Both CLI and web consume this identically.
    """

    def __init__(self, workflow: WorkflowDef, config: dict):
        """
        Args:
            workflow: The workflow definition (name + ordered steps)
            config:   Key-value pairs for formatting prompt templates
        """
        self.workflow = workflow
        self.config = config
        self.current_index = 0
        self.step_complete_signaled = False
        self.write_file_called = False
        self.max_turns_per_step = 25
        self.turn_count = 0

    # ── Properties ───────────────────────────────────────────

    @property
    def current_step(self) -> StepDef:
        """The step currently being executed."""
        if self.current_index >= len(self.workflow.steps):
            return None
        return self.workflow.steps[self.current_index]

    @property
    def visible_steps(self) -> int:
        """Count of steps the user experiences (excludes no-ai)."""
        return sum(1 for s in self.workflow.steps if s.type != "no-ai")

    @property
    def visible_index(self) -> int:
        """1-based index of current step among visible steps."""
        count = 0
        for i, s in enumerate(self.workflow.steps):
            if s.type != "no-ai":
                count += 1
            if i == self.current_index:
                return count
        return count

    @property
    def progress(self) -> str:
        """Human-readable progress string, e.g. 'Step 3/9: Refine: Assumptions'."""
        step = self.current_step
        if step is None:
            return f"{self.workflow.name}: Complete"
        return f"Step {self.visible_index}/{self.visible_steps}: {step.label}"

    @property
    def is_complete(self) -> bool:
        """True when all steps have been executed."""
        return self.current_index >= len(self.workflow.steps)

    # ── Prompt & tools ───────────────────────────────────────

    def get_system_prompt(self) -> str:
        """Build the system prompt for the current step.

        Formats the step's prompt template with config values.
        For interactive steps, appends the complete_step instruction.
        """
        step = self.current_step
        if step is None:
            return ""

        prompt = _safe_format(step.prompt, self.config)

        if step.type == "interactive":
            prompt += COMPLETE_STEP_INSTRUCTION

        return prompt

    def get_tools(self, base_tools: list) -> list:
        """Return base_tools, plus complete_step for interactive steps.

        Args:
            base_tools: The standard tool list (write_file, read_file, etc.)
        """
        tools = list(base_tools)
        step = self.current_step
        if step and step.type == "interactive":
            tools.append(COMPLETE_STEP_TOOL)
        return tools

    def get_kickoff_message(self) -> str:
        """Return the initial user message for the current step."""
        step = self.current_step
        if step is None:
            return ""
        return _safe_format(step.kickoff, self.config)

    # ── Completion detection ─────────────────────────────────

    def handle_tool_call(self, name: str, input_data: dict):
        """Intercept complete_step tool calls.

        Returns a result string if handled, None otherwise.
        The host should call this before dispatching to its own tool handlers.
        """
        if name == "complete_step":
            self.step_complete_signaled = True
            summary = input_data.get("summary", "")
            logger.info("Step '%s' complete: %s", self.current_step.id, summary)
            return f"Step '{self.current_step.label}' marked complete."
        return None

    def notify_write_file(self):
        """Called by the host when the AI successfully uses write_file."""
        self.write_file_called = True

    def on_turn_end(self) -> bool:
        """Called after each AI turn. Returns True if the step should advance.

        For interactive steps: advances when complete_step was called.
        For autonomous steps: advances when write_file was called.
        Also enforces max_turns_per_step safety net.
        """
        step = self.current_step
        if step is None:
            return False

        self.turn_count += 1

        if step.type == "interactive":
            if self.step_complete_signaled:
                return True
        elif step.type == "autonomous":
            if self.write_file_called:
                return True

        # Safety net: auto-advance after too many turns
        if self.turn_count >= self.max_turns_per_step:
            logger.warning(
                "Step '%s' hit max turns (%d) — auto-advancing.",
                step.id, self.max_turns_per_step,
            )
            return True

        return False

    # ── Step advancement ─────────────────────────────────────

    def advance(self):
        """Move to the next step. Returns the new StepDef, or None if done.

        Resets per-step state (flags, turn count).
        """
        self.step_complete_signaled = False
        self.write_file_called = False
        self.turn_count = 0
        self.current_index += 1

        if self.current_index >= len(self.workflow.steps):
            return None
        return self.workflow.steps[self.current_index]


# ── Helpers ──────────────────────────────────────────────────────

def _safe_format(template: str, config: dict) -> str:
    """Format a template string, ignoring missing keys.

    Uses str.format_map with a defaultdict-like fallback so that
    {placeholders} not in config are left as-is rather than raising.
    """
    if not template:
        return ""

    class _SafeDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    try:
        return template.format_map(_SafeDict(config))
    except (ValueError, IndexError):
        # If the template has complex format specs that break, return as-is
        return template
