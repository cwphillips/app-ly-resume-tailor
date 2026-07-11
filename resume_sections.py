"""Single source of truth for walking a resume's sections.

Section ordering, skill-group capping, and optional-section skipping used to be
re-implemented in every output format (the DOCX exporter, the Streamlit
preview, and the diff markdown). This module owns that traversal once: an
output format supplies a :class:`SectionVisitor` and never re-derives the walk.

``walk_sections`` calls exactly the visitor methods for the sections present in
the template, in template order, and only for optional sections (summary,
certifications, projects) that actually have content. Skill groups arrive
already capped to the template's ``max_skill_groups``.
"""

from __future__ import annotations

from typing import Protocol

from models.schemas import (
    CertificationEntry,
    ContactFields,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    ResumeBodyJSON,
    SkillGroup,
)
from templates.library import Section, Template


def capped_skills(resume: ResumeBodyJSON, template: Template) -> list[SkillGroup]:
    """Return the resume's skill groups capped to the template's limit."""
    groups = resume.skills
    if template.max_skill_groups is not None:
        groups = groups[: template.max_skill_groups]
    return groups


def contact_detail_parts(contact: ContactFields) -> list[str]:
    """Return the non-name contact details in display order, omitting blanks.

    Shared by every exporter so the field order (email, phone, location,
    LinkedIn, GitHub) is defined in exactly one place.
    """
    parts = [contact.email]
    for value in (contact.phone, contact.location, contact.linkedin, contact.github):
        if value:
            parts.append(value)
    return parts


class SectionVisitor(Protocol):
    """Per-section output hooks driven by :func:`walk_sections`.

    An implementation decides how each section is rendered (Word paragraphs,
    Streamlit calls, markdown lines); it never decides ordering, capping, or
    whether an optional section appears — that is the walker's job.
    """

    def summary(self, text: str) -> None: ...

    def experience(self, entries: list[ExperienceEntry]) -> None: ...

    def skills(self, groups: list[SkillGroup]) -> None: ...

    def education(self, entries: list[EducationEntry]) -> None: ...

    def certifications(self, entries: list[CertificationEntry]) -> None: ...

    def projects(self, entries: list[ProjectEntry]) -> None: ...


def walk_sections(
    resume: ResumeBodyJSON, template: Template, visitor: SectionVisitor
) -> None:
    """Drive ``visitor`` over ``resume`` in ``template`` order.

    Experience, skills, and education always render (they are required sections);
    summary, certifications, and projects render only when they have content.
    Skill groups are capped before being handed to the visitor.
    """
    for section in template.sections:
        if section == Section.SUMMARY:
            if resume.summary:
                visitor.summary(resume.summary)
        elif section == Section.EXPERIENCE:
            visitor.experience(resume.experience)
        elif section == Section.SKILLS:
            visitor.skills(capped_skills(resume, template))
        elif section == Section.EDUCATION:
            visitor.education(resume.education)
        elif section == Section.CERTIFICATIONS:
            if resume.certifications:
                visitor.certifications(resume.certifications)
        elif section == Section.PROJECTS:
            if resume.projects:
                visitor.projects(resume.projects)


class _MarkdownVisitor:
    """Accumulate a plain-markdown representation of a resume, used for the
    refinement diff and as a reusable text export."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def summary(self, text: str) -> None:
        self.lines += ["**Summary**", text, ""]

    def experience(self, entries: list[ExperienceEntry]) -> None:
        self.lines.append("**Experience**")
        for exp in entries:
            self.lines.append(
                f"**{exp.title}** — {exp.company}"
                + (f" | {exp.location}" if exp.location else "")
                + f" | {exp.start_date} – {exp.end_date}"
            )
            self.lines += [f"- {b}" for b in exp.bullets]
            self.lines.append("")

    def skills(self, groups: list[SkillGroup]) -> None:
        self.lines.append("**Skills**")
        self.lines += [f"{g.category}: {', '.join(g.skills)}" for g in groups]
        self.lines.append("")

    def education(self, entries: list[EducationEntry]) -> None:
        self.lines.append("**Education**")
        self.lines += [
            f"**{edu.degree}** — {edu.institution} | {edu.graduation_date}"
            for edu in entries
        ]
        self.lines.append("")

    def certifications(self, entries: list[CertificationEntry]) -> None:
        self.lines.append("**Certifications**")
        for cert in entries:
            line = f"**{cert.name}** — {cert.issuer}"
            if cert.date:
                line += f" | {cert.date}"
            self.lines.append(line)
        self.lines.append("")

    def projects(self, entries: list[ProjectEntry]) -> None:
        self.lines.append("**Projects**")
        for proj in entries:
            self.lines += [
                f"**{proj.name}**: {proj.description}",
                f"Technologies: {', '.join(proj.technologies)}",
            ] + [f"- {b}" for b in proj.bullets]
            self.lines.append("")


def resume_to_markdown(resume: ResumeBodyJSON, template: Template) -> str:
    """Return a plain-markdown representation of the resume, in template order.

    Shared by the refinement diff; a natural base for a future markdown export.
    """
    visitor = _MarkdownVisitor()
    walk_sections(resume, template, visitor)
    return "\n".join(visitor.lines)
