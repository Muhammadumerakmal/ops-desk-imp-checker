"""Custom runner — FR-11.

A custom runner stamps a request id and elapsed time around *every* run in the
process. It is registered once at startup (`install()`), and no agent definition
changes to accommodate it — agents never mention it. Because it subclasses the SDK's
default runner and is installed globally, its wrapper output appears for the Desk's
run and for the specialist's run alike.

This is the one thing the runner sees that hooks cannot: hooks observe events *inside*
a run (agents, tools, handoffs); the runner wraps the run as a whole — total
wall-clock time and a request id that ties every span in that run together (viva Q8).
"""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar

from agents.run import AgentRunner, set_default_agent_runner

# The request id for the run currently in flight, readable elsewhere (e.g. hooks).
current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)


class StampedRunner(AgentRunner):
    """Wraps each run with a request id and elapsed-time stamp."""

    async def run(self, starting_agent, input, **kwargs):  # type: ignore[override]
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        token = current_request_id.set(request_id)
        start = time.perf_counter()
        agent_name = getattr(starting_agent, "name", "?")
        print(f"[runner] {request_id} START agent={agent_name}")
        try:
            return await super().run(starting_agent, input, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            print(f"[runner] {request_id} END   agent={agent_name} ({elapsed:.2f}s)")
            current_request_id.reset(token)


def install() -> None:
    """Register the custom runner once, at startup."""
    set_default_agent_runner(StampedRunner())
