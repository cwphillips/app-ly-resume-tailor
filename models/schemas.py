from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
from anthropic.types import ToolParam


class SkillGroup(BaseModel):
    category: str = Field(
        description="Category label, e.g. 'Languages', 'Tools', 'Frameworks', 'Platforms'."
    )
    skills: list[str] = Field(min_length=1)


class ExperienceEntry(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    start_date: str = Field(description="'MMM YYYY' format (e.g. 'Jan 2022'). Use 'Present' for current roles.")
    end_date: str = Field(description="'MMM YYYY' format (e.g. 'Jan 2022'). Use 'Present' for current roles.")
    bullets: list[str] = Field(min_length=1)


class EducationEntry(BaseModel):
    degree: str
    institution: str
    graduation_date: str = Field(description="'MMM YYYY' format (e.g. 'May 2019').")


class CertificationEntry(BaseModel):
    name: str
    issuer: str
    date: Optional[str] = Field(
        default=None,
        description="'MMM YYYY' format (e.g. 'Jun 2023'), or null if unknown.",
    )


class ProjectEntry(BaseModel):
    name: str
    description: str = Field(description="One sentence describing the project and its purpose.")
    technologies: list[str] = Field(description="Technologies, languages, and tools used.")
    bullets: list[str] = Field(
        min_length=1,
        description="Achievement-focused bullets. Use action verbs, past tense.",
    )
    url: Optional[str] = Field(default=None, description="Project URL or repo link, if public.")


class ResumeBodyJSON(BaseModel):
    summary: Optional[str] = Field(
        default=None,
        description=(
            "A concise professional summary (2-4 sentences). "
            "Return null if the caller has requested no summary."
        ),
    )
    rationale: str = Field(
        description=(
            "A brief explanation (3-6 sentences) of the tailoring decisions made: "
            "which skills were emphasised, which were de-emphasised, and why, "
            "relative to the target job listing."
        )
    )
    experience: list[ExperienceEntry] = Field(
        description="Work experience entries in reverse-chronological order."
    )
    skills: list[SkillGroup] = Field(
        description="Skills grouped by category, relevant to the target role.",
        min_length=1,
    )
    education: list[EducationEntry]
    certifications: Optional[list[CertificationEntry]] = None
    projects: Optional[list[ProjectEntry]] = None
    skipped_sections: list[str] = Field(
        default_factory=list,
        description=(
            "Names of optional sections omitted because source material lacked content. "
            "Use the section's enum value: 'certifications' or 'projects'."
        ),
    )


class ReviewJSON(BaseModel):
    score: int = Field(ge=0, le=100, description="Overall ATS + hiring-manager score (0-100).")
    strengths: list[str] = Field(description="What the resume does well.")
    concerns: list[str] = Field(description="Issues that could hurt the application.")
    suggestions: list[str] = Field(
        description="Specific, actionable improvements ranked by impact."
    )


class ContactFields(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None


# ---------------------------------------------------------------------------
# Anthropic tool definitions (derived from Pydantic schemas)
# ---------------------------------------------------------------------------

TAILORING_TOOL: ToolParam = {
    "name": "submit_resume",
    "description": (
        "Submit the complete tailored resume body. "
        "Do NOT include any contact information (name, email, phone, address, LinkedIn, GitHub) — "
        "those fields are injected separately and must not appear here."
    ),
    "input_schema": ResumeBodyJSON.model_json_schema(),
}

REVIEW_TOOL: ToolParam = {
    "name": "submit_review",
    "description": "Submit the structured review of the tailored resume.",
    "input_schema": ReviewJSON.model_json_schema(),
}
