"""Course knowledge store — FR-2, NFR-4.

Course facts live in `courses.json`. This module is the *only* place that reads that
file. The agent never touches it directly — it reaches these facts solely through the
tools in `tools.py`. Deleting a course from the JSON removes it from the Desk's
answers with no code change, and unknown ids return a sentence rather than raising
(NFR-4).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# courses.json sits at the project root (one level up from src/).
_COURSES_PATH = Path(__file__).resolve().parent.parent / "courses.json"


def _load() -> list[dict[str, Any]]:
    """Read courses fresh each call so file edits show up with no restart (FR-2)."""
    with _COURSES_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("courses", [])


def all_courses() -> list[dict[str, Any]]:
    return _load()


def find_course(course_id: str) -> dict[str, Any] | None:
    return next((c for c in _load() if c["id"] == course_id), None)


def find_assignment(course_id: str, assignment_id: str) -> dict[str, Any] | None:
    course = find_course(course_id)
    if course is None:
        return None
    return next(
        (a for a in course.get("assignments", []) if a["id"] == assignment_id),
        None,
    )
