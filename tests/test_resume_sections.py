"""Tests for the shared section-walk abstraction.

These pin the single source of truth for section ordering, skill-group capping,
and optional-section skipping that the DOCX exporter, the Streamlit preview, and
the diff markdown all consume.
"""

from __future__ import annotations

from dataclasses import replace

from models.schemas import ResumeBodyJSON
from resume_sections import capped_skills, resume_to_markdown, walk_sections
from templates.library import DEFAULT_TEMPLATE, TEMPLATES, Section, Template

FULL_RESUME = {
    "summary": "Backend engineer with a decade of Python.",
    "rationale": "Emphasised backend depth.",
    "experience": [
        {
            "title": "Staff Engineer",
            "company": "Acme",
            "location": "Remote",
            "start_date": "Jan 2020",
            "end_date": "Present",
            "bullets": ["Led the platform team", "Cut latency 40%"],
        }
    ],
    "skills": [
        {"category": "Languages", "skills": ["Python", "Go"]},
        {"category": "Cloud", "skills": ["AWS"]},
        {"category": "Tools", "skills": ["Docker"]},
        {"category": "Data", "skills": ["Postgres"]},
    ],
    "education": [
        {"degree": "BSc CS", "institution": "State U", "graduation_date": "May 2012"}
    ],
    "certifications": [
        {"name": "AWS SA", "issuer": "Amazon", "date": "Jun 2023"},
    ],
    "projects": [
        {
            "name": "app-ly",
            "description": "Resume tailor.",
            "technologies": ["Python", "Streamlit"],
            "bullets": ["Shipped it"],
        }
    ],
}


class Recorder:
    """A visitor that records which section hooks fire, in order."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def summary(self, text):
        self.calls.append(("summary", text))

    def experience(self, entries):
        self.calls.append(("experience", len(entries)))

    def skills(self, groups):
        self.calls.append(("skills", [g.category for g in groups]))

    def education(self, entries):
        self.calls.append(("education", len(entries)))

    def certifications(self, entries):
        self.calls.append(("certifications", len(entries)))

    def projects(self, entries):
        self.calls.append(("projects", len(entries)))

    @property
    def sections(self) -> list[str]:
        return [name for name, _ in self.calls]


def _resume(**overrides) -> ResumeBodyJSON:
    return ResumeBodyJSON(**{**FULL_RESUME, **overrides})


def test_walk_follows_template_order():
    resume = _resume()
    rec = Recorder()
    walk_sections(resume, TEMPLATES["technical"], rec)
    # technical: Summary -> Skills -> Experience -> Projects -> Education
    assert rec.sections == [
        "summary",
        "skills",
        "experience",
        "projects",
        "education",
    ]


def test_skill_groups_capped_to_template_limit():
    resume = _resume()  # 4 skill groups
    template = Template(
        id="t", name="T", description="", sections=[Section.SKILLS], max_skill_groups=2
    )
    rec = Recorder()
    walk_sections(resume, template, rec)
    assert rec.calls == [("skills", ["Languages", "Cloud"])]
    # capped_skills is the same logic exposed directly.
    assert [g.category for g in capped_skills(resume, template)] == [
        "Languages",
        "Cloud",
    ]


def test_no_cap_when_max_is_none():
    resume = _resume()
    template = replace(TEMPLATES["technical"], max_skill_groups=None)
    assert len(capped_skills(resume, template)) == 4


def test_optional_sections_skipped_when_empty():
    resume = _resume(summary=None, certifications=None, projects=None)
    # Use a template that lists every section so skips are the only reason to omit.
    template = Template(
        id="all",
        name="All",
        description="",
        sections=[
            Section.SUMMARY,
            Section.EXPERIENCE,
            Section.SKILLS,
            Section.EDUCATION,
            Section.CERTIFICATIONS,
            Section.PROJECTS,
        ],
    )
    rec = Recorder()
    walk_sections(resume, template, rec)
    assert rec.sections == ["experience", "skills", "education"]


def test_optional_sections_present_when_populated():
    resume = _resume()
    template = Template(
        id="all",
        name="All",
        description="",
        sections=[
            Section.SUMMARY,
            Section.EXPERIENCE,
            Section.SKILLS,
            Section.EDUCATION,
            Section.CERTIFICATIONS,
            Section.PROJECTS,
        ],
    )
    rec = Recorder()
    walk_sections(resume, template, rec)
    assert "certifications" in rec.sections
    assert "projects" in rec.sections
    assert "summary" in rec.sections


def test_resume_to_markdown_respects_cap_and_skip():
    resume = _resume(summary=None)
    md = resume_to_markdown(resume, DEFAULT_TEMPLATE)  # standard, cap 5
    # Summary omitted (None); required headers present.
    assert "**Summary**" not in md
    assert "**Experience**" in md
    assert "**Skills**" in md
    assert "**Education**" in md
    # Standard template omits certifications/projects sections entirely.
    assert "**Certifications**" not in md
    assert "Cut latency 40%" in md


def test_resume_to_markdown_caps_skill_lines():
    resume = _resume()
    template = Template(
        id="t", name="T", description="", sections=[Section.SKILLS], max_skill_groups=1
    )
    md = resume_to_markdown(resume, template)
    assert "Languages: Python, Go" in md
    assert "Cloud:" not in md  # capped out
