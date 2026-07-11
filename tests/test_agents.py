"""Unit tests for the agent layer with a fully mocked Anthropic client.

These exercise the parts most likely to break on an SDK or model change —
prompt assembly and tool-block extraction — without making any network call.
The Anthropic client is replaced with lightweight fakes that capture the
request kwargs (so we can assert on the assembled prompt) and return canned
responses.
"""

from __future__ import annotations

import pytest

import agents.review as review_agent
import agents.tailoring as tailoring_agent

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


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _Block:
    def __init__(self, type_: str, input_: dict | None = None) -> None:
        self.type = type_
        self.input = input_ or {}


class _Response:
    def __init__(self, content: list, usage: _Usage, stop_reason: str = "tool_use"):
        self.content = content
        self.usage = usage
        self.stop_reason = stop_reason


class _Delta:
    def __init__(self, type_: str, partial_json: str = "") -> None:
        self.type = type_
        self.partial_json = partial_json


class _Event:
    def __init__(self, type_: str, delta: _Delta | None = None) -> None:
        self.type = type_
        self.delta = delta


class _Stream:
    def __init__(self, events: list, final: _Response) -> None:
        self._events = events
        self._final = final

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self._events)

    def get_final_message(self) -> _Response:
        return self._final


class _Messages:
    def __init__(self, capture: dict, *, response=None, stream=None) -> None:
        self._capture = capture
        self._response = response
        self._stream = stream

    def create(self, **kwargs):
        self._capture.update(kwargs)
        return self._response

    def stream(self, **kwargs):
        self._capture.update(kwargs)
        return self._stream


class _Client:
    def __init__(self, messages: _Messages) -> None:
        self.messages = messages


def _install_review_client(monkeypatch, response) -> dict:
    capture: dict = {}
    client = _Client(_Messages(capture, response=response))
    monkeypatch.setattr(review_agent.anthropic, "Anthropic", lambda **kw: client)
    return capture


def _install_tailor_client(monkeypatch, stream) -> dict:
    capture: dict = {}
    client = _Client(_Messages(capture, stream=stream))
    monkeypatch.setattr(tailoring_agent.anthropic, "Anthropic", lambda **kw: client)
    return capture


def _prompt(capture: dict) -> str:
    return capture["messages"][0]["content"]


def _tool_response(tool_input: dict, *, in_tok=100, out_tok=200) -> _Response:
    return _Response([_Block("tool_use", tool_input)], _Usage(in_tok, out_tok))


# --------------------------------------------------------------------------- #
# Tailoring agent
# --------------------------------------------------------------------------- #
def test_tailoring_returns_parsed_resume_and_tokens(monkeypatch):
    stream = _Stream([], _tool_response(VALID_RESUME, in_tok=111, out_tok=222))
    _install_tailor_client(monkeypatch, stream)

    result = tailoring_agent.run(
        resume_text="my resume", job_listing="the job", api_key="k"
    )

    assert result.resume.skills[0].category == "Languages"
    assert result.input_tokens == 111
    assert result.output_tokens == 222


def test_tailoring_missing_tool_block_raises(monkeypatch):
    stream = _Stream(
        [], _Response([_Block("text")], _Usage(1, 1), stop_reason="end_turn")
    )
    _install_tailor_client(monkeypatch, stream)

    with pytest.raises(RuntimeError) as excinfo:
        tailoring_agent.run(resume_text="r", job_listing="j", api_key="k")
    assert "end_turn" in str(excinfo.value)


def test_tailoring_progress_callback_invoked_during_stream(monkeypatch):
    events = [
        _Event("content_block_delta", _Delta("input_json_delta", '{"rationale":')),
        _Event("content_block_delta", _Delta("input_json_delta", ' "value"}')),
        _Event("message_stop"),  # non-delta event must be ignored
    ]
    stream = _Stream(events, _tool_response(VALID_RESUME))
    _install_tailor_client(monkeypatch, stream)

    seen: list[int] = []
    tailoring_agent.run(
        resume_text="r",
        job_listing="j",
        api_key="k",
        progress_callback=seen.append,
    )
    # Two input_json_delta events => two callbacks, each a positive token estimate.
    assert len(seen) == 2
    assert all(n >= 1 for n in seen)


