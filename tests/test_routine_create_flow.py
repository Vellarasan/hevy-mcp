"""End-to-end: natural-language exercise names -> template ids -> create_routine."""
from __future__ import annotations

import pytest
from rapidfuzz import fuzz, process


@pytest.mark.asyncio
async def test_resolve_then_create(client, mock_hevy):
    """Simulate Claude's flow: resolve names -> build payload -> POST /routines."""
    # Step 1: load template library.
    page = await client.get("/exercise_templates", params={"page": 1, "pageSize": 100})
    templates = page["exercise_templates"]
    by_id = {t["id"]: t for t in templates}
    name_to_id = {t["title"]: t["id"] for t in templates}

    # Step 2: fuzzy-resolve user-typed exercise names.
    user_request = ["barbell back squat", "incline db press should miss", "overhead press"]

    def best(name: str) -> str | None:
        match = process.extractOne(name, name_to_id.keys(), scorer=fuzz.WRatio)
        if match is None:
            return None
        title, score, _ = match
        return name_to_id[title] if score >= 70 else None

    squat_id = best("barbell back squat")
    ohp_id = best("overhead press")
    assert squat_id == "tpl_squat"
    assert ohp_id == "tpl_ohp"
    assert by_id[squat_id]["primary_muscle_group"] == "quads"

    # Step 3: build payload and POST.
    routine = {
        "title": "Hypertrophy Upper A",
        "exercises": [
            {"exercise_template_id": ohp_id, "sets": [
                {"set_type": "normal", "weight_kg": 50, "reps": 8},
                {"set_type": "normal", "weight_kg": 50, "reps": 8},
            ]},
        ],
    }
    resp = await client.post("/routines", json={"routine": routine})
    assert resp["routine"]["title"] == "Hypertrophy Upper A"
