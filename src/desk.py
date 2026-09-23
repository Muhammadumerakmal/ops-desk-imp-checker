"""Agent assembly — FR-5, FR-6, FR-7, FR-8, FR-9, FR-10.

Builds, in one place:
  * a single base specialist, cloned into an Assignments specialist (cold) and a
    Careers specialist (warm) — FR-5;
  * a Summariser exposed as a tool, not a handoff — FR-6;
  * the Desk (triage) agent that owns the conversation, carries the input guardrail
    (FR-8), the scholarship/close_ticket/ceiling controls (FR-9), the data + profile
    tools (FR-2/FR-3), dynamic instructions (FR-4), and `output_type=Ticket` (FR-7).

The Assignments specialist is where the agent-level hooks (FR-10) attach.
"""

from __future__ import annotations

from agents import Agent, StopAtTools, handoff

from .config import BASE_MODEL_SETTINGS, make_model
from .guardrails import topic_guardrail
from .hooks import SpecialistAgentHooks
from .instructions import desk_instructions_callable
from .models import Ticket
from .tools import (
    apply_scholarship_extension,
    close_ticket,
    get_course,
    get_my_profile,
    list_courses,
    lookup_assignment,
)
from agents import ModelSettings


# --------------------------------------------------------------------------- #
# FR-5 — one base agent, cloned into two specialists.
# The base owns the shared model; the clones inherit it without restating it.
# --------------------------------------------------------------------------- #
_base_specialist = Agent(
    name="Base Specialist",
    instructions="You are a specialist at the Saylani bootcamp Ops Desk.",
    model=make_model(),  # shared model — clones do NOT set their own
    model_settings=BASE_MODEL_SETTINGS,
    tools=[get_my_profile, get_course, lookup_assignment, list_courses],
)

# Attach agent-level hooks (FR-10) to exactly ONE specialist.
assignments_hooks = SpecialistAgentHooks(label="assignments")

assignments_specialist = _base_specialist.clone(
    name="Assignments Specialist",
    handoff_description="Handles assignment, deadline, and submission questions.",
    instructions=(
        "You are the Assignments specialist. Answer questions about assignments, "
        "deadlines, and submission policies. Be COLD and FACTUAL: look every fact up "
        "with your tools, give the due date and the late-submission policy plainly, "
        "and do not pad. Never invent an assignment id."
    ),
    # Cold and factual: deterministic (differs from the base only in instructions
    # and settings, per FR-5).
    model_settings=ModelSettings(temperature=0.0, max_tokens=500),
    hooks=assignments_hooks,
)

careers_specialist = _base_specialist.clone(
    name="Careers Specialist",
    handoff_description="Handles career, job, and portfolio questions.",
    instructions=(
        "You are the Careers specialist. Answer questions about jobs, portfolios, "
        "interviews, and career direction for bootcamp students. Be WARM and "
        "encouraging — motivate the student while staying practical and specific."
    ),
    # Warmer voice: higher temperature (deliberate, defensible per FR-5).
    model_settings=ModelSettings(temperature=0.7, max_tokens=500),
)


# --------------------------------------------------------------------------- #
# FR-6 — a Summariser exposed as a TOOL (not a handoff).
# The Desk calls it, gets three lines back, and keeps speaking in its own voice.
# --------------------------------------------------------------------------- #
_summariser = Agent(
    name="Summariser",
    instructions=(
        "You condense a policy explanation into exactly three short lines. No "
        "preamble, no closing — just three lines a student can skim."
    ),
    model=make_model(),
    model_settings=ModelSettings(temperature=0.0, max_tokens=160),
)

summarise_policy_tool = _summariser.as_tool(
    tool_name="summarise_policy",
    tool_description="Condense a long policy answer into three short lines.",
)


# --------------------------------------------------------------------------- #
# The Desk — owns the conversation. Everything hangs off here.
# --------------------------------------------------------------------------- #
def build_desk() -> Agent:
    """Construct the Desk agent. Called once per session (FR-12) or per process."""
    return Agent(
        name="Ops Desk",
        # FR-4 — instructions rebuilt each turn from the profile in context.
        instructions=desk_instructions_callable,
        # FR-1 — model set on the agent.
        model=make_model(),
        model_settings=BASE_MODEL_SETTINGS,
        # FR-2 / FR-3 / FR-9 — data tools, profile tool, scholarship-only tool,
        # close_ticket, plus the Summariser-as-tool (FR-6).
        tools=[
            list_courses,
            get_course,
            lookup_assignment,
            get_my_profile,
            apply_scholarship_extension,  # FR-9a: only offered to scholarship tier
            close_ticket,  # FR-9b: ends the run
            summarise_policy_tool,  # FR-6
        ],
        # FR-5 — hand the conversation to whichever specialist fits.
        handoffs=[handoff(assignments_specialist), handoff(careers_specialist)],
        # FR-8 — refuse off-topic before the Desk model runs.
        input_guardrails=[topic_guardrail],
        # FR-7 — the resolved output is a typed Ticket.
        output_type=Ticket,
        # FR-9b — calling close_ticket ends the run; its return is the final output.
        tool_use_behavior=StopAtTools(stop_at_tool_names=["close_ticket"]),
    )
