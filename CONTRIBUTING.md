# Contributing to hevy-mcp

Thanks for considering a contribution! This is a small project, so the workflow is light.

## Getting set up

```bash
git clone https://github.com/Vellarasan/hevy-mcp.git
cd hevy-mcp
uv sync --extra dev          # or: python -m venv .venv && pip install -e ".[dev]"
pytest -q
```

You'll need a Hevy PRO account and an API key (<https://hevy.com/settings?developer>) to run anything against the real API. Unit tests run offline against `respx` mocks, so a key is *not* required for `pytest`.

## Style

- **Format / lint**: `ruff check .` and `ruff format .`
- **Types**: `mypy src/` (best-effort; not enforced in CI yet).
- **Tests**: every new tool needs at least one test. Use the fixtures in `tests/fixtures/` and `respx` to mock Hevy.

## Adding a new tool

1. Add the implementation in the relevant module under `src/hevy_mcp/tools/` (or create a new module and register it in `tools/__init__.py`).
2. Decorate with `@tool_guard` so errors come back as `{error, hint}`.
3. Write a docstring that tells Claude *when* to call this tool and *what to call before it* — Claude treats the docstring as the tool description.
4. Add a test under `tests/`.
5. Update the README's tool table and the CHANGELOG.

## Pull requests

- Branch from `main`.
- Keep PRs focused — one feature or fix per PR.
- Include a short description of what changed and why; link any related issues.
- Make sure CI passes (lint + tests + docker image size).

## Security issues

Please don't open a public issue for security bugs — see [SECURITY.md](SECURITY.md).

## Code of conduct

Be kind. We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
