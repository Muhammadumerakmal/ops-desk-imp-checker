# Concepts — Understanding the Saylani Student Ops Desk

This document explains the **whole project** in plain language: what each piece is,
why it exists, and where to find it in the code. Read it top to bottom and you will
understand every concept the build uses — enough to defend it at the viva.

> **One-line summary:** a student types a question; a triage agent (the *Desk*) works
> out whether it is about an assignment, a career, or admin, answers it from real
> course data, refuses anything off-topic, knows who is asking without being told, and
> closes with a structured ticket — and every run is auditable and traceable.

---

## 1. The big picture

```
                          you type a question
                                   │
                    ┌──────────────▼───────────────┐
                    │  FR-8 INPUT GUARDRAIL         │  off-topic? → polite refusal
                    │  (cheap topic check first)    │  (Desk model never runs)
                    └──────────────┬───────────────┘
                                   │ on-topic
             FR-11 custom runner stamps request-id + clock
                                   │
                    ┌──────────────▼───────────────┐
                    │        THE DESK (triage)      │  owns the conversation
                    │  • reads your profile (FR-3)  │
                    │  • builds its prompt from it  │  (FR-4 dynamic instructions)
                    │  • uses course tools (FR-2)   │
                    └───┬───────────┬───────────┬───┘
          admin/policy  │  assignment│   career │
        answers itself, │   HANDOFF  │  HANDOFF │        (FR-5)
        calls Summariser│      ▼      │     ▼    │
        TOOL (FR-6)     │ Assignments │  Careers │
                        │  Specialist │Specialist│
                        │ (cold)      │ (warm)   │
                        │ [agent hooks│          │        (FR-10)
                        │  fire here] │          │
                        └──────┬──────┴────┬─────┘
                               │           │
                    FR-7 typed Ticket   specialist prose answer
                               │
              run-level hooks → audit_log.jsonl (FR-10)
                     one trace exported (FR-13)
```

Two things run *around* every conversation:
- the **custom runner** (FR-11) — wraps each run with a request id and a timer;
- **tracing** (FR-13) — records every step as one trace you can open in a dashboard.

---

## 2. The model provider — and one honest deviation

**Concept: where the model is configured.** In the OpenAI Agents SDK you can set the
model three ways: globally (for the whole process), per run, or **on the agent
itself**. This project sets it **on each agent** — `Agent(..., model=make_model())`.
That is what FR-1 demands, and it is why the forbidden global setter
(`set_default_openai_client`) appears nowhere.

**The deviation (be upfront about this at the viva).** The brief asks for
`gemini-2.5-flash` through Gemini's OpenAI-compatible endpoint. The key available for
this build is a real **OpenAI** key, which cannot authenticate against Google's
servers. So we kept the *exact architecture* — model set on the agent, through an
OpenAI-compatible `AsyncOpenAI` client — and pointed it at OpenAI's own endpoint with
`gpt-4o-mini`. Everything FR-1 actually tests still holds: async entry point, model on
the agent, no global client. Switching back to Gemini is a one-line change in
`src/config.py` (base URL + model id). This is documented in `constitution.md` §1.

**Files:** `src/config.py` (`make_model`, `get_client`, the missing-key check).

---

## 3. Every concept, explained

The fundamentals guide has 20 parts. Each is *forced* by a requirement. Here is each
concept in your own words, why it is here, and where it lives.

### 3.1 Async runner and `asyncio.run` (FR-1)
An **agent run is asynchronous** — it awaits network calls to the model. The program's
entry point is an `async def main()` driven by `asyncio.run(main())`. The Chainlit
handler likewise `await`s the run. *Why it matters:* calling a synchronous variant
inside an async web handler blocks the event loop.
**Files:** `main.py` (`asyncio.run`), `app.py` (`await Runner.run`).

### 3.2 Tools (FR-2)
A **tool** is a Python function the model may call. The model cannot read files or
databases on its own — it can only *ask* to call a tool you gave it. Course facts live
in `courses.json`; the agent reaches them **only** through `list_courses`,
`get_course`, and `lookup_assignment`. Delete a course from the JSON and it vanishes
from the Desk's answers with no code change, because the tool reads the file fresh
every call.
**Files:** `src/tools.py`, `src/course_store.py`, `courses.json`.

