import io

import pytest
from docx import Document

from exporters.docx import render
from models.schemas import ContactFields, EducationEntry, ExperienceEntry, ResumeBodyJSON


def _make_resume(**overrides) -> ResumeBodyJSON:
    defaults = dict(
        summary="A seasoned engineer with cloud experience.",
        rationale="Focused on Python and distributed systems to match the JD.",
        experience=[
            ExperienceEntry(
                title="Senior Engineer",
                company="TechCo",
                location="Remote",
                start_date="Mar 2021",
                end_date="Present",
                bullets=["Led migration to Kubernetes.", "Reduced costs by 20%."],
            )
        ],
        skills=["Python", "Kubernetes", "AWS"],
        education=[
            EducationEntry(
                degree="B.S. Computer Science",
                institution="State University",
                graduation_date="May 2018",
            )
        ],
    )
    defaults.update(overrides)
    return ResumeBodyJSON(**defaults)


def _make_contact(**overrides) -> ContactFields:
    defaults = dict(name="Jane Smith", email="jane@example.com")
    defaults.update(overrides)
    return ContactFields(**defaults)


def _full_text(doc: Document) -> str:
    return "\n".join(p.text for p in doc.paragraphs)


# ---------------------------------------------------------------------------
# Output validity
# ---------------------------------------------------------------------------

def test_render_returns_bytes():
    result = render(_make_resume(), _make_contact())
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_render_produces_valid_docx():
    result = render(_make_resume(), _make_contact())
    doc = Document(io.BytesIO(result))
    assert len(doc.paragraphs) > 0


# ---------------------------------------------------------------------------
# Contact fields appear in output
# ---------------------------------------------------------------------------

def test_contact_name_in_docx():
    contact = _make_contact(name="Alice Wonderland", email="alice@example.com")
    doc = Document(io.BytesIO(render(_make_resume(), contact)))
    assert "Alice Wonderland" in _full_text(doc)


def test_contact_email_in_docx():
    contact = _make_contact(email="alice@example.com")
    doc = Document(io.BytesIO(render(_make_resume(), contact)))
    assert "alice@example.com" in _full_text(doc)


def test_optional_contact_fields_in_docx():
    contact = _make_contact(
        phone="+1 555 123 4567",
        location="Austin, TX",
        linkedin="linkedin.com/in/alice",
        github="github.com/alice",
    )
    doc = Document(io.BytesIO(render(_make_resume(), contact)))
    text = _full_text(doc)
    assert "+1 555 123 4567" in text
    assert "Austin, TX" in text
    assert "linkedin.com/in/alice" in text
    assert "github.com/alice" in text


# ---------------------------------------------------------------------------
# Resume content appears in output
# ---------------------------------------------------------------------------

def test_summary_in_docx():
    resume = _make_resume(summary="Unique summary text for testing.")
    doc = Document(io.BytesIO(render(resume, _make_contact())))
    assert "Unique summary text for testing." in _full_text(doc)


def test_experience_title_in_docx():
    doc = Document(io.BytesIO(render(_make_resume(), _make_contact())))
    assert "Senior Engineer" in _full_text(doc)


def test_skills_in_docx():
    doc = Document(io.BytesIO(render(_make_resume(), _make_contact())))
    text = _full_text(doc)
    assert "Python" in text
    assert "Kubernetes" in text


def test_education_in_docx():
    doc = Document(io.BytesIO(render(_make_resume(), _make_contact())))
    assert "State University" in _full_text(doc)


# ---------------------------------------------------------------------------
# Rationale must NOT appear in the rendered document
# ---------------------------------------------------------------------------

def test_rationale_absent_from_docx():
    resume = _make_resume(rationale="This rationale should never appear in the DOCX output.")
    doc = Document(io.BytesIO(render(resume, _make_contact())))
    assert "This rationale should never appear in the DOCX output." not in _full_text(doc)
