"""Workout tools.

Hevy caps workout list page_size at 10. We enforce that here so Claude gets a
helpful error before the round-trip rather than a 422 back from the API.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..errors import tool_guard
from ..formatters import format_workout
from ..schemas import Workout

WORKOUT_PAGE_SIZE_MAX = 10


def register(mcp, ctx) -> None:
    client = ctx.client

    @mcp.tool()
    @tool_guard
    async def list_workouts(
        page: int = Field(1, ge=1, description="1-indexed page number."),
        page_size: int = Field(10, ge=1, le=WORKOUT_PAGE_SIZE_MAX,
                                description="Workouts per page. Hevy caps this at 10."),
    ) -> dict[str, Any]:
        """List the user's workouts in reverse-chronological order.

        Use this first when the user asks about "recent workouts", "last N sessions",
        "what did I train on Monday", etc. Each item is a *summary*; call
        `get_workout(workout_id)` for full set-by-set detail when the user asks
        about specific weights, RPE, or progression.
        """
        data = await client.get("/workouts", params={"page": page, "pageSize": page_size})
        items = _items(data)
        return {
            "text": "\n\n".join(format_workout(w) for w in items) or "(no workouts on this page)",
            "data": data,
            "page": page,
            "page_count": data.get("page_count") if isinstance(data, dict) else None,
        }

    @mcp.tool()
    @tool_guard
    async def get_workout(workout_id: str) -> dict[str, Any]:
        """Fetch a single workout with every set, rep, weight, RPE, and note.

        Use this when the user asks about a *specific* workout or wants to compare
        sets across sessions. Pair with `list_workouts` to discover the id first.
        """
        data = await client.get(f"/workouts/{workout_id}")
        return {"text": format_workout(_unwrap(data, "workout")), "data": data}

    @mcp.tool()
    @tool_guard
    async def get_workout_count() -> dict[str, Any]:
        """Total number of workouts the user has logged. Cheap; safe to call eagerly."""
        data = await client.get("/workouts/count")
        count = data.get("workout_count") if isinstance(data, dict) else data
        return {"text": f"{count} workouts", "data": data, "count": count}

    @mcp.tool()
    @tool_guard
    async def get_workout_events(
        page: int = 1,
        page_size: int = 10,
        since: str | None = Field(
            None,
            description="ISO-8601 timestamp. Only events newer than this are returned.",
        ),
    ) -> dict[str, Any]:
        """Stream of workout change events (created/updated/deleted).

        Use to detect new workouts since a previous interaction without re-paginating
        the full list. The `since` parameter is ISO-8601 (e.g. `2025-01-01T00:00:00Z`).
        """
        params: dict[str, Any] = {"page": page, "pageSize": page_size}
        if since:
            params["since"] = since
        data = await client.get("/workouts/events", params=params)
        return {"data": data, "page": page}

    @mcp.tool()
    @tool_guard
    async def create_workout(workout: dict[str, Any]) -> dict[str, Any]:
        """Log a completed workout to Hevy.

        `workout` shape:
          { title, description?, start_time, end_time, is_private?, exercises: [
              { exercise_template_id, notes?, superset_id?, sets: [
                  { type, weight_kg?, reps?, rpe?, distance_meters?, duration_seconds? }
              ] }
          ] }

        Resolve `exercise_template_id` values via `search_exercise_templates` *before*
        calling this tool — never invent IDs.
        """
        validated = Workout.model_validate(workout).model_dump(exclude_none=True)
        data = await client.post("/workouts", json={"workout": validated})
        return {"text": "Workout logged.", "data": data}

    @mcp.tool()
    @tool_guard
    async def update_workout(workout_id: str, workout: dict[str, Any]) -> dict[str, Any]:
        """Replace the contents of an existing logged workout. Same payload shape as `create_workout`."""
        validated = Workout.model_validate(workout).model_dump(exclude_none=True)
        data = await client.put(f"/workouts/{workout_id}", json={"workout": validated})
        return {"text": "Workout updated.", "data": data}


def _items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for k in ("workouts", "items", "results", "data"):
            v = data.get(k)
            if isinstance(v, list):
                return v
    if isinstance(data, list):
        return data
    return []


def _unwrap(data: Any, key: str) -> dict[str, Any]:
    if isinstance(data, dict) and key in data and isinstance(data[key], dict):
        return data[key]
    return data if isinstance(data, dict) else {}
