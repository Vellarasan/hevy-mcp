"""Routine folder tools."""

from __future__ import annotations

from typing import Any

from ..errors import tool_guard


def register(mcp, ctx) -> None:
    client = ctx.client

    @mcp.tool()
    @tool_guard
    async def list_routine_folders(page: int = 1, page_size: int = 10) -> dict[str, Any]:
        """List the user's routine folders (e.g. 'Push/Pull/Legs', 'Hypertrophy Block')."""
        return {"data": await client.get("/routine_folders",
                                          params={"page": page, "pageSize": page_size})}

    @mcp.tool()
    @tool_guard
    async def get_routine_folder(folder_id: int) -> dict[str, Any]:
        """Fetch a single routine folder by id."""
        return {"data": await client.get(f"/routine_folders/{folder_id}")}

    @mcp.tool()
    @tool_guard
    async def create_routine_folder(title: str) -> dict[str, Any]:
        """Create a new routine folder. Returns the new folder including its id, which
        you can pass to `create_routine` as `folder_id`.
        """
        data = await client.post("/routine_folders",
                                  json={"routine_folder": {"title": title}})
        return {"text": f"Folder '{title}' created.", "data": data}
