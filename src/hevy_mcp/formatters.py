"""JSON -> readable text helpers.

Tools return both a `text` field (compact, human/Claude readable) and a `data`
field (the raw structured payload). Empirically Claude reasons better when given
a digested view alongside the JSON, especially for nested workout/routine data.
"""

from __future__ import annotations

from typing import Any


def _fmt_weight(w: float | None) -> str:
    if w is None:
        return "bw"
    if w == int(w):
        return f"{int(w)}kg"
    return f"{w:.1f}kg"


def _fmt_set(s: dict[str, Any]) -> str:
    bits: list[str] = []
    reps = s.get("reps")
    weight = s.get("weight_kg")
    duration = s.get("duration_seconds")
    distance = s.get("distance_meters")
    rpe = s.get("rpe")
    set_type = s.get("set_type") or "normal"

    if reps is not None and weight is not None:
        bits.append(f"{reps} x {_fmt_weight(weight)}")
    elif reps is not None:
        bits.append(f"{reps} reps")
    elif duration is not None:
        bits.append(f"{duration}s")
    if distance is not None:
        bits.append(f"{distance}m")
    if rpe is not None:
        bits.append(f"RPE {rpe}")
    if set_type and set_type != "normal":
        bits.append(f"[{set_type}]")
    return " ".join(bits) or "-"


def format_workout(w: dict[str, Any]) -> str:
    title = w.get("title") or "(untitled)"
    start = w.get("start_time") or ""
    lines = [f"# {title}  {start}".rstrip()]
    if w.get("description"):
        lines.append(w["description"])
    for ex in w.get("exercises") or []:
        ex_title = ex.get("title") or ex.get("exercise_template_id") or "exercise"
        sets = ex.get("sets") or []
        set_strs = [_fmt_set(s) for s in sets]
        lines.append(f"- {ex_title}: " + ", ".join(set_strs) if set_strs else f"- {ex_title}")
        if ex.get("notes"):
            lines.append(f"    note: {ex['notes']}")
    return "\n".join(lines)


def format_routine(r: dict[str, Any]) -> str:
    lines = [f"## Routine: {r.get('title') or '(untitled)'}"]
    if r.get("notes"):
        lines.append(r["notes"])
    for ex in r.get("exercises") or []:
        ex_title = ex.get("title") or ex.get("exercise_template_id") or "exercise"
        sets = ex.get("sets") or []
        set_strs = [_fmt_set(s) for s in sets]
        rest = f" rest={ex['rest_seconds']}s" if ex.get("rest_seconds") else ""
        lines.append(f"- {ex_title}{rest}: " + ", ".join(set_strs))
    return "\n".join(lines)


def format_template(t: dict[str, Any]) -> str:
    parts = [t.get("title", "?")]
    mg = t.get("primary_muscle_group")
    eq = t.get("equipment")
    if mg:
        parts.append(f"({mg})")
    if eq:
        parts.append(f"[{eq}]")
    return " ".join(parts) + f"  id={t.get('id')}"
