from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal


def is_available() -> bool:
    return shutil.which("soffice") is not None


def convert(docx_bytes: bytes, fmt: Literal["pdf", "odt"]) -> bytes:
    """Convert DOCX bytes to the target format using LibreOffice CLI.

    Raises RuntimeError if LibreOffice is not installed or conversion fails.
    """
    if not is_available():
        raise RuntimeError(
            "LibreOffice is not installed or 'soffice' is not on PATH. "
            "Install LibreOffice to enable PDF and ODT export."
        )

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "resume.docx"
        src.write_bytes(docx_bytes)

        result = subprocess.run(
            ["soffice", "--headless", "--convert-to", fmt, "--outdir", tmp, str(src)],
            check=False,
            capture_output=True,
        )

        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")
            raise RuntimeError(
                f"LibreOffice conversion to {fmt.upper()} failed "
                f"(exit code {result.returncode}): {stderr}"
            )

        out_path = Path(tmp) / f"resume.{fmt}"
        if not out_path.exists():
            raise RuntimeError(
                f"LibreOffice ran successfully but output file '{out_path.name}' was not found."
            )

        return out_path.read_bytes()
