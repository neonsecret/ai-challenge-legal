import json


def parse_sse_events(text: str) -> list[dict]:
    """Parse SSE wire format into list of {event, data} dicts."""
    events = []
    current = {}
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:"):].strip()
        elif line == "" and current:
            events.append(current)
            current = {}
        # ignore comment lines (: ping)
    if current:
        events.append(current)
    return events


async def test_sse_delivers_three_events(app_client):
    response = await app_client.get(
        "/api/v1/query/stream",
        params={"question": "What is the limitation period under DIFC Law No. 5 of 2005?"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    events = parse_sse_events(response.text)
    # Filter out ping comments; keep named events only
    named = [e for e in events if "event" in e]
    assert len(named) == 3, f"Expected 3 events, got {len(named)}: {named}"
    assert named[0]["event"] == "status"
    assert named[1]["event"] == "answer"
    assert named[2]["event"] == "done"


async def test_sse_status_event_data(app_client):
    response = await app_client.get(
        "/api/v1/query/stream",
        params={"question": "What is the limitation period under DIFC Law No. 5 of 2005?"},
    )
    events = parse_sse_events(response.text)
    status_events = [e for e in events if e.get("event") == "status"]
    assert status_events, "No status event found"
    data = json.loads(status_events[0]["data"])
    assert data["status"] == "processing"


async def test_sse_answer_event_schema(app_client):
    response = await app_client.get(
        "/api/v1/query/stream",
        params={"question": "What is the limitation period under DIFC Law No. 5 of 2005?"},
    )
    events = parse_sse_events(response.text)
    answer_events = [e for e in events if e.get("event") == "answer"]
    assert answer_events, "No answer event found"
    data = json.loads(answer_events[0]["data"])
    # Must match QueryResponse schema
    assert "answer" in data
    assert "sources" in data
    assert "confidence" in data
    assert "latency_ms" in data
    assert "model_name" in data


async def test_sse_question_too_short(app_client):
    response = await app_client.get(
        "/api/v1/query/stream",
        params={"question": "hi"},
    )
    assert response.status_code == 422


async def test_sse_not_ready(app_client):
    from neolex.main import app
    app.state.ready = False
    try:
        response = await app_client.get(
            "/api/v1/query/stream",
            params={"question": "What is the limitation period?"},
        )
        assert response.status_code == 503
    finally:
        app.state.ready = True
