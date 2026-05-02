# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-05-02

### Fixed
- Set-type field name mismatch with the Hevy API. Pydantic models declared
  `set_type`, but the Hevy REST API uses `type`. This broke two paths:
  (1) `create_routine` / `update_routine` / `create_workout` payloads were
  rejected by Hevy with `"set_type is not allowed"`, and (2) silently — Hevy
  GET responses' real `type` was stored as an `extra` field, leaving the
  modeled `set_type` at its default `"normal"`, so warmup-set filtering in
  `estimate_one_rep_max` and `volume_by_muscle_group` never matched and
  warmups polluted e1RM and volume calculations. Renamed `set_type` → `type`
  consistently across `schemas.py`, `formatters.py`, `tools/analytics.py`,
  tool docstrings, tests, and fixtures.
- `update_routine` no longer sends `folder_id` (or other server-managed
  fields) to Hevy. Hevy's `PUT /routines/{id}` rejects `folder_id` with HTTP
  400 — confirmed via Hevy's OpenAPI spec — and there is no public endpoint
  for moving a routine between folders. The new `_sanitize_routine_for_put`
  helper strips `id`, `folder_id`, `created_at`, `updated_at`, and `index`
  from the top-level routine before the PUT, so `update_routine` now accepts
  the raw output of `get_routine` as input. If the caller did supply a
  `folder_id`, the response includes a `warning` field explaining the
  limitation rather than silently no-op-ing.

### Changed
- Extracted `_do_update_routine`, `_do_create_routine` (in
  `tools/routines.py`) and `_score_e1rm` (in `tools/analytics.py`) as module-
  level async helpers so the tool bodies can be unit-tested directly without
  going through the FastMCP wrapper. Behavior is unchanged.

### Tests
- New `tests/test_analytics.py` — pins the warmup filter against silent
  regressions of the set_type→type bug.
- New `tests/test_routines_update.py` — pins the PUT payload sanitizer with
  unit tests of the helper plus an integration test that asserts `folder_id`,
  `id`, and timestamps never reach the wire.

## [0.1.1] - 2026-05-02

### Fixed
- PyPI project page now shows the author name. Split author (display) from
  maintainer (contact email) in `pyproject.toml` so the legacy `Author`
  metadata field is populated.

## [0.1.0] - 2026-05-01

### Added
- Initial public release.
- 21 MCP tools covering the Hevy API surface: workouts, routines, routine folders,
  exercise templates, webhook subscriptions.
- Three analytics tools computed client-side: `estimate_one_rep_max`,
  `volume_by_muscle_group`, `progression_trend`.
- Dual transport: stdio for Claude Desktop, Streamable HTTP for claude.ai
  custom connectors (`--http`).
- Fuzzy exercise resolver (`search_exercise_templates`) backed by a 24-hour
  TTL cache of the Hevy library.
- Idempotent routine creation (duplicate-title detection with `force=True` override).
- Uniform `{error, hint}` tool responses; rate-limit aware client honoring `Retry-After`.
- Docker image (~170 MB) and GitHub Actions CI.

[Unreleased]: https://github.com/Vellarasan/hevy-mcp/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/Vellarasan/hevy-mcp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Vellarasan/hevy-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Vellarasan/hevy-mcp/releases/tag/v0.1.0
