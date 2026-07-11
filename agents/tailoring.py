from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import anthropic
from pydantic import ValidationError

from agents.errors import MalformedModelOutputError
from config import MAX_API_RETRIES, MODEL_ID
from models.schemas import TAILORING_TOOL, ResumeBodyJSON, ReviewJSON


@dataclass
class TailoringResult:
    resume: ResumeBodyJSON
    input_tokens: int
    output_tokens: int


def _parse_resume(tool_input: dict) -> ResumeBodyJSON:
    """Parse the tool payload into a ResumeBodyJSON, mapping schema failures
    to a clear, typed error."""
    try:
        return ResumeBodyJSON(**tool_input)
    except ValidationError as err:
        raise MalformedModelOutputError(
            "The model returned resume data that didn't match the expected "
            "format. This happens occasionally — please try again."
        ) from err


SYSTEM_PROMPT = """\
You are an expert resume writer.

Your task is to produce a tailored resume body that maximises the applicant's chances of
impressing a human hiring manager — using ONLY the content the applicant has
provided. You must NEVER invent experience, companies, job titles, dates, metrics, credentials,
or skills that are not present in the input.

FORMATTING RULES (non-negotiable):
- Use only the standard section names: Summary, Experience, Skills, Education, Certifications, Projects.
- No tables, columns, text boxes, headers/footers, or graphics.
- Action verbs, past tense for prior roles, present tense for current role.
- Bullet points should be concise (one line preferred, two lines maximum).
- Quantify impact wherever the source material provides numbers; do not fabricate metrics.

DATE FORMAT:
- All dates must use 'MMM YYYY' format (e.g. 'Jan 2022'). For current roles use 'Present'.

TAILORING RULES:
- Mirror the exact keywords and phrases from the job listing where truthful.
- Rank and order bullets within each role by relevance to the target role.
- Omit skills and experience that are clearly irrelevant to the target role to save space.
- If a page limit is specified, trim ruthlessly: fewer bullets, shorter summary, fewer skill groups.
- Group skills into meaningful categories (e.g. 'Languages', 'Frameworks', 'Cloud', 'Tools').

OPTIONAL SECTIONS:
- Only populate `certifications` if the source material explicitly lists certifications or credentials.
- Only populate `projects` if the source material explicitly describes projects.
- If there is insufficient content for an optional section, set it to null and add its section
  enum value ('certifications' or 'projects') to `skipped_sections`.

CONTACT INFORMATION:
- Do NOT include name, email, phone, address, LinkedIn, GitHub, or any other personal contact
  details in your output. Those fields are managed separately and must not appear in any field
  you return.

OUTPUT:
- Call the `submit_resume` tool with the complete structured resume body.
- Populate the `rationale` field with a clear explanation of the tailoring choices you made.
"""


def run(
    *,
    resume_text: str,
    job_listing: str,
    target_role: str = "",
    page_limit: int | None = None,
    allow_reword: bool = True,
    include_summary: bool = True,
    max_skill_groups: int | None = None,
    previous_resume: ResumeBodyJSON | None = None,
    review_feedback: ReviewJSON | None = None,
    progress_callback: Callable[[int], None] | None = None,
    api_key: str,
) -> TailoringResult:
    """Call the TailoringAgent and return a TailoringResult with the resume and token usage.

    Contact fields must NOT be passed to this function — they are injected at render time only.
    """
    client = anthropic.Anthropic(api_key=api_key, max_retries=MAX_API_RETRIES)

    parts: list[str] = []

    if previous_resume is not None and review_feedback is not None:
        parts.append(
            "## REFINEMENT PASS\n"
            "You are refining a previously tailored resume based on reviewer feedback.\n"
            "Address every concern and act on every suggestion listed below.\n"
        )
        parts.append(
            f"### Previous Resume (JSON)\n```json\n{previous_resume.model_dump_json(indent=2)}\n```"
        )
        parts.append(
            f"### Reviewer Feedback\n"
            f"Score: {review_feedback.score}/100\n"
            f"Concerns:\n"
            + "\n".join(f"- {c}" for c in review_feedback.concerns)
            + "\n"
            "Suggestions:\n" + "\n".join(f"- {s}" for s in review_feedback.suggestions)
        )
        parts.append("---")

    parts.append(f"## Applicant's Source Material\n{resume_text.strip()}")
    parts.append(f"## Job Listing\n{job_listing.strip()}")

    if target_role:
        parts.append(f"## Target Role\n{target_role.strip()}")

    if page_limit is not None:
        parts.append(
            f"## Page Limit\nThe final resume must fit on {page_limit} page(s). "
            "Trim content aggressively to meet this constraint."
        )

    if not allow_reword:
        parts.append(
            "## Verbatim Content Constraint\n"
            "You must NOT reword, rephrase, or paraphrase any bullet points or skills. "
            "Copy them exactly as written in the source material. "
            "You may only select which items to include and reorder them by relevance."
        )

    if not include_summary:
        parts.append(
            "## No Summary\n"
            "Do NOT generate a summary. Return null for the `summary` field."
        )

    if max_skill_groups is not None:
        parts.append(
            f"## Skill Group Limit\n"
            f"Generate at most {max_skill_groups} skill groups. "
            "Choose the most relevant categories for this role."
        )

    prompt = "\n\n".join(parts)

    json_chars = 0
    with client.messages.stream(
        model=MODEL_ID,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[TAILORING_TOOL],
        tool_choice={"type": "tool", "name": "submit_resume"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for event in stream:
            if (
                event.type == "content_block_delta"
                and event.delta.type == "input_json_delta"
            ):
                json_chars += len(event.delta.partial_json)
                if progress_callback is not None:
                    progress_callback(max(1, json_chars // 4))
        response = stream.get_final_message()

    tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use_block is None:
        raise RuntimeError(
            "TailoringAgent: the model did not return a tool_use block. "
            f"Stop reason: {response.stop_reason}. "
            "This is unexpected — try again or check your API key and quota."
        )
    return TailoringResult(
        resume=_parse_resume(tool_use_block.input),
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
