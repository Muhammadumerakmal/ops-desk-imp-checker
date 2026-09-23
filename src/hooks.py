"""Lifecycle hooks — FR-10, NFR-3.

Two kinds of hooks, deliberately different in scope:

* `AuditRunHooks` (RunHooks) — RUN-LEVEL. Registered on the whole run, it sees *every*
  agent in the conversation and the handoff between them. It records an ordered
  timeline and appends it to `audit_log.jsonl`, so the audit trail is durable, not
  only printed (NFR-3).

* `SpecialistAgentHooks` (AgentHooks) — AGENT-LEVEL. Attached to exactly one agent
  (the Assignments specialist). It only fires while that agent is the active one.
  This is why it goes quiet the instant the conversation hands off to a *different*
  agent: agent-level hooks are scoped to their agent, not the run (viva Q7).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents import Agent, AgentHooks, RunContextWrapper, RunHooks

_AUDIT_PATH = Path(__file__).resolve().parent.parent / "audit_log.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditRunHooks(RunHooks):
    """Run-level: one ordered timeline across every agent in the conversation."""

    def __init__(self, request_id: str | None = None) -> None:
        self.request_id = request_id
        self.timeline: list[dict[str, Any]] = []

    def _record(self, event: str, **fields: Any) -> None:
        self.timeline.append({"at": _now(), "event": event, **fields})

    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:
        # Capture the request id stamped by the custom runner (FR-11), which is only
        # set on the contextvar while the run is in flight.
        if self.request_id is None:
            from .runner import current_request_id

            self.request_id = current_request_id.get()
        self._record("agent_start", agent=agent.name)

    async def on_agent_end(
        self, context: RunContextWrapper, agent: Agent, output: Any
    ) -> None:
        self._record("agent_end", agent=agent.name, output_type=type(output).__name__)

    async def on_handoff(
        self, context: RunContextWrapper, from_agent: Agent, to_agent: Agent
    ) -> None:
        self._record("handoff", **{"from": from_agent.name, "to": to_agent.name})

    async def on_tool_start(
        self, context: RunContextWrapper, agent: Agent, tool: Any
    ) -> None:
        self._record("tool_start", agent=agent.name, tool=tool.name)

    async def on_tool_end(
        self, context: RunContextWrapper, agent: Agent, tool: Any, result: Any
    ) -> None:
        self._record("tool_end", agent=agent.name, tool=tool.name)

    def flush(self) -> None:
        """Write the whole timeline as one durable JSONL record (NFR-3)."""
        record = {
            "request_id": self.request_id,
            "logged_at": _now(),
            "timeline": self.timeline,
        }
        with _AUDIT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def render(self) -> str:
        """A human-readable one-line-per-step view of the timeline."""
        lines = []
        for step in self.timeline:
            event = step["event"]
            if event == "handoff":
                lines.append(f"  handoff: {step['from']} -> {step['to']}")
            elif event in ("agent_start", "agent_end"):
                lines.append(f"  {event}: {step['agent']}")
            elif event in ("tool_start", "tool_end"):
                lines.append(f"  {event}: {step['tool']} (in {step['agent']})")
        return "\n".join(lines)


class SpecialistAgentHooks(AgentHooks):
    """Agent-level: watches ONE specialist closely; silent once control leaves it."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.fired: list[str] = []
        self._t0: float | None = None

    async def on_start(self, context: RunContextWrapper, agent: Agent) -> None:
        self._t0 = time.perf_counter()
        self.fired.append("on_start")
        print(f"[agent-hook:{self.label}] START {agent.name}")

    async def on_end(
        self, context: RunContextWrapper, agent: Agent, output: Any
    ) -> None:
        elapsed = (time.perf_counter() - self._t0) if self._t0 else 0.0
        self.fired.append("on_end")
        print(f"[agent-hook:{self.label}] END {agent.name} ({elapsed:.2f}s)")

    async def on_tool_start(
        self, context: RunContextWrapper, agent: Agent, tool: Any
    ) -> None:
        self.fired.append(f"tool_start:{tool.name}")
        print(f"[agent-hook:{self.label}] tool {tool.name}")
