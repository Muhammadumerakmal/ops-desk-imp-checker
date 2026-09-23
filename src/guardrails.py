"""Input guardrail — FR-8.

A guardrail runs *before* the Desk's model. If the student's question is unrelated to
the bootcamp, the guardrail trips a tripwire; the SDK raises
`InputGuardrailTripwireTriggered`, which `main.py`/`app.py` catch and answer with a
courteous refusal. The Desk's model — the expensive one that would have written the
answer — never runs, so a blocked question costs nothing at that model (provable from
the trace: no Desk generation span appears).

Classification is done by a small, cheap guardrail agent, kept deliberately separate
from the Desk so its cost and behaviour are isolated.
"""

from __future__ import annotations

from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrail,
    RunContextWrapper,
    Runner,
)
from pydantic import BaseModel

from .config import make_model


class TopicCheck(BaseModel):
    is_about_bootcamp: bool
    reason: str


_guardrail_agent = Agent(
    name="Topic Guardrail",
    instructions=(
        "You decide whether a message is about a coding bootcamp — its courses, "
        "assignments, deadlines, schedules, policies, attendance, or careers/jobs for "
        "its students. Set is_about_bootcamp=true for anything plausibly about the "
        "bootcamp or a student's studies or career. Set it false for clearly "
        "unrelated topics: weather, sports, cooking, celebrities, general trivia, "
        "politics, or requests for code/help unrelated to a course. Give a short "
        "reason."
    ),
    model=make_model(),
    output_type=TopicCheck,
)


async def _topic_guardrail(
    ctx: RunContextWrapper, agent: Agent, user_input
) -> GuardrailFunctionOutput:
    result = await Runner.run(_guardrail_agent, user_input, context=ctx.context)
    check: TopicCheck = result.final_output
    return GuardrailFunctionOutput(
        output_info=check,
        # Trip the wire when the message is NOT about the bootcamp.
        tripwire_triggered=not check.is_about_bootcamp,
    )


# The object attached to the Desk's `input_guardrails`.
topic_guardrail = InputGuardrail(guardrail_function=_topic_guardrail, name="on_topic")

REFUSAL_MESSAGE = (
    "I can only help with questions about this bootcamp — your courses, assignments, "
    "schedules, policies, or careers. Please ask me something about that."
)
