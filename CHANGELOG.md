# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Vellarasan/hevy-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Vellarasan/hevy-mcp/releases/tag/v0.1.0
