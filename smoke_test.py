#!/usr/bin/env python3
"""Smoke test against a real Hevy PRO account.

Usage:
    HEVY_API_KEY=sk_live_... python smoke_test.py

Reads (only) — never mutates routines or workouts. Exits 0 on success.
"""
from __future__ import annotations

import asyncio
import os
import sys

from hevy_mcp.hevy_client import HevyClient


async def main() -> int:
    if not os.environ.get("HEVY_API_KEY"):
        print("HEVY_API_KEY not set", file=sys.stderr)
        return 2
    c = HevyClient()
    try:
        count = await c.get("/workouts/count")
        print(f"workout_count = {count}")
        page = await c.get("/workouts", params={"page": 1, "pageSize": 1})
        items = page.get("workouts") or []
        print(f"latest_workout_title = {items[0]['title'] if items else '(none)'}")
        templates = await c.get("/exercise_templates", params={"page": 1, "pageSize": 5})
        print(f"templates_sample = {[t['title'] for t in templates.get('exercise_templates', [])][:5]}")
        return 0
    finally:
        await c.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
