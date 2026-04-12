"""PDF generation for legal document templates.

Primary renderer: xelatex — high-quality typesetting for formal legal submissions.
Fallback renderer: weasyprint — HTML→PDF via pango/cairo, no TeX dependency.

Security model:
  - xelatex path: all user-provided field values are LaTeX-escaped before injection.
  - weasyprint path: all user-provided field values are HTML-escaped before injection.
  - xelatex runs via asyncio.create_subprocess_exec (never shell=True).
  - Temp files live in a tmpdir and are deleted in a finally block.
  - PDFs are cached by (doc_id, version) in /tmp/vitreon_pdf_cache/.

xelatex binary availability is checked at module import time; a WARNING is
logged if xelatex is missing so the server starts but PDF endpoints degrade.
"""

from __future__ import annotations

import asyncio
import html as html_module
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
        "xelatex binary not found on PATH. PDF generation will use weasyprint fallback. "
        "Install TeX Live or MacTeX for higher-quality PDF output."
    )
else:
    logger.info("xelatex found at %s", _XELATEX_BIN)

# ---------------------------------------------------------------------------
# weasyprint fallback availability check (startup)
# ---------------------------------------------------------------------------

_WEASYPRINT_AVAILABLE = False
try:
    import weasyprint as _weasyprint_mod  # noqa: F401

    _WEASYPRINT_AVAILABLE = True
    logger.info("weasyprint available as PDF fallback renderer")
except Exception as _wp_err:
    logger.warning("weasyprint not available: %s. PDF endpoints will return 503.", _wp_err)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

_XELATEX_TIMEOUT_S = 30  # seconds per xelatex run


class PDFTimeoutError(RuntimeError):
    """Raised when xelatex compilation exceeds the per-run timeout."""


# ---------------------------------------------------------------------------
# Cache directory
# ---------------------------------------------------------------------------

_CACHE_DIR = Path("/tmp/vitreon_pdf_cache")  # nosec B108 — intentional /tmp usage
_CACHE_DIR.mkdir(parents=True, exist_ok=True)  # create once at import time


def _cache_path(doc_id: uuid.UUID, version: int) -> Path:
    return _CACHE_DIR / f"{doc_id}_{version}.pdf"


# ---------------------------------------------------------------------------
# LaTeX escaping (for xelatex path)
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


def _inject_fields_html(template: str, fields: dict[str, str]) -> str:
    """Replace {{field_name}} placeholders with HTML-escaped user values.

    Used by the weasyprint renderer — HTML-escapes instead of LaTeX-escapes.
    """

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        raw_value = fields.get(key, "")
        return html_module.escape(str(raw_value))

    return _PLACEHOLDER_RE.sub(_replace, template)


# ---------------------------------------------------------------------------
# LaTeX → HTML converter (for weasyprint fallback)
# ---------------------------------------------------------------------------

# Strip everything up to and including \begin{document}
_PREAMBLE_RE = re.compile(r".*?\\begin\{document\}", re.DOTALL)
# Strip \end{document} and everything after
_END_DOC_RE = re.compile(r"\\end\{document\}.*", re.DOTALL)