### 3.3 Local context (FR-3)
**Run context** is a Python object passed to a run via `context=`. It travels
*alongside* the conversation, not *inside* the prompt. Tools receive it as their first
parameter (`ctx: RunContextWrapper[StudentProfile]`). The student's name/roll/tier are
in this object and **never** typed into prompt text — grep the source for a name and
you find it only where we built the profile.
**Key detail (viva Q1):** when a tool's first parameter is the context wrapper, the SDK
**omits it from the tool's JSON schema**. So `get_my_profile`'s schema has *no*
parameters — the model cannot (and need not) pass the profile; the runtime injects it.
**Files:** `src/profiles.py`, `get_my_profile` in `src/tools.py`.

### 3.4 Dynamic instructions (FR-4)
Instead of a fixed system prompt, the Desk's `instructions` is a **function** the SDK
calls each turn. It reads the profile from context and builds the prompt: greets by
name, names the course, and turns **terse** once `open_tickets >= 3`. Three profiles →
three visibly different prompts, and you can print the resolved prompt before any model
call by calling `build_desk_instructions(profile)` directly.
**Files:** `src/instructions.py`.

### 3.5 Model settings (FR-5, NFR-2)
`ModelSettings` carries `temperature`, `max_tokens`, etc. **Every agent declares its
own**, so nothing runs unbounded (NFR-2). The Assignments specialist is `temperature=0`
(cold, factual); the Careers specialist is `temperature=0.7` (warm). These are
deliberate, defensible choices, not defaults.
**Files:** `src/config.py` (`BASE_MODEL_SETTINGS`), `src/desk.py`.

### 3.6 Cloning (FR-5)
`agent.clone(**overrides)` copies a base agent, changing only what you name. Both
specialists are `_base_specialist.clone(...)`, overriding **only** instructions and
model settings. They **share the base's model object** (they don't restate it) — proven
in code by `assignments_specialist.model is _base_specialist.model` being `True`.
**Files:** `src/desk.py`.

### 3.7 Handoffs (FR-5)
A **handoff** *transfers ownership* of the conversation to another agent. After the
Desk hands off to a specialist, the **specialist** speaks to the student in its own
voice. You can tell who answered from `result.last_agent.name` after the run, and the
handoff shows up in the run's items (and in our audit timeline).
**Files:** `src/desk.py` (`handoffs=[handoff(...), handoff(...)]`).

### 3.8 Agents as tools (FR-6)
The opposite of a handoff. The **Summariser** is an agent, but it is exposed to the
Desk as a *tool* via `.as_tool()`. When the Desk calls it, control **returns** to the
Desk with the summary — the Desk keeps the conversation and speaks in its own voice.
**Why the difference?** A tool returns a *value* to the caller; a handoff *replaces* the
caller. The Summariser must return three lines so the Desk can keep talking and still
emit the ticket, so it is a tool. The specialists must *answer the student* in their
own tone, so they are handoffs. (Viva Q3.)
**Files:** `src/desk.py` (`_summariser.as_tool(...)`).

