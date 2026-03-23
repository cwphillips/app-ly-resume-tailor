from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
from anthropic.types import ToolParam


class ExperienceEntry(BaseModel):
    title: str
    company: str
    location: str
    start_date: str
    end_date: str
    bullets: list[str] = Field(min_length=1)


class EducationEntry(BaseModel):
    degree: str
    institution: str
    graduation_date: str


class ResumeBodyJSON(BaseModel):
    summary: str = Field(description="A concise professional summary (2-4 sentences).")
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
    skills: list[str] = Field(
        description="A flat list of skills relevant to the target role.",
        min_length=1,
    )
    education: list[EducationEntry]


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
