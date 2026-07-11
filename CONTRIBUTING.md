# Contributing

Thanks for your interest in `app-ly`! This is a portfolio project, but issues
and PRs are welcome. This guide covers local setup, running the app, and the
checks CI expects.

## Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** for dependency and environment management
- An **[Anthropic API key](https://console.anthropic.com/)** to run the app
  (not needed to run the tests)
- **LibreOffice** *(optional)* — only for PDF/ODT export

## Setup

```bash
# Install dependencies (including dev tools) into a managed virtualenv
uv sync --group dev
```

## Running the app

```bash
uv run streamlit run app.py
```

Provide your API key via the `ANTHROPIC_API_KEY` environment variable or the
sidebar field:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
uv run streamlit run app.py
```

## Tests

The suite is pure-Python and makes **no** network calls, so it runs without an
API key:

```bash
uv run pytest
```

Please add tests for new behavior. Where logic needs to be testable, prefer
extracting it into a small module rather than leaving it inline in `app.py`
(which can't be imported without executing the Streamlit script).

## Lint and format

We use [ruff](https://docs.astral.sh/ruff/) for both linting and formatting.
Before opening a PR, make sure these pass — CI runs the same checks:

```bash
uv run ruff check .            # lint
uv run ruff format --check .   # verify formatting
```

To auto-fix:

```bash
uv run ruff check --fix .      # apply lint autofixes
uv run ruff format .           # format in place
```

The formatter owns line length; `E501` is intentionally not linted (see the
`[tool.ruff]` config in `pyproject.toml`).

## Continuous integration

Every push and PR to `main` runs two jobs (`.github/workflows/ci.yml`): a
**lint & format** check and the **test** suite. A PR should be green before
review.

## Pull requests

- Keep changes focused; one logical change per PR.
- Read [`CLAUDE.md`](CLAUDE.md) for the project's design invariants — in
  particular the contact-PII boundary and the "no ATS framing" stance — and
  don't break them.
- Keep changes local/self-hostable: no auth, billing, or hosted-service
  assumptions.