### 3.9 Structured output (FR-7)
An agent with `output_type=Ticket` (a Pydantic model) is **forced** to produce a valid
`Ticket`, not prose. After the run, `type(result.final_output) is Ticket`, and you
branch on `ticket.resolved` in a real Python `if`. If the model returns something that
can't be parsed into a `Ticket`, the SDK raises `ModelBehaviorError` — a *loud parsing
error*, not a half-filled object. (Viva Q6: a missing field surfaces as that exception
from the SDK's output-parsing layer.)
**Files:** `src/models.py` (`Ticket`), `output_type=Ticket` in `src/desk.py`, the
`isinstance(..., Ticket)` branch in `main.py`/`app.py`.

### 3.10 Advanced tool control (FR-9, NFR-4)
Three separate controls:
- **Tool gating** — `function_tool(is_enabled=_is_scholarship)`. The
  `apply_scholarship_extension` tool is *absent* (not refused) for non-scholarship
  students. Same question, two tiers → two different tool sets.
- **A stopping rule** — `tool_use_behavior=StopAtTools(["close_ticket"])`. The moment
  `close_ticket` is called, the run ends and that tool's return value becomes the final
  output. Because it returns a `Ticket`, FR-7 still holds.
- **A ceiling** — `max_turns=8`. If a run needs more turns it is looping, so the SDK
  **raises** `MaxTurnsExceeded`, which we catch and report rather than burning budget.
**Files:** `src/tools.py`, `src/desk.py`, `src/config.py` (`MAX_TURNS`), the
`except MaxTurnsExceeded` blocks.

### 3.11 Guardrails (FR-8)
An **input guardrail** runs *before* the Desk's model. A small, cheap guardrail agent
classifies the message; if it's off-topic, the guardrail's tripwire fires and the SDK
raises `InputGuardrailTripwireTriggered`, which we catch and answer politely. The
Desk's (expensive) model **never runs**, so a blocked question costs nothing at it —
provable from the trace, which shows a guardrail span but **no Desk generation span**.
(Viva Q2.)
**Files:** `src/guardrails.py`, the `except InputGuardrailTripwireTriggered` blocks.

### 3.12 Lifecycle hooks — agent-level (FR-10)
`AgentHooks` attach to **one agent** and fire on that agent's lifecycle
(`on_start`, `on_tool_start`, `on_end`). We attach `SpecialistAgentHooks` to the
**Assignments specialist only**. They fire while that agent is active and go **silent**
the instant control moves elsewhere — which is exactly why, when the Desk hands off to
*Careers* instead, these hooks never fire. (Viva Q7: agent hooks are scoped to their
agent, not the run.)
**Files:** `src/hooks.py` (`SpecialistAgentHooks`), attached in `src/desk.py`.

### 3.13 Run lifecycle hooks — run-level (FR-10, NFR-3)
`RunHooks` attach to the **whole run** and see **every** agent plus the handoff
between them. `AuditRunHooks` records an ordered timeline (`on_agent_start`,
`on_handoff`, `on_tool_start/end`, `on_agent_end`) and appends it to
`audit_log.jsonl` — durable, not only printed (NFR-3).
**Counts for one handoff ticket (viva Q7):** run-level `on_agent_start` fires **once
per agent** (Desk, then specialist = 2); `on_llm_start` fires **once per model call**
(often more than 2, e.g. Desk decides → specialist answers → any tool round-trips).
**Files:** `src/hooks.py` (`AuditRunHooks`), used in `main.py`/`app.py`.

### 3.14 Custom runners (FR-11)
A **custom runner** subclasses the SDK's default runner and is registered **once** at
startup with `set_default_agent_runner(...)`. Ours stamps a **request id** and
**elapsed time** around every run in the process — the Desk's run *and* each
specialist's run — and **no agent file mentions it**.
**What the runner sees that hooks cannot (viva Q8):** hooks observe events *inside* a
run (which agent, which tool). The runner wraps the run *as a whole* — total wall-clock
time and a request id that ties every span of that run together.
**Files:** `src/runner.py` (`StampedRunner`, `install`).

### 3.15 Tracing (FR-13, NFR-3)
**Tracing** records each run as a tree of **spans** (agent spans, generation spans,
tool spans, handoff spans, guardrail spans). We turn it on, export it under our key,
and wrap the whole conversation in one `trace("Student Ops Desk", trace_id=...)` so a
single conversation is **one trace**, not several.
**Files:** `main.py`/`app.py` (`set_tracing_export_api_key`, `trace(...)`).

### 3.16 Chainlit (FR-12)
**Chainlit** gives the Desk a browser chat UI. The agent and profile are built **once
per session** in `@cl.on_chat_start` and stored in `cl.user_session`; conversation
history is kept there too, so a second message understands the first. `cl.user_session`
is isolated per browser session, so two windows don't share history. The handler
`await`s the run.
**Files:** `app.py`.

---

## 4. The 13 requirements, at a glance

| FR | What it proves | Where |
|----|----------------|-------|
| FR-1 | Model on the agent, async entry, no global client | `config.py`, `main.py` |
| FR-2 | Course facts only via tools; delete a course → answer changes | `tools.py`, `course_store.py`, `courses.json` |
| FR-3 | Student in context, never in prompt; no wrapper in schema | `profiles.py`, `tools.py` |
| FR-4 | Prompt rebuilt per turn from the profile | `instructions.py` |
| FR-5 | Two specialists cloned from one base, reached by handoff | `desk.py` |
| FR-6 | Summariser as a tool, not a handoff | `desk.py` |
| FR-7 | Resolved query → typed `Ticket`, branched on in Python | `models.py`, `desk.py`, `main.py` |
| FR-8 | Off-topic refused before the Desk model runs | `guardrails.py` |
| FR-9 | Tool gating + close_ticket stop + turn ceiling | `tools.py`, `desk.py`, `config.py` |
| FR-10 | Run-level timeline across agents + agent hooks on one specialist | `hooks.py` |
| FR-11 | Custom runner stamps every run, no agent knows | `runner.py` |
| FR-12 | Browser UI, per-session memory, windows isolated, awaited | `app.py` |
| FR-13 | One conversation → one trace, every span nameable | `main.py`, `app.py` |

**Non-functional:** NFR-1 secrets in gitignored `.env` + clear missing-key error;
NFR-2 per-agent settings + ceiling; NFR-3 durable audit + tracing; NFR-4 tools return
sentences, never raise; NFR-5 spec committed before code (git history).

---

## 5. The eight viva questions — short answers

1. **Schema for a profile-reading tool; why no wrapper param?** `get_my_profile`'s
   schema is empty. The SDK excludes the `RunContextWrapper` first parameter from the
   generated schema because the runtime injects context; the model never supplies it.
2. **A blocked question cost nothing — prove it from the trace.** The trace of an
   off-topic message has a guardrail span but **no Desk generation span**. The Desk
   model was never invoked because the tripwire raised first.
3. **What do the specialists share with the base, what is their own?** Shared: the
   model object (via clone). Their own: `name`, `handoff_description`, `instructions`,
   `model_settings` (temperature/tone), and — for Assignments only — the agent hooks.
4. **Rename one specialist — what silently degrades and from where?** The name is the
   identity used in `result.last_agent.name` and in the audit timeline; renaming it
   changes what those report, and the handoff tool name the model sees is derived from
   the agent, so routing prompts that referenced the old name degrade. The name comes
   from the `Agent(name=...)` / `clone(name=...)` call in `desk.py`.
5. **Why does the Chainlit handler await the run, and the exact error if it doesn't?**
   The run is a coroutine; a browser handler must not block the event loop. If you call
   the synchronous `Runner.run_sync` inside the async handler you get a
   `RuntimeError: ... cannot be called from a running event loop`.
6. **Ticket came back missing a field — which exception, which layer?** The SDK's
   output-parsing layer raises `ModelBehaviorError` (Pydantic validation failed) rather
   than returning a half-filled `Ticket`.
7. **Which hook fires once per agent, which once per model call? Counts for one
   ticket.** `on_agent_start` fires once per agent (Desk + one specialist = 2);
   `on_llm_start` fires once per model call (≥2, more with tool round-trips). The
   agent-level hooks on Assignments fire only while it is active.
8. **What does the custom runner see that hooks cannot?** The run as a whole — total
   elapsed wall-clock time and a per-run request id that correlates every span; hooks
   only see individual in-run events.

---

## 6. How to run and verify

```bash
pip install -r requirements.txt
cp .env.example .env          # then paste your key into .env

python main.py                # terminal Desk
python -m chainlit run app.py -w   # browser Desk (http://localhost:8000)
```

Quick verifications you can demo on the spot:

| Check | How |
|-------|-----|
| FR-1 no global client | `grep -rn set_default_openai_client --include=*.py .` → nothing |
| FR-2 data-driven | delete a course from `courses.json`, ask again — it's gone |
| FR-3 name not in prompt | `grep -rn "Bilal" --include=*.py .` → only `profiles.py` |
| FR-3 no wrapper param | print `get_my_profile.params_json_schema` → empty properties |
| FR-4 per-turn prompt | print `build_desk_instructions(p)` for three profiles |
| FR-5 handoff | ask "when is a3 due?" → `last_agent` is *Assignments Specialist* |
| FR-8 refusal | ask "weather in Karachi?" → polite refusal, no Desk answer |
| FR-9 gating | `desk.get_all_tools(ctx)` for regular vs scholarship |
| FR-10 audit | read `audit_log.jsonl` — one timeline naming both agents in order |
| FR-13 trace | open the printed trace URL, name each span |

---

## 7. Project map

```
constitution.md   the rules the build may not violate (Phase 0)
spec.md           what the Desk does, in behaviour (Phase 0)
plan.md           the architecture (Phase 0)
tasks.md          ordered implementation tasks (Phase 0)
concepts.md       this file — the explainer

courses.json      FR-2 course data (edit to change answers)
main.py           FR-1 async terminal entry point
app.py            FR-12 Chainlit browser interface
requirements.txt  dependencies

src/config.py        FR-1, NFR-1  model/client, missing-key error, ceiling
src/profiles.py      FR-3  StudentProfile + sample profiles
src/course_store.py  FR-2  the only reader of courses.json
src/models.py        FR-7  the Ticket type
src/instructions.py  FR-4  dynamic instructions builder
src/tools.py         FR-2/FR-3/FR-9  function tools
src/guardrails.py    FR-8  input guardrail
src/hooks.py         FR-10 run-level + agent-level hooks
src/runner.py        FR-11 custom runner
src/desk.py          FR-5/FR-6/FR-7  agents assembled here
```

**The three things the Desk will not do:** answer off-topic questions, invent course
facts, or put student identity in the prompt text.
