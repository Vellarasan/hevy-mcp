"""Regression tests for the silent set_type→type bug (fixed in 0.1.2).

Background: until 0.1.2 our schemas declared `set_type` while the Hevy REST
API uses `type`. Two effects:
  1. Loud — POST/PUT bodies were rejected with "set_type is not allowed".
  2. Silent — Hevy GETs return `type`. Pydantic stored that as an extra,
     leaving the modeled `set_type` at its default "normal", so the warmup
     filter in `estimate_one_rep_max` and `volume_by_muscle_group` (which
     read `s.get("set_type") == "warmup"`) never matched and warmup sets
     polluted the analytics.

These tests exercise the extracted `_score_e1rm` helper directly so the
warmup-filter logic can never silently break again, regardless of how it's
wired into FastMCP.
"""

from __future__ import annotations

from hevy_mcp.tools.analytics import _score_e1rm


def test_score_e1rm_excludes_warmups_even_when_warmup_would_outrank():
    """A heavy single-rep warmup must NOT win against a lighter working set.

    Epley: 60 * (1 + 1/30) ≈ 62.0   (warmup, must be excluded)
    Epley: 50 * (1 + 5/30) ≈ 58.3   (working set, the only valid candidate)

    Pre-0.1.2 the warmup wasn't filtered (because the filter looked for
    `set_type` while the Hevy field is `type`), so it incorrectly won.
    """
    sets = [
        ({"type": "warmup", "weight_kg": 60, "reps": 1}, "2026-04-01T00:00:00Z"),
        ({"type": "normal", "weight_kg": 50, "reps": 5}, "2026-04-02T00:00:00Z"),
    ]
    scored = _score_e1rm(sets, "epley")
    assert len(scored) == 1, "warmup should have been excluded"
    best = scored[0][1]
    assert best["weight_kg"] == 50
    assert best["reps"] == 5
    assert best["type"] == "normal"


def test_score_e1rm_excludes_high_reps_and_missing_data():
    sets = [
        ({"type": "normal", "weight_kg": 40, "reps": 20}, None),       # reps too high
        ({"type": "normal", "weight_kg": None, "reps": 5}, None),      # no weight
        ({"type": "normal", "weight_kg": 80, "reps": 0}, None),        # zero reps
        ({"type": "normal", "weight_kg": 80, "reps": 3},
         "2026-04-03T00:00:00Z"),                                      # the only valid one
    ]
    scored = _score_e1rm(sets, "epley")
    assert len(scored) == 1
    assert scored[0][1]["weight_kg"] == 80
    assert scored[0][1]["reps"] == 3


def test_score_e1rm_sorts_descending_and_uses_brzycki():
    sets = [
        ({"type": "normal", "weight_kg": 100, "reps": 5}, None),  # epley=116.7, brzycki=112.5
        ({"type": "normal", "weight_kg": 110, "reps": 3}, None),  # epley=121.0, brzycki=116.5
    ]
    scored_epley = _score_e1rm(sets, "epley")
    scored_brzycki = _score_e1rm(sets, "brzycki")
    # Both formulas should rank the 110x3 set first.
    assert scored_epley[0][1]["weight_kg"] == 110
    assert scored_brzycki[0][1]["weight_kg"] == 110
    # Brzycki gives a different absolute number than Epley.
    assert scored_epley[0][0] != scored_brzycki[0][0]
