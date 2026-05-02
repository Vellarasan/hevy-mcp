"""Regression tests for the PUT /routines/{id} folder_id rejection (fixed in 0.1.2).

Hevy's OpenAPI spec is explicit: PostRoutinesRequestBody includes folder_id;
PutRoutinesRequestBody does not. Sending folder_id on PUT yields HTTP 400
"routine.folder_id is not allowed". There is also no public Hevy endpoint for
moving a routine between folders. These tests pin the sanitizer behavior so
the bug can never come back.
"""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

from hevy_mcp.tools.routines import _do_update_routine, _sanitize_routine_for_put


# ---------- unit tests of the sanitizer ---------- #

def test_sanitize_drops_folder_id_id_and_timestamps():
    cleaned, had_folder = _sanitize_routine_for_put({
        "id": "r1",
        "folder_id": 99,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "index": 3,
        "title": "Push Day",
        "notes": "x",
        "exercises": [],
    })
    assert had_folder is True
    for k in ("id", "folder_id", "created_at", "updated_at", "index"):
        assert k not in cleaned, f"{k} should have been stripped"
    # Real fields preserved.
    assert cleaned["title"] == "Push Day"
    assert cleaned["notes"] == "x"
    assert cleaned["exercises"] == []


def test_sanitize_returns_false_when_folder_id_absent():
    cleaned, had_folder = _sanitize_routine_for_put({"title": "X", "exercises": []})
    assert had_folder is False
    assert cleaned == {"title": "X", "exercises": []}


def test_sanitize_returns_false_when_folder_id_is_none():
    """Explicit folder_id=None should NOT trigger the warning — it's the API's
    way of saying 'no folder', which is the same as omitting it."""
    cleaned, had_folder = _sanitize_routine_for_put({
        "title": "X", "folder_id": None, "exercises": [],
    })
    assert had_folder is False
    assert "folder_id" not in cleaned


# ---------- integration test: real outgoing PUT body ---------- #

@pytest.mark.asyncio
async def test_update_routine_does_not_send_folder_id_to_hevy(client, hevy_base):
    """End-to-end: build a routine dict that includes folder_id, id, created_at,
    call _do_update_routine against a respx-mocked Hevy, and assert the captured
    PUT body has none of those keys at the top level."""
    captured: dict = {}

    with respx.mock(base_url=hevy_base, assert_all_called=True) as router:
        def capture(request):
            captured["body"] = json.loads(request.content)
            return Response(200, json={"routine": {"id": "r1", "title": "Push Day"}})

        router.put("/routines/r1").mock(side_effect=capture)

        result = await _do_update_routine(client, "r1", {
            "id": "r1",
            "folder_id": 42,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "title": "Push Day",
            "exercises": [
                {
                    "exercise_template_id": "tpl_bench",
                    "sets": [{"type": "normal", "weight_kg": 100, "reps": 5}],
                }
            ],
        })

    sent_routine = captured["body"]["routine"]
    for forbidden in ("id", "folder_id", "created_at", "updated_at"):
        assert forbidden not in sent_routine, (
            f"{forbidden} leaked into the PUT body — sanitizer is broken"
        )
    assert sent_routine["title"] == "Push Day"
    # The set's `type` field still rides through unchanged (not stripped).
    assert sent_routine["exercises"][0]["sets"][0]["type"] == "normal"

    # Caller gets a clear warning that folder_id was ignored.
    assert "warning" in result
    assert "folder_id" in result["warning"]


@pytest.mark.asyncio
async def test_update_routine_no_warning_when_no_folder_id_supplied(client, hevy_base):
    captured: dict = {}
    with respx.mock(base_url=hevy_base, assert_all_called=True) as router:
        def capture(request):
            captured["body"] = json.loads(request.content)
            return Response(200, json={"routine": {"id": "r1", "title": "Push Day"}})
        router.put("/routines/r1").mock(side_effect=capture)
        result = await _do_update_routine(client, "r1", {
            "title": "Push Day",
            "exercises": [
                {
                    "exercise_template_id": "tpl_bench",
                    "sets": [{"type": "normal", "weight_kg": 100, "reps": 5}],
                }
            ],
        })
    assert "warning" not in result
