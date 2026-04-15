import pytest
from pydantic import ValidationError

from neolex.schemas.query import (
    QueryRequest,
    pipeline_dict_to_response,
)


def test_query_request_defaults():
    req = QueryRequest(question="Is there a limitation period?")
    assert req.answer_type == "free_text"


def test_query_request_too_short():
    with pytest.raises(ValidationError):
        QueryRequest(question="hi")


def test_query_request_too_long():
    with pytest.raises(ValidationError):
        QueryRequest(question="x" * 2001)


def test_query_request_invalid_type():
    with pytest.raises(ValidationError):
        QueryRequest(question="What is the penalty?", answer_type="blob")


def test_query_request_strips_whitespace():
    req = QueryRequest(question="  What is the limitation period?  ")
    assert not req.question.startswith(" ")


def _make_result(**overrides) -> dict:
    base = {
        "id": "test-id",
        "question": "What is the limitation period?",
        "answer_type": "free_text",
        "answer": "The limitation period is 6 years under Article 10.",
        "chunk_pages": [{"doc_id": "DIFC-LAW-5-2005", "page_numbers": [12]}],
        "ttft_ms": 500,
        "tpot_ms": 10.0,
        "total_time_ms": 3200,
        "input_tokens": 1500,
        "output_tokens": 80,
        "model_name": "claude-sonnet-4-6",
    }
    base.update(overrides)
    return base


def test_pipeline_dict_to_response_happy_path():
    result = pipeline_dict_to_response(_make_result())
    assert result.confidence == "high"
    assert result.latency_ms == 3200
    assert result.model_name == "vitreon-legal"  # public name masked
    assert len(result.sources) == 1


def test_source_citation_maps_correctly():
    result = pipeline_dict_to_response(_make_result())
    source = result.sources[0]
    assert source.doc_id == "DIFC-LAW-5-2005"
    assert source.page_numbers == [12]


def test_pipeline_dict_none_answer():
    result = pipeline_dict_to_response(_make_result(answer=None))
    assert result.confidence == "not_found"
    assert result.answer is None


def test_pipeline_dict_error_model():
    result = pipeline_dict_to_response(_make_result(model_name="error"))
    assert result.confidence == "degraded"


def test_pipeline_dict_timeout_model():
    result = pipeline_dict_to_response(_make_result(model_name="timeout"))
    assert result.confidence == "degraded"


def test_boolean_answer_preserved():
    # Pydantic answer: Any must not coerce True to 1 or "true"
    result = pipeline_dict_to_response(_make_result(answer=True, answer_type="boolean"))
    assert result.answer is True
    assert isinstance(result.answer, bool)


def test_start_line_zero_preserved():
    # start_line=0 is a valid 0-indexed line number; must NOT be coerced to None
    result = _make_result(chunk_pages=[{"doc_id": "doc1.txt", "page_numbers": [1], "start_line": 0, "end_line": 42}])
    source = pipeline_dict_to_response(result).sources[0]
    assert source.start_line == 0, "start_line=0 must be preserved, not coerced to None"
    assert source.end_line == 42


def test_start_line_absent_is_none():
    # When start_line/end_line are not in the chunk dict, they must be None
    result = _make_result(chunk_pages=[{"doc_id": "doc1.txt", "page_numbers": [1]}])
    source = pipeline_dict_to_response(result).sources[0]
    assert source.start_line is None
    assert source.end_line is None


def test_start_line_positive_preserved():
    result = _make_result(chunk_pages=[{"doc_id": "doc1.txt", "page_numbers": [1], "start_line": 100, "end_line": 150}])
    source = pipeline_dict_to_response(result).sources[0]
    assert source.start_line == 100
    assert source.end_line == 150
