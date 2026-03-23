from __future__ import annotations

import io
from typing import Optional

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.text import WD_ALIGN_PARAGRAPH

from models.schemas import ResumeBodyJSON, ContactFields


def _set_font(run, name: str = "Calibri", size_pt: float = 11, bold: bool = False) -> None:
    run.font.name = name
    run.font.size = Pt(size_pt)
    run.font.bold = bold


def _add_section_header(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text.upper())
    _set_font(run, size_pt=11, bold=True)
    # Bottom border to mimic a rule under the heading
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_contact_line(doc: Document, contact: ContactFields) -> None:
    """Render the name + contact info at the top of the document."""
    # Name
    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_para.paragraph_format.space_after = Pt(2)
    name_run = name_para.add_run(contact.name)
    _set_font(name_run, size_pt=16, bold=True)

    # Contact line: email | phone | location | linkedin | github
    parts: list[str] = [contact.email]
    if contact.phone:
        parts.append(contact.phone)
    if contact.location:
        parts.append(contact.location)
    if contact.linkedin:
        parts.append(contact.linkedin)
    if contact.github:
        parts.append(contact.github)

    contact_para = doc.add_paragraph()
    contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact_para.paragraph_format.space_after = Pt(4)
    contact_run = contact_para.add_run("  |  ".join(parts))
    _set_font(contact_run, size_pt=10)


def render(resume: ResumeBodyJSON, contact: ContactFields) -> bytes:
    """Render a ResumeBodyJSON + ContactFields into DOCX bytes.

    ContactFields are injected here only — they must never appear in LLM prompts.
    """
    doc = Document()

    # Page margins (narrow for more content space)
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)

    # Default paragraph spacing
    doc.styles["Normal"].paragraph_format.space_after = Pt(2)
    doc.styles["Normal"].paragraph_format.space_before = Pt(0)

    # --- Contact block (PII injected here) ---
    _add_contact_line(doc, contact)

    # --- Summary ---
    _add_section_header(doc, "Summary")
    summary_para = doc.add_paragraph()
    summary_para.paragraph_format.space_after = Pt(4)
    _set_font(summary_para.add_run(resume.summary), size_pt=11)

    # --- Experience ---
    _add_section_header(doc, "Experience")
    for entry in resume.experience:
        # Title | Company | Location                        Start – End
        header_para = doc.add_paragraph()
        header_para.paragraph_format.space_before = Pt(4)
        header_para.paragraph_format.space_after = Pt(0)
        title_run = header_para.add_run(f"{entry.title}  —  {entry.company}")
        _set_font(title_run, bold=True, size_pt=11)
        if entry.location:
            loc_run = header_para.add_run(f"  |  {entry.location}")
            _set_font(loc_run, size_pt=10)

        dates_para = doc.add_paragraph()
        dates_para.paragraph_format.space_after = Pt(1)
        dates_run = dates_para.add_run(f"{entry.start_date} – {entry.end_date}")
        _set_font(dates_run, size_pt=10)
        dates_run.font.color.rgb = RGBColor(0x60, 0x60, 0x60)

        for bullet in entry.bullets:
            bullet_para = doc.add_paragraph(style="List Bullet")
            bullet_para.paragraph_format.left_indent = Inches(0.25)
            bullet_para.paragraph_format.space_after = Pt(1)
            _set_font(bullet_para.add_run(bullet), size_pt=11)

    # --- Skills ---
    _add_section_header(doc, "Skills")
    skills_para = doc.add_paragraph()
    skills_para.paragraph_format.space_after = Pt(4)
    _set_font(skills_para.add_run(", ".join(resume.skills)), size_pt=11)

    # --- Education ---
    _add_section_header(doc, "Education")
    for entry in resume.education:
        edu_para = doc.add_paragraph()
        edu_para.paragraph_format.space_before = Pt(3)
        edu_para.paragraph_format.space_after = Pt(1)
        degree_run = edu_para.add_run(entry.degree)
        _set_font(degree_run, bold=True, size_pt=11)
        inst_run = edu_para.add_run(f"  —  {entry.institution}  |  {entry.graduation_date}")
        _set_font(inst_run, size_pt=10)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