def test_tailoring_base_prompt_omits_optional_blocks(monkeypatch):
    capture = _install_tailor_client(
        monkeypatch, _Stream([], _tool_response(VALID_RESUME))
    )
    tailoring_agent.run(resume_text="my resume", job_listing="the job", api_key="k")

    prompt = _prompt(capture)
    assert "## Applicant's Source Material" in prompt
    assert "## Job Listing" in prompt
    assert "## REFINEMENT PASS" not in prompt
    assert "## Target Role" not in prompt
    assert "## Page Limit" not in prompt
    assert "Verbatim Content Constraint" not in prompt
    assert "## No Summary" not in prompt
    assert "## Skill Group Limit" not in prompt


def test_tailoring_optional_blocks_included_when_set(monkeypatch):
    capture = _install_tailor_client(
        monkeypatch, _Stream([], _tool_response(VALID_RESUME))
    )
    tailoring_agent.run(
        resume_text="r",
        job_listing="j",
        target_role="SRE",
        page_limit=2,
        allow_reword=False,
        include_summary=False,
        max_skill_groups=3,
        api_key="k",
    )

    prompt = _prompt(capture)
    assert "## Target Role" in prompt
    assert "## Page Limit" in prompt
    assert "Verbatim Content Constraint" in prompt
    assert "## No Summary" in prompt
    assert "## Skill Group Limit" in prompt


def test_tailoring_refinement_framing_only_with_prev_and_feedback(monkeypatch):
    from models.schemas import ResumeBodyJSON, ReviewJSON

    prev = ResumeBodyJSON(**VALID_RESUME)
    feedback = ReviewJSON(**VALID_REVIEW)

    capture = _install_tailor_client(
        monkeypatch, _Stream([], _tool_response(VALID_RESUME))
    )
    tailoring_agent.run(
        resume_text="r",
        job_listing="j",
        previous_resume=prev,
        review_feedback=feedback,
        api_key="k",
    )
    prompt = _prompt(capture)
    assert "## REFINEMENT PASS" in prompt
    assert "### Reviewer Feedback" in prompt
    assert "Add a Kubernetes bullet" in prompt  # a suggestion is threaded in

    # previous_resume without feedback must NOT trigger the refinement block.
    capture2 = _install_tailor_client(
        monkeypatch, _Stream([], _tool_response(VALID_RESUME))
    )
    tailoring_agent.run(
        resume_text="r", job_listing="j", previous_resume=prev, api_key="k"
    )
    assert "## REFINEMENT PASS" not in _prompt(capture2)


# --------------------------------------------------------------------------- #
# Review agent
# --------------------------------------------------------------------------- #
def test_review_returns_parsed_review_and_tokens(monkeypatch):
    from models.schemas import ResumeBodyJSON

    resume = ResumeBodyJSON(**VALID_RESUME)
    capture = _install_review_client(
        monkeypatch, _tool_response(VALID_REVIEW, in_tok=30, out_tok=5)
    )

    result = review_agent.run(resume=resume, job_listing="the job", api_key="k")

    assert result.review.score == 82
    assert result.input_tokens == 30
    assert result.output_tokens == 5
    # The serialised resume is embedded in the prompt.
    assert "Languages" in _prompt(capture)


def test_review_missing_tool_block_raises(monkeypatch):
    from models.schemas import ResumeBodyJSON

    resume = ResumeBodyJSON(**VALID_RESUME)
    _install_review_client(
        monkeypatch, _Response([_Block("text")], _Usage(1, 1), stop_reason="end_turn")
    )

    with pytest.raises(RuntimeError) as excinfo:
        review_agent.run(resume=resume, job_listing="j", api_key="k")
    assert "end_turn" in str(excinfo.value)


def test_review_optional_blocks_conditional(monkeypatch):
    from models.schemas import ResumeBodyJSON

    resume = ResumeBodyJSON(**VALID_RESUME)

    capture = _install_review_client(monkeypatch, _tool_response(VALID_REVIEW))
    review_agent.run(resume=resume, job_listing="j", api_key="k")
    prompt = _prompt(capture)
    assert "## Target Role" not in prompt
    assert "## Page Limit" not in prompt

    capture2 = _install_review_client(monkeypatch, _tool_response(VALID_REVIEW))
    review_agent.run(
        resume=resume,
        job_listing="j",
        target_role="SRE",
        page_limit=2,
        api_key="k",
    )
    prompt2 = _prompt(capture2)
    assert "## Target Role" in prompt2
    assert "## Page Limit" in prompt2
