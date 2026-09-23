# Plan — Saylani Student Ops Desk

The architecture: which agents exist, which owns the conversation, what each tool is
called and returns, and the shape of every data structure crossing a boundary.

## Agents

| Agent | Owns conversation? | Model | Settings | Role |
|---|---|---|---|---|
| **Desk** (triage) | **Yes** — the orchestrator | `gpt-4o-mini` on the agent | `temperature=0.3`, `max_tokens` set | Reads profile, answers admin/policy questions itself, decides handoffs, calls the Summariser tool, emits the `Ticket`. Holds the FR-8 input guardrail. |
| **base_specialist** | never runs directly | `gpt-4o-mini` on the agent | base settings | The single base cloned into the two specialists (FR-5). Defines the shared model so specialists don't restate it. |
| **Assignments specialist** | Yes, after handoff | inherited via clone | `temperature=0.0` (cold, factual) | Answers assignment/deadline/policy questions in prose. Carries the FR-10 **agent-level** hooks. |
| **Careers specialist** | Yes, after handoff | inherited via clone | `temperature=0.7` (warmer) | Answers career questions in a warmer voice. |
| **Summariser** | No — invoked as a tool | `gpt-4o-mini` on the agent | `temperature=0.0`, low `max_tokens` | Condenses a long policy answer to three lines (FR-6). Exposed via `.as_tool(...)`, not a handoff. |

**Why Assignments/Careers are handoffs but Summariser is a tool:** a handoff
*transfers ownership* of the conversation — the specialist then speaks to the student
in its own voice (FR-5 wants that warm/cold difference to reach the student). The
Summariser must *not* own the conversation: the Desk needs the three-line summary
back so it can keep speaking in its own voice and still emit the ticket. A tool
returns a value to the caller; a handoff replaces the caller. That is the whole
distinction (viva Q3/Q&A).

## Data structures crossing boundaries

```python
# Local run context (FR-3) — travels as `context=`, never in prompt text.
@dataclass
class StudentProfile:
    name: str
    roll_no: str
    course_id: str
    tier: str = "regular"        # "regular" | "scholarship"
    open_tickets: int = 0

# The Desk's structured close (FR-7) — the final_output for a resolved query.
class Ticket(BaseModel):
    category: Literal["assignment", "career", "admin"]
    summary: str
    next_step: str
    resolved: bool
    escalate: bool
```

`courses.json` shape (FR-2), read only through tools:

```json
{ "courses": [ { "id", "title", "schedule",
                 "policies": { ... },
                 "assignments": [ { "id", "title", "due" } ] } ] }
```

## Tools (name → returns)

| Tool | Reads | Returns | Requirement |
|---|---|---|---|
| `list_courses()` | `courses.json` | one line per course (id + title) | FR-2 |
| `get_course(course_id)` | `courses.json` | schedule + policies, or "no such course" sentence | FR-2, NFR-4 |
| `lookup_assignment(course_id, assignment_id)` | `courses.json` | assignment detail, or "no such assignment" sentence (never invented) | FR-2, NFR-4 |
| `get_my_profile(ctx)` | run context | the caller's course + tier as a sentence; **`ctx` is not in the schema** | FR-3 |
| `apply_scholarship_extension(...)` | run context | grants an extension — **only offered when `tier == "scholarship"`** (`is_enabled`) | FR-9a |
| `close_ticket(...)` | args | a `Ticket`; **ends the run** via `StopAtTools` | FR-9b |
| Summariser (`summarise_policy`) | its own model | three-line summary, returned to the Desk | FR-6 |

All data tools degrade to a sentence on bad input (NFR-4); none raise.

## Control flow of one conversation

```
student text
   │
   ▼
[FR-8 input guardrail]  ── off-topic ──▶ tripwire caught ──▶ polite refusal (no Desk model call)
   │ on-topic
   ▼
[custom runner: stamp request-id + start clock]         (FR-11, registered once)
   │
   ▼
[Desk agent]  reads profile via tool (FR-3)
   │   builds dynamic instructions from profile (FR-4)
   ├── admin/policy question ─▶ answers itself, may call Summariser tool (FR-6) ─▶ emits Ticket (FR-7)
   ├── assignment question ──▶ handoff ─▶ [Assignments specialist] answers (FR-5)   [agent hooks fire here, FR-10]
   ├── career question ─────▶ handoff ─▶ [Careers specialist] answers (FR-5)
   └── student asks to close ─▶ close_ticket tool ─▶ run ends, Ticket is final_output (FR-9b)
   │
   ▼
[custom runner: stop clock, log elapsed]                (FR-11)
[run-level hooks flushed to audit_log.jsonl]            (FR-10, NFR-3)
[one trace exported]                                    (FR-13)
```

## Turn ceiling (FR-9c)

`max_turns = 8`. Rationale: the deepest legitimate path is
profile-read → tool/handoff → specialist answer → summary → ticket, comfortably
under 8. A run that needs more than 8 turns is looping, so we let
`MaxTurnsExceeded` raise and catch it at the top level rather than burning budget.

## Hooks (FR-10)

- **`AuditRunHooks(RunHooks)`** — run-level. Records an ordered timeline
  (`on_agent_start`, `on_handoff`, `on_tool_start/end`, `on_agent_end`) across *every*
  agent, appended to `audit_log.jsonl`.
- **`SpecialistAgentHooks(AgentHooks)`** — attached to the **Assignments specialist
  only**. Goes quiet the moment control leaves that agent — which is why, when the
  Desk hands *off* to Careers, these hooks never fire (viva Q7).

## Files

```
main.py                 FR-1  async terminal entry point (asyncio.run)
app.py                  FR-12 Chainlit interface, per-session memory
courses.json            FR-2  course data (edit to change answers)
src/config.py           FR-1, NFR-1  client + per-agent model + missing-key check
src/profiles.py         FR-3  StudentProfile + sample profiles
src/course_store.py     FR-2  load/query courses.json
src/models.py           FR-7  Ticket pydantic model
src/instructions.py     FR-4  dynamic instructions builder
src/tools.py            FR-2, FR-3, FR-9  function tools
src/guardrails.py       FR-8  input guardrail
src/hooks.py            FR-10 run-level + agent-level hooks
src/desk.py             FR-5, FR-6, FR-7  builds base/specialists/summariser/Desk
src/runner.py           FR-11 custom runner registered at startup
```

## Risks and mitigations

- **Ticket vs. handoff tension** — a specialist that answers in prose would make
  `final_output` a string, not a `Ticket`. Mitigation: the **Desk** owns the ticket;
  the canonical "one conversation → one ticket" demo resolves an admin question at the
  Desk. Handoff demos legitimately end in specialist prose (documented, FR-5).
- **Provider swap** — isolated to `src/config.py` so returning to Gemini is one edit.
- **Secret leakage** — `.env` gitignored before first commit; key never logged.
