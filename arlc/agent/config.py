"""Agent configuration constants.

All magic numbers and tunable parameters in one place.
Override via environment variables where noted.
"""

import os

# --- Search ---
SEARCH_TOP_K: int = int(os.environ.get("AGENT_SEARCH_TOP_K", "3"))
SEARCH_TOP_K_THOROUGH: int = int(os.environ.get("AGENT_SEARCH_TOP_K_THOROUGH", "10"))
SEARCH_MAX_PER_DOC: int = int(os.environ.get("AGENT_SEARCH_MAX_PER_DOC", "3"))
SEARCH_ANSWER_TYPE: str = "free_text"

# --- Agent loop ---
MAX_SEARCHES_PER_TURN: int = int(os.environ.get("AGENT_MAX_SEARCHES", "5"))
MAX_ACCUMULATED_DOCS: int = int(os.environ.get("AGENT_MAX_DOCS", "50"))
MAX_HISTORY_MESSAGES: int = int(os.environ.get("AGENT_MAX_HISTORY", "10"))  # 5 Q&A pairs

# --- Web search ---
WEB_SEARCH_MAX_RESULTS: int = int(os.environ.get("AGENT_WEB_SEARCH_MAX", "3"))
WEB_SEARCH_ENABLED: bool = os.environ.get("AGENT_WEB_SEARCH_ENABLED", "true").lower() == "true"
MAX_WEB_SOURCES: int = int(os.environ.get("AGENT_MAX_WEB_SOURCES", "15"))

# --- Timeouts ---
AGENT_TIMEOUT_SECONDS: int = int(os.environ.get("AGENT_TIMEOUT_SECONDS", "600"))

# --- LLM ---
LLM_MODEL: str = os.environ.get("AGENT_LLM_MODEL", "claude-sonnet-4-6")
LLM_MODEL_FAST: str = os.environ.get("AGENT_LLM_MODEL_FAST", "claude-haiku-4-5")
LLM_MAX_TOKENS: int = int(os.environ.get("AGENT_LLM_MAX_TOKENS", "4096"))
LLM_MAX_TOKENS_FAST: int = int(os.environ.get("AGENT_LLM_MAX_TOKENS_FAST", "1024"))

# --- Haiku routing (NEO-2322 winner: classifier) ---
# Controls which model fires on the first reason call (search_count == 0).
#   "classifier" (default)   — Haiku only for greetings/meta; Sonnet for research queries (option C)
#   "search_count"           — Haiku on turn-1 query formulation, Sonnet after any search (option B)
#   "disabled"               — Sonnet for all calls (option A)
# Benchmark result (2026-04-17, 5q×2sets×3modes): classifier=90% > disabled=80% > search_count=70%
HAIKU_ROUTING_MODE: str = os.environ.get("AGENT_HAIKU_ROUTING_MODE", "classifier")
