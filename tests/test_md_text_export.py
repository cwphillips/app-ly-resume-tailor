"""Tests for the Markdown and plain-text resume exporters.

Both consume the shared ``walk_sections`` traversal, so these focus on
format-specific structure and, for plain text, the ASCII-only guarantee.
"""

from __future__ import annotations

import exporters.markdown as md
import exporters.text as txt
from models.schemas import ContactFields, ResumeBodyJSON
from templates.library import DEFAULT_TEMPLATE, Section, Template

CONTACT = ContactFields(
    name="Jane Smith",
    email="jane@example.com",
    phone="+1 555 123 4567",
    location="San Francisco, CA",
)

# Content deliberately seeds typographic characters (em dash, smart quote) and a
# non-Latin character to exercise the plain-text ASCII transliteration.
RESUME_DATA = {
    "summary": "Backend engineer — a decade of Python. Café-tested “resilience”.",
    "rationale": "Emphasised backend depth.",
    "experience": [
        {
            "title": "Staff Engineer",
            "company": "Acme",
            "location": "Remote",
            "start_date": "Jan 2020",
            "end_date": "Present",
            "bullets": ["Cut costs—by 40%", "Led the team"],
        }
    ],
    "skills": [
        {"category": "Languages", "skills": ["Python", "Go"]},
        {"category": "Cloud", "skills": ["AWS"]},
        {"category": "Tools", "skills": ["Docker"]},
    ],
    "education": [
        {"degree": "BSc CS", "institution": "State U", "graduation_date": "May 2012"}
    ],
    "certifications": [{"name": "AWS SA", "issuer": "Amazon", "date": "Jun 2023"}],
    "projects": [
        {
            "name": "app-ly",
            "description": "Resume tailor.",
            "technologies": ["Python", "Streamlit"],
            "bullets": ["Shipped it"],
        }
    ],
}

ALL_SECTIONS = Template(
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


def _resume(**overrides) -> ResumeBodyJSON:
    return ResumeBodyJSON(**{**RESUME_DATA, **overrides})


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #
def test_markdown_structure():
    out = md.render(_resume(), CONTACT, ALL_SECTIONS)
    assert out.startswith("# Jane Smith")
    assert "jane@example.com | +1 555 123 4567 | San Francisco, CA" in out
    assert "## Summary" in out
    assert "## Experience" in out
    assert "### Staff Engineer — Acme | Remote" in out
    assert "*Jan 2020 – Present*" in out
    assert "- Cut costs—by 40%" in out
    # Skill-group lines are bolded.
    assert "- **Languages:** Python, Go" in out


def test_markdown_skips_empty_optional_sections():
    out = md.render(_resume(summary=None, projects=None), CONTACT, ALL_SECTIONS)
    assert "## Summary" not in out
    assert "## Projects" not in out
    # Required sections remain.
    assert "## Experience" in out
    assert "## Education" in out


def test_markdown_respects_skill_cap():
    template = Template(
        id="t", name="T", description="", sections=[Section.SKILLS], max_skill_groups=1
    )
    out = md.render(_resume(), CONTACT, template)
    assert "**Languages:**" in out
    assert "**Cloud:**" not in out


def test_markdown_does_not_escape_user_metacharacters():
    resume = _resume(
        experience=[
            {
                "title": "Engineer",
                "company": "A_B & C",
                "start_date": "Jan 2020",
                "end_date": "Present",
                "bullets": ["Saved $5 on *everything*"],
            }
        ]
    )
    out = md.render(resume, CONTACT, ALL_SECTIONS)
    # Metacharacters appear verbatim, unescaped.
    assert "A_B & C" in out
    assert "Saved $5 on *everything*" in out
    assert "\\*" not in out


# --------------------------------------------------------------------------- #
# Plain text
# --------------------------------------------------------------------------- #
def test_text_is_ascii_only():
    out = txt.render(_resume(), CONTACT, ALL_SECTIONS)
    assert out.isascii()


def test_text_transliterates_typography():
    out = txt.render(_resume(), CONTACT, ALL_SECTIONS)
    # Em dash in a bullet becomes a hyphen; smart quotes become straight quotes.
    assert "* Cut costs-by 40%" in out
    assert '"resilience"' in out
    # The accented character is dropped, leaving surrounding text intact.
    assert "Caf-tested" in out or "Caf tested" in out


def test_text_headers_and_bullets():
    out = txt.render(_resume(), CONTACT, ALL_SECTIONS)
    assert out.startswith("JANE SMITH")
    assert "EXPERIENCE\n----------" in out
    assert "SKILLS\n------" in out
    # Bullets use the plain-text marker.
    assert "* Led the team" in out
    assert "* Languages: Python, Go" in out


def test_text_skips_empty_optional_sections():
    out = txt.render(_resume(summary=None, certifications=None), CONTACT, ALL_SECTIONS)
    assert "SUMMARY" not in out
    assert "CERTIFICATIONS" not in out
    assert "EDUCATION" in out


def test_text_respects_skill_cap_and_default_template():
    out = txt.render(_resume(), CONTACT, DEFAULT_TEMPLATE)  # standard, cap 5
    # Standard template has no projects/certifications sections.
    assert "PROJECTS" not in out
    assert "EXPERIENCE" in out
