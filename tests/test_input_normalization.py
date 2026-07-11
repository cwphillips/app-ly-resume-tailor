"""Unit tests for the conservative resume-paste normalization pass.

These are pure-Python tests — no API calls. The guiding invariant is that
already-clean text passes through unchanged, and no transform ever drops a
line that carries resume content.
"""

from input_normalization import normalize_resume_text

# ---------------------------------------------------------------------------
# The core invariant: clean text is returned unchanged
# ---------------------------------------------------------------------------


def test_already_clean_text_is_unchanged():
    clean = (
        "Jane Doe\n"
        "Senior Engineer\n"
        "\n"
        "Experience\n"
        "- Built a thing that scaled to 1M users\n"
        "- Led a team of 4 engineers\n"
        "\n"
        "Skills\n"
        "Python, Go, Kubernetes"
    )
    assert normalize_resume_text(clean) == clean


def test_normalization_is_idempotent():
    messy = "•\tFirst\r\n\r\n\r\n•  Second​\n"
    once = normalize_resume_text(messy)
    assert normalize_resume_text(once) == once


def test_empty_input_returns_empty_string():
    assert normalize_resume_text("") == ""
    assert normalize_resume_text("   \n\n  ") == ""


# ---------------------------------------------------------------------------
# Bullet glyphs -> "- "
# ---------------------------------------------------------------------------


def test_bullet_glyph_with_space_becomes_ascii_marker():
    assert normalize_resume_text("• Did a thing") == "- Did a thing"


def test_bullet_glyph_without_space_becomes_ascii_marker():
    assert normalize_resume_text("•Did a thing") == "- Did a thing"


def test_various_bullet_glyphs_are_normalized():
    for glyph in ["▪", "‣", "·", "◦", "●", "○", "■"]:
        assert normalize_resume_text(f"{glyph} Item") == "- Item"


def test_dash_bullet_glyphs_are_normalized():
    # En/em dashes used as leading bullets become the ASCII marker.
    assert normalize_resume_text("– Item") == "- Item"
    assert normalize_resume_text("— Item") == "- Item"


def test_existing_ascii_bullets_are_left_alone():
    text = "- Already a clean bullet\n* Star bullet"
    assert normalize_resume_text(text) == text


def test_hyphenated_word_is_not_treated_as_bullet():
    assert normalize_resume_text("first-class engineer") == "first-class engineer"


# ---------------------------------------------------------------------------
# Typographic characters -> ASCII
# ---------------------------------------------------------------------------


def test_smart_quotes_become_ascii():
    assert normalize_resume_text("“Hello” he ‘said’") == "\"Hello\" he 'said'"


def test_apostrophe_becomes_ascii():
    assert normalize_resume_text("company’s growth") == "company's growth"


def test_dashes_and_ellipsis_become_ascii():
    assert normalize_resume_text("2019–2024") == "2019-2024"
    assert normalize_resume_text("scaled—fast") == "scaled-fast"
    assert normalize_resume_text("and so on…") == "and so on..."


def test_ligatures_are_folded_to_ascii():
    # NFKC folds the "fi"/"ffl" ligatures.
    assert normalize_resume_text("eﬃcient waﬄe") == "efficient waffle"


def test_zero_width_characters_are_stripped():
    assert normalize_resume_text("clean​text﻿") == "cleantext"


def test_non_breaking_space_becomes_regular_space():
    assert normalize_resume_text("New York") == "New York"


# ---------------------------------------------------------------------------
# Whitespace / blank-line handling
# ---------------------------------------------------------------------------


def test_blank_line_runs_collapse():
    assert normalize_resume_text("A\n\n\n\nB") == "A\n\nB"


def test_trailing_and_leading_whitespace_per_line_is_stripped():
    assert normalize_resume_text("  A line  \n\tB line\t") == "A line\nB line"


def test_leading_and_trailing_blank_lines_are_trimmed():
    assert normalize_resume_text("\n\n  Content  \n\n") == "Content"


def test_crlf_line_endings_are_normalized():
    assert normalize_resume_text("A\r\nB\rC") == "A\nB\nC"


# ---------------------------------------------------------------------------
# Repeated page furniture
# ---------------------------------------------------------------------------


def test_repeated_page_numbers_are_dropped():
    text = (
        "Experience at Acme\n"
        "Page 1 of 2\n"
        "More experience\n"
        "Page 2 of 2\n"
        "Page 1 of 2\n"
        "Education"
    )
    result = normalize_resume_text(text)
    assert "Page 1 of 2" not in result
    assert "Experience at Acme" in result
    assert "Education" in result


def test_repeated_bare_page_numbers_are_dropped():
    text = "Section one\n2\nSection two\n2"
    assert normalize_resume_text(text) == "Section one\nSection two"


def test_single_page_number_is_preserved():
    # Not repeated -> could be legitimate content, so it is left alone.
    text = "Managed a team of 5\nPage 1"
    assert normalize_resume_text(text) == text


def test_repeated_real_content_is_not_dropped():
    # Only page-furniture patterns are eligible; ordinary repeated lines stay.
    text = "Python\nJava\nPython\nJava"
    assert normalize_resume_text(text) == text
