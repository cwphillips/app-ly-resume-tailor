# CLAUDE.md

Orientation for AI agents and contributors working in this repo. Read this
first — several load-bearing design decisions are not obvious from the code
alone.

## What this is

`app-ly` is a **locally-hosted** Streamlit app that tailors a resume to a job
listing using Claude. The user pastes their resume (or a skills list) and a job
listing; two agents run in sequence — a **tailoring** agent that produces a
structured resume, then a **review** agent that scores it and suggests
improvements. The user can run up to two refinement passes and export to
DOCX (and PDF/ODT if LibreOffice is installed).

It is designed to run on one person's machine with their own API key. There is
no auth, no billing, no multi-tenancy, and no hosted-service assumption. Keep
changes in that spirit.

## Layout

| Path | Responsibility |
|---|---|
| `app.py` | Streamlit UI and session state (the app entry point). Wires the UI to `pipeline.py`. |
| `pipeline.py` | UI-agnostic tailor→review orchestration and token accounting. Shared by `app.py` and `cli.py`; progress is surfaced through a `ProgressReporter` hook, never a `streamlit` import. |
| `cli.py` | Headless entry point (`uv run python cli.py …`) — runs the same pipeline and writes a DOCX without the browser. |
| `agents/` | The `tailoring` and `review` agents — prompt building, the Anthropic call, and parsing tool output into schemas. `errors.py` holds shared typed errors. |
| `models/schemas.py` | Pydantic models for the resume/review payloads **and** the Anthropic tool definitions derived from them. |
| `exporters/` | `docx.py` renders a resume to a Word document; `converter.py` shells out to LibreOffice for PDF/ODT. |
| `templates/library.py` | The `Section` enum and the built-in templates (section order + skill-group limits). |
| `input_normalization.py` | Conservative, no-LLM cleanup of pasted resume text. |
| `diff_view.py` | Renders the refinement diff as coloured, HTML-escaped markup. |
| `tests/` | `pytest` suite. Pure-Python — no network calls. |
| `prds/`, `plans/` | Original product and implementation planning docs (background context). |

## Run and test

```bash
uv sync                              # install deps (Python 3.13+)
uv run streamlit run app.py          # run the app locally
uv run pytest                        # run the test suite
uv run ruff check .                  # lint
uv run ruff format .                 # format
```

The app reads the API key from `ANTHROPIC_API_KEY` (or a sidebar field). See
`CONTRIBUTING.md` for the full lint/format/test workflow that CI enforces.

## Design invariants — do not break these

1. **Contact PII never enters a prompt.** Name, email, phone, location,
   LinkedIn, and GitHub are collected in the UI and injected only at
   document-render time. They must never be passed to the agents or appear in
   any prompt string. The tailoring agent's system prompt explicitly forbids
   emitting them, and `tests/test_input_validation.py` pins this — keep that
   test green.

2. **Conservative beats thorough for input normalization.** `input_normalization.py`
   cleans messy pasted text (bullet glyphs, smart quotes, blank-line runs). A
   step that drops a legitimate resume line is worse than one that leaves an
   artifact in. Already-clean text must pass through unchanged — this invariant
   is pinned by a test.

3. **No "ATS" framing.** The project intentionally dropped applicant-tracking-
   system language. Do not reintroduce it in code, UI copy, docs, or prompts.
   The review agent scores on keyword match + hiring-manager skim, not "ATS
   compatibility".

## Conventions

- Small, single-purpose modules extracted out of `app.py` so their logic is
  unit-testable without importing the Streamlit script (`input_normalization.py`,
  `diff_view.py` are examples). Prefer this over inlining testable logic in the UI.
- New code must pass `ruff check` and `ruff format --check`, and ship with tests.
