"""Feature Specification workflow definition for the step engine.

Defines the 10-step spec creation workflow as a WorkflowDef.
Prompts are imported from spec.py (the canonical source).

Usage:
    from _spec_workflow import SPEC_WORKFLOW, build_spec_config
    from _step_engine import StepEngine

    config = build_spec_config(idea="...", slug="...", ...)
    engine = StepEngine(SPEC_WORKFLOW, config)
"""

import os
import sys

# Ensure scripts dir is on path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _step_engine import StepDef, WorkflowDef


def _load_prompts():
    """Import prompt constants from spec.py."""
    import importlib.util
    spec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec.py")
    loader = importlib.util.spec_from_file_location("spec_mod", spec_path)
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    return mod


_spec = _load_prompts()

# ── Step definitions ─────────────────────────────────────────────

SPEC_STEPS = [
    StepDef(
        id="interview",
        label="Interview",
        type="interactive",
        prompt=_spec.INTERVIEW_PHASE_PROMPT,
        kickoff="Begin. Interview me about this feature.",
    ),
    StepDef(
        id="draft",
        label="Write Spec",
        type="autonomous",
        prompt=_spec.DRAFT_PHASE_PROMPT,
        kickoff=(
            "Write the feature spec now based on our interview "
            "conversation. The interview transcript is in the "
            "conversation history above."
        ),
    ),
    StepDef(
        id="refine-1",
        label="Refine: Assumptions",
        type="interactive",
        prompt=_spec.REFINE_ROUND_PROMPTS[0],
        kickoff="Begin refinement Round 1: Assumptions. Read the spec and challenge the first assumption.",
    ),
    StepDef(
        id="refine-2",
        label="Refine: Edge Cases",
        type="interactive",
        prompt=_spec.REFINE_ROUND_PROMPTS[1],
        kickoff="Begin refinement Round 2: Edge Cases. Read the spec and stress-test the first edge case.",
    ),
    StepDef(
        id="refine-3",
        label="Refine: Scope Boundaries",
        type="interactive",
        prompt=_spec.REFINE_ROUND_PROMPTS[2],
        kickoff="Begin refinement Round 3: Scope Boundaries. Read the spec and propose the first adjacent feature.",
    ),
    StepDef(
        id="refine-4",
        label="Refine: Architecture",
        type="interactive",
        prompt=_spec.REFINE_ROUND_PROMPTS[3],
        kickoff="Begin refinement Round 4: Architecture Review. Read the spec and challenge the first architectural implication.",
    ),
    StepDef(
        id="refine-5",
        label="Refine: PII/Compliance",
        type="interactive",
        prompt=_spec.REFINE_ROUND_PROMPTS[4],
        kickoff="Begin refinement Round 5: PII / Compliance Review. Read the spec and classify the first data element.",
    ),
    StepDef(
        id="refine-6",
        label="Refine: UX/Interaction",
        type="interactive",
        prompt=_spec.REFINE_ROUND_PROMPTS[5],
        kickoff="Begin refinement Round 6: UX & Interaction Review. Read the spec and challenge the first UX concern.",
    ),
    StepDef(
        id="update",
        label="Update Spec",
        type="autonomous",
        prompt=_spec.UPDATE_PHASE_PROMPT,
        kickoff=(
            "Update the spec with all refinement findings and check "
            "off readiness checklist items. The refinement "
            "conversation is in the history above."
        ),
    ),
    StepDef(
        id="finalize",
        label="Finalize",
        type="no-ai",
        prompt="",
        kickoff="",
    ),
]

SPEC_WORKFLOW = WorkflowDef(name="Feature Specification", steps=SPEC_STEPS)


# ── Config builder ───────────────────────────────────────────────

def build_spec_config(*, idea, slug, execution, priority,
                      total_budget="", epic="", epic_title="",
                      contract="", service_catalog="", template="",
                      code_repo_guidance=""):
    """Build the config dict for formatting spec workflow prompt templates.

    All values are strings. Missing optional values default to empty or placeholder text.
    """
    return {
        "idea": idea,
        "slug": slug,
        "execution": execution,
        "priority": priority,
        "total_budget": total_budget or '""',
        "epic": epic or '""',
        "epic_title": epic_title or '""',
        "contract": contract or "(no contract exists yet)",
        "service_catalog": service_catalog or "(no service catalog found)",
        "template": template,
        "code_repo_guidance": code_repo_guidance,
    }