def _latex_to_html_body(latex: str) -> str:
    """Convert a subset of LaTeX markup to HTML.

    Handles only the commands actually used in the Vitreon legal templates.
    The input is the document body (after \\begin{document}, before \\end{document})
    with field values already injected (HTML-escaped).

    This is deliberately a narrow converter — it only handles what's in the templates,
    not arbitrary LaTeX. Unknown commands are stripped or left as-is.
    """
    body = latex

    # --- Block environments ---
    body = re.sub(
        r"\\begin\{center\}(.*?)\\end\{center\}",
        lambda m: f'<div style="text-align:center;">{m.group(1).strip()}</div>',
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{quote\}(.*?)\\end\{quote\}",
        lambda m: (
            f'<blockquote style="margin-left:2em;margin-right:2em;font-style:italic;">{m.group(1).strip()}</blockquote>'
        ),
        body,
        flags=re.DOTALL,
    )

    # --- Inline font commands: {size\textbf{...}} and \textbf{...} ---
    # Large bold (section title style): {\large\textbf{...}}
    body = re.sub(
        r"\{\\large\\textbf\{(.*?)\}\}",
        lambda m: f'<strong style="font-size:14pt;">{m.group(1)}</strong>',
        body,
    )
    # \textbf{...}
    body = re.sub(r"\\textbf\{(.*?)\}", r"<strong>\1</strong>", body)
    # \textit{...}
    body = re.sub(r"\\textit\{(.*?)\}", r"<em>\1</em>", body)
    # \emph{...}
    body = re.sub(r"\\emph\{(.*?)\}", r"<em>\1</em>", body)
    # \small (inline — wrap in a span)
    body = re.sub(r"\\small\s*", '<span style="font-size:9pt;">', body)
    # Close dangling <span> from \small — match content up to the next closing brace
    body = re.sub(r'(<span style="font-size:9pt;">)([^}]*)\}', r"\1\2</span>", body)

    # --- Spacing commands → vertical gaps ---
    body = re.sub(r"\\vspace\{[^}]*\}", "<br>", body)
    body = re.sub(r"\\medskip\b", "<br>", body)
    body = re.sub(r"\\bigskip\b", "<br><br>", body)
    body = re.sub(r"\\smallskip\b", "<br>", body)

    # --- Horizontal rule (signature line) ---
    body = re.sub(r"\\rule\{[^}]*\}\{[^}]*\}", '<hr style="width:60%;margin:0;border-top:1px solid black;">', body)

    # --- Non-breaking space --- (LaTeX ~)
    # Replace ~ used as non-breaking space (not inside commands) with &nbsp;
    body = body.replace("~", "&nbsp;")

    # --- Strip remaining LaTeX commands (preamble helpers, etc.) ---
    # Remove \noindent
    body = re.sub(r"\\noindent\b", "", body)
    # Remove explicit \ (forced line break in LaTeX) — becomes a newline
    body = re.sub(r"\\\\\n?", "<br>", body)
    # Remove backslash-space (\ ) — spacing command
    body = re.sub(r"\\ ", " ", body)
    # Remove \pagebreak, \clearpage
    body = re.sub(r"\\(?:pagebreak|clearpage|newpage)\b", "", body)

    # --- Convert double newlines to paragraph breaks ---
    # Multiple blank lines → paragraph break
    body = re.sub(r"\n{2,}", "</p><p>", body)
    # Single newlines → space (within a paragraph)
    body = body.replace("\n", " ")

    # --- Wrap in paragraph tags ---
    body = f"<p>{body}</p>"

    # --- Clean up empty paragraphs and extra whitespace ---
    body = re.sub(r"<p>\s*</p>", "", body)
    body = re.sub(r"<p>\s*<br>\s*</p>", "", body)
    body = re.sub(r"(<br>\s*){3,}", "<br><br>", body)

    return body


