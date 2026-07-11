"""Tests for the UI-agnostic tailor->review pipeline.

The pipeline must be importable and runnable without a Streamlit session and
without network access. These tests stub the two agents and assert the
orchestration wiring: token accounting, progress reporting, and how the
refinement-pass arguments are threaded through.
"""

from __future__ import annotations

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


def _stub_agents(monkeypatch, *, calls=None):
    """Patch both agents to return fixed results, recording their kwargs."""
    resume = _parse_resume(VALID_RESUME)
    review = _parse_review(VALID_REVIEW)

    def fake_tailor(**kwargs):
        if calls is not None:
            calls["tailor"] = kwargs
        # Exercise the progress callback the way the real agent would.
        cb = kwargs.get("progress_callback")
        if cb is not None:
            cb(10)
            cb(25)
        return TailoringResult(resume=resume, input_tokens=100, output_tokens=200)

    def fake_review(**kwargs):
        if calls is not None:
            calls["review"] = kwargs
        return ReviewResult(review=review, input_tokens=30, output_tokens=5)

    monkeypatch.setattr(pipeline.tailoring_agent, "run", fake_tailor)
    monkeypatch.setattr(pipeline.review_agent, "run", fake_review)
    return resume, review


def test_run_pipeline_returns_result_and_sums_tokens(monkeypatch):
    resume, review = _stub_agents(monkeypatch)

    result = pipeline.run_pipeline(
        api_key="k",
        resume_text="my resume",
        job_listing="the job",
    )

    assert result.resume is resume
    assert result.review is review
    assert result.input_tokens == 130  # 100 + 30
    assert result.output_tokens == 205  # 200 + 5


def test_run_pipeline_runs_without_a_reporter(monkeypatch):
    # Default no-op reporter path must not raise.
    _stub_agents(monkeypatch)
    result = pipeline.run_pipeline(
        api_key="k", resume_text="r", job_listing="j", progress=None
    )
    assert result.review.score == 82


def test_progress_reporter_receives_hooks(monkeypatch):
    _stub_agents(monkeypatch)

    class Recorder(pipeline.ProgressReporter):
        def __init__(self):
            self.messages: list[str] = []
            self.tokens: list[int] = []
            self.done_calls = 0

        def message(self, text):
            self.messages.append(text)

        def token_progress(self, approx_tokens):
            self.tokens.append(approx_tokens)

        def token_progress_done(self):
            self.done_calls += 1

    rec = Recorder()
    pipeline.run_pipeline(api_key="k", resume_text="r", job_listing="j", progress=rec)

    # Two step-start lines + two "Done" lines.
    assert len(rec.messages) == 4
    assert any("Step 1 of 2" in m for m in rec.messages)
    assert any("Step 2 of 2" in m for m in rec.messages)
    assert rec.tokens == [10, 25]
    assert rec.done_calls == 1


def test_first_pass_label_and_refinement_label(monkeypatch):
    _stub_agents(monkeypatch)

    first = []
    pipeline.run_pipeline(
        api_key="k",
        resume_text="r",
        job_listing="j",
        progress=type(
            "P",
            (pipeline.ProgressReporter,),
            {"message": lambda self, t: first.append(t)},
        )(),
    )
    assert any("Tailoring resume" in m for m in first)

    refine = []
    prev = _parse_resume(VALID_RESUME)
    prev_review = _parse_review(VALID_REVIEW)
    pipeline.run_pipeline(
        api_key="k",
        resume_text="r",
        job_listing="j",
        previous_resume=prev,
        review_feedback=prev_review,
        progress=type(
            "P",
            (pipeline.ProgressReporter,),
            {"message": lambda self, t: refine.append(t)},
        )(),
    )
    assert any("Refinement pass" in m for m in refine)


def test_refinement_args_threaded_to_tailor(monkeypatch):
    calls: dict = {}
    _stub_agents(monkeypatch, calls=calls)

    prev = _parse_resume(VALID_RESUME)
    prev_review = _parse_review(VALID_REVIEW)
    pipeline.run_pipeline(
        api_key="k",
        resume_text="r",
        job_listing="j",
        target_role="SRE",
        page_limit=1,
        allow_reword=False,
        include_summary=False,
        max_skill_groups=4,
        previous_resume=prev,
        review_feedback=prev_review,
    )

    tailor_kwargs = calls["tailor"]
    assert tailor_kwargs["previous_resume"] is prev
    assert tailor_kwargs["review_feedback"] is prev_review
    assert tailor_kwargs["allow_reword"] is False
    assert tailor_kwargs["include_summary"] is False
    assert tailor_kwargs["max_skill_groups"] == 4
    # The review agent does not receive the refinement-only arguments.
    assert "previous_resume" not in calls["review"]
    assert calls["review"]["page_limit"] == 1
