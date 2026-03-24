from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Section(str, Enum):
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    SKILLS = "skills"
    EDUCATION = "education"
    CERTIFICATIONS = "certifications"
    PROJECTS = "projects"


@dataclass
class Template:
    id: str
    name: str
    description: str
    sections: list[Section]
    max_skill_groups: int | None = None


TEMPLATES: dict[str, Template] = {
    "standard": Template(
        id="standard",
        name="Standard",
        description="Classic order suited to most roles.",
        sections=[
            Section.SUMMARY,
            Section.EXPERIENCE,
            Section.SKILLS,
            Section.EDUCATION,
        ],
        max_skill_groups=5,
    ),
    "technical": Template(
        id="technical",
        name="Technical",
        description="Leads with skills — ideal for engineering and technical roles.",
        sections=[
            Section.SUMMARY,
            Section.SKILLS,
            Section.EXPERIENCE,
            Section.PROJECTS,
            Section.EDUCATION,
        ],
        max_skill_groups=6,
    ),
    "recent_grad": Template(
        id="recent_grad",
        name="Recent Graduate",
        description="Highlights education and projects for early-career candidates.",
        sections=[
            Section.SUMMARY,
            Section.EDUCATION,
            Section.EXPERIENCE,
            Section.SKILLS,
            Section.PROJECTS,
        ],
        max_skill_groups=4,
    ),
}

DEFAULT_TEMPLATE = TEMPLATES["standard"]
