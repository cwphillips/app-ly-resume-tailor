# app-ly — AI resume tailor

[![CI](https://github.com/cwphillips/app-ly-resume-tailor/actions/workflows/ci.yml/badge.svg)](https://github.com/cwphillips/app-ly-resume-tailor/actions/workflows/ci.yml)

A locally-hosted AI resume tailoring tool. Paste your resume (or a skills list) and a job listing; the app produces a polished, tailored resume using Claude.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- An [Anthropic API key](https://console.anthropic.com/)
- LibreOffice *(optional — required only for PDF and ODT export)*

## Setup

```bash
# Clone / navigate to the project
cd app-ly-resume-tailor

# Install dependencies
uv sync
```

## Running the app

**Local (this machine only):**
```bash
uv run streamlit run app.py
```

**LAN (accessible from any device on your network):**
```bash
uv run streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```
Then open `http://<your-machine-ip>:8501` in any browser on the same network.

## API key

The app reads your Anthropic API key from the `ANTHROPIC_API_KEY` environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
uv run streamlit run app.py
```

Alternatively, paste it directly into the **Anthropic API Key** field in the app sidebar each session.

## Command-line (headless)

The same tailor → review pipeline runs without the browser, so you can script it. It reads `ANTHROPIC_API_KEY` from the environment, writes a DOCX, and prints the review score and suggestions:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
uv run python cli.py resume.txt job.txt \
  --name "Jane Smith" --email jane@example.com \
  --target-role "Senior Backend Engineer" \
  --output tailored.docx
```

`resume.txt` and `job.txt` are plain-text files (your resume/skills and the job listing). Contact details are passed as flags and, exactly as in the app, are injected into the document only — they are never sent to the API.

| Option | Description |
|---|---|
| `--name`, `--email` | Required — used in the document header only. |
| `--phone`, `--location`, `--linkedin`, `--github` | Optional contact details. |
| `--target-role` | Role to tailor toward. |
| `--page-limit {1-4}` | Constrain the resume to N pages. |
| `--template {standard,technical,recent_grad}` | Layout template (default: `standard`). |
| `--output` | Output DOCX path (default: `resume.docx`). |

Run `uv run python cli.py --help` for the full list.

## Features

### Resume tailoring

Paste your existing resume text (or a raw list of skills and experience) and a job listing. The app calls Claude to produce a tailored resume body that mirrors the job listing's keywords and ranks your experience by relevance.

After generation, up to two **refinement passes** are available. Each pass takes the current resume and the AI reviewer's feedback and produces an improved version — no extra input required. After each refinement, a colour-coded **diff view** shows exactly what changed.

### AI review

Every generation and refinement pass is automatically followed by a structured review: a 0–100 keyword-match + hiring-manager score, strengths, concerns, and ranked suggestions. The score delta is shown after each refinement so you can track improvement.

An **estimated cost** (based on Claude Sonnet 4.6 list pricing) is displayed after each run, cumulative across all generation and refinement passes.

> The model ID and per-token pricing live in [`config.py`](config.py) — update them there if the model or its list price changes.

### Resume sections

The app supports the following resume sections. Optional sections are only included when the source material contains relevant content:

| Section | Required |
|---|---|
| Summary | Optional (toggle in sidebar) |
| Experience | Yes |
| Skills | Yes |
| Education | Yes |
| Certifications | Optional |
| Projects | Optional |

### Templates

After generation, choose from three built-in templates that control section order and how many skill groups are shown. Each option shows a short description to help you pick the right one. Switching templates is instant — no API call needed.

| Template | Section order | Skill groups |
|---|---|---|
| Standard | Summary → Experience → Skills → Education | up to 5 |
| Technical | Summary → Skills → Experience → Projects → Education | up to 6 |
| Recent Graduate | Summary → Education → Experience → Skills → Projects | up to 4 |

### Generation controls

The sidebar Settings section includes two toggles:

- **Allow rewording** *(on by default)* — when enabled, Claude may rephrase and reword your content to better match the job listing. When disabled, bullet points and skills are copied verbatim from your source material; only selection and ordering change.
- **Include summary** *(on by default)* — when disabled, no summary section is generated. Note: if rewording is disabled but a summary is included, Claude still needs to compose the summary from your source material.

Both settings apply to the current run (generate or refine) and can be changed between passes.

### Session save / load

Use the **Save inputs** button in the sidebar to download your current inputs (resume text, job listing, target role, and contact fields) as a JSON file. Upload that file on a future visit to restore everything in one step — useful if you work on multiple job applications or pick up where you left off after closing the browser.

### Export

Download your tailored resume as a **DOCX**, **Markdown** (`.md`), or **plain-text** (`.txt`) file. Markdown keeps your content verbatim (no escaping) for editing or publishing; plain text is ASCII-only for clean pasting into any text field. All formats reflect the currently selected template.

## PDF and ODT export

Install LibreOffice and ensure `soffice` is on your PATH:

**macOS:**
```bash
brew install --cask libreoffice
```

**Ubuntu / Debian:**
```bash
sudo apt install libreoffice --no-install-recommends
```

Restart the app after installing. PDF and ODT download buttons will appear automatically.

## Running the tests

```bash
uv run pytest
```

## Privacy

- Resume content and the job listing are sent to Anthropic's API for tailoring and review.
- Contact information (name, email, phone, location, LinkedIn, GitHub) is **never** sent to the API — it is collected locally and injected into the document at render time only.
- No data is persisted server-side between sessions. The optional session save feature writes a file to your local machine only.
