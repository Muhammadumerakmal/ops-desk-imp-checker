# Tasks — Saylani Student Ops Desk

Ordered implementation tasks. Each is small enough to verify on its own and names the
requirement it satisfies. Checked off as the build proceeds. **No task here is
started until this file and the other three Phase-0 artifacts are committed** (NFR-5).

## Phase 0 — specification gate (no code)

- [x] T0.1 — `constitution.md`, `spec.md`, `plan.md`, `tasks.md` written.
  - Verify: four files exist and agree; committed in a single spec-only commit.

## Phase 1 — core desk (FR-1 … FR-4)

- [x] T1.1 — `src/config.py`: load `.env`; clear error if `OPENAI_API_KEY` missing
  (NFR-1); build one `AsyncOpenAI` client; `desk_model()` factory returns an
  `OpenAIChatCompletionsModel` set on the agent. No `set_default_openai_client`. (FR-1)
  - Verify: import with key present → OK; unset key → one-line `RuntimeError`.
- [x] T1.2 — `courses.json` + `src/course_store.py`: load and query courses. (FR-2)
  - Verify: `list_courses` reflects file edits; unknown id → sentence, not crash.
- [x] T1.3 — `src/models.py`: `Ticket` pydantic model. (FR-7)
- [x] T1.4 — `src/profiles.py`: `StudentProfile` dataclass + three sample profiles. (FR-3)
- [x] T1.5 — `src/tools.py` (data + profile tools): `list_courses`, `get_course`,
  `lookup_assignment`, `get_my_profile(ctx)`. (FR-2, FR-3)
  - Verify: `get_my_profile` schema has **no** `ctx`/wrapper param.
- [x] T1.6 — `src/instructions.py`: dynamic instructions from profile — greet by
  name, name the course, terser at `open_tickets >= 3`. (FR-4)
  - Verify: three profiles → three different resolved prompts, printable pre-call.
- [x] T1.7 — `src/desk.py` (Desk only) + `main.py`: async entry, `asyncio.run`, a
  typed question answered in the terminal. (FR-1)
  - Verify: `python main.py`, type a question, get an answer.

## Phase 2 — specialists (FR-5 … FR-9)

- [x] T2.1 — `src/desk.py`: `base_specialist`; clone → Assignments (cold) & Careers
  (warm); register handoffs on the Desk. (FR-5)
  - Verify: `result.last_agent` names the specialist; handoff item present.
- [x] T2.2 — `src/desk.py`: Summariser agent → `.as_tool()` on the Desk. (FR-6)
  - Verify: final message after summarising still comes from the Desk.
- [x] T2.3 — Desk `output_type=Ticket`; branch on `resolved` in Python. (FR-7)
  - Verify: `type(final_output) is Ticket`; impossible request → parsing error.
- [x] T2.4 — `src/guardrails.py`: input guardrail refusing off-topic; caught in
  `main.py`/`app.py`. (FR-8)
  - Verify: off-topic → courteous refusal, no Desk model call, no crash.
- [x] T2.5 — `src/tools.py`: scholarship-only tool (`is_enabled`); `close_ticket`
  (`StopAtTools`); `max_turns=8` ceiling caught. (FR-9)
  - Verify: regular vs scholarship → different tool sets; ceiling raises & is caught.

## Phase 3 — operations and interface (FR-10 … FR-13)

- [x] T3.1 — `src/hooks.py`: `AuditRunHooks` (run-level) → `audit_log.jsonl`;
  `SpecialistAgentHooks` on Assignments only. (FR-10, NFR-3)
  - Verify: one question → one timeline naming both agents in order.
- [x] T3.2 — `src/runner.py`: custom runner stamping request-id + elapsed, registered
  once at startup; no agent file mentions it. (FR-11)
  - Verify: wrapper output appears for Desk and specialist runs.
- [x] T3.3 — `app.py`: Chainlit; agent + profile built once per session; memory;
  `await` the run. (FR-12)
  - Verify: second message understood; two windows isolated.
- [x] T3.4 — tracing on, exported under our key, one trace per conversation. (FR-13)
  - Verify: open the trace; every span nameable.

## Demo

- [x] T4.1 — one clean conversation → one trace → one ticket. (whole project)

## Cut order if the clock runs out

FR-11 → FR-6 → AgentHooks half of FR-10. **Never** cut FR-7 or FR-8.
