"""Function tools — FR-2 (course data), FR-3 (profile), FR-9 (gating & stopping).

Every tool returns a sentence the model can act on, even on bad data (NFR-4). None of
them raise into the runner.
"""

from __future__ import annotations

from agents import (
    Agent,
    AgentBase,
    RunContextWrapper,
    function_tool,
)

from . import course_store
from .models import Ticket
from .profiles import StudentProfile


# --------------------------------------------------------------------------- #
# FR-2 — course knowledge, reachable only through tools
# --------------------------------------------------------------------------- #
@function_tool
def list_courses() -> str:
    """List every course the bootcamp offers, by id and title."""
    courses = course_store.all_courses()
    if not courses:
        return "There are no courses on record right now."
    return "\n".join(f"- {c['id']}: {c['title']}" for c in courses)


@function_tool
def get_course(course_id: str) -> str:
    """Fetch one course's schedule and policies by its id.

    Args:
        course_id: The course id, e.g. "agentic-ai-w4".
    """
    course = course_store.find_course(course_id)
    if course is None:
        return (
            f"There is no course with id '{course_id}'. Use list_courses to see the "
            "valid ids."
        )
    policies = "; ".join(f"{k}: {v}" for k, v in course.get("policies", {}).items())
    return (
        f"{course['title']} ({course['id']}). Schedule: {course['schedule']}. "
        f"Policies: {policies}."
    )


@function_tool
def lookup_assignment(course_id: str, assignment_id: str) -> str:
    """Look up one assignment by its id within a course.

    Args:
        course_id: The course id, e.g. "agentic-ai-w4".
        assignment_id: The assignment id, e.g. "a3".
    """
    if course_store.find_course(course_id) is None:
        return f"There is no course with id '{course_id}', so no assignments to check."
    assignment = course_store.find_assignment(course_id, assignment_id)
    if assignment is None:
        return (
            f"There is no assignment '{assignment_id}' in {course_id}. I cannot "
            "invent one — please check the id."
        )
    return (
        f"Assignment {assignment['id']}: \"{assignment['title']}\", "
        f"due {assignment['due']} (course {course_id})."
    )


# --------------------------------------------------------------------------- #
# FR-3 — the student is in context, never in the prompt
# The first parameter is the run context. The SDK omits it from the generated
# tool schema, so there is no "wrapper" parameter for the model to fill.
# --------------------------------------------------------------------------- #
@function_tool
def get_my_profile(ctx: RunContextWrapper[StudentProfile]) -> str:
    """Return the current student's enrolled course and tier."""
    p = ctx.context
    return (
        f"You are enrolled in course '{p.course_id}' on the {p.tier} tier, with "
        f"{p.open_tickets} open ticket(s)."
    )


# --------------------------------------------------------------------------- #
# FR-9a — a tool only OFFERED to scholarship-tier students (absent, not refused)
# --------------------------------------------------------------------------- #
def _is_scholarship(ctx: RunContextWrapper[StudentProfile], agent: AgentBase) -> bool:
    return getattr(ctx.context, "tier", "regular") == "scholarship"


@function_tool(is_enabled=_is_scholarship)
def apply_scholarship_extension(assignment_id: str, days: int) -> str:
    """Grant a scholarship student a deadline extension on an assignment.

    Args:
        assignment_id: The assignment to extend, e.g. "a3".
        days: How many extra days to grant (1-7).
    """
    days = max(1, min(days, 7))
    return (
        f"A scholarship extension of {days} day(s) has been recorded for assignment "
        f"{assignment_id}. The student should still submit as early as they can."
    )


# --------------------------------------------------------------------------- #
# FR-9b — a close_ticket tool that ENDS the run the moment it is called.
# Wired on the Desk with tool_use_behavior=StopAtTools(["close_ticket"]), so this
# tool's return value becomes the run's final_output. It returns a Ticket, so
# type(final_output) is Ticket still holds (FR-7).
# --------------------------------------------------------------------------- #
@function_tool
def close_ticket(
    category: str,
    summary: str,
    next_step: str,
    resolved: bool,
    escalate: bool,
) -> Ticket:
    """Close the conversation and file the ticket. Ends the run immediately.

    Args:
        category: One of "assignment", "career", or "admin".
        summary: One line describing what the student needed.
        next_step: The single next action for the student or staff.
        resolved: True if the student's need is fully handled.
        escalate: True if a human must follow up.
    """
    cat = category if category in ("assignment", "career", "admin") else "admin"
    return Ticket(
        category=cat,
        summary=summary,
        next_step=next_step,
        resolved=resolved,
        escalate=escalate,
    )
