"""Client-side analytics tools layered on top of `/workouts`.

These compute quickly enough that we don't need a separate cache; they iterate the
workout pages on demand. The `since`/`until` filters are ISO-8601 strings.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

from ..errors import HevyApiError, tool_guard

MAX_PAGES_DEFAULT = 30  # 30 * 10 = 300 workouts; covers ~1y for most users


def register(mcp, ctx) -> None:
    client = ctx.client

    @mcp.tool()
    @tool_guard
    async def estimate_one_rep_max(
        exercise_template_id: str,
        method: str = "epley",
        max_pages: int = MAX_PAGES_DEFAULT,
    ) -> dict[str, Any]:
        """Estimate the user's 1RM on a given exercise from their recent top sets.

        Walks the user's workouts (newest first), gathers every set of the target
        exercise, and applies a strength formula:
          - "epley":   weight * (1 + reps/30)
          - "brzycki": weight * 36 / (37 - reps)

        Returns the highest e1RM observed plus the contributing set, plus a short
        recent history. Skips warmups and reps>15 (formulas are unreliable past that).
        """
        sets = await _collect_sets_for_exercise(client, exercise_template_id, max_pages)
        if not sets:
            return {"error": "No sets found for that exercise.",
                    "hint": "Verify the template id with `search_exercise_templates`."}

        scored: list[tuple[float, dict[str, Any]]] = []
        for s, when in sets:
            w, r = s.get("weight_kg"), s.get("reps")
            if w is None or r is None or r <= 0 or r > 15 or s.get("set_type") == "warmup":
                continue
            e1rm = _epley(w, r) if method == "epley" else _brzycki(w, r)
            scored.append((e1rm, {**s, "estimated_1rm_kg": round(e1rm, 1), "performed_at": when}))
        if not scored:
            return {"error": "No working sets in the recent history qualify for an e1RM estimate.",
                    "hint": "Log a few heavier working sets, then try again."}
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        return {
            "text": f"Best e1RM: {best['estimated_1rm_kg']}kg (from {best.get('reps')} x {best.get('weight_kg')}kg)",
            "best_estimate_kg": best["estimated_1rm_kg"],
            "method": method,
            "best_set": best,
            "recent_estimates": [e[1] for e in scored[:10]],
        }

    @mcp.tool()
    @tool_guard
    async def volume_by_muscle_group(
        since: str | None = None,
        until: str | None = None,
        max_pages: int = MAX_PAGES_DEFAULT,
    ) -> dict[str, Any]:
        """Aggregate working-set volume (kg lifted) by primary muscle group over a window.

        Useful for "which muscle groups have I been neglecting?" prompts. Volume per
        set = weight_kg * reps; warmups excluded. Requires the template list to be
        loaded (it will be cached on first call).
        """
        ctx_templates = ctx.template_cache.get("templates:all") or []
        if not ctx_templates:
            # Force a load via list endpoint — keeps this tool standalone.
            page = 1
            while page <= 20:
                d = await client.get("/exercise_templates", params={"page": page, "pageSize": 100})
                items = d.get("exercise_templates") if isinstance(d, dict) else None
                if not items:
                    break
                ctx_templates.extend(items)
                if len(items) < 100:
                    break
                page += 1
            ctx.template_cache.set("templates:all", ctx_templates)
        by_id = {t["id"]: t for t in ctx_templates if t.get("id")}

        since_dt = _parse_dt(since)
        until_dt = _parse_dt(until)

        volume: dict[str, float] = defaultdict(float)
        sets_count: dict[str, int] = defaultdict(int)

        async for workout in _iter_workouts(client, max_pages):
            when = _parse_dt(workout.get("start_time") or workout.get("end_time"))
            if since_dt and when and when < since_dt:
                # workouts are newest-first, so we can stop here
                break
            if until_dt and when and when > until_dt:
                continue
            for ex in workout.get("exercises") or []:
                tpl = by_id.get(ex.get("exercise_template_id")) or {}
                muscle = tpl.get("primary_muscle_group") or "unknown"
                for s in ex.get("sets") or []:
                    if s.get("set_type") == "warmup":
                        continue
                    w, r = s.get("weight_kg"), s.get("reps")
                    if w is None or r is None:
                        continue
                    volume[muscle] += w * r
                    sets_count[muscle] += 1

        ranked = sorted(volume.items(), key=lambda kv: kv[1], reverse=True)
        text = "\n".join(f"{m:>14}  {v:>10.0f}kg-reps  ({sets_count[m]} sets)" for m, v in ranked)
        return {
            "text": text or "(no qualifying sets in window)",
            "by_muscle": {m: {"volume_kg_reps": v, "working_sets": sets_count[m]} for m, v in ranked},
            "window": {"since": since, "until": until},
        }

    @mcp.tool()
    @tool_guard
    async def progression_trend(
        exercise_template_id: str,
        since: str | None = None,
        max_pages: int = MAX_PAGES_DEFAULT,
    ) -> dict[str, Any]:
        """Top-set e1RM over time for a single exercise. Returns a per-session series
        suitable for charting.
        """
        since_dt = _parse_dt(since)
        sets = await _collect_sets_for_exercise(client, exercise_template_id, max_pages)
        # bucket by date, take best e1RM per session
        per_day: dict[str, float] = {}
        for s, when in sets:
            w, r = s.get("weight_kg"), s.get("reps")
            if w is None or r is None or r <= 0 or r > 15 or s.get("set_type") == "warmup":
                continue
            dt = _parse_dt(when)
            if since_dt and dt and dt < since_dt:
                continue
            if dt is None:
                continue
            day = dt.date().isoformat()
            e1rm = _epley(w, r)
            if e1rm > per_day.get(day, 0):
                per_day[day] = e1rm
        series = [{"date": d, "e1rm_kg": round(v, 1)} for d, v in sorted(per_day.items())]
        if len(series) >= 2:
            slope_per_week = _slope_per_week(series)
        else:
            slope_per_week = None
        return {
            "series": series,
            "slope_kg_per_week": slope_per_week,
            "text": (
                f"{len(series)} sessions; "
                f"slope ~{slope_per_week:+.2f}kg/week" if slope_per_week is not None
                else f"{len(series)} sessions"
            ),
        }


# ---- helpers ---- #

def _epley(weight: float, reps: int) -> float:
    return weight * (1 + reps / 30.0)


def _brzycki(weight: float, reps: int) -> float:
    if reps >= 37:
        return weight  # formula breaks down
    return weight * 36.0 / (37.0 - reps)


def _parse_dt(s: Any) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    try:
        # tolerate trailing Z
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


async def _iter_workouts(client, max_pages: int):
    for page in range(1, max_pages + 1):
        try:
            data = await client.get("/workouts", params={"page": page, "pageSize": 10})
        except HevyApiError as e:
            if e.status == 404:
                break
            raise
        items = data.get("workouts") if isinstance(data, dict) else None
        if not items:
            break
        for w in items:
            yield w
        if len(items) < 10:
            break


async def _collect_sets_for_exercise(
    client, template_id: str, max_pages: int,
) -> list[tuple[dict[str, Any], str | None]]:
    out: list[tuple[dict[str, Any], str | None]] = []
    async for w in _iter_workouts(client, max_pages):
        when = w.get("start_time") or w.get("end_time")
        for ex in w.get("exercises") or []:
            if ex.get("exercise_template_id") != template_id:
                continue
            for s in ex.get("sets") or []:
                out.append((s, when))
    return out


def _slope_per_week(series: list[dict[str, Any]]) -> float:
    """Simple least-squares slope of e1RM vs. day-index, scaled to per-week."""
    xs = []
    ys = []
    base = datetime.fromisoformat(series[0]["date"])
    for pt in series:
        d = datetime.fromisoformat(pt["date"])
        xs.append((d - base).days)
        ys.append(pt["e1rm_kg"])
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs) or 1.0
    slope_per_day = num / den
    return slope_per_day * 7.0
