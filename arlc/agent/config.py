"""Agent configuration constants.

All magic numbers and tunable parameters in one place.
Override via environment variables where noted.
"""
import os

# --- Search ---
SEARCH_TOP_K: int = int(os.environ.get("AGENT_SEARCH_TOP_K", "3"))
SEARCH_MAX_PER_DOC: int = 1
SEARCH_ANSWER_TYPE: str = "free_text"

# --- Agent loop ---
MAX_SEARCHES_PER_TURN: int = int(os.environ.get("AGENT_MAX_SEARCHES", "5"))
MAX_ACCUMULATED_DOCS: int = int(os.environ.get("AGENT_MAX_DOCS", "10"))
MAX_HISTORY_MESSAGES: int = int(os.environ.get("AGENT_MAX_HISTORY", "10"))  # 5 Q&A pairs

# --- Web search ---
WEB_SEARCH_MAX_RESULTS: int = int(os.environ.get("AGENT_WEB_SEARCH_MAX", "3"))
WEB_SEARCH_ENABLED: bool = os.environ.get("AGENT_WEB_SEARCH_ENABLED", "true").lower() == "true"
MAX_WEB_SOURCES: int = int(os.environ.get("AGENT_MAX_WEB_SOURCES", "15"))

# --- Timeouts ---
AGENT_TIMEOUT_SECONDS: int = int(os.environ.get("AGENT_TIMEOUT_SECONDS", "300"))

# --- LLM ---
LLM_MODEL: str = os.environ.get("AGENT_LLM_MODEL", "claude-sonnet-4-6")
LLM_MODEL_FAST: str = os.environ.get("AGENT_LLM_MODEL_FAST", "claude-haiku-4-5")
LLM_MAX_TOKENS: int = int(os.environ.get("AGENT_LLM_MAX_TOKENS", "4096"))
