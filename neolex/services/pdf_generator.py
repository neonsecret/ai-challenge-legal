"""PDF generation via xelatex for legal document templates.

Security model:
  - All user-provided field values are LaTeX-escaped before injection.
  - xelatex runs via asyncio.create_subprocess_exec (never shell=True).
  - Temp files live in a tmpdir and are deleted in a finally block.
  - PDFs are cached by (doc_id, version) in /tmp/vitreon_pdf_cache/.

xelatex binary availability is checked at module import time; a WARNING is
logged if xelatex is missing so the server starts but PDF endpoints degrade.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# xelatex availability check (startup)
# ---------------------------------------------------------------------------

_XELATEX_BIN: str | None = shutil.which("xelatex")

if _XELATEX_BIN is None:
    logger.warning(
        "xelatex binary not found on PATH. PDF generation endpoints will return 503. "
        "Install TeX Live or MacTeX to enable PDF generation."
    )
else:
    logger.info("xelatex found at %s", _XELATEX_BIN)

# ---------------------------------------------------------------------------
# Cache directory
# ---------------------------------------------------------------------------

_CACHE_DIR = Path("/tmp/vitreon_pdf_cache")  # nosec B108 — intentional /tmp usage
_CACHE_DIR.mkdir(parents=True, exist_ok=True)  # create once at import time


def _cache_path(doc_id: uuid.UUID, version: int) -> Path:
    return _CACHE_DIR / f"{doc_id}_{version}.pdf"


# ---------------------------------------------------------------------------
# LaTeX escaping
# ---------------------------------------------------------------------------

# Single-pass regex over all LaTeX special characters.
# A regex sub with a function is used instead of sequential str.replace() to avoid
# the double-escaping problem: if we replace \ first (→ \textbackslash{}) and then
# replace { and } separately, the braces we just introduced get escaped again.
_LATEX_SPECIAL_RE = re.compile(r"[\\&%$#_{}~^]")

_LATEX_ESCAPE_TABLE: dict[str, str] = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(value: str) -> str:
    """Escape all LaTeX special characters in a user-provided field value.

    Uses a single regex pass so that replacement strings (e.g. '\\textbackslash{}')
    are never re-scanned — the braces inside them are not escaped a second time.

    Must be called on EVERY user-controlled string before template injection
    to prevent LaTeX injection attacks (arbitrary command execution via shell_escape,
    file reads via \\input, etc.).
    """
    return _LATEX_SPECIAL_RE.sub(lambda m: _LATEX_ESCAPE_TABLE[m.group(0)], value)


# ---------------------------------------------------------------------------
# Template field injection
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _inject_fields(template: str, fields: dict[str, str]) -> str:
    """Replace {{field_name}} placeholders with escaped user values.

    Unknown placeholders (no matching key in fields) are replaced with an
    empty string so the document renders cleanly rather than with raw placeholders.
    """

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        raw_value = fields.get(key, "")
        return escape_latex(str(raw_value))

    return _PLACEHOLDER_RE.sub(_replace, template)


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------


async def generate_pdf(
    doc_id: uuid.UUID,
    version: int,
    template: str,
    fields: dict[str, str],
) -> bytes:
    """Generate a PDF from a LaTeX template and user-provided fields.

    Returns cached PDF bytes if (doc_id, version) is already cached.
    Raises RuntimeError if xelatex is not available.
    Raises RuntimeError if xelatex compilation fails.

    Security notes:
      - escape_latex() is applied to ALL field values before template injection.
      - xelatex is called via create_subprocess_exec — never shell=True.
      - Temp directory is isolated from the project root.
    """
    if _XELATEX_BIN is None:
        raise RuntimeError(
            "xelatex is not installed. PDF generation is unavailable. Contact support or install TeX Live."
        )

    # Return cached PDF if available
    cached = _cache_path(doc_id, version)
    if cached.exists():
        logger.debug("PDF cache hit: doc_id=%s version=%d", doc_id, version)
        return cached.read_bytes()

    # Inject escaped field values into the LaTeX template
    filled_tex = _inject_fields(template, fields)

    tmpdir = tempfile.mkdtemp(prefix="vitreon_pdf_")
    try:
        tex_path = Path(tmpdir) / "document.tex"
        tex_path.write_text(filled_tex, encoding="utf-8")

        # Run xelatex twice (resolves cross-references, e.g. \ref) — common practice
        for run in range(2):
            proc = await asyncio.create_subprocess_exec(
                _XELATEX_BIN,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory",
                tmpdir,
                str(tex_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmpdir,  # run inside the tmpdir, not the project root
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                log_output = (stdout + stderr).decode("utf-8", errors="replace")[-3000:]
                logger.error(
                    "xelatex failed (run %d, returncode=%d) for doc_id=%s:\n%s",
                    run + 1,
                    proc.returncode,
                    doc_id,
                    log_output,
                )
                raise RuntimeError(
                    f"PDF compilation failed (xelatex exit code {proc.returncode}). "
                    "Check that the template is valid LaTeX."
                )

        pdf_path = Path(tmpdir) / "document.pdf"
        if not pdf_path.exists():
            raise RuntimeError("xelatex completed but no PDF was produced.")

        pdf_bytes = pdf_path.read_bytes()

        # Write to cache atomically (rename is atomic on POSIX)
        tmp_cache = cached.with_suffix(".tmp")
        tmp_cache.write_bytes(pdf_bytes)
        tmp_cache.rename(cached)

        logger.info("PDF generated for doc_id=%s version=%d (%d bytes)", doc_id, version, len(pdf_bytes))
        return pdf_bytes

    finally:
        # Clean up temp files even on error
        shutil.rmtree(tmpdir, ignore_errors=True)


def invalidate_cache(doc_id: uuid.UUID) -> None:
    """Remove all cached PDFs for a given document (call after fields update)."""
    if not _CACHE_DIR.exists():
        return
    for path in _CACHE_DIR.glob(f"{doc_id}_*.pdf"):
        try:
            path.unlink()
        except OSError:
            logger.warning("Failed to remove PDF cache file: %s", path)
