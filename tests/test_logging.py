"""Tests for the structured-logging setup and the pipeline's log output.

Covers: LOG_LEVEL honouring, idempotent configuration, that generation and
refinement runs emit a token-usage line, that failures are logged with context,
and — critically — that no resume / job-listing / contact text is ever logged.
"""

from __future__ import annotations

import logging

import pytest

import logging_config
import pipeline
from agents.review import ReviewResult, _parse_review
from agents.tailoring import TailoringResult, _parse_resume

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

SECRET_RESUME = "SUPERSECRETRESUME_do_not_log"
SECRET_JOB = "SUPERSECRETJOBLISTING_do_not_log"


def _stub_agents(monkeypatch, *, tailor_raises=None):
    resume = _parse_resume(VALID_RESUME)
    review = _parse_review(VALID_REVIEW)

    def fake_tailor(**kwargs):
        if tailor_raises is not None:
            raise tailor_raises
        return TailoringResult(resume=resume, input_tokens=100, output_tokens=200)

    def fake_review(**kwargs):
        return ReviewResult(review=review, input_tokens=30, output_tokens=5)

    monkeypatch.setattr(pipeline.tailoring_agent, "run", fake_tailor)
    monkeypatch.setattr(pipeline.review_agent, "run", fake_review)


# --------------------------------------------------------------------------- #
# configure_logging
# --------------------------------------------------------------------------- #
def test_configure_logging_honours_log_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    logger = logging_config.configure_logging()
    assert logger.level == logging.DEBUG


def test_configure_logging_defaults_to_info(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    logger = logging_config.configure_logging()
    assert logger.level == logging.INFO


def test_configure_logging_is_idempotent(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    first = logging_config.configure_logging()
    handler_count = len(first.handlers)
    second = logging_config.configure_logging()
    assert second is first
    assert len(second.handlers) == handler_count  # no handler pile-up


def test_bad_log_level_falls_back_to_info(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "NONSENSE")
    logger = logging_config.configure_logging()
    assert logger.level == logging.INFO


# --------------------------------------------------------------------------- #
# Pipeline logging
# --------------------------------------------------------------------------- #
@pytest.fixture
def _capture_pipeline_logs(caplog):
    # Ensure records reach caplog regardless of any earlier configure_logging()
    # call that may have set propagate=False on the app_ly logger.
    logging.getLogger("app_ly").propagate = True
    caplog.set_level(logging.INFO, logger="app_ly.pipeline")
    return caplog


def test_generation_run_logs_token_usage(monkeypatch, _capture_pipeline_logs):
    _stub_agents(monkeypatch)
    pipeline.run_pipeline(api_key="k", resume_text="r", job_listing="j")

    text = _capture_pipeline_logs.text
    assert "pipeline start: mode=generate" in text
    assert "input_tokens=100" in text
    assert "output_tokens=200" in text
    assert "total_input_tokens=130" in text
    assert "total_output_tokens=205" in text


def test_refinement_run_is_logged_as_refine(monkeypatch, _capture_pipeline_logs):
    _stub_agents(monkeypatch)
    prev = _parse_resume(VALID_RESUME)
    feedback = _parse_review(VALID_REVIEW)
    pipeline.run_pipeline(
        api_key="k",
        resume_text="r",
        job_listing="j",
        previous_resume=prev,
        review_feedback=feedback,
    )
    assert "mode=refine" in _capture_pipeline_logs.text


def test_failure_is_logged_with_traceback(monkeypatch, _capture_pipeline_logs):
    _stub_agents(monkeypatch, tailor_raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        pipeline.run_pipeline(api_key="k", resume_text="r", job_listing="j")

    records = [r for r in _capture_pipeline_logs.records if r.levelno >= logging.ERROR]
    assert records, "a failure should be logged at ERROR level"
    assert any("pipeline failed" in r.getMessage() for r in records)
    assert any(r.exc_info is not None for r in records)  # traceback attached


def test_no_pii_in_logs(monkeypatch, _capture_pipeline_logs):
    _stub_agents(monkeypatch)
    pipeline.run_pipeline(
        api_key="k", resume_text=SECRET_RESUME, job_listing=SECRET_JOB
    )
    text = _capture_pipeline_logs.text
    assert SECRET_RESUME not in text
    assert SECRET_JOB not in text
