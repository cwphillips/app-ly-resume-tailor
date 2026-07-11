from __future__ import annotations

from dataclasses import dataclass

import agents.review as review_agent
import agents.tailoring as tailoring_agent
from agents.review import ReviewResult
from agents.tailoring import TailoringResult
from config import MODEL_ID
from models.schemas import ResumeBodyJSON, ReviewJSON


class ProgressReporter:
    """No-op progress hook for the tailor→review pipeline.

    The pipeline is UI-agnostic and never imports a UI library. Callers that
    want to surface progress (the Streamlit app, a headless CLI) subclass this
    and pass an instance to :func:`run_pipeline`. Omitting it runs silently,
    which is what tests and simple scripts want.
    """

    def message(self, text: str) -> None:
        """Report a discrete progress line (a step starting or finishing)."""

    def token_progress(self, approx_tokens: int) -> None:
        """Report the running approximate token count while the tailoring model
        streams its response. May be called many times per run."""

    def token_progress_done(self) -> None:
        """Signal that streaming has finished so any live token indicator can be
        cleared."""


@dataclass
class PipelineResult:
    resume: ResumeBodyJSON
    review: ReviewJSON
    input_tokens: int
    output_tokens: int


def run_pipeline(
    *,
    api_key: str,
    resume_text: str,
    job_listing: str,
    target_role: str = "",
    page_limit: int | None = None,
    allow_reword: bool = True,
    include_summary: bool = True,
    max_skill_groups: int | None = None,
    previous_resume: ResumeBodyJSON | None = None,
    review_feedback: ReviewJSON | None = None,
    progress: ProgressReporter | None = None,
) -> PipelineResult:
    """Run the two-agent pipeline (tailor, then review) and return the resulting
    resume, review, and combined token usage.

    UI-agnostic: pass a :class:`ProgressReporter` to surface progress, or omit it
    to run silently. This function has no dependency on Streamlit and is callable
    without a running Streamlit session.

    Contact fields must NOT be passed here — they are injected at render time only.
    """
    reporter = progress or ProgressReporter()

    label = "Refinement pass" if previous_resume is not None else "Tailoring resume"
    reporter.message(f"**Step 1 of 2 — {label}** (model: `{MODEL_ID}`)")

    tailor_result: TailoringResult = tailoring_agent.run(
        resume_text=resume_text,
        job_listing=job_listing,
        target_role=target_role,
        page_limit=page_limit,
        allow_reword=allow_reword,
        include_summary=include_summary,
        max_skill_groups=max_skill_groups,
        previous_resume=previous_resume,
        review_feedback=review_feedback,
        progress_callback=reporter.token_progress,
        api_key=api_key,
    )
    reporter.token_progress_done()
    reporter.message(
        f"  Done — {tailor_result.input_tokens:,} in, "
        f"{tailor_result.output_tokens:,} out."
    )

    reporter.message(f"**Step 2 of 2 — Reviewing resume** (model: `{MODEL_ID}`)")
    review_result: ReviewResult = review_agent.run(
        resume=tailor_result.resume,
        job_listing=job_listing,
        target_role=target_role,
        page_limit=page_limit,
        api_key=api_key,
    )
    reporter.message(
        f"  Done — {review_result.input_tokens:,} in, "
        f"{review_result.output_tokens:,} out."
    )

    return PipelineResult(
        resume=tailor_result.resume,
        review=review_result.review,
        input_tokens=tailor_result.input_tokens + review_result.input_tokens,
        output_tokens=tailor_result.output_tokens + review_result.output_tokens,
    )
