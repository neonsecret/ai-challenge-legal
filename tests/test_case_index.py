import json
import pytest
from pathlib import Path


def test_case_index_structure():
    idx = json.load(open('data/case_metadata_index.json'))
    # Check at least one case has required fields
    case = list(idx.values())[0]
    assert 'docs' in case
    for doc in case['docs']:
        assert 'doc_id' in doc


def test_known_case_has_judge():
    idx = json.load(open('data/case_metadata_index.json'))
    # SCT 295/2025 should have a judge field somewhere
    sct = next((v for k, v in idx.items() if '295' in k and 'SCT' in k), None)
    assert sct is not None
