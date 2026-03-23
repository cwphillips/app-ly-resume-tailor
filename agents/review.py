from __future__ import annotations

import anthropic

from models.schemas import ResumeBodyJSON, ReviewJSON, REVIEW_TOOL

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are a dual-mode resume evaluator. You will assess the provided resume body against the
target job listing in two passes:

PASS 1 — ATS KEYWORD SCANNER:
Scan the resume for exact and semantically equivalent matches to the keywords, skills, tools,
and phrases in the job listing. Note gaps and over-represented terms.

PASS 2 — HIRING MANAGER (30-SECOND SKIM):
Read the resume as a hiring manager who has 30 seconds per candidate. Ask: Is the value
proposition immediately clear? Does the experience map to the role? Are there red flags?

SCORING (0-100):
- 90-100: Excellent keyword coverage, compelling narrative, no red flags.
- 70-89: Good match with minor gaps or weak phrasing.
- 50-69: Moderate match; noticeable gaps or structural issues.
- Below 50: Poor match or significant problems.

If a page limit was specified, factor in whether the content appears appropriately trimmed.

OUTPUT:
- Call the `submit_review` tool with a structured assessment.
- `strengths`: what the resume does well (be specific, cite examples).
- `concerns`: issues that could hurt the application (ranked by severity).
- `suggestions`: actionable improvements ranked by expected impact.
"""


def run(
    *,
    resume: ResumeBodyJSON,
    job_listing: str,
    target_role: str = "",
    page_limit: int | None = None,
    api_key: str,
) -> ReviewJSON:
    """Call the ReviewAgent and return a validated ReviewJSON."""
    client = anthropic.Anthropic(api_key=api_key)

    parts: list[str] = [
        f"## Resume Body (JSON)\n```json\n{resume.model_dump_json(indent=2)}\n```",
        f"## Job Listing\n{job_listing.strip()}",
    ]

    if target_role:
        parts.append(f"## Target Role\n{target_role.strip()}")

    if page_limit is not None:
        parts.append(f"## Page Limit\nThe resume is intended to fit on {page_limit} page(s).")

    prompt = "\n\n".join(parts)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[REVIEW_TOOL],
        tool_choice={"type": "tool", "name": "submit_review"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if tool_use_block is None:
        raise RuntimeError(
            "ReviewAgent: the model did not return a tool_use block. "
            f"Stop reason: {response.stop_reason}. "
            "This is unexpected — try again or check your API key and quota."
        )
    return ReviewJSON(**tool_use_block.input)
