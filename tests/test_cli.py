"""Tests for the headless CLI.

The pipeline and DOCX exporter are stubbed, so these run without network access
or a real API key. They cover argument parsing, the API-key/file guards, and
that a successful run writes the DOCX and prints the review score.
"""

from __future__ import annotations

import pytest

import cli
import pipeline
from models.schemas import ResumeBodyJSON, ReviewJSON

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


def _write_inputs(tmp_path):
    resume = tmp_path / "resume.txt"
    job = tmp_path / "job.txt"
    resume.write_text("Senior engineer with Python experience.", encoding="utf-8")
    job.write_text("Looking for a Python backend engineer.", encoding="utf-8")
    return resume, job


def _stub_pipeline(monkeypatch, *, capture=None):
    """Patch the pipeline to return a canned result and the exporter to a stub."""
    result = pipeline.PipelineResult(
        resume=ResumeBodyJSON(**VALID_RESUME),
        review=ReviewJSON(**VALID_REVIEW),
        input_tokens=100,
        output_tokens=200,
    )

    def fake_run(**kwargs):
        if capture is not None:
            capture.update(kwargs)
        return result

    monkeypatch.setattr(cli.pipeline, "run_pipeline", fake_run)
    monkeypatch.setattr(cli.docx_exporter, "render", lambda *a, **k: b"DOCX-BYTES")
    return result


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_missing_api_key_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resume, job = _write_inputs(tmp_path)
    code = cli.main([str(resume), str(job), "--name", "Jane", "--email", "j@x.com"])
    assert code == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_missing_input_file_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    _stub_pipeline(monkeypatch)
    missing = tmp_path / "nope.txt"
    job = tmp_path / "job.txt"
    job.write_text("job", encoding="utf-8")
    code = cli.main([str(missing), str(job), "--name", "Jane", "--email", "j@x.com"])
    assert code == 2
    assert "reading input file" in capsys.readouterr().err.lower()


def test_empty_resume_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    _stub_pipeline(monkeypatch)
    resume = tmp_path / "resume.txt"
    job = tmp_path / "job.txt"
    resume.write_text("   \n  ", encoding="utf-8")
    job.write_text("job", encoding="utf-8")
    code = cli.main([str(resume), str(job), "--name", "Jane", "--email", "j@x.com"])
    assert code == 2
    assert "empty" in capsys.readouterr().err.lower()


def test_happy_path_writes_docx_and_prints_score(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    capture: dict = {}
    _stub_pipeline(monkeypatch, capture=capture)
    resume, job = _write_inputs(tmp_path)
    out = tmp_path / "out.docx"

    code = cli.main(
        [
            str(resume),
            str(job),
            "--name",
            "Jane Smith",
            "--email",
            "jane@example.com",
            "--target-role",
            "Backend Engineer",
            "--page-limit",
            "1",
            "--template",
            "technical",
            "--output",
            str(out),
        ]
    )

    assert code == 0
    assert out.read_bytes() == b"DOCX-BYTES"

    stdout = capsys.readouterr().out
    assert "Review score: 82/100" in stdout
    assert "Add a Kubernetes bullet" in stdout

    # Pipeline received the parsed args, and the template's skill-group cap.
    assert capture["target_role"] == "Backend Engineer"
    assert capture["page_limit"] == 1
    assert capture["max_skill_groups"] == 6  # technical template cap


def test_contact_never_passed_to_pipeline(tmp_path, monkeypatch):
    # The pipeline must not receive contact fields — they are render-time only.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    capture: dict = {}
    _stub_pipeline(monkeypatch, capture=capture)
    resume, job = _write_inputs(tmp_path)
    cli.main(
        [
            str(resume),
            str(job),
            "--name",
            "Jane Smith",
            "--email",
            "jane@example.com",
            "--phone",
            "555-1234",
            "--output",
            str(tmp_path / "o.docx"),
        ]
    )
    joined = " ".join(str(v) for v in capture.values())
    assert "Jane Smith" not in joined
    assert "jane@example.com" not in joined
    assert "555-1234" not in joined


def test_page_limit_out_of_range_rejected():
    with pytest.raises(SystemExit) as exc:
        cli.main(["r.txt", "j.txt", "--name", "J", "--email", "e", "--page-limit", "9"])
    assert exc.value.code == 2  # argparse usage error
