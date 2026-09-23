"""Terminal entry point — FR-1 (async, asyncio.run), plus the wiring for FR-8, FR-9,
FR-10, FR-11, FR-13.

Run:  python main.py
Type a question; type 'quit' to exit. The whole session is one trace (FR-13).
"""

from __future__ import annotations

import asyncio
import sys

# Windows consoles default to cp1252; force UTF-8 so output never crashes on a glyph.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover - older interpreters
    pass

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


def _show_result(final_output) -> None:
    """FR-7 — branch on the typed result in Python, not by reading prose."""
    if isinstance(final_output, Ticket):
        ticket = final_output
        print(f"\n[Desk] {ticket.summary}")
        print(f"       Next step: {ticket.next_step}")
        # `resolved` is used in a Python `if`, not read by a human (FR-7).
        if ticket.resolved:
            print(f"       [resolved] Filed as a '{ticket.category}' ticket.")
        else:
            print(f"       [open] '{ticket.category}' ticket.")
        if ticket.escalate:
            print("       [escalated] A human will follow up.")
        print(f"       [ticket] {ticket.model_dump()}")
    else:
        # After a handoff, a specialist answered in prose (FR-5).
        print(f"\n[Specialist] {final_output}")


async def handle_turn(desk, profile, history) -> list:
    """Run one turn. Returns the updated conversation history (memory)."""
    audit = AuditRunHooks()
    try:
        result = await Runner.run(
            desk,
            history,
            context=profile,
            hooks=audit,             # FR-10 run-level timeline
            max_turns=MAX_TURNS,     # FR-9c ceiling
        )
    except InputGuardrailTripwireTriggered:
        # FR-8 — off-topic caught here; the Desk model never ran.
        print(f"\n[Desk] {REFUSAL_MESSAGE}")
        return history
    except MaxTurnsExceeded:
        # FR-9c — the ceiling raised rather than looping; reported, not crashed.
        print(
            f"\n[Desk] This request took more than {MAX_TURNS} turns, so I stopped to "
            "avoid looping. Please rephrase or narrow it."
        )
        return history

    audit.flush()  # NFR-3 — durable audit trail (request id captured during the run)
    print("\n[audit] timeline for this turn:")
    print(audit.render())
    print(f"[audit] last agent: {result.last_agent.name}")

    _show_result(result.final_output)
    return result.to_input_list()  # memory carried into the next turn


async def main() -> None:
    install_runner()  # FR-11 — register the custom runner once, at startup
    set_tracing_export_api_key(tracing_export_key())  # FR-13

    desk = build_desk()
    profile = DEFAULT_PROFILE
    history: list = []

    trace_id = gen_trace_id()
    print("Saylani Student Ops Desk - type a question, or 'quit' to exit.")
    print(f"(signed in as {profile.name} | {profile.tier} tier | {profile.course_id})")
    print(f"(trace: https://platform.openai.com/traces/trace?trace_id={trace_id})\n")

    # FR-13 — the whole conversation is ONE trace.
    with trace("Student Ops Desk", trace_id=trace_id):
        while True:
            try:
                user_input = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit"):
                break

            history = history + [{"role": "user", "content": user_input}]
            history = await handle_turn(desk, profile, history)


if __name__ == "__main__":
    asyncio.run(main())  # FR-1 — async entry point driven by asyncio.run
