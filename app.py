from __future__ import annotations

import os
from typing import Optional

import anthropic
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import agents.tailoring as tailoring_agent
import agents.review as review_agent
import exporters.docx as docx_exporter
import exporters.converter as converter

from agents.tailoring import TailoringResult
from agents.review import ReviewResult
from models.schemas import ContactFields, ResumeBodyJSON, ReviewJSON
from templates.library import TEMPLATES, DEFAULT_TEMPLATE, Template

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="app-ly",
    page_icon=":briefcase:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
defaults: dict = {
    "resume_body": None,
    "review": None,
    "previous_score": None,
    "refinement_count": 0,
    "docx_bytes": None,
    "libreoffice_available": None,
    "running": False,
    "selected_template_id": DEFAULT_TEMPLATE.id,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Detect LibreOffice once per session
if st.session_state.libreoffice_available is None:
    st.session_state.libreoffice_available = converter.is_available()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_api_key(ui_key: str) -> str:
    return ui_key.strip() or os.environ.get("ANTHROPIC_API_KEY", "")


def _run_pipeline(
    *,
    api_key: str,
    resume_text: str,
    job_listing: str,
    target_role: str,
    page_limit: Optional[int],
    allow_reword: bool,
    include_summary: bool,
    status,  # st.status container
    previous_resume: Optional[ResumeBodyJSON] = None,
    review_feedback: Optional[ReviewJSON] = None,
) -> tuple[ResumeBodyJSON, ReviewJSON]:
    label = "Refinement pass" if previous_resume is not None else "Tailoring resume"

    status.write(f"**Step 1 of 2 — {label}** (model: `claude-sonnet-4-6`)")
    tailor_result: TailoringResult = tailoring_agent.run(
        resume_text=resume_text,
        job_listing=job_listing,
        target_role=target_role,
        page_limit=page_limit,
        allow_reword=allow_reword,
        include_summary=include_summary,
        previous_resume=previous_resume,
        review_feedback=review_feedback,
        api_key=api_key,
    )
    status.write(
        f"  Done — {tailor_result.input_tokens:,} tokens in, "
        f"{tailor_result.output_tokens:,} tokens out."
    )

    status.write("**Step 2 of 2 — Reviewing resume** (model: `claude-sonnet-4-6`)")
    review_result: ReviewResult = review_agent.run(
        resume=tailor_result.resume,
        job_listing=job_listing,
        target_role=target_role,
        page_limit=page_limit,
        api_key=api_key,
    )
    status.write(
        f"  Done — {review_result.input_tokens:,} tokens in, "
        f"{review_result.output_tokens:,} tokens out."
    )

    return tailor_result.resume, review_result.review


def _render_resume_preview(resume: ResumeBodyJSON, template: Template) -> None:
    from templates.library import Section

    st.subheader("Resume Preview")

    for section in template.sections:
        if section == Section.SUMMARY and resume.summary:
            st.markdown(f"**Summary**\n\n{resume.summary}")

        elif section == Section.EXPERIENCE:
            st.markdown("**Experience**")
            for exp in resume.experience:
                st.markdown(
                    f"**{exp.title}** — {exp.company}"
                    + (f" | {exp.location}" if exp.location else "")
                    + f"\n\n_{exp.start_date} – {exp.end_date}_"
                )
                for bullet in exp.bullets:
                    st.markdown(f"- {bullet}")

        elif section == Section.SKILLS:
            groups = resume.skills
            if template.max_skill_groups is not None:
                groups = groups[: template.max_skill_groups]
            skills_line = " | ".join(
                f"{g.category}: {', '.join(g.skills)}" for g in groups
            )
            st.markdown(f"**Skills**\n\n{skills_line}")

        elif section == Section.EDUCATION:
            st.markdown("**Education**")
            for edu in resume.education:
                st.markdown(f"**{edu.degree}** — {edu.institution} | {edu.graduation_date}")

        elif section == Section.CERTIFICATIONS and resume.certifications:
            st.markdown("**Certifications**")
            for cert in resume.certifications:
                line = f"**{cert.name}** — {cert.issuer}"
                if cert.date:
                    line += f" | {cert.date}"
                st.markdown(line)

        elif section == Section.PROJECTS and resume.projects:
            st.markdown("**Projects**")
            for proj in resume.projects:
                st.markdown(f"**{proj.name}**")
                st.markdown(proj.description)
                st.caption(f"Technologies: {', '.join(proj.technologies)}")
                for bullet in proj.bullets:
                    st.markdown(f"- {bullet}")

    with st.expander("Why this resume? (tailoring rationale)"):
        st.write(resume.rationale)


def _render_review_panel(review: ReviewJSON, previous_score: Optional[int] = None) -> None:
    st.subheader("Review")

    score_display = f"**Score: {review.score}/100**"
    if previous_score is not None:
        delta = review.score - previous_score
        sign = "+" if delta >= 0 else ""
        score_display += f"  (was {previous_score} — {sign}{delta})"
    st.markdown(score_display)

    if review.strengths:
        st.markdown("**Strengths**")
        for s in review.strengths:
            st.markdown(f"- {s}")

    if review.concerns:
        st.markdown("**Concerns**")
        for c in review.concerns:
            st.markdown(f"- {c}")

    if review.suggestions:
        st.markdown("**Suggestions**")
        for i, sug in enumerate(review.suggestions, 1):
            st.markdown(f"{i}. {sug}")


def _render_export_buttons(contact: ContactFields, template: Template) -> None:
    st.subheader("Export")

    docx_bytes = docx_exporter.render(st.session_state.resume_body, contact, template)
    st.session_state.docx_bytes = docx_bytes

    st.download_button(
        label="Download DOCX",
        data=docx_bytes,
        file_name="resume.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    if st.session_state.libreoffice_available:
        col_pdf, col_odt = st.columns(2)
        with col_pdf:
            if st.button("Download PDF"):
                try:
                    pdf_bytes = converter.convert(docx_bytes, "pdf")
                    st.download_button(
                        label="Click to save PDF",
                        data=pdf_bytes,
                        file_name="resume.pdf",
                        mime="application/pdf",
                        key="pdf_save",
                    )
                except RuntimeError as e:
                    st.error(str(e))
        with col_odt:
            if st.button("Download ODT"):
                try:
                    odt_bytes = converter.convert(docx_bytes, "odt")
                    st.download_button(
                        label="Click to save ODT",
                        data=odt_bytes,
                        file_name="resume.odt",
                        mime="application/vnd.oasis.opendocument.text",
                        key="odt_save",
                    )
                except RuntimeError as e:
                    st.error(str(e))
    else:
        st.info(
            "PDF and ODT export unavailable — install LibreOffice and restart the app to enable."
        )


# ---------------------------------------------------------------------------
# Sidebar — inputs
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("app-ly")
    st.caption("AI-powered resume tailoring")

    st.info(
        "Resume content and job listing are sent to Anthropic's API. "
        "Your contact details are never included.",
        icon=":material/lock:",
    )

    st.divider()
    st.subheader("Contact Information")
    st.caption("Never sent to the AI — injected into your document locally.")

    contact_name = st.text_input("Full Name *", placeholder="Jane Smith")
    contact_email = st.text_input("Email *", placeholder="jane@example.com")
    contact_phone = st.text_input("Phone", placeholder="+1 555 123 4567")
    contact_location = st.text_input("Location", placeholder="San Francisco, CA")
    contact_linkedin = st.text_input("LinkedIn URL", placeholder="linkedin.com/in/janesmith")
    contact_github = st.text_input("GitHub URL", placeholder="github.com/janesmith")

    st.divider()
    st.subheader("Settings")

    api_key_input = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-… (or set ANTHROPIC_API_KEY env var)",
    )
    target_role = st.text_input(
        "Target Role (optional)",
        placeholder="e.g. Senior Software Engineer",
    )
    page_limit_enabled = st.checkbox("Enforce page limit")
    page_limit: Optional[int] = None
    if page_limit_enabled:
        page_limit = st.number_input("Page limit", min_value=1, max_value=4, value=1, step=1)

    allow_reword = st.checkbox("Allow rewording", value=True)
    include_summary = st.checkbox("Include summary", value=True)
    if not allow_reword and include_summary:
        st.caption(
            "Rewording is off, but the summary still requires the LLM to compose "
            "text from your source material."
        )

# ---------------------------------------------------------------------------
# Main content area
# ---------------------------------------------------------------------------
st.header("Tailor Your Resume")

col_left, col_right = st.columns(2)

with col_left:
    resume_text = st.text_area(
        "Your Resume / Skills",
        height=300,
        placeholder=(
            "Paste your current resume text, or a bullet-point list of your skills and experience."
        ),
    )

with col_right:
    job_listing = st.text_area(
        "Job Listing",
        height=300,
        placeholder="Paste the full job description here.",
    )

# ---------------------------------------------------------------------------
# Generate button
# ---------------------------------------------------------------------------
api_key = _resolve_api_key(api_key_input)

missing: list[str] = []
if not api_key:
    missing.append("Anthropic API key (sidebar → Settings)")
if not contact_name.strip():
    missing.append("Full Name (sidebar → Contact Information)")
if not contact_email.strip():
    missing.append("Email (sidebar → Contact Information)")
if not resume_text.strip():
    missing.append("Your Resume / Skills")
if not job_listing.strip():
    missing.append("Job Listing")

generate_disabled = bool(missing) or st.session_state.running

if missing and not st.session_state.running:
    st.warning("To generate, please fill in: " + ", ".join(missing) + ".")

generate_label = "Generating..." if st.session_state.running else "Generate Tailored Resume"

if st.button(generate_label, type="primary", disabled=generate_disabled, use_container_width=True):
    st.session_state.running = True
    st.session_state.resume_body = None
    st.session_state.review = None
    st.session_state.previous_score = None
    st.session_state.refinement_count = 0
    st.session_state.docx_bytes = None
    st.session_state.selected_template_id = DEFAULT_TEMPLATE.id

    try:
        with st.status("Running pipeline...", expanded=True) as status:
            resume, review = _run_pipeline(
                api_key=api_key,
                resume_text=resume_text,
                job_listing=job_listing,
                target_role=target_role,
                page_limit=page_limit,
                allow_reword=allow_reword,
                include_summary=include_summary,
                status=status,
            )
            status.update(label="Pipeline complete.", state="complete", expanded=False)
        st.session_state.resume_body = resume
        st.session_state.review = review
    except anthropic.AuthenticationError:
        st.error("Invalid API key. Check your key and try again.")
    except anthropic.RateLimitError:
        st.error("Rate limit reached. Wait a moment and try again.")
    except anthropic.APIError as e:
        st.error(f"Anthropic API error: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    finally:
        st.session_state.running = False
    st.rerun()

# ---------------------------------------------------------------------------
# Refinement button
# ---------------------------------------------------------------------------
MAX_REFINEMENTS = 2

if (
    st.session_state.resume_body is not None
    and st.session_state.refinement_count < MAX_REFINEMENTS
    and not st.session_state.running
):
    refine_label = (
        f"Refine Resume "
        f"({st.session_state.refinement_count + 1} of {MAX_REFINEMENTS})"
    )
    if st.button(refine_label, use_container_width=True):
        st.session_state.running = True
        prev_score = st.session_state.review.score if st.session_state.review else None

        try:
            with st.status(
                f"Running refinement {st.session_state.refinement_count + 1} of {MAX_REFINEMENTS}...",
                expanded=True,
            ) as status:
                resume, review = _run_pipeline(
                    api_key=api_key,
                    resume_text=resume_text,
                    job_listing=job_listing,
                    target_role=target_role,
                    page_limit=page_limit,
                    allow_reword=allow_reword,
                    include_summary=include_summary,
                    previous_resume=st.session_state.resume_body,
                    review_feedback=st.session_state.review,
                    status=status,
                )
                status.update(label="Refinement complete.", state="complete", expanded=False)
            st.session_state.previous_score = prev_score
            st.session_state.resume_body = resume
            st.session_state.review = review
            st.session_state.refinement_count += 1
            st.session_state.docx_bytes = None
        except anthropic.AuthenticationError:
            st.error("Invalid API key. Check your key and try again.")
        except anthropic.RateLimitError:
            st.error("Rate limit reached. Wait a moment and try again.")
        except anthropic.APIError as e:
            st.error(f"Anthropic API error: {e}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")
        finally:
            st.session_state.running = False
        st.rerun()

if st.session_state.refinement_count >= MAX_REFINEMENTS:
    st.info("Maximum refinements reached. Click 'Generate' to start over with a fresh run.")

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if st.session_state.resume_body is not None:
    st.divider()

    # Skipped sections callout
    skipped = st.session_state.resume_body.skipped_sections
    if skipped:
        skipped_names = ", ".join(s.capitalize() for s in skipped)
        st.info(
            f"These sections were not included because your source material didn't contain "
            f"enough information: **{skipped_names}**. "
            "Add that content to your resume text and regenerate to include them."
        )

    # Template selector
    template_names = [t.name for t in TEMPLATES.values()]
    template_ids = list(TEMPLATES.keys())
    current_index = template_ids.index(st.session_state.selected_template_id)
    selected_name = st.radio(
        "Template",
        template_names,
        index=current_index,
        horizontal=True,
        label_visibility="collapsed",
    )
    selected_template_id = template_ids[template_names.index(selected_name)]
    st.session_state.selected_template_id = selected_template_id
    selected_template = TEMPLATES[selected_template_id]

    res_col, rev_col = st.columns([3, 2])

    with res_col:
        _render_resume_preview(st.session_state.resume_body, selected_template)

    with rev_col:
        if st.session_state.review is not None:
            _render_review_panel(
                st.session_state.review,
                previous_score=st.session_state.previous_score,
            )

    st.divider()

    contact = ContactFields(
        name=contact_name,
        email=contact_email,
        phone=contact_phone or None,
        location=contact_location or None,
        linkedin=contact_linkedin or None,
        github=contact_github or None,
    )
    _render_export_buttons(contact, selected_template)
