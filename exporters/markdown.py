"""Render a tailored resume to a Markdown document.

Consumes the shared ``walk_sections`` traversal, so section ordering,
skill-group capping, and optional-section skipping are not re-implemented here.
Contact details are injected at render time only — they never enter a prompt.

User content is emitted verbatim: Markdown metacharacters in the applicant's
own text are intentionally not escaped, since escaping would litter the raw
output for text that is theirs to begin with.
"""

from __future__ import annotations

from models.schemas import (
    CertificationEntry,
    ContactFields,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    ResumeBodyJSON,
    SkillGroup,
)
from resume_sections import contact_detail_parts, walk_sections
from templates.library import DEFAULT_TEMPLATE, Template


class _MarkdownVisitor:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def summary(self, text: str) -> None:
        self.lines += ["## Summary", "", text, ""]

    def experience(self, entries: list[ExperienceEntry]) -> None:
        self.lines += ["## Experience", ""]
        for entry in entries:
            heading = f"### {entry.title} — {entry.company}"
            if entry.location:
                heading += f" | {entry.location}"
            self.lines.append(heading)
            self.lines += [f"*{entry.start_date} – {entry.end_date}*", ""]
            self.lines += [f"- {bullet}" for bullet in entry.bullets]
            self.lines.append("")

    def skills(self, groups: list[SkillGroup]) -> None:
        self.lines += ["## Skills", ""]
        self.lines += [
            f"- **{group.category}:** {', '.join(group.skills)}" for group in groups
        ]
        self.lines.append("")

    def education(self, entries: list[EducationEntry]) -> None:
        self.lines += ["## Education", ""]
        for entry in entries:
            self.lines += [
                f"### {entry.degree} — {entry.institution}",
                entry.graduation_date,
                "",
            ]

    def certifications(self, entries: list[CertificationEntry]) -> None:
        self.lines += ["## Certifications", ""]
        for entry in entries:
            heading = f"### {entry.name} — {entry.issuer}"
            if entry.date:
                heading += f" | {entry.date}"
            self.lines += [heading, ""]

    def projects(self, entries: list[ProjectEntry]) -> None:
        self.lines += ["## Projects", ""]
        for entry in entries:
            self.lines += [
                f"### {entry.name}",
                entry.description,
                f"*Technologies: {', '.join(entry.technologies)}*",
                "",
            ]
            self.lines += [f"- {bullet}" for bullet in entry.bullets]
            self.lines.append("")


def render(
    resume: ResumeBodyJSON,
    contact: ContactFields,
    template: Template = DEFAULT_TEMPLATE,
) -> str:
    """Render a ResumeBodyJSON + ContactFields into a Markdown string."""
    visitor = _MarkdownVisitor()
    lines: list[str] = [
        f"# {contact.name}",
        "",
        " | ".join(contact_detail_parts(contact)),
        "",
    ]
    walk_sections(resume, template, visitor)
    lines += visitor.lines
    return "\n".join(lines).rstrip() + "\n"
