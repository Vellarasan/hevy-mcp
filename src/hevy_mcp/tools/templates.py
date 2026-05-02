"""Exercise-template tools.

The template list rarely changes (~400 entries) so we cache the *full* list
client-side with a 24h TTL. After the first call:
  - `search_exercise_templates` runs a rapidfuzz match locally (<100ms cold-start
    after warm cache, near-instant after).
  - `get_exercise_template` is served from cache when possible.
  - `list_exercise_templates` slices the cached list rather than re-paginating.
"""

from __future__ import annotations

import asyncio
from typing import Any

from rapidfuzz import fuzz, process

from ..cache import TTLCache
from ..errors import tool_guard
from ..formatters import format_template

CACHE_TTL_SECONDS = 24 * 60 * 60
CACHE_KEY = "templates:all"


def register(mcp, ctx) -> None:
    client = ctx.client
    cache: TTLCache[list[dict[str, Any]]] = ctx.template_cache
    lock = asyncio.Lock()

    async def _all_templates() -> list[dict[str, Any]]:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached
        async with lock:
            cached = cache.get(CACHE_KEY)
            if cached is not None:
                return cached
            collected: list[dict[str, Any]] = []
            page = 1
            while True:
                data = await client.get("/exercise_templates",
                                         params={"page": page, "pageSize": 100})
                batch = _items(data)
                if not batch:
                    break
                collected.extend(batch)
                page_count = data.get("page_count") if isinstance(data, dict) else None
                if page_count is not None and page >= page_count:
                    break
                if len(batch) < 100:
                    break
                page += 1
                if page > 20:  # safety net — Hevy library is finite
                    break
            cache.set(CACHE_KEY, collected)
            return collected

    @mcp.tool()
    @tool_guard
    async def list_exercise_templates(
        page: int = 1, page_size: int = 50,
    ) -> dict[str, Any]:
        """Paginated browse of the Hevy exercise library (~400 entries). Cached for 24h.

        Prefer `search_exercise_templates` when looking up a specific exercise — it's
        far faster than scanning pages.
        """
        all_t = await _all_templates()
        start = (page - 1) * page_size
        end = start + page_size
        slice_ = all_t[start:end]
        return {
            "text": "\n".join(format_template(t) for t in slice_),
            "data": {"items": slice_, "page": page,
                      "page_count": (len(all_t) + page_size - 1) // page_size,
                      "total": len(all_t)},
        }

    @mcp.tool()
    @tool_guard
    async def get_exercise_template(template_id: str) -> dict[str, Any]:
        """Fetch a single exercise template by id (the Hevy library entry, not a logged set)."""
        all_t = await _all_templates()
        for t in all_t:
            if t.get("id") == template_id:
                return {"text": format_template(t), "data": t}
        # Fall back to live fetch if cache miss (custom user exercises etc.).
        data = await client.get(f"/exercise_templates/{template_id}")
        return {"data": data}

    @mcp.tool()
    @tool_guard
    async def search_exercise_templates(
        query: str,
        equipment: str | None = None,
        muscle_group: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Fuzzy-search the Hevy exercise library. **Use this before `create_routine`
        or `create_workout`** — it returns the `exercise_template_id` you need.

        - `query`: free-text exercise name. e.g. "barbell back squat", "incline db press".
        - `equipment`: optional filter, e.g. "barbell", "dumbbell", "cable", "machine", "bodyweight".
        - `muscle_group`: optional filter on `primary_muscle_group`, e.g. "chest", "lats", "quads".

        Returns ranked candidates with id, title, equipment, primary_muscle_group, and a
        match score 0-100. Pick the top hit unless the user disambiguates.
        """
        all_t = await _all_templates()
        candidates = all_t

        if equipment:
            eq = equipment.lower()
            candidates = [t for t in candidates if (t.get("equipment") or "").lower() == eq]
        if muscle_group:
            mg = muscle_group.lower()
            candidates = [t for t in candidates
                          if (t.get("primary_muscle_group") or "").lower() == mg
                          or mg in {m.lower() for m in (t.get("secondary_muscle_groups") or [])}]

        if not candidates:
            return {
                "error": f"No exercises matched the filters (equipment={equipment!r}, muscle_group={muscle_group!r}).",
                "hint": "Drop one of the filters and search by name only.",
                "results": [],
            }

        choices = {t["id"]: t.get("title", "") for t in candidates if t.get("id")}
        ranked = process.extract(query, choices, scorer=fuzz.WRatio, limit=limit)
        by_id = {t["id"]: t for t in candidates if t.get("id")}
        results = [
            {**by_id[tid], "match_score": int(score)}
            for (_title, score, tid) in ranked
        ]
        return {
            "text": "\n".join(f"{r['match_score']:>3}  {format_template(r)}" for r in results),
            "results": results,
        }


def _items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for k in ("exercise_templates", "items", "results", "data"):
            v = data.get(k)
            if isinstance(v, list):
                return v
    if isinstance(data, list):
        return data
    return []
