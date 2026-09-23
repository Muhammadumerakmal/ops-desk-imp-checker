# Spec — Saylani Student Ops Desk

## Objective

The Ops Desk is the **front door for student questions** about the bootcamp. A
student asks something in plain language; the Desk:

1. decides whether the question is about an **assignment**, a **career** matter, or
   **course administration**,
2. answers it from **real course data** (never invented),
3. **refuses** anything that isn't about the course,
4. knows **who is asking** without being told in the prompt, and
5. closes every resolved conversation with a **structured ticket** a downstream
   system could file.

Every run it performs can be **audited** after the fact.

Success looks like: one clean conversation in the browser, producing one trace and
one typed ticket, with the student never named in the prompt text.

## What the Desk does (behaviour, in our words)

| # | Requirement | Behaviour |
|---|---|---|
| FR-1 | Model-backed agent, configured at agent level | A question typed in the terminal is answered by the model. Model is set on the agent, not globally or per run. `set_default_openai_client` appears nowhere. Entry point is `async`, driven by `asyncio.run`. |
| FR-2 | Course knowledge, only through tools | Course facts live in `courses.json`. The agent reaches them only by calling tools: list courses, fetch one course's schedule/policies, look up an assignment by id. Deleting a course from the file removes it from answers with no code change; the Desk refuses to invent an assignment id. |
| FR-3 | Student in context, never in prompt | A `StudentProfile` is passed to every run as local context. Tools read it. The prompt text never contains the student's name, roll number, or tier. A profile-reading tool's schema has no wrapper parameter. |
| FR-4 | Instructions that change per turn | The system prompt is built at request time from the profile: greets by name, names the enrolled course, and becomes terser once `open_tickets >= 3`. Three profiles → three visibly different prompts, printable before any model call. |
| FR-5 | Two specialists, cloned from one base, reached by handoff | An **Assignments** specialist (cold, factual) and a **Careers** specialist (warmer) are produced by cloning one base agent, differing only in instructions and model settings. The Desk hands the conversation to whichever fits; the specialist answers the student. The answering agent is identifiable after the run; the handoff appears in the run's items; specialists share the base's model without restating it. |
| FR-6 | One specialist as a tool, not a handoff | A **Summariser** condenses a long policy answer to three lines. It is wired as a *tool* the Desk calls, so the Desk keeps the conversation and speaks in its own voice. The final message after summarisation still comes from the Desk. |
| FR-7 | Every resolved conversation produces a structured ticket | The Desk's final output for a resolved query is a typed `Ticket` object, not prose. `type(final_output) is Ticket`; `resolved` is branched on in Python; a deliberately impossible request surfaces the SDK's parsing error, not a half-filled object. |
| FR-8 | Guardrail that refuses non-course questions | An **input guardrail** rejects anything unrelated to the bootcamp before the Desk's model runs. The tripwire is caught and answered politely; the program does not crash; the refusal costs nothing at the model that would have answered. |
| FR-9 | Tool gating, a stopping rule, and a ceiling | (a) A tool offered **only to `scholarship`-tier** students — absent, not refused, for everyone else. (b) A `close_ticket` tool that **ends the run** the moment it is called, its output becoming the final result. (c) A **turn ceiling** that raises rather than loops, caught and reported. |
| FR-10 | Audit trail across the run; one agent watched closely | **Run-level hooks** record an ordered timeline covering every agent in a conversation, including the handoff. **Agent-level hooks** are attached to exactly one specialist. One question → one timeline naming both agents in order. |
| FR-11 | Custom runner wrapping every run | A custom runner stamps a **request id and elapsed time** around every run in the process, registered once at startup. No agent definition changes to accommodate it; no agent file mentions it. |
| FR-12 | Chainlit interface with per-session memory | The Desk is usable in a browser. The agent and profile are built **once per session**, not per message. The conversation remembers earlier turns. Two browser windows do not share history. The handler `await`s the run. |
| FR-13 | Traceable conversations | Tracing is on, exported under our own key. A single student conversation appears as **one trace**, not several. Every span is nameable. |

## Non-functional requirements

- **NFR-1 Secrets** — keys in gitignored `.env`; missing key → clear startup error.
- **NFR-2 Cost** — every agent declares its own model settings; nothing runs without a ceiling.
- **NFR-3 Observability** — every conversation traceable; the FR-10 timeline is written durably (`audit_log.jsonl`), not only printed.
- **NFR-4 Failure** — a tool hitting bad data returns an actionable sentence; a tool that raises into the runner is a defect.
- **NFR-5 Provenance** — `git log` shows the four Phase-0 artifacts committed before the first code commit.

## Three things this project explicitly will NOT do

1. **It will not answer off-topic questions.** Anything outside the bootcamp is
   refused by the FR-8 guardrail before the Desk's model runs — no weather, no
   general trivia, no coding help unrelated to a course.
2. **It will not invent course facts.** If an assignment id or course is not in
   `courses.json`, the Desk says it cannot find it rather than fabricating one.
3. **It will not put student identity in the prompt text.** Name, roll number, and
   tier travel only as run context and are surfaced solely by instructions we wrote.

## Commands

```
Install:   pip install -r requirements.txt
Configure: copy .env.example -> .env  and paste your key
Terminal:  python main.py
Browser:   chainlit run app.py -w
Traces:    https://platform.openai.com/traces   (workflow "Student Ops Desk")
```

## Success criteria (Definition of Done)

| Requirement | How it is checked |
|---|---|
| Spec preceded code | `git log` order — Phase 0 artifacts first |
| Desk answers from `courses.json` | Delete a course; the answer changes |
| Profile never in the prompt | Tool schema has no wrapper; grep the source |
| Prompt changes per student | Three profiles, three resolved prompts |
| Handoff reaches a specialist | Answering agent identified after the run |
| Ticket is typed | `type(final_output) is Ticket`, branched on in Python |
| Off-topic is refused, cheaply | Refusal shown, no billed call at the Desk model |
| Tools differ by tier | Same question, two tiers, two tool sets |
| One conversation, one trace | Trace opened, every span named |
| Runs in a browser with memory | Second message understood, windows isolated |

## Open questions / resolved decisions

- **Provider**: resolved — OpenAI `gpt-4o-mini` via OpenAI-compatible client, as a
  documented deviation from Gemini (see `constitution.md` §1).
- **Cut list** (if the clock runs out), in order: FR-11 → FR-6 → the AgentHooks half
  of FR-10. **Never** cut FR-7 or FR-8.
