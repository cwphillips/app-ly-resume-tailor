# Implementation Plan: app-ly
Generated: 2026-03-22
Status: Draft

---

## Table of Contents
1. [Summary Metrics](#summary-metrics)
2. [Technical Architecture Breakdown](#technical-architecture-breakdown)
3. [Development Phases and Milestones](#development-phases-and-milestones)
4. [Resource Allocation and Estimates](#resource-allocation-and-estimates)
5. [Risk Assessment and Mitigation](#risk-assessment-and-mitigation)
6. [Dependencies and Blockers](#dependencies-and-blockers)
7. [Testing Strategy](#testing-strategy)

---

## Summary Metrics

| Item | Value |
|------|-------|
| Total estimated duration | ~2.5 weeks (solo developer) |
| Number of phases | 4 |
| Key external dependency | Anthropic API (`claude-sonnet-4-6`) |
| Optional system dependency | LibreOffice (PDF/ODT export) |
| Critical path | Schemas → Agents → UI → Exporter → Refinement loop |
| Highest risk item | Anthropic tool use schema design (shapes everything downstream) |

---

## Technical Architecture Breakdown

### Module Map

```
app-ly/
├── pyproject.toml              # uv-managed dependencies
├── app.py                      # Streamlit entrypoint; session state, UI layout, pipeline orchestration
├── models/
│   └── schemas.py              # Pydantic models: ResumeBodyJSON, ReviewJSON, ContactFields
├── agents/
│   ├── tailoring.py            # TailoringAgent: builds prompt, calls Anthropic tool use, returns ResumeBodyJSON
│   └── review.py               # ReviewAgent: builds prompt, calls Anthropic tool use, returns ReviewJSON
├── exporters/
│   ├── docx.py                 # DocxExporter: renders ResumeBodyJSON + ContactFields → .docx bytes
│   └── converter.py            # FormatConverter: wraps LibreOffice CLI subprocess → .pdf/.odt bytes
├── plans/
│   └── implementation-plan-app-ly-20260322.md
└── prds/
    └── prd-app-ly-20260322.md
```

### Data Flow

```
                        ┌─────────────────────────────────────────┐
                        │             Streamlit UI (app.py)        │
                        │                                          │
  User Input            │  ┌─────────────┐   ┌──────────────────┐ │
  ─────────────────────►│  │ ContactFields│   │  Content Fields  │ │
                        │  │ (PII — UI   │   │  resume_text     │ │
                        │  │  only)      │   │  job_listing     │ │
                        │  └──────┬──────┘   │  target_role     │ │
                        │         │          │  page_limit      │ │
                        │         │          │  api_key         │ │
                        │         │          └────────┬─────────┘ │
                        │         │                   │           │
                        │         │         ┌─────────▼─────────┐ │
                        │         │         │  TailoringAgent   │ │
                        │         │         │  (Anthropic API)  │ │
                        │         │         └─────────┬─────────┘ │
                        │         │                   │           │
                        │         │         ┌─────────▼─────────┐ │
                        │         │         │   ResumeBodyJSON  │ │
                        │         │         │   + rationale     │ │
                        │         │         └──────┬────────────┘ │
                        │         │                │              │
                        │         │         ┌──────▼────────────┐ │
                        │         │         │   ReviewAgent     │ │
                        │         │         │  (Anthropic API)  │ │
                        │         │         └──────┬────────────┘ │
                        │         │                │              │
                        │         │         ┌──────▼────────────┐ │
                        │         │         │    ReviewJSON     │ │
                        │         │         └──────┬────────────┘ │
                        │         │                │              │
                        │         │    [Optional: Refinement Loop │
                        │         │     max 2x — reruns Tailor   │
                        │         │     + Review with feedback]   │
                        │         │                │              │
                        │         │         ┌──────▼────────────┐ │
                        │         └────────►│   DocxExporter    │ │
                        │                   │  (python-docx)    │ │
                        │                   └──────┬────────────┘ │
                        │                          │              │
                        │                   ┌──────▼────────────┐ │
                        │                   │ FormatConverter   │ │
                        │                   │ (LibreOffice CLI) │ │
                        │                   │ [optional]        │ │
                        │                   └───────────────────┘ │
                        └─────────────────────────────────────────┘
```

### Key Design Decisions

**Anthropic tool use for structured output**

Both agents use the Anthropic tool use API with `tool_choice={"type": "tool", "name": "<tool_name>"}` to force a single, schema-conformant response. This eliminates JSON parsing errors and retry logic. The tool definition is derived directly from the Pydantic models in `schemas.py`.

```python
# Conceptual pattern used in both agents
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[resume_tool_definition],
    tool_choice={"type": "tool", "name": "submit_resume"},
    messages=[{"role": "user", "content": prompt}],
    system=SYSTEM_PROMPT,
)
result = ResumeBodyJSON(**response.content[0].input)
```

**Streamlit session state**

All pipeline state lives in `st.session_state` — never on disk. Key state keys:

| Key | Type | Description |
|-----|------|-------------|
| `resume_body` | `ResumeBodyJSON \| None` | Current tailored resume body |
| `review` | `ReviewJSON \| None` | Current review output |
| `refinement_count` | `int` | Number of refinement passes run (0–2) |
| `docx_bytes` | `bytes \| None` | Most recently generated DOCX |
| `libreoffice_available` | `bool` | Set once at startup via `shutil.which` |

**PII boundary**

The `ContactFields` Pydantic model is constructed from UI inputs and passed only to `DocxExporter.render()`. It is never serialized into any agent prompt. The agents operate exclusively on `ResumeBodyJSON` (which has no contact fields) and the raw text inputs.

**DOCX template**

Implemented programmatically in `docx.py` using `python-docx`. No `.docx` template file on disk — styles are defined in code for reproducibility and portability. The fixed style spec from the PRD maps directly to `python-docx` paragraph and run styles.

---

## Development Phases and Milestones

### Phase 1 — Foundation and Core Pipeline
**Goal:** End-to-end skeleton that can generate a tailored resume and display it in the UI.

**Tasks:**
1. **Project setup**
   - Add dependencies to `pyproject.toml`: `streamlit`, `anthropic`, `python-docx`, `pydantic`
   - Verify Python 3.13 compatibility for all deps
   - Create directory structure (`agents/`, `exporters/`, `models/`)

2. **Define schemas** (`models/schemas.py`)
   - `ResumeBodyJSON` Pydantic model (with `rationale` field)
   - `ReviewJSON` Pydantic model
   - `ContactFields` Pydantic model
   - Derive Anthropic tool definitions from each model

3. **TailoringAgent** (`agents/tailoring.py`)
   - System prompt encoding ATS best practices, content-only instructions, page limit logic
   - User prompt assembly from: resume_text, job_listing, target_role, page_limit
   - Anthropic tool use call returning `ResumeBodyJSON`
   - No PII in any prompt string (enforced by the function signature — contact fields are not a parameter)

4. **ReviewAgent** (`agents/review.py`)
   - System prompt encoding hiring manager / ATS critic persona
   - User prompt assembly from: `ResumeBodyJSON`, job_listing, target_role, page_limit
   - Anthropic tool use call returning `ReviewJSON`

5. **Basic DOCX exporter** (`exporters/docx.py`)
   - Implement fixed template: name header, contact line, section headers, bullets, body text
   - `render(resume: ResumeBodyJSON, contact: ContactFields) -> bytes`
   - Contact fields injected at render time only

6. **Streamlit UI — Phase 1** (`app.py`)
   - Contact fields section (name, email, phone, location, LinkedIn, GitHub)
   - Content fields section (API key w/ env var fallback, resume text, job listing, target role, page limit)
   - "Generate Tailored Resume" button
   - Progress indicators: "Tailoring resume..." → "Running review..."
   - Plain-text resume preview rendered from `ResumeBodyJSON`
   - Collapsible "Why this resume?" rationale panel
   - Review panel: score badge, strengths, concerns, suggestions
   - DOCX download button

**Milestone:** User can paste a resume + job listing, click generate, see a plain-text preview + review, and download a DOCX.

**Success criteria:**
- `ResumeBodyJSON` is always valid and schema-conformant (no parse errors)
- DOCX opens correctly in LibreOffice Writer
- Contact fields appear in DOCX but are absent from all API request logs
- Review score displays as an integer 0–100

---

### Phase 2 — Refinement Loop
**Goal:** Enable the optional feedback loop where review output feeds back into the tailoring agent.

**Tasks:**
1. **Refinement pass logic** (`app.py`)
   - Track `refinement_count` in session state (0–2)
   - Show "Refine Resume" button only when `refinement_count < 2` and a resume exists
   - On click: call `TailoringAgent` with current `ResumeBodyJSON` + `ReviewJSON` + original inputs
   - Then call `ReviewAgent` on the refined output
   - Update `resume_body`, `review`, `docx_bytes` in session state
   - Increment `refinement_count`

2. **TailoringAgent refinement mode** (`agents/tailoring.py`)
   - Add optional `previous_resume: ResumeBodyJSON | None` and `review_feedback: ReviewJSON | None` parameters
   - When present, inject them into the prompt as context for the refinement pass
   - System prompt instructs the agent to address each concern and suggestion

3. **UI refinement indicators**
   - "Refinement 1 of 2" / "Refinement 2 of 2" counter
   - "Max refinements reached" message when limit hit
   - Score delta display: show previous score alongside current score after a refinement

**Milestone:** User can trigger up to 2 refinement passes and see score changes after each.

**Success criteria:**
- Refinement is strictly opt-in
- Export buttons always reflect the most recently generated resume
- `refinement_count` resets to 0 when the user clicks "Generate" again (new session)
- PII never appears in refinement prompts (same boundary as Phase 1)

---

### Phase 3 — Full Export (PDF / ODT)
**Goal:** Enable PDF and ODT download when LibreOffice is available.

**Tasks:**
1. **LibreOffice detection** (`exporters/converter.py`)
   - `is_available() -> bool` using `shutil.which("soffice")`
   - Cache result in `st.session_state.libreoffice_available` at app startup

2. **FormatConverter** (`exporters/converter.py`)
   - `convert(docx_bytes: bytes, target_format: Literal["pdf", "odt"]) -> bytes`
   - Write DOCX to a `tempfile.TemporaryDirectory`, run `soffice --headless --convert-to <format>`, read output, clean up
   - Raise a clear exception if `soffice` exits non-zero

3. **UI export buttons**
   - PDF and ODT download buttons rendered conditionally on `libreoffice_available`
   - Persistent info banner if LibreOffice not found: "PDF and ODT export unavailable — install LibreOffice and restart to enable"
   - Conversion triggered on button click (not pre-computed)

**Milestone:** All three download formats functional when LibreOffice is installed; DOCX-only with clear messaging when it is not.

**Success criteria:**
- PDF and ODT render without visual artifacts from the DOCX source
- Conversion completes in under 10 seconds
- App still runs normally with no LibreOffice installed

---

### Phase 4 — Polish and LAN Accessibility
**Goal:** Production-ready local deployment with robust error handling and LAN access.

**Tasks:**
1. **Error handling throughout**
   - Catch `anthropic.AuthenticationError` → "Invalid API key. Check your key and try again."
   - Catch `anthropic.RateLimitError` → "Rate limit reached. Wait a moment and try again."
   - Catch `anthropic.APIError` → "Anthropic API error: {message}"
   - Catch tool use schema mismatch (shouldn't happen but guard it) → surface clearly
   - Catch LibreOffice subprocess errors → surface with exit code
   - All errors via `st.error()` — no unhandled exceptions

2. **Privacy notice**
   - Persistent info box: "Resume content and job listing are sent to Anthropic's API. Your contact details are never included."

3. **LAN accessibility**
   - Document how to run: `streamlit run app.py --server.address 0.0.0.0 --server.port 8501`
   - Add a `README.md` with setup and run instructions

4. **Final UI polish**
   - Logical field grouping (collapsible sidebar or sections for contact vs. content)
   - Sensible field tab order
   - Disable generate button while a pipeline run is in progress (prevent double-submit)

**Milestone:** App is fully functional, handles all error cases gracefully, and is accessible from any browser on the local network.

**Success criteria:**
- No unhandled exceptions under any tested input condition
- App is reachable at `http://<server-ip>:8501` from the local network
- All error states surface a human-readable message

---

## Resource Allocation and Estimates

This is a solo developer project. Estimates reflect a single developer working at a focused pace including design thinking, debugging, and prompt engineering iteration.

| Phase | Estimated Duration | Notes |
|-------|--------------------|-------|
| Phase 1 — Core Pipeline | 5–6 days | Heaviest phase; schemas + prompt engineering take time to get right |
| Phase 2 — Refinement Loop | 2–3 days | Builds directly on Phase 1 patterns |
| Phase 3 — Full Export | 1–2 days | LibreOffice integration is straightforward once DOCX works |
| Phase 4 — Polish | 1–2 days | Error handling and LAN setup are well-defined |
| **Total** | **~2–2.5 weeks** | Includes 20% buffer for prompt iteration and edge cases |

**Critical path:** `schemas.py` → `TailoringAgent` → `ReviewAgent` → `DocxExporter` → `app.py` UI wiring

All other work depends on the schema definitions being stable. Finalizing `ResumeBodyJSON` and `ReviewJSON` early (ideally in Phase 1, Day 1) prevents rework downstream.

---

## Risk Assessment and Mitigation

### High Impact

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Prompt engineering takes longer than expected to produce consistent, high-quality output | Medium | High | Allocate 2+ days in Phase 1 for prompt iteration with real resume + JD test cases; treat prompt quality as a first-class deliverable |
| Anthropic tool use schema doesn't perfectly constrain output for edge-case inputs (e.g., very short skills list, foreign-language JD) | Medium | High | Test with a variety of input shapes early; add defensive validation in the agent layer even though tool use is enforced |
| DOCX template produces poor pagination for resumes with a lot of content | Medium | Medium | Test with verbose inputs early in Phase 1; adjust font sizes and margins before Phase 3 |

### Medium Impact

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LibreOffice CLI produces inconsistent PDF output on macOS vs. Linux | Low | Medium | Test on both platforms early in Phase 3; document any platform-specific flags |
| Refinement loop produces a lower score than the initial pass | Medium | Medium | Display both scores side-by-side; user always chooses which version to export |
| User includes PII in the resume/skills text area despite warnings | Medium | Medium | Cannot prevent — UI warning is the control; document this limitation clearly |
| `python-docx` font fallback (Liberation Sans) renders differently than Calibri on different OS | Low | Low | Acceptable for v1; document the fallback in README |

### Low Impact

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Streamlit session state resets unexpectedly (e.g., browser refresh) | High | Low | Stateless by design — user just regenerates. No data loss. |
| Anthropic API latency spikes beyond 60 seconds | Low | Low | Surface a timeout message; user can retry |

---

## Dependencies and Blockers

### Python Package Dependencies

| Package | Version constraint | Notes |
|---------|-------------------|-------|
| `streamlit` | `>=1.40` | Tested against recent stable |
| `anthropic` | `>=0.40` | Must support tool use with `tool_choice` |
| `python-docx` | `>=1.1` | 1.x has cleaner API than 0.x |
| `pydantic` | `>=2.0` | V2 required for `.model_json_schema()` used in tool definitions |

### System Dependencies

| Dependency | Required? | Notes |
|-----------|-----------|-------|
| Python 3.13 | Yes | Already pinned in `.python-version` |
| LibreOffice | Optional | PDF/ODT export only; `soffice` must be on PATH |
| `uv` | Recommended | For dependency management; `pip` also works |

### Internal Dependencies (Phase Ordering)

```
schemas.py (Phase 1, Day 1)
    └── TailoringAgent (Phase 1)
    └── ReviewAgent (Phase 1)
    └── DocxExporter (Phase 1)
            └── FormatConverter (Phase 3)
    └── app.py wiring (Phase 1 → Phase 2 → Phase 4)
                └── Refinement loop (Phase 2)
```

`schemas.py` is the only true blocker — everything else can proceed in parallel once schemas are stable.

### Potential Blockers

- **Anthropic API access**: Requires a valid `claude-sonnet-4-6` API key with sufficient credits. Verify access before starting Phase 1.
- **LibreOffice install**: On a headless Linux server, install via `sudo apt install libreoffice --no-install-recommends` (or equivalent). Test the `soffice --headless` command manually before Phase 3.

---

## Testing Strategy

Given this is a solo personal-use tool with no CI/CD infrastructure, the testing strategy is pragmatic: cover the logic that can break silently, and rely on manual end-to-end testing for the AI-dependent pipeline.

### Unit Tests (automate these)

Focus on the non-LLM components where correctness is deterministic:

| Test | What to verify |
|------|---------------|
| `test_schemas.py` | `ResumeBodyJSON` and `ReviewJSON` reject invalid inputs; `ContactFields` optional fields work |
| `test_docx_exporter.py` | `render()` produces valid `.docx` bytes; contact fields appear in output; `rationale` field is absent from rendered doc |
| `test_converter.py` | `is_available()` returns correct bool; `convert()` raises on bad input; output bytes are non-empty when LibreOffice present |
| `test_input_validation.py` | PII fields never appear in any string passed to agent prompt-building functions |

Run with: `uv run pytest`

### Manual / Integration Tests (run these with real API calls)

These require a live Anthropic API key and are run manually during development:

| Scenario | What to check |
|----------|--------------|
| Full resume input + detailed JD | Valid ResumeBodyJSON, good keyword coverage, rationale is meaningful |
| Skills bullet list only (no full resume) | Agent produces a complete resume body without fabricating experience |
| Very short / sparse input | Agent handles gracefully; no hallucination; review flags thin content |
| Page limit = 1 set | Content is trimmed; review score reflects constraint |
| Refinement loop x2 | Score improves or stays stable; export reflects final version |
| Invalid API key | `st.error()` message shown; app does not crash |
| LibreOffice absent | DOCX downloads; info banner shown; PDF/ODT buttons absent |
| LibreOffice present | PDF and ODT download and open correctly |
| LAN access | App loads from a second device on the same network |

### What Not to Test

- LLM output quality (subjective, non-deterministic — covered by manual review)
- Streamlit rendering details (owned by Streamlit)
- LibreOffice conversion fidelity (owned by LibreOffice)

---

## Technical Notes

### Prompt Engineering Guidance

The system prompts for both agents are the highest-leverage part of this project. Recommended approach:

- **Tailoring agent system prompt** should explicitly state: (1) only use content from the provided input, (2) never invent experience, companies, dates, or metrics, (3) ATS formatting rules (standard headers, no tables/columns, action verbs, past tense), (4) page limit as a hard constraint when set.
- **Review agent system prompt** should adopt a dual persona: first pass as an ATS keyword scanner, second pass as a hiring manager skimming for 30 seconds. This produces more actionable feedback than a generic "review" instruction.
- Keep both system prompts in the agent files as module-level constants (not hardcoded in function bodies) so they are easy to iterate on.

### Pydantic → Anthropic Tool Definition

Pydantic V2's `.model_json_schema()` produces a JSON Schema that is directly compatible with the Anthropic tools API `input_schema` field. This keeps the schema definition as the single source of truth:

```python
from pydantic import BaseModel
from anthropic.types import ToolParam

class ResumeBodyJSON(BaseModel):
    summary: str
    rationale: str
    ...

resume_tool: ToolParam = {
    "name": "submit_resume",
    "description": "Submit the tailored resume body.",
    "input_schema": ResumeBodyJSON.model_json_schema(),
}
```

### LibreOffice Temp File Pattern

LibreOffice CLI writes its output to the same directory as the input file. Use `tempfile.TemporaryDirectory` as a context manager to ensure cleanup:

```python
import subprocess
import tempfile
from pathlib import Path

def convert(docx_bytes: bytes, fmt: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "resume.docx"
        src.write_bytes(docx_bytes)
        subprocess.run(
            ["soffice", "--headless", "--convert-to", fmt, "--outdir", tmp, str(src)],
            check=True,
            capture_output=True,
        )
        return (Path(tmp) / f"resume.{fmt}").read_bytes()
```
