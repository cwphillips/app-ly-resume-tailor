# app-ly

A locally-hosted AI resume tailoring tool. Paste your resume (or a skills list) and a job listing; the app produces an ATS-optimised, tailored resume using Claude.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- An [Anthropic API key](https://console.anthropic.com/)
- LibreOffice *(optional — required only for PDF and ODT export)*

## Setup

```bash
# Clone / navigate to the project
cd app-ly

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

## Privacy

- Resume content and the job listing are sent to Anthropic's API for tailoring and review.
- Contact information (name, email, phone, location, LinkedIn, GitHub) is **never** sent to the API — it is collected locally and injected into the document at render time only.
- No data is persisted between sessions.
