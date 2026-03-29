"""LangGraph ReAct agent for legal research.

Wraps the existing FAISS + reranker retrieval pipeline as a tool
the LLM can call autonomously. The agent decides when to search,
what query to use (in the corpus language), and when accumulated
documents are sufficient to produce a grounded answer.
"""

from arlc.agent.graph import build_agent_graph, run_agent_turn

__all__ = ["build_agent_graph", "run_agent_turn"]
