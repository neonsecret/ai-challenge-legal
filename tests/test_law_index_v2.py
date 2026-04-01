import json


def test_latest_edition_index_exists():
    idx = json.load(open("data/latest_edition_index.json"))
    # Should have at least 9 entries for warmup
    assert len(idx) >= 9


def test_edition_has_doc_id():
    idx = json.load(open("data/latest_edition_index.json"))
    for law_name, entry in list(idx.items())[:3]:
        assert "doc_id" in entry
        assert "year" in entry