# Disclaimer footer text (mirrors the LaTeX \fancyfoot)
_DISCLAIMER_CZ = "Vzor — zkontrolujte a upravte před podáním. Tento dokument není právním poradenstvím."
_DISCLAIMER_EN = "Template — review and modify before submission. This document is not legal advice."

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<style>
  @page {{
    size: A4;
    margin: 2.5cm 2.5cm 3.5cm 3cm;
    @bottom-center {{
      content: "{disclaimer}";
      font-size: 8pt;
      font-style: italic;
      color: #555;
    }}
    @bottom-right {{
      content: counter(page);
      font-size: 8pt;
      color: #555;
    }}
  }}
  body {{
    font-family: "TeX Gyre Termes", "Times New Roman", Georgia, serif;
    font-size: 12pt;
    line-height: 1.6;
    color: #111;
  }}
  strong {{ font-weight: bold; }}
  em {{ font-style: italic; }}
  blockquote {{
    margin-left: 2em;
    margin-right: 2em;
    font-style: italic;
  }}
  p {{ margin: 0.4em 0; }}
  hr {{
    border: none;
    border-top: 1px solid black;
    width: 60%;
    margin: 0;
  }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _latex_to_html(latex_template: str, fields: dict[str, str], jurisdiction: str = "EN") -> str:
    """Convert a filled LaTeX template to an HTML document for weasyprint rendering.

    Steps:
    1. Inject HTML-escaped field values into the template
    2. Strip the preamble (everything before \\begin{document})
    3. Strip the \\end{document} trailer
    4. Convert LaTeX markup to HTML equivalents
    5. Wrap in a full HTML document with CSS

    ``jurisdiction`` selects the disclaimer footer language: "CZ" → Czech text,
    all other values (DIFC, UK, AU, general, …) → English.
    """
    # 1. Inject field values (HTML-escaped)
    filled = _inject_fields_html(latex_template, fields)

    # 2. Strip preamble
    filled = _PREAMBLE_RE.sub("", filled, count=1)
    # 3. Strip \end{document}
    filled = _END_DOC_RE.sub("", filled)

    # 4. Convert LaTeX to HTML
    body_html = _latex_to_html_body(filled.strip())

    # 5. Wrap in HTML document with locale-appropriate disclaimer and lang attribute
    is_cz = jurisdiction.upper() == "CZ"
    disclaimer = _DISCLAIMER_CZ if is_cz else _DISCLAIMER_EN
    lang = "cs" if is_cz else "en"
    return _HTML_TEMPLATE.format(body=body_html, disclaimer=disclaimer, lang=lang)


# ---------------------------------------------------------------------------
# weasyprint PDF generation
# ---------------------------------------------------------------------------


async def _generate_pdf_weasyprint(
    doc_id: uuid.UUID,
    version: int,
    template: str,
    fields: dict[str, str],
    jurisdiction: str = "EN",
) -> bytes:
    """Generate a PDF using weasyprint (HTML→PDF fallback for when xelatex is absent).

    Converts the LaTeX template to HTML, then renders to PDF via weasyprint.
    Supports all Unicode characters including Czech diacritics.
    """
    import weasyprint

    html_doc = _latex_to_html(template, fields, jurisdiction)

    def _render() -> bytes:
        return weasyprint.HTML(string=html_doc).write_pdf()

    pdf_bytes: bytes = await asyncio.to_thread(_render)

    # Write to cache atomically
    cached = _cache_path(doc_id, version)
    tmp_cache = cached.with_suffix(".tmp")
    tmp_cache.write_bytes(pdf_bytes)
    tmp_cache.rename(cached)

    logger.info(
        "PDF generated via weasyprint for doc_id=%s version=%d (%d bytes)",
        doc_id,
        version,
        len(pdf_bytes),
    )
    return pdf_bytes


# ---------------------------------------------------------------------------
# PDF generation (public API — chooses renderer automatically)
# ---------------------------------------------------------------------------


async def generate_pdf(
    doc_id: uuid.UUID,
    version: int,
    template: str,
    fields: dict[str, str],
    jurisdiction: str = "EN",
) -> bytes:
    """Generate a PDF from a LaTeX template and user-provided fields.

    Uses xelatex when available; falls back to weasyprint otherwise.
    Returns cached PDF bytes if (doc_id, version) is already cached.
    Raises RuntimeError if neither renderer is available.
    Raises RuntimeError if compilation/rendering fails.

    ``jurisdiction`` controls the disclaimer footer language in the weasyprint
    path (xelatex uses the LaTeX template's own \\fancyfoot directly).
    Pass the template's jurisdiction string, e.g. "CZ", "DIFC", "UK", "AU".

    Security notes (xelatex path):
      - escape_latex() is applied to ALL field values before template injection.
      - xelatex is called via create_subprocess_exec — never shell=True.
      - Temp directory is isolated from the project root.

    Security notes (weasyprint path):
      - html.escape() is applied to ALL field values before template injection.
      - weasyprint runs in-process via asyncio.to_thread (no subprocess).
    """
    # Return cached PDF if available
    cached = _cache_path(doc_id, version)
    if cached.exists():
        logger.debug("PDF cache hit: doc_id=%s version=%d", doc_id, version)
        return cached.read_bytes()

    if _XELATEX_BIN is not None:
        return await _generate_pdf_xelatex(doc_id, version, template, fields)

    if _WEASYPRINT_AVAILABLE:
        return await _generate_pdf_weasyprint(doc_id, version, template, fields, jurisdiction)

    raise RuntimeError(
        "No PDF renderer available. Install TeX Live (xelatex) or ensure "
        "weasyprint dependencies (pango, cairo, glib) are present."
    )


# ---------------------------------------------------------------------------
# xelatex PDF generation (original implementation)
# ---------------------------------------------------------------------------


async def _generate_pdf_xelatex(
    doc_id: uuid.UUID,
    version: int,
    template: str,
    fields: dict[str, str],
) -> bytes:
    """Generate a PDF from a LaTeX template using xelatex.

    Raises RuntimeError if xelatex is not available.
    Raises RuntimeError if xelatex compilation fails.
    Raises PDFTimeoutError if compilation exceeds the timeout.
    """
    if _XELATEX_BIN is None:  # pragma: no cover — checked by caller
        raise RuntimeError(
            "xelatex is not installed. PDF generation is unavailable. Contact support or install TeX Live."
        )

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
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_XELATEX_TIMEOUT_S)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise PDFTimeoutError(f"xelatex timed out after {_XELATEX_TIMEOUT_S}s for doc_id={doc_id}")

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
        cached = _cache_path(doc_id, version)
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
