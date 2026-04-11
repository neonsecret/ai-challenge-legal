"""Application-level constants for the Vitreon Legal API layer (neolex/).

These are protocol values shared across multiple routers or modules.
Centralising them here means a rename only happens in one place.

For RAG/embedding pipeline constants see arlc/constants.py.
For per-environment config (env-driven settings) see neolex/config.py.
"""

# ---------------------------------------------------------------------------
# Document drafting
# ---------------------------------------------------------------------------

CUSTOM_SLUG: str = "__custom__"
"""Magic slug sent by the frontend when the user selects a blank / freeform
document.  There is no database template row with this slug; the pipeline
resolves it to FREEFORM_SLUG so the FK constraint on
chat_documents.template_slug is satisfied."""

FREEFORM_SLUG: str = "vlastni_dokument"
"""Database slug for the freeform (blank) document template.
Corresponds to the seed row created by scripts/seed_templates.py."""

MAX_DOCS_PER_CONVERSATION: int = 3
"""Maximum number of draft documents allowed per conversation.
Enforced in both the REST endpoint (drafting.py) and the query pipeline
(query.py) with a pg_advisory_xact_lock to prevent races."""
