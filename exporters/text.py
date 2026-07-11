"""Render a tailored resume to plain text for clean pasting into any text field.

Consumes the shared ``walk_sections`` traversal, so section ordering,
skill-group capping, and optional-section skipping are not re-implemented here.
Contact details are injected at render time only — they never enter a prompt.

The output is guaranteed ASCII-only: common typographic characters are
transliterated and anything else is dropped, so the result pastes cleanly
everywhere.
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

# Transliterate the typographic characters that commonly show up in resume text
# to their closest ASCII equivalent. Anything not covered here is stripped by the
# final encode step, keeping the output strictly ASCII.
_ASCII_MAP = {
    "—": "-",  # em dash
    "–": "-",  # en dash
    "‐": "-",  # hyphen
    "‑": "-",  # non-breaking hyphen
    "‘": "'",  # left single quote
    "’": "'",  # right single quote / apostrophe
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "•": "*",  # bullet
    "…": "...",  # ellipsis
    " ": " ",  # non-breaking space
    "−": "-",  # minus sign
}


def _to_ascii(text: str) -> str:
    for unicode_char, replacement in _ASCII_MAP.items():
        text = text.replace(unicode_char, replacement)
    return text.encode("ascii", "ignore").decode("ascii")


def _header(title: str) -> list[str]:
    """An uppercase section header followed by an underline rule."""
    return [title.upper(), "-" * len(title)]


class _TextVisitor:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def summary(self, text: str) -> None:
        self.lines += _header("Summary")
        self.lines += [text, ""]

    def experience(self, entries: list[ExperienceEntry]) -> None:
        self.lines += _header("Experience")
        for entry in entries:
            heading = f"{entry.title} - {entry.company}"
            if entry.location:
                heading += f" | {entry.location}"
            self.lines.append(heading)
            self.lines.append(f"{entry.start_date} - {entry.end_date}")
            self.lines += [f"* {bullet}" for bullet in entry.bullets]
            self.lines.append("")

    def skills(self, groups: list[SkillGroup]) -> None:
        self.lines += _header("Skills")
        self.lines += [
            f"* {group.category}: {', '.join(group.skills)}" for group in groups
        ]
        self.lines.append("")

    def education(self, entries: list[EducationEntry]) -> None:
        self.lines += _header("Education")
        for entry in entries:
            self.lines.append(f"{entry.degree} - {entry.institution}")
            self.lines.append(entry.graduation_date)
            self.lines.append("")

    def certifications(self, entries: list[CertificationEntry]) -> None:
        self.lines += _header("Certifications")
        for entry in entries:
            line = f"{entry.name} - {entry.issuer}"
            if entry.date:
                line += f" | {entry.date}"
            self.lines.append(line)
        self.lines.append("")

    def projects(self, entries: list[ProjectEntry]) -> None:
        self.lines += _header("Projects")
        for entry in entries:
            self.lines.append(entry.name)
            self.lines.append(entry.description)
            self.lines.append(f"Technologies: {', '.join(entry.technologies)}")
            self.lines += [f"* {bullet}" for bullet in entry.bullets]
            self.lines.append("")


def render(
    resume: ResumeBodyJSON,
    contact: ContactFields,
    template: Template = DEFAULT_TEMPLATE,
) -> str:
    """Render a ResumeBodyJSON + ContactFields into an ASCII-only plain-text string."""
    visitor = _TextVisitor()
    lines: list[str] = [
        contact.name.upper(),
        " | ".join(contact_detail_parts(contact)),
        "",
    ]
    walk_sections(resume, template, visitor)
    lines += visitor.lines
    return _to_ascii("\n".join(lines).rstrip() + "\n")
