import pytest
from pydantic import ValidationError

from models.schemas import (
    CertificationEntry,
    ContactFields,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    ReviewJSON,
    ResumeBodyJSON,
    SkillGroup,
    TAILORING_TOOL,
    REVIEW_TOOL,
)


# ---------------------------------------------------------------------------
# ResumeBodyJSON
# ---------------------------------------------------------------------------

def _valid_resume() -> dict:
    return {
        "summary": "Experienced software engineer.",
        "rationale": "Emphasised Python and cloud skills to match the JD.",
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Acme Corp",
                "location": "San Francisco, CA",
                "start_date": "Jan 2020",
                "end_date": "Present",
                "bullets": ["Built distributed systems.", "Reduced latency by 30%."],
            }
        ],
        "skills": [{"category": "Languages", "skills": ["Python", "SQL"]}],
        "education": [
            {
                "degree": "B.S. Computer Science",
                "institution": "State University",
                "graduation_date": "May 2019",
            }
        ],
    }


def test_resume_body_valid():
    resume = ResumeBodyJSON(**_valid_resume())
    assert resume.summary == "Experienced software engineer."
    assert len(resume.experience) == 1
    assert resume.experience[0].title == "Software Engineer"


def test_resume_body_missing_required_field():
    data = _valid_resume()
    del data["summary"]
    with pytest.raises(ValidationError):
        ResumeBodyJSON(**data)


def test_resume_body_empty_skills_rejected():
    data = _valid_resume()
    data["skills"] = []
    with pytest.raises(ValidationError):
        ResumeBodyJSON(**data)


def test_resume_body_empty_bullets_rejected():
    data = _valid_resume()
    data["experience"][0]["bullets"] = []
    with pytest.raises(ValidationError):
        ResumeBodyJSON(**data)


def test_resume_body_has_rationale():
    resume = ResumeBodyJSON(**_valid_resume())
    assert resume.rationale


# ---------------------------------------------------------------------------
# SkillGroup
# ---------------------------------------------------------------------------

def test_skill_group_valid():
    group = SkillGroup(category="Languages", skills=["Python", "SQL"])
    assert group.category == "Languages"
    assert group.skills == ["Python", "SQL"]


def test_skill_group_empty_skills_rejected():
    with pytest.raises(ValidationError):
        SkillGroup(category="Languages", skills=[])


# ---------------------------------------------------------------------------
# CertificationEntry
# ---------------------------------------------------------------------------

def test_certification_entry_with_date():
    cert = CertificationEntry(name="AWS SAA", issuer="Amazon", date="Jun 2023")
    assert cert.date == "Jun 2023"


def test_certification_entry_optional_date():
    cert = CertificationEntry(name="AWS SAA", issuer="Amazon")
    assert cert.date is None


# ---------------------------------------------------------------------------
# ProjectEntry
# ---------------------------------------------------------------------------

def test_project_entry_valid():
    proj = ProjectEntry(
        name="My Project",
        description="A tool for doing things.",
        technologies=["Python", "Docker"],
        bullets=["Built the thing.", "Reduced cost by 15%."],
    )
    assert proj.name == "My Project"
    assert proj.url is None


def test_project_entry_empty_bullets_rejected():
    with pytest.raises(ValidationError):
        ProjectEntry(
            name="My Project",
            description="A tool.",
            technologies=["Python"],
            bullets=[],
        )


# ---------------------------------------------------------------------------
# ResumeBodyJSON optional sections and skipped_sections
# ---------------------------------------------------------------------------

def test_skipped_sections_defaults_to_empty_list():
    resume = ResumeBodyJSON(**_valid_resume())
    assert resume.skipped_sections == []


def test_skipped_sections_populated():
    data = _valid_resume()
    data["skipped_sections"] = ["certifications", "projects"]
    resume = ResumeBodyJSON(**data)
    assert resume.skipped_sections == ["certifications", "projects"]


def test_certifications_default_none():
    resume = ResumeBodyJSON(**_valid_resume())
    assert resume.certifications is None


def test_projects_default_none():
    resume = ResumeBodyJSON(**_valid_resume())
    assert resume.projects is None


def test_experience_location_optional():
    data = _valid_resume()
    data["experience"][0].pop("location")
    resume = ResumeBodyJSON(**data)
    assert resume.experience[0].location is None


# ---------------------------------------------------------------------------
# ReviewJSON
# ---------------------------------------------------------------------------

def _valid_review() -> dict:
    return {
        "score": 78,
        "strengths": ["Good keyword coverage."],
        "concerns": ["Missing leadership examples."],
        "suggestions": ["Add metrics to bullets."],
    }


def test_review_valid():
    review = ReviewJSON(**_valid_review())
    assert review.score == 78


def test_review_score_below_zero_rejected():
    data = _valid_review()
    data["score"] = -1
    with pytest.raises(ValidationError):
        ReviewJSON(**data)


def test_review_score_above_100_rejected():
    data = _valid_review()
    data["score"] = 101
    with pytest.raises(ValidationError):
        ReviewJSON(**data)


def test_review_score_boundary_values():
    for score in (0, 100):
        data = _valid_review()
        data["score"] = score
        review = ReviewJSON(**data)
        assert review.score == score


# ---------------------------------------------------------------------------
# ContactFields
# ---------------------------------------------------------------------------

def test_contact_required_fields():
    contact = ContactFields(name="Jane Smith", email="jane@example.com")
    assert contact.name == "Jane Smith"
    assert contact.email == "jane@example.com"


def test_contact_optional_fields_default_none():
    contact = ContactFields(name="Jane Smith", email="jane@example.com")
    assert contact.phone is None
    assert contact.location is None
    assert contact.linkedin is None
    assert contact.github is None


def test_contact_optional_fields_accepted():
    contact = ContactFields(
        name="Jane Smith",
        email="jane@example.com",
        phone="+1 555 000 0000",
        location="Austin, TX",
        linkedin="linkedin.com/in/jane",
        github="github.com/jane",
    )
    assert contact.phone == "+1 555 000 0000"
    assert contact.github == "github.com/jane"


def test_contact_missing_name_rejected():
    with pytest.raises(ValidationError):
        ContactFields(email="jane@example.com")


def test_contact_missing_email_rejected():
    with pytest.raises(ValidationError):
        ContactFields(name="Jane Smith")


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

def test_tailoring_tool_structure():
    assert TAILORING_TOOL["name"] == "submit_resume"
    assert "input_schema" in TAILORING_TOOL
    schema = TAILORING_TOOL["input_schema"]
    assert "properties" in schema
    assert "rationale" in schema["properties"]


def test_review_tool_structure():
    assert REVIEW_TOOL["name"] == "submit_review"
    assert "input_schema" in REVIEW_TOOL
    schema = REVIEW_TOOL["input_schema"]
    assert "score" in schema["properties"]
