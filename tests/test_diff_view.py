"""Unit tests for the refinement diff-view HTML renderer."""

import difflib

from diff_view import diff_to_html


def _diff(old: str, new: str) -> list[str]:
    return list(
        difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=1)
    )


def test_html_special_characters_render_literally():
    diff = _diff("C > D and R&D", "C++ > C and <script>")
    out = diff_to_html(diff)
    # Content is escaped...
    assert "C++ &gt; C and &lt;script&gt;" in out
    assert "R&amp;D" in out
    # ...and no raw resume-supplied angle brackets leak into the markup.
    assert "<script>" not in out


def test_added_and_removed_lines_get_their_colours():
    diff = _diff("old line", "new line")
    out = diff_to_html(diff)
    assert "background:#f8d7da" in out  # removed
    assert "background:#d4edda" in out  # added


def test_hunk_header_gets_muted_colour():
    diff = _diff("a\nb\nc", "a\nB\nc")
    out = diff_to_html(diff)
    assert 'style="color:#6c757d;display:block">@@' in out


def test_file_header_lines_are_dropped():
    diff = _diff("x", "y")
    out = diff_to_html(diff)
    assert "---" not in out
    assert "+++" not in out


def test_output_is_wrapped_in_pre_block():
    out = diff_to_html(_diff("a", "b"))
    assert out.startswith("<pre")
    assert out.endswith("</pre>")
