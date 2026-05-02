from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from hevy_mcp.cache import TTLCache
from hevy_mcp.hevy_client import HevyClient


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def hevy_base() -> str:
    return "https://api.hevyapp.com/v1"


@pytest.fixture
def api_key(monkeypatch) -> str:
    monkeypatch.setenv("HEVY_API_KEY", "sk_test_fake")
    return "sk_test_fake"


@pytest.fixture
async def client(api_key, hevy_base):
    c = HevyClient(api_key=api_key, base_url=hevy_base)
    yield c
    await c.aclose()


@pytest.fixture
def mock_hevy(hevy_base):
    with respx.mock(base_url=hevy_base, assert_all_called=False) as router:
        router.get("/workouts", params={"page": 1, "pageSize": 10}).mock(
            return_value=Response(200, json=_load("workouts_page1.json"))
        )
        router.get("/exercise_templates").mock(
            return_value=Response(200, json=_load("templates.json"))
        )
        router.get("/routines").mock(
            return_value=Response(200, json={"page": 1, "page_count": 1, "routines": []})
        )
        router.post("/routines").mock(
            return_value=Response(200, json={"routine": {"id": "r_new", "title": "Hypertrophy Upper A"}})
        )
        yield router


@pytest.fixture
def template_cache():
    return TTLCache(ttl_seconds=60)
