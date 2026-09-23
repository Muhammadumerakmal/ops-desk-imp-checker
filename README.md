# Saylani Student Ops Desk

A spec-driven agentic build: a triage "Desk" agent answers student questions about a
bootcamp from real course data, routes to specialists, refuses off-topic questions,
and closes every resolved conversation with a structured ticket — fully audited and
traced.

Built on the OpenAI Agents SDK. **Start with [`concepts.md`](concepts.md)** — it
explains the whole project and every concept in plain language.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env        # then paste your API key into .env

python main.py                     # terminal interface
python -m chainlit run app.py -w   # browser interface
```

## What's here

| File | Purpose |
|------|---------|
| `constitution.md` `spec.md` `plan.md` `tasks.md` | Phase-0 spec artifacts (committed before any code) |
| `concepts.md` | **The explainer — read this first** |
| `main.py` | Async terminal entry point (FR-1) |
| `app.py` | Chainlit browser UI with per-session memory (FR-12) |
| `courses.json` | Course data; edit it and answers change (FR-2) |
| `src/` | The Desk, specialists, tools, guardrail, hooks, runner |

## Provider note

The brief asks for `gemini-2.5-flash`; this build runs OpenAI `gpt-4o-mini` through the
same OpenAI-compatible, per-agent architecture, because the available key is an OpenAI
key. Switching back to Gemini is a one-line change in `src/config.py`. See
`constitution.md` §1.

## Requirements coverage

FR-1…FR-13 and NFR-1…NFR-5 are implemented and verified; each is mapped to its file and
a demo check in `concepts.md` §4 and §6.
