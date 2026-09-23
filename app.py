"""Chainlit interface — FR-12 (plus FR-8/FR-9/FR-10/FR-11/FR-13 in the browser).

Run:  chainlit run app.py -w

Per-session design:
  * The Desk agent and the StudentProfile are built ONCE, in `on_chat_start`, and
    stored in the per-session store — not rebuilt on every message.
  * Conversation history lives in the same per-session store, so a second message
    refers to the first and is understood.
  * `cl.user_session` is isolated per browser session, so two windows never share
    history.
  * The message handler `await`s `Runner.run` (the async entry point) rather than
    calling a synchronous variant.
"""

from __future__ import annotations

import chainlit as cl
from agents import (
    InputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
    Runner,
    gen_trace_id,
    set_tracing_export_api_key,
    trace,
)

from src.config import MAX_TURNS, tracing_export_key
from src.desk import build_desk
from src.guardrails import REFUSAL_MESSAGE
from src.hooks import AuditRunHooks
from src.models import Ticket
from src.profiles import DEFAULT_PROFILE
from src.runner import install as install_runner

# FR-11 — register the custom runner once, at process startup (module import).
install_runner()
# FR-13 — tracing exported under our key.
set_tracing_export_api_key(tracing_export_key())


@cl.on_chat_start
async def start() -> None:
    """Build the agent and profile ONCE per session (FR-12)."""
    profile = DEFAULT_PROFILE
    cl.user_session.set("desk", build_desk())
    cl.user_session.set("profile", profile)
    cl.user_session.set("history", [])
    # One trace id per conversation (FR-13) — every message this session is one trace.
    cl.user_session.set("trace_id", gen_trace_id())
    await cl.Message(
        content=(
            f"Hello {profile.name}. You are signed in on the **{profile.tier}** tier "
            f"for `{profile.course_id}`. Ask me anything about the bootcamp."
        )
    ).send()


def _format(final_output) -> str:
    """FR-7 — branch on the typed result in Python before rendering."""
    if isinstance(final_output, Ticket):
        t = final_output
        status = "resolved" if t.resolved else "open"  # branched, not read as prose
        lines = [
            t.summary,
            f"**Next step:** {t.next_step}",
            f"_Filed as a **{t.category}** ticket ({status})._",
        ]
        if t.escalate:
            lines.append("_Escalated to a human._")
        return "\n\n".join(lines)
    # After a handoff, a specialist answered in its own voice (FR-5).
    return str(final_output)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    desk = cl.user_session.get("desk")
    profile = cl.user_session.get("profile")
    history = cl.user_session.get("history")
    trace_id = cl.user_session.get("trace_id")

    # Memory: append this turn to the running history (FR-12).
    history = history + [{"role": "user", "content": message.content}]

    audit = AuditRunHooks()
    try:
        # FR-13 — group every message of this conversation under one trace.
        with trace("Student Ops Desk", trace_id=trace_id):
            # The handler AWAITS the run (FR-12) — never Runner.run_sync.
            result = await Runner.run(
                desk,
                history,
                context=profile,
                hooks=audit,
                max_turns=MAX_TURNS,
            )
    except InputGuardrailTripwireTriggered:
        await cl.Message(content=REFUSAL_MESSAGE).send()  # FR-8
        return
    except MaxTurnsExceeded:
        await cl.Message(
            content=(
                f"That request took more than {MAX_TURNS} turns, so I stopped to "
                "avoid looping. Please rephrase or narrow it."
            )
        ).send()  # FR-9c
        return

    audit.flush()  # FR-10 / NFR-3 — durable audit trail

    # Persist updated memory for the next message (FR-12).
    cl.user_session.set("history", result.to_input_list())

    await cl.Message(content=_format(result.final_output)).send()
