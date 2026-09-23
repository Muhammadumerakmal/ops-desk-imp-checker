"""Local run context — FR-3.

A StudentProfile is passed to every run as `context=`. Tools read it. The prompt text
never contains the student's name, roll number, or tier — grepping the source for a
student's name finds it only in the objects constructed right here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StudentProfile:
    name: str
    roll_no: str
    course_id: str
    tier: str = "regular"  # "regular" or "scholarship"
    open_tickets: int = 0


# Three sample profiles — used to demonstrate FR-4 (three different resolved prompts)
# and FR-9 (regular vs scholarship tool sets).
SAMPLE_PROFILES: dict[str, StudentProfile] = {
    "ayesha": StudentProfile(
        name="Ayesha Khan",
        roll_no="AI-0421",
        course_id="agentic-ai-w4",
        tier="regular",
        open_tickets=0,
    ),
    "bilal": StudentProfile(
        name="Bilal Ahmed",
        roll_no="AI-0512",
        course_id="agentic-ai-w4",
        tier="scholarship",
        open_tickets=1,
    ),
    "sana": StudentProfile(
        name="Sana Malik",
        roll_no="WD-0130",
        course_id="web-dev-we2",
        tier="regular",
        open_tickets=4,  # >= 3 -> the Desk turns terser (FR-4)
    ),
}

# The default profile the terminal entry point runs as.
DEFAULT_PROFILE = SAMPLE_PROFILES["bilal"]
