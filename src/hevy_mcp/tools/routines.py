"""Routine tools.

Idempotency note: `create_routine` checks for an existing routine with the same
title in the target folder and asks Claude to confirm with `force=True` before
duplicating. This catches the very common pattern of Claude re-running a tool
after a transient error and silently doubling routines.

Update note: Hevy's PUT /routines/{id} endpoint does NOT accept `folder_id`.
Confirmed via Hevy's OpenAPI: PostRoutinesRequestBody includes folder_id;
PutRoutinesRequestBody does not. There is also no public endpoint anywhere
in the Hevy API for moving a routine between folders. We strip folder_id (and
defensively a few other server-managed fields) before every PUT and surface a
warning to the caller if one was supplied so they don't silently get a no-op.
"""

from __future__ import annotations

from typing import Any

from ..errors import tool_guard
from ..formatters import format_routine
from ..schemas import Routine

# Top-level routine fields PUT /routines/{id} either rejects outright (folder_id)
# or that round-trip from a GET response and would be silently rejected (the
# id/created_at/updated_at/index group). Stripping these makes update_routine
# accept the output of get_routine as input without further massaging.
_PUT_ROUTINE_DROP_TOP = ("id", "folder_id", "created_at", "updated_at", "index")

_FOLDER_MOVE_WARNING = (
    "folder_id was supplied but ignored. Hevy's PUT /routines/{id} doesn't accept "
    "folder_id, and there is no public API endpoint for moving a routine between "
    "folders. The routine stays in its existing folder. To 'move' a routine, "
    "create a new copy in the target folder and delete the old one in the Hevy app."
)


def _sanitize_routine_for_put(routine: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Strip fields that PUT /routines/{id} rejects.

    Returns ``(cleaned, folder_id_was_explicitly_set)``. The boolean lets the
    caller surface a warning to the user that folder reassignment is not
    supported by Hevy's API.
    """
    folder_id_was_present = routine.get("folder_id") is not None
    cleaned = {k: v for k, v in routine.items() if k not in _PUT_ROUTINE_DROP_TOP}
    return cleaned, folder_id_was_present


async def _do_create_routine(
    client, routine: dict[str, Any], force: bool,
) -> dict[str, Any]:
    """Module-level body of the create_routine tool — kept testable without FastMCP."""
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


async def _do_update_routine(
    client, routine_id: str, routine: dict[str, Any],
) -> dict[str, Any]:
    """Module-level body of the update_routine tool — kept testable without FastMCP.

    Sanitizes the payload (drops folder_id and a few server-managed fields) and
    surfaces a `warning` field to the caller if folder_id was explicitly set, so
    users notice the silent no-op rather than thinking the move worked.
    """
    validated = Routine.model_validate(routine).model_dump(exclude_none=True)
    sanitized, folder_id_was_present = _sanitize_routine_for_put(validated)
    data = await client.put(f"/routines/{routine_id}", json={"routine": sanitized})
    out: dict[str, Any] = {"text": "Routine updated.", "data": data}
    if folder_id_was_present:
        out["warning"] = _FOLDER_MOVE_WARNING
    return out


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
                  { type, weight_kg?, reps?, rpe? }
              ] }
          ] }

        WORKFLOW for natural-language requests:
          1. Resolve every exercise name to a template id with `search_exercise_templates`.
          2. (Optional) Create or look up the target folder with the folder tools.
          3. Call this tool. If a routine with the same title already exists in the
             folder you'll get back a `duplicate_of` payload — confirm with the user,
             then re-call with `force=True` (or call `update_routine` instead).
        """
        return await _do_create_routine(client, routine, force)

    @mcp.tool()
    @tool_guard
    async def update_routine(routine_id: str, routine: dict[str, Any]) -> dict[str, Any]:
        """Update an existing routine in place.

        Same payload shape as `create_routine.routine`, with one important caveat:
        Hevy's PUT endpoint does NOT accept `folder_id`, and there is no public API
        endpoint for moving a routine between folders. If `folder_id` is present in
        the payload it is silently stripped and a `warning` is included in the
        response. To 'move' a routine, create a new copy in the target folder and
        delete the old one in the Hevy app.
        """
        return await _do_update_routine(client, routine_id, routine)


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
