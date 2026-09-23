"""Structured output — FR-7.

The Desk's final output for a resolved query is this typed object, not prose. Because
the Desk declares `output_type=Ticket`, the SDK forces the model to fill every field;
a request it cannot resolve into a valid Ticket surfaces the SDK's parsing error
(`ModelBehaviorError`) instead of a half-filled object.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Ticket(BaseModel):
    category: Literal["assignment", "career", "admin"]
    summary: str
    next_step: str
    resolved: bool
    escalate: bool
