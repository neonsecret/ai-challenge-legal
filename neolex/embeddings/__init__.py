"""NeoLex embedding layer — pluggable embedder backends.

When EMBEDDING_MODEL env var is "qwen3-8b" or "qwen3-0.6b", call
`neolex.embeddings.adapter.activate()` before loading the arlc pipeline to
monkey-patch arlc.retriever with the Qwen3 backend.  Default ("snowflake")
leaves arlc untouched.
"""
