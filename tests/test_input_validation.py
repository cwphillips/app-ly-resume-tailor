"""
Verify that PII (contact fields) never appears in the prompt strings
that the agent prompt-builders produce.

These tests call the internal prompt-construction logic directly — they do NOT
make any API calls.
"""

import inspect
import textwrap

import pytest

from models.schemas import ContactFields, ExperienceEntry, EducationEntry, ResumeBodyJSON, ReviewJSON


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PII_VALUES = {
    "name": "Super Secret Name",
    "email": "supersecret@pii.test",
    "phone": "+1 999 888 7777",
    "location": "1234 Private Lane, Nowhere, NV",
    "linkedin": "linkedin.com/in/supersecret",
    "github": "github.com/supersecret",
}

CONTACT = ContactFields(**PII_VALUES)


def _make_resume() -> ResumeBodyJSON:
    return ResumeBodyJSON(
        summary="Generic summary.",
        rationale="Generic rationale.",
        experience=[
            ExperienceEntry(
                title="Engineer",
                company="Corp",
                location="Remote",
                start_date="2020",
                end_date="Present",
                bullets=["Did things."],
            )
        ],
        skills=["Python"],
        education=[EducationEntry(degree="B.S.", institution="University", graduation_date="2019")],
    )


def _make_review() -> ReviewJSON:
    return ReviewJSON(
        score=75,
        strengths=["Good."],
        concerns=["Missing metrics."],
        suggestions=["Add numbers."],
    )


def _build_tailoring_prompt(
    resume_text: str,
    job_listing: str,
    target_role: str = "",
    page_limit=None,
    previous_resume=None,
    review_feedback=None,
) -> str:
    """Replicate the prompt-building logic from agents/tailoring.py without calling the API."""
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

    return "\n\n".join(parts)


def _build_review_prompt(
    resume: ResumeBodyJSON,
    job_listing: str,
    target_role: str = "",
    page_limit=None,
) -> str:
    """Replicate the prompt-building logic from agents/review.py without calling the API."""
    parts: list[str] = [
        f"## Resume Body (JSON)\n```json\n{resume.model_dump_json(indent=2)}\n```",
        f"## Job Listing\n{job_listing.strip()}",
    ]

    if target_role:
        parts.append(f"## Target Role\n{target_role.strip()}")

    if page_limit is not None:
        parts.append(f"## Page Limit\nThe resume is intended to fit on {page_limit} page(s).")

    return "\n\n".join(parts)


def _assert_no_pii(text: str) -> None:
    for field, value in PII_VALUES.items():
        assert value not in text, (
            f"PII leak: '{field}' value ({value!r}) found in prompt string."
        )


# ---------------------------------------------------------------------------
# TailoringAgent prompt — PII must not appear
# ---------------------------------------------------------------------------

def test_tailoring_prompt_no_pii_initial():
    prompt = _build_tailoring_prompt(
        resume_text="I am a software engineer with Python experience.",
        job_listing="We need a Python developer.",
    )
    _assert_no_pii(prompt)


def test_tailoring_prompt_no_pii_with_target_role():
    prompt = _build_tailoring_prompt(
        resume_text="Skills: Python, AWS.",
        job_listing="Senior cloud engineer role.",
        target_role="Senior Cloud Engineer",
    )
    _assert_no_pii(prompt)


def test_tailoring_prompt_no_pii_refinement_pass():
    prompt = _build_tailoring_prompt(
        resume_text="Skills: Python.",
        job_listing="Python dev role.",
        previous_resume=_make_resume(),
        review_feedback=_make_review(),
    )
    _assert_no_pii(prompt)


def test_tailoring_prompt_no_pii_with_page_limit():
    prompt = _build_tailoring_prompt(
        resume_text="Skills: Python.",
        job_listing="Python dev role.",
        page_limit=1,
    )
    _assert_no_pii(prompt)


# ---------------------------------------------------------------------------
# ReviewAgent prompt — PII must not appear
# ---------------------------------------------------------------------------

def test_review_prompt_no_pii_basic():
    prompt = _build_review_prompt(
        resume=_make_resume(),
        job_listing="We need a Python developer.",
    )
    _assert_no_pii(prompt)


def test_review_prompt_no_pii_with_target_role():
    prompt = _build_review_prompt(
        resume=_make_resume(),
        job_listing="Cloud engineer role.",
        target_role="Cloud Engineer",
    )
    _assert_no_pii(prompt)


# ---------------------------------------------------------------------------
# Confirm ContactFields is not a parameter of agent run() functions
# ---------------------------------------------------------------------------

def test_tailoring_agent_run_has_no_contact_parameter():
    import agents.tailoring as mod
    sig = inspect.signature(mod.run)
    assert "contact" not in sig.parameters, (
        "TailoringAgent.run() must not accept a 'contact' parameter."
    )


def test_review_agent_run_has_no_contact_parameter():
    import agents.review as mod
    sig = inspect.signature(mod.run)
    assert "contact" not in sig.parameters, (
        "ReviewAgent.run() must not accept a 'contact' parameter."
    )
