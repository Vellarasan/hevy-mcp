"""Routine tools.

Idempotency note: `create_routine` checks for an existing routine with the same
title in the target folder and asks Claude to confirm with `force=True` before
duplicating. This catches the very common pattern of Claude re-running a tool
after a transient error and silently doubling routines.
"""

from __future__ import annotations

from typing import Any

from ..errors import tool_guard
from ..formatters import format_routine
from ..schemas import Routine


def register(mcp, ctx) -> None:
    client = ctx.client

    @mcp.tool()
    @tool_guard
    async def list_routines(page: int = 1, page_size: int = 10) -> dict[str, Any]:
        """List the user's saved routines (templates they follow). Paginated."""
        data = await client.get("/routines", params={"page": page, "pageSize": page_size})
        items = _items(data, "routines")
        return {
            "text": "\n\n".join(format_routine(r) for r in items) or "(no routines on this page)",
            "data": data,
        }

    @mcp.tool()
    @tool_guard
    async def get_routine(routine_id: str) -> dict[str, Any]:
        """Fetch a single routine with every exercise and target set."""
        data = await client.get(f"/routines/{routine_id}")
        return {"text": format_routine(_unwrap(data, "routine")), "data": data}

    @mcp.tool()
    @tool_guard
    async def create_routine(
        routine: dict[str, Any],
        force: bool = False,
    ) -> dict[str, Any]:
        """Create a new routine.

        Required `routine` shape:
          { title, folder_id?, notes?, exercises: [
              { exercise_template_id, rest_seconds?, notes?, sets: [
                  { set_type, weight_kg?, reps?, rpe? }
              ] }
          ] }

        WORKFLOW for natural-language requests:
          1. Resolve every exercise name to a template id with `search_exercise_templates`.
          2. (Optional) Create or look up the target folder with the folder tools.
          3. Call this tool. If a routine with the same title already exists in the
             folder you'll get back a `duplicate_of` payload — confirm with the user,
             then re-call with `force=True` (or call `update_routine` instead).
        """
        validated = Routine.model_validate(routine).model_dump(exclude_none=True)
        title = validated.get("title")
        folder_id = validated.get("folder_id")

        if not force and title:
            dup = await _find_duplicate(client, title, folder_id)
            if dup is not None:
                return {
                    "error": f"A routine titled {title!r} already exists in this folder.",
                    "hint": ("Confirm with the user. To overwrite, call `update_routine` "
                             "with the existing id. To create anyway, re-call with force=True."),
                    "duplicate_of": dup,
                }

        data = await client.post("/routines", json={"routine": validated})
        return {"text": f"Routine '{title}' created.", "data": data}

    @mcp.tool()
    @tool_guard
    async def update_routine(routine_id: str, routine: dict[str, Any]) -> dict[str, Any]:
        """Update an existing routine in place. Same payload shape as `create_routine.routine`."""
        validated = Routine.model_validate(routine).model_dump(exclude_none=True)
        data = await client.put(f"/routines/{routine_id}", json={"routine": validated})
        return {"text": "Routine updated.", "data": data}


async def _find_duplicate(client, title: str, folder_id: int | None) -> dict[str, Any] | None:
    """Best-effort scan of the first few pages for a same-title routine."""
    title_norm = title.strip().lower()
    for page in range(1, 4):  # 3 pages * 10 = 30 routines, enough for typical libraries
        data = await client.get("/routines", params={"page": page, "pageSize": 10})
        items = _items(data, "routines")
        for r in items:
            if (r.get("title") or "").strip().lower() != title_norm:
                continue
            if folder_id is None or r.get("folder_id") == folder_id:
                return r
        if not items or len(items) < 10:
            break
    return None


def _items(data: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for k in (key, "items", "results", "data"):
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
