from __future__ import annotations

import anthropic

from models.schemas import ResumeBodyJSON, ReviewJSON, TAILORING_TOOL

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are an expert resume writer and ATS optimisation specialist.

Your task is to produce a tailored resume body that maximises the applicant's chances of passing
ATS filters and impressing a human hiring manager — using ONLY the content the applicant has
provided. You must NEVER invent experience, companies, job titles, dates, metrics, credentials,
or skills that are not present in the input.

ATS FORMATTING RULES (non-negotiable):
- Use only the standard section names: Summary, Experience, Skills, Education.
- No tables, columns, text boxes, headers/footers, or graphics.
- Action verbs, past tense for prior roles, present tense for current role.
- Bullet points should be concise (one line preferred, two lines maximum).
- Quantify impact wherever the source material provides numbers; do not fabricate metrics.

TAILORING RULES:
- Mirror the exact keywords and phrases from the job listing where truthful.
- Rank and order bullets within each role by relevance to the target role.
- Omit skills and experience that are clearly irrelevant to the target role to save space.
- If a page limit is specified, trim ruthlessly: fewer bullets, shorter summary, fewer skills.

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
    previous_resume: ResumeBodyJSON | None = None,
    review_feedback: ReviewJSON | None = None,
    api_key: str,
) -> ResumeBodyJSON:
    """Call the TailoringAgent and return a validated ResumeBodyJSON.

    Contact fields must NOT be passed to this function — they are injected at render time only.
    """
    client = anthropic.Anthropic(api_key=api_key)

    parts: list[str] = []

    if previous_resume is not None and review_feedback is not None:
        parts.append(
            "## REFINEMENT PASS\n"
            "You are refining a previously tailored resume based on reviewer feedback.\n"
            "Address every concern and act on every suggestion listed below.\n"
        )
        parts.append(f"### Previous Resume (JSON)\n```json\n{previous_resume.model_dump_json(indent=2)}\n```")
        parts.append(
            f"### Reviewer Feedback\n"
            f"Score: {review_feedback.score}/100\n"
            f"Concerns:\n" + "\n".join(f"- {c}" for c in review_feedback.concerns) + "\n"
            f"Suggestions:\n" + "\n".join(f"- {s}" for s in review_feedback.suggestions)
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

    prompt = "\n\n".join(parts)

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[TAILORING_TOOL],
        tool_choice={"type": "tool", "name": "submit_resume"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if tool_use_block is None:
        raise RuntimeError(
            "TailoringAgent: the model did not return a tool_use block. "
            f"Stop reason: {response.stop_reason}. "
            "This is unexpected — try again or check your API key and quota."
        )
    return ResumeBodyJSON(**tool_use_block.input)
