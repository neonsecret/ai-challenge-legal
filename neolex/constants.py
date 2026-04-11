"""Shared constants for the Vitreon Legal API layer (neolex/).

For RAG pipeline constants (truncation limits, embedding budgets, etc.)
see arlc/constants.py.
"""

# ═══════════════════════════════════════════════════════════════════════════
# Document Drafting
# Shared between neolex/routers/drafting.py and neolex/routers/query.py.
# ═══════════════════════════════════════════════════════════════════════════

DRAFTING_CUSTOM_SLUG: str = "__custom__"
"""Slug the frontend sends for a blank/freeform custom document.

There is no DB template row with this slug — it must be resolved to
DRAFTING_FREEFORM_SLUG before any FK-constrained DB operation."""

DRAFTING_FREEFORM_SLUG: str = "vlastni_dokument"
"""DB slug for the freeform template (seed: scripts/seed_templates.py).

Used as the effective slug when the frontend sends DRAFTING_CUSTOM_SLUG,
satisfying the FK constraint on chat_documents.template_slug."""

DRAFTING_MAX_DOCS_PER_CONVERSATION: int = 3
"""Maximum number of draft documents allowed per conversation.

Enforced both in the REST create endpoint (with pg_advisory_xact_lock)
and in the pipeline document creation helper (_create_pipeline_document)."""
