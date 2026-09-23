# Constitution — Saylani Student Ops Desk

The rules this build may not violate. Every source file is written in service of
these; a change that breaks one of them is a defect regardless of whether the
program still runs.

## 1. Model provider and where it is configured

- The Desk runs on an **OpenAI-compatible Chat Completions client**. The model is
  attached **to each agent** (via `model=OpenAIChatCompletionsModel(...)`), never
  globally and never per-run. `set_default_openai_client(...)` is forbidden.
- **Deliberate, documented deviation from FR-1.** The brief specifies
  `gemini-2.5-flash` via Gemini's OpenAI-compatible endpoint. The key available for
  this build is a real **OpenAI** key, which cannot authenticate against Google's
  endpoint. We therefore run the *same architecture* — model set on the agent,
  through an OpenAI-compatible `AsyncOpenAI` client — against OpenAI's own endpoint
  with `gpt-4o-mini`. Everything FR-1 actually tests (async entry point, per-agent
  model, no `set_default_openai_client`) still holds. Swapping back to Gemini is a
  one-line change in `src/config.py` (base_url + model id + key). This deviation is
  recorded here so it is defensible at the viva, not hidden.

## 2. Secrets

- Keys live **only in `.env`**, which is gitignored. No key is ever hard-coded,
  printed, logged, or committed.
- A **missing key produces a clear startup error** (one sentence, actionable), not a
  stack trace three layers deep (NFR-1).

## 3. Tools never raise to the caller

- Every tool returns a **sentence the model can act on**, even on bad data. A tool
  that raises into the runner is a defect, not a feature (NFR-4).
- The single deliberate exception is the **turn ceiling** (FR-9): exceeding it
  *raises* `MaxTurnsExceeded`, which the program catches at the top level and reports.

## 4. Student data never reaches the model except through instructions we wrote

- The `StudentProfile` is passed as **local run context**, never concatenated into
  user input. Tools read it; the raw object is never serialised into a prompt.
- The only student facts the model sees are the ones our **dynamic instructions**
  (FR-4) deliberately place there (name, course, terseness). Grepping the source for
  the student's name finds it only in the object we constructed (FR-3).

## 5. Provenance

- The four Phase-0 artifacts (`constitution.md`, `spec.md`, `plan.md`, `tasks.md`)
  are **committed before the first line of source code** (NFR-5). A single commit
  containing both a spec and an implementation fails Phase 0.

## 6. Cost and observability

- **Every agent declares its own `model_settings`.** Nothing generates without a
  turn ceiling (NFR-2).
- **Every conversation is traceable**, and the FR-10 audit timeline is written to a
  durable file, not only printed (NFR-3).

## 7. Ownership

- The agent writes the code; we own it. Anything in this repository that cannot be
  explained at the viva is unfinished. Requirements are numbered and testable:
  "FR-7 works" means it can be demonstrated on demand.
