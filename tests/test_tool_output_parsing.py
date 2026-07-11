"""Tests for schema-validation handling when parsing agent tool output.

A structurally-valid tool call whose fields fail Pydantic validation should
surface as a typed MalformedModelOutputError, not a bare ValidationError that
the app reports as a generic "Unexpected error".
"""

import pytest

from agents.errors import MalformedModelOutputError
from agents.review import _parse_review
from agents.tailoring import _parse_resume

VALID_RESUME = {
    "rationale": "Emphasised backend skills relevant to the role.",
    "experience": [],
    "skills": [{"category": "Languages", "skills": ["Python"]}],
    "education": [],
}

VALID_REVIEW = {
    "score": 82,
    "strengths": ["Clear impact metrics"],
    "concerns": ["Thin on cloud experience"],
    "suggestions": ["Add a Kubernetes bullet"],
}


def test_valid_resume_payload_parses():
    resume = _parse_resume(VALID_RESUME)
    assert resume.skills[0].category == "Languages"


def test_valid_review_payload_parses():
    review = _parse_review(VALID_REVIEW)
    assert review.score == 82


def test_malformed_resume_raises_typed_error():
    # skills has min_length=1, so an empty list fails validation.
    bad = {**VALID_RESUME, "skills": []}
    with pytest.raises(MalformedModelOutputError) as excinfo:
        _parse_resume(bad)
    assert "please try again" in str(excinfo.value).lower()


def test_malformed_resume_missing_required_field_raises_typed_error():
    bad = {k: v for k, v in VALID_RESUME.items() if k != "rationale"}
    with pytest.raises(MalformedModelOutputError):
        _parse_resume(bad)


def test_malformed_review_out_of_range_score_raises_typed_error():
    # score is constrained to 0-100.
    bad = {**VALID_REVIEW, "score": 150}
    with pytest.raises(MalformedModelOutputError) as excinfo:
        _parse_review(bad)
    assert "please try again" in str(excinfo.value).lower()


def test_typed_error_is_a_runtime_error():
    # app.py catches it distinctly, but it stays a RuntimeError for callers
    # that only handle the broad category.
    assert issubclass(MalformedModelOutputError, RuntimeError)
