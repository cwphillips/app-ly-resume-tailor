"""Headless CLI for the resume tailoring pipeline.

Runs the same tailor->review pipeline as the Streamlit app, without a browser.
It reuses the shared, UI-agnostic ``pipeline.run_pipeline`` and the existing
DOCX exporter — no prompt or orchestration logic is duplicated here.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    uv run python cli.py resume.txt job.txt --name "Jane Smith" --email jane@example.com

Contact details (name/email/…) are collected as flags and injected only at
document-render time — exactly as in the app, they never enter a prompt.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import anthropic

import exporters.docx as docx_exporter
import pipeline
from agents.errors import MalformedModelOutputError
from input_normalization import normalize_resume_text
from models.schemas import ContactFields
from templates.library import DEFAULT_TEMPLATE, TEMPLATES


class _StderrProgress(pipeline.ProgressReporter):
    """Print pipeline step messages to stderr so stdout stays reserved for the
    review summary. Token-progress ticks are dropped — they only make sense in a
    live UI."""

    def message(self, text: str) -> None:
        # Strip the light markdown the shared messages carry for the app's UI.
        cleaned = text.replace("**", "").replace("`", "").strip()
        print(cleaned, file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Tailor a resume to a job listing with Claude, headless.",
    )
    parser.add_argument(
        "resume", type=Path, help="Path to the resume / skills text file."
    )
    parser.add_argument("job", type=Path, help="Path to the job-listing text file.")
    parser.add_argument(
        "--name", required=True, help="Full name (for the document header)."
    )
    parser.add_argument(
        "--email", required=True, help="Email (for the document header)."
    )
    parser.add_argument("--phone", help="Phone number (optional).")
    parser.add_argument("--location", help="Location (optional).")
    parser.add_argument("--linkedin", help="LinkedIn URL (optional).")
    parser.add_argument("--github", help="GitHub URL (optional).")
    parser.add_argument(
        "--target-role", default="", help="Target role to tailor toward."
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        choices=range(1, 5),
        metavar="{1-4}",
        help="Constrain the resume to N pages.",
    )
    parser.add_argument(
        "--template",
        choices=list(TEMPLATES.keys()),
        default=DEFAULT_TEMPLATE.id,
        help=f"Layout template (default: {DEFAULT_TEMPLATE.id}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("resume.docx"),
        help="Output DOCX path (default: resume.docx).",
    )
    return parser


def _print_review(review, output_path: Path) -> None:
    print(f"\nSaved: {output_path}")
    print(f"Review score: {review.score}/100")
    if review.strengths:
        print("\nStrengths:")
        for s in review.strengths:
            print(f"  + {s}")
    if review.concerns:
        print("\nConcerns:")
        for c in review.concerns:
            print(f"  - {c}")
    if review.suggestions:
        print("\nSuggestions:")
        for i, sug in enumerate(review.suggestions, 1):
            print(f"  {i}. {sug}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY is not set. Export it and try again.",
            file=sys.stderr,
        )
        return 2

    try:
        resume_text = args.resume.read_text(encoding="utf-8")
        job_listing = args.job.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        return 2

    # Same conservative cleanup the app applies at the input boundary.
    resume_text = normalize_resume_text(resume_text)

    if not resume_text.strip():
        print("Error: the resume file is empty.", file=sys.stderr)
        return 2
    if not job_listing.strip():
        print("Error: the job-listing file is empty.", file=sys.stderr)
        return 2

    template = TEMPLATES[args.template]

    try:
        result = pipeline.run_pipeline(
            api_key=api_key,
            resume_text=resume_text,
            job_listing=job_listing,
            target_role=args.target_role,
            page_limit=args.page_limit,
            max_skill_groups=template.max_skill_groups,
            progress=_StderrProgress(),
        )
    except anthropic.AuthenticationError:
        print("Error: invalid API key.", file=sys.stderr)
        return 1
    except anthropic.RateLimitError:
        print("Error: rate limit reached. Try again shortly.", file=sys.stderr)
        return 1
    except anthropic.APIError as e:
        print(f"Error: Anthropic API error: {e}", file=sys.stderr)
        return 1
    except MalformedModelOutputError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    contact = ContactFields(
        name=args.name,
        email=args.email,
        phone=args.phone or None,
        location=args.location or None,
        linkedin=args.linkedin or None,
        github=args.github or None,
    )
    docx_bytes = docx_exporter.render(result.resume, contact, template)
    args.output.write_bytes(docx_bytes)

    _print_review(result.review, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
