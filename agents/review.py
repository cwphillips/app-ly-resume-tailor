from __future__ import annotations

from dataclasses import dataclass

import anthropic
from pydantic import ValidationError

from agents.errors import MalformedModelOutputError
from config import MAX_API_RETRIES, MODEL_ID
from models.schemas import REVIEW_TOOL, ResumeBodyJSON, ReviewJSON


@dataclass
class ReviewResult:
    review: ReviewJSON
    input_tokens: int
    output_tokens: int


def _parse_review(tool_input: dict) -> ReviewJSON:
    """Parse the tool payload into a ReviewJSON, mapping schema failures to a
    clear, typed error."""
    try:
        return ReviewJSON(**tool_input)
    except ValidationError as err:
        raise MalformedModelOutputError(
            "The model returned review data that didn't match the expected "
            "format. This happens occasionally — please try again."
        ) from err


SYSTEM_PROMPT = """\
You are a dual-mode resume evaluator. You will assess the provided resume body against the
target job listing in two passes:

PASS 1 — KEYWORD MATCH:
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
- Be terse. Each list item must fit on one line (≤25 words). No explanatory prose.
- `strengths`: up to 3 bullet-style phrases — what the resume does well.
- `concerns`: up to 3 bullet-style phrases — issues that could hurt the application, ranked by severity.
- `suggestions`: up to 3 imperative phrases — actionable improvements ranked by expected impact.
"""


def run(
    *,
    resume: ResumeBodyJSON,
    job_listing: str,
    target_role: str = "",
    page_limit: int | None = None,
    api_key: str,
) -> ReviewResult:
    """Call the ReviewAgent and return a ReviewResult with the review and token usage."""
    client = anthropic.Anthropic(api_key=api_key, max_retries=MAX_API_RETRIES)

    parts: list[str] = [
        f"## Resume Body (JSON)\n```json\n{resume.model_dump_json(indent=2)}\n```",
        f"## Job Listing\n{job_listing.strip()}",
    ]

    if target_role:
        parts.append(f"## Target Role\n{target_role.strip()}")

    if page_limit is not None:
        parts.append(
            f"## Page Limit\nThe resume is intended to fit on {page_limit} page(s)."
        )

    prompt = "\n\n".join(parts)

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=768,
        system=SYSTEM_PROMPT,
        tools=[REVIEW_TOOL],
        tool_choice={"type": "tool", "name": "submit_review"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use_block is None:
        raise RuntimeError(
            "ReviewAgent: the model did not return a tool_use block. "
            f"Stop reason: {response.stop_reason}. "
            "This is unexpected — try again or check your API key and quota."
        )
    return ReviewResult(
        review=_parse_review(tool_use_block.input),
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
