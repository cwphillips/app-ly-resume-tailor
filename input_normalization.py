"""Conservative, no-LLM normalization for pasted resume text.

When users copy a resume out of a PDF, the paste is messy: repeated page
headers/footers, scrambled whitespace, bullet glyphs, and ligature/Unicode
artifacts. This module cleans up those artifacts *conservatively* before the
text is handed to the tailoring agent.

Design rule: **conservative beats thorough.** A step that drops a legitimate
resume line is worse than one that leaves an artifact in. None of these
transforms touch the substance of a line, and already-clean text passes
through unchanged (see the tests).
"""

from __future__ import annotations

import re
import unicodedata

# Zero-width and BOM-style characters that carry no meaning in pasted text.
_ZERO_WIDTH = str.maketrans(
    "",
    "",
    "".join(
        [
            "​",  # zero-width space
            "‌",  # zero-width non-joiner
            "‍",  # zero-width joiner
            "⁠",  # word joiner
            "﻿",  # zero-width no-break space / BOM
        ]
    ),
)

# Typographic characters that NFKC leaves intact but have plain-ASCII
# equivalents. (NFKC already folds ligatures like "fi" and non-breaking
# spaces, so those are not listed here.)
_TYPOGRAPHIC = {
    "‘": "'",  # left single quote
    "’": "'",  # right single quote / apostrophe
    "‚": "'",  # single low quote
    "‛": "'",  # single high-reversed quote
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "„": '"',  # double low quote
    "‟": '"',  # double high-reversed quote
    "–": "-",  # en dash
    "—": "-",  # em dash
    "―": "-",  # horizontal bar
    "−": "-",  # minus sign
    "…": "...",  # horizontal ellipsis
}
_TYPOGRAPHIC_TABLE = str.maketrans(_TYPOGRAPHIC)

# Glyphs that commonly appear as leading list bullets. ASCII "-"/"*" are
# intentionally excluded so hyphenated or already-clean lines are left alone.
_BULLET_GLYPHS = "•▪‣·◦●○■□▸►◆♦∙⁃–—"
_LEADING_BULLET = re.compile(rf"^[{re.escape(_BULLET_GLYPHS)}]+\s*")

# Standalone page-number furniture, e.g. "Page 3", "Page 3 of 12", "- 3 -",
# or a bare "3". Only removed when the identical line repeats (see below).
_PAGE_NUMBER = re.compile(r"^(page\s+)?\d+(\s+of\s+\d+)?$|^-\s*\d+\s*-$", re.IGNORECASE)


def normalize_resume_text(raw: str) -> str:
    """Return a conservatively cleaned version of pasted resume text.

    Clean text is returned unchanged. The pass never removes a line that
    carries resume content; only whitespace, typographic artifacts, and
    obvious repeated page furniture are touched.
    """
    if not raw:
        return ""

    # 1. Strip zero-width junk, fold compatibility forms (ligatures, NBSP),
    #    then transliterate remaining typographic characters to ASCII.
    text = raw.translate(_ZERO_WIDTH)
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_TYPOGRAPHIC_TABLE)

    # 2. Normalize line endings and clean each line.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_normalize_line(line) for line in text.split("\n")]

    # 3. Drop repeated page-number furniture.
    lines = _drop_repeated_page_furniture(lines)

    # 4. Collapse runs of blank lines to a single blank line.
    lines = _collapse_blank_runs(lines)

    # 5. Trim leading/trailing blank lines from the whole document.
    return "\n".join(lines).strip("\n")


def _normalize_line(line: str) -> str:
    """Strip surrounding whitespace and rewrite a leading bullet glyph."""
    line = line.strip()
    match = _LEADING_BULLET.match(line)
    if match:
        remainder = line[match.end() :]
        return f"- {remainder}".rstrip()
    return line


def _drop_repeated_page_furniture(lines: list[str]) -> list[str]:
    """Remove page-number lines that appear more than once in the paste."""
    counts: dict[str, int] = {}
    for line in lines:
        if _PAGE_NUMBER.match(line):
            counts[line] = counts.get(line, 0) + 1
    repeated = {line for line, n in counts.items() if n > 1}
    if not repeated:
        return lines
    return [line for line in lines if line not in repeated]


def _collapse_blank_runs(lines: list[str]) -> list[str]:
    """Collapse consecutive blank lines down to a single blank line."""
    result: list[str] = []
    previous_blank = False
    for line in lines:
        blank = line == ""
        if blank and previous_blank:
            continue
        result.append(line)
        previous_blank = blank
    return result
