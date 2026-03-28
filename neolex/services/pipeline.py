"""Adapter: wraps arlc.pipeline._process_question for single HTTP question.

This is the ONLY neolex/ file that imports from arlc/.
Do NOT import from arlc/ anywhere else in neolex/.
"""
from __future__ import annotations
import asyncio
import uuid
from typing import Any


async def run_single_question(
    question: str,
    answer_type: str,
    semaphore: asyncio.Semaphore,
    route_fn: Any,
    retrieve_fn: Any,
    answer_fn: Any,
    on_status: Any = None,
) -> dict:
    """Route one HTTP question through the arlc pipeline.

    on_status: optional callable(stage: str) emitted at each pipeline stage.
    Called from the event loop (between awaits), so asyncio.Queue.put_nowait is safe.

    _process_question is already async def — await it directly.
    Do NOT wrap it in asyncio.to_thread() (it would create a nested event loop).
    Do NOT call asyncio.run() here (event loop is already running in FastAPI).
    """
    from arlc.pipeline import _process_question

    question_data = {
        "id": str(uuid.uuid4()),
        "question": question,
        "answer_type": answer_type,
    }
    return await _process_question(
        question_data, route_fn, retrieve_fn, answer_fn, semaphore,
        on_status=on_status,
    )
