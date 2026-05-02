from __future__ import annotations

import pytest

from hevy_mcp.formatters import format_workout


@pytest.mark.asyncio
async def test_list_workouts_returns_items(client, mock_hevy):
    data = await client.get("/workouts", params={"page": 1, "pageSize": 10})
    assert data["workouts"][0]["title"] == "Push Day A"


def test_format_workout_renders_sets():
    workout = {
        "title": "Push Day A",
        "start_time": "2026-04-28T17:00:00Z",
        "exercises": [
            {
                "title": "Bench Press",
                "sets": [
                    {"set_type": "warmup", "weight_kg": 60, "reps": 8},
                    {"set_type": "normal", "weight_kg": 100, "reps": 5, "rpe": 8},
                ],
            }
        ],
    }
    out = format_workout(workout)
    assert "Push Day A" in out
    assert "5 x 100kg" in out
    assert "RPE 8" in out
    assert "[warmup]" in out


@pytest.mark.asyncio
async def test_unauthorized_surfaces_helpful_hint(monkeypatch, hevy_base):
    monkeypatch.delenv("HEVY_API_KEY", raising=False)
    from hevy_mcp.errors import HevyApiError
    from hevy_mcp.hevy_client import HevyClient

    c = HevyClient(api_key="", base_url=hevy_base)
    try:
        with pytest.raises(HevyApiError) as exc:
            await c.request("GET", "/workouts")
        assert exc.value.status == 401
        assert "HEVY_API_KEY" in exc.value.hint or "key" in exc.value.hint.lower()
    finally:
        await c.aclose()
