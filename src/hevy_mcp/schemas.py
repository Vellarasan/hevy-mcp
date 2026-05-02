"""Pydantic models mirroring the relevant Hevy resources.

These are deliberately permissive (extra='allow') because the Hevy OpenAPI surface
evolves; we don't want a new optional field on the server side to break the client.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SetType = Literal["normal", "warmup", "dropset", "failure"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ---------- Sets / Exercises ---------- #

class WorkoutSet(_Base):
    index: int | None = None
    type: SetType = "normal"
    weight_kg: float | None = None
    reps: int | None = None
    distance_meters: float | None = None
    duration_seconds: int | None = None
    rpe: float | None = None
    custom_metric: float | None = None


class WorkoutExercise(_Base):
    exercise_template_id: str
    superset_id: int | None = None
    notes: str | None = None
    sets: list[WorkoutSet] = Field(default_factory=list)


class Workout(_Base):
    id: str | None = None
    title: str
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    is_private: bool = False
    exercises: list[WorkoutExercise] = Field(default_factory=list)


# ---------- Routines ---------- #

class RoutineSet(_Base):
    """Routines use the same set shape as workouts; reps/weight are targets."""
    index: int | None = None
    type: SetType = "normal"
    weight_kg: float | None = None
    reps: int | None = None
    distance_meters: float | None = None
    duration_seconds: int | None = None
    rpe: float | None = None
    custom_metric: float | None = None


class RoutineExercise(_Base):
    exercise_template_id: str
    superset_id: int | None = None
    rest_seconds: int | None = None
    notes: str | None = None
    sets: list[RoutineSet] = Field(default_factory=list)


class Routine(_Base):
    id: str | None = None
    title: str
    folder_id: int | None = None
    notes: str | None = None
    exercises: list[RoutineExercise] = Field(default_factory=list)


class RoutineFolder(_Base):
    id: int | None = None
    title: str


# ---------- Exercise templates ---------- #

class ExerciseTemplate(_Base):
    id: str
    title: str
    type: str | None = None
    primary_muscle_group: str | None = None
    secondary_muscle_groups: list[str] = Field(default_factory=list)
    equipment: str | None = None
    is_custom: bool | None = None


# ---------- Generic page wrapper ---------- #

class Page(_Base):
    page: int
    page_count: int
    items: list[Any]
