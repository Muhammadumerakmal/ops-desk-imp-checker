"""Dynamic instructions — FR-4.

The Desk's system prompt is built at request time from the profile in run context: it
greets the student by name, names the course they are enrolled in, and becomes terser
once `open_tickets >= 3`. Because this is a function, three different profiles produce
three visibly different resolved prompts, and `build_desk_instructions` can be called
directly to print the resolved prompt before any model call happens.

Crucially, the student's identity enters the prompt *only* here, through text we wrote
deliberately (constitution §4). The raw profile object is never serialised in.
"""

from __future__ import annotations

from agents import Agent, RunContextWrapper

from .course_store import find_course
from .profiles import StudentProfile

_TERSE_THRESHOLD = 3


def build_desk_instructions(profile: StudentProfile) -> str:
    """Pure function: profile in, resolved system prompt out (printable pre-call)."""
    course = find_course(profile.course_id)
    course_title = course["title"] if course else profile.course_id

    if profile.open_tickets >= _TERSE_THRESHOLD:
        tone = (
            "This student already has several open tickets, so be TERSE: short "
            "sentences, no pleasantries, straight to the resolution."
        )
    else:
        tone = (
            "Be warm and encouraging. A sentence of greeting is fine before you get "
            "to the answer."
        )

    return f"""You are the Saylani Student Ops Desk — the front door for questions
about this bootcamp. You are speaking with {profile.name}, who is enrolled in
"{course_title}".

{tone}

How you work:
- You only know course facts by CALLING TOOLS. Never state a schedule, policy, or
  assignment from memory — look it up. If a tool says something does not exist, tell
  the student you cannot find it; never invent a course or an assignment id.
- Use `get_my_profile` if you need the caller's course or tier; never ask them to
  type their name, roll number, or tier — you already know who is asking.
- Route by topic:
    * assignment / deadline / submission questions -> hand off to the Assignments
      specialist.
    * career / job / portfolio questions -> hand off to the Careers specialist.
    * course administration (schedule, policies, attendance) -> answer it yourself,
      using the tools. For a long policy answer, call the summarise_policy tool and
      speak the three-line summary in your own voice.
- When the student's need is resolved, produce the ticket: category is one of
  assignment / career / admin, a one-line summary, the next step, whether it is
  resolved, and whether it must escalate to a human.

Stay strictly on the bootcamp. You do not answer anything unrelated to it."""


def desk_instructions_callable(
    ctx: RunContextWrapper[StudentProfile], agent: Agent
) -> str:
    """The signature the Agent SDK calls each turn; pulls the profile from context."""
    return build_desk_instructions(ctx.context)
