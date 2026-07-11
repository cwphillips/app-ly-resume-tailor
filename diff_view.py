"""Render the refinement diff view as a coloured HTML block.

Kept out of ``app.py`` so the pure rendering logic can be unit-tested without
importing the Streamlit script.
"""

from __future__ import annotations

import html

# Inline styles for each unified-diff line, keyed by leading character.
_DIFF_STYLES = {
    "+": "background:#d4edda;color:#155724;display:block",  # added
    "-": "background:#f8d7da;color:#721c24;display:block",  # removed
    "@": "color:#6c757d;display:block",  # hunk header (@@ ... @@)
}
_DIFF_STYLE_DEFAULT = "color:#495057;display:block"  # context


def diff_to_html(diff_lines: list[str]) -> str:
    """Render unified-diff lines as a coloured, HTML-escaped ``<pre>`` block.

    The first two lines (the ``---``/``+++`` file headers) are dropped. Each
    line's content is escaped before being wrapped in span markup, so resume
    text containing ``<``, ``>``, or ``&`` (e.g. ``C++ > C``, ``R&D``) renders
    literally instead of injecting stray markup.
    """
    html_lines = []
    for line in diff_lines[2:]:
        style = _DIFF_STYLES.get(line[:1], _DIFF_STYLE_DEFAULT)
        html_lines.append(f'<span style="{style}">{html.escape(line)}</span>')
    return (
        '<pre style="font-size:0.8rem;line-height:1.4">'
        + "".join(html_lines)
        + "</pre>"
    )
