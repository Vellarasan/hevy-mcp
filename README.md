# hevy-mcp

> Connect Claude to your [Hevy](https://hevy.com) workout log.

`hevy-mcp` is a [Model Context Protocol](https://modelcontextprotocol.io) server that lets Claude (Desktop or claude.ai) read your workouts, design new routines, save them to your Hevy library, and analyze your training trends — the same kind of access ChatGPT users get from Hevy's official integration.

[![CI](https://github.com/YOUR-USER/hevy-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR-USER/hevy-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/hevy-mcp.svg)](https://pypi.org/project/hevy-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/hevy-mcp.svg)](https://pypi.org/project/hevy-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

```text
You: "Build me a 4-day upper/lower hypertrophy split focused on the muscle groups
      I've trained least over the last 30 days, and save it in a folder called
      'Hypertrophy Block 1'."

Claude: ✓ checked your last 30 days of training (lats and rear delts are behind)
        ✓ created folder "Hypertrophy Block 1"
        ✓ resolved 22 exercises against Hevy's library
        ✓ saved 4 routines: Upper A, Lower A, Upper B, Lower B
        Open the Hevy app to start any of them.
```

---

## What you can ask Claude to do

- **Look back** — *"Show me my last 10 workouts and tell me which muscle groups I've been neglecting."*
- **Plan ahead** — *"Based on my bench press history, what's a good top set for tomorrow?"*
- **Build routines** — *"Build me a 4-day upper/lower hypertrophy split and save it."*
- **Edit routines** — *"On 'Push Day A', swap dumbbell shoulder press for a barbell overhead press, 4 sets of 5."*
- **Analyze** — *"Estimate my 1RM on the main lifts and chart squat progression over the last 90 days."*

---

## Requirements

- A **Hevy PRO** subscription (the developer API requires it).
- Your Hevy API key — get it at <https://hevy.com/settings?developer>.
- Either **Python 3.11+** *or* **Docker**.
- Claude Desktop, or a claude.ai workspace that supports custom connectors.

---

## Quick start — Claude Desktop (5 minutes)

### 1. Install

```bash
# Easiest, with uv (https://docs.astral.sh/uv/):
uv tool install hevy-mcp

# Or with pipx:
pipx install hevy-mcp

# Or with plain pip:
python -m pip install hevy-mcp
```

### 2. Add it to Claude Desktop

Open Claude Desktop's config file:

- **macOS** — `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows** — `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux** — `~/.config/Claude/claude_desktop_config.json`

Add the `hevy` entry under `mcpServers` (create the file if it doesn't exist):

```json
{
  "mcpServers": {
    "hevy": {
      "command": "hevy-mcp",
      "env": {
        "HEVY_API_KEY": "sk_live_paste_your_key_here"
      }
    }
  }
}
```

> If `hevy-mcp` isn't on your PATH (uv-tool installs sometimes aren't picked up by the Claude Desktop launcher), use the absolute path you get from `which hevy-mcp` — for example `/Users/you/.local/bin/hevy-mcp`.

### 3. Restart Claude Desktop

Quit fully (⌘Q on macOS) and reopen. You should see a tools indicator showing the `hevy` server is connected.

### 4. Try it

> "Use the hevy tool to fetch my last 3 workouts and summarize them."

If Claude shows your real workouts, you're done. 🎉

---

## Alternative — claude.ai (remote connector)

If you use claude.ai in the browser instead of Claude Desktop, run `hevy-mcp` as an HTTP service and add it as a custom connector.

### 1. Run the server somewhere with HTTPS

The simplest path is Docker on Fly.io / Render / Railway:

```bash
docker build -t hevy-mcp .
docker run --rm -p 8000:8000 -e HEVY_API_KEY=sk_live_... hevy-mcp
```

Or directly with the CLI:

```bash
hevy-mcp --http --host 0.0.0.0 --port 8000
```

The MCP endpoint is at `/mcp`.

### 2. Add it as a custom connector

In claude.ai, go to **Settings → Connectors → Add custom connector** and use your public HTTPS URL ending in `/mcp` (e.g. `https://hevy-mcp.fly.dev/mcp`).

### Multi-user note

If multiple users will share the same deployment, don't bake `HEVY_API_KEY` into the container env — instead, send it as a per-request header. The server reads `X-Hevy-Api-Key` if present and falls back to the env var. A small auth-injecting reverse proxy (Cloudflare Worker, Nginx) in front of the server is the usual pattern.

---

## What it can do (full tool list)

| Group | Tool | What it does |
|---|---|---|
| **Workouts** | `list_workouts` | Page through your workout history, newest first. |
| | `get_workout` | Full detail of one workout — every set, rep, weight, RPE, note. |
| | `get_workout_count` | Total workouts logged. |
| | `get_workout_events` | Stream of created/updated/deleted events since a timestamp. |
| | `create_workout` | Log a completed workout. |
| | `update_workout` | Edit an already-logged workout. |
| **Routines** | `list_routines`, `get_routine` | Read your saved routines. |
| | `create_routine` | Save a new routine (with duplicate-title protection). |
| | `update_routine` | Modify an existing routine. |
| **Folders** | `list_routine_folders`, `get_routine_folder`, `create_routine_folder` | Organize routines. |
| **Exercise library** | `search_exercise_templates` | Fuzzy search Hevy's ~400-exercise library by name, equipment, or muscle. |
| | `list_exercise_templates`, `get_exercise_template` | Browse/look up exercises. |
| **Webhooks** | `create_webhook_subscription`, `get_webhook_subscription`, `delete_webhook_subscription` | One subscription per key (Hevy limit). |
| **Analytics** | `estimate_one_rep_max` | Epley/Brzycki e1RM from your top working sets. |
| | `volume_by_muscle_group` | Tonnage per muscle group over a window. |
| | `progression_trend` | e1RM-vs-time series for a single lift, with weekly slope. |

Under the hood:

- **Smart caching** — the exercise library is fetched once and cached for 24 hours; fuzzy search runs in memory.
- **Rate-limit aware** — backs off on 429s and honors `Retry-After`.
- **Idempotent writes** — creating a routine with a duplicate title in the same folder asks Claude to confirm before doubling.
- **LLM-friendly errors** — every error comes back as `{ error, hint }`. The hint suggests the next concrete tool call.
- **Never logs your API key.**

---

## Troubleshooting

<details>
<summary><strong>Claude Desktop says the server "disconnected" right after starting</strong></summary>

Most common cause: the `command` in `claude_desktop_config.json` isn't on the launcher's PATH. Replace `"command": "hevy-mcp"` with the absolute path from `which hevy-mcp` (or `where hevy-mcp` on Windows). Restart Claude Desktop.
</details>

<details>
<summary><strong>Tool calls fail with "HEVY_API_KEY is missing or invalid"</strong></summary>

- Check that you pasted the key into the `env` block (not the `args` block).
- Confirm your Hevy PRO subscription is active.
- Rotate your key at <https://hevy.com/settings?developer> and try again.
</details>

<details>
<summary><strong>Claude can't find the right exercise when creating a routine</strong></summary>

`search_exercise_templates` is fuzzy but not magic. If Claude picks the wrong exercise, ask it to "search again with a more specific name" or pass an `equipment` filter (e.g. *"barbell"*).
</details>

<details>
<summary><strong>It's slow on the first call</strong></summary>

The exercise library is fetched on the first lookup (one-time, ~200ms). Every call after that hits the in-memory cache. The cache lasts 24 hours.
</details>

---

## Development

```bash
git clone https://github.com/YOUR-USER/hevy-mcp.git
cd hevy-mcp
uv sync --extra dev          # creates .venv and installs deps
pytest -q                    # offline tests (no real API needed)

# Run against your real Hevy account:
HEVY_API_KEY=sk_live_... python smoke_test.py

# Stdio (Claude Desktop):
hevy-mcp

# HTTP (claude.ai):
hevy-mcp --http --port 8000
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the longer version.

### Project layout

```
hevy-mcp/
├── src/hevy_mcp/
│   ├── server.py        # transport bootstrap (stdio + streamable-http)
│   ├── hevy_client.py   # async httpx client w/ retries & error mapping
│   ├── schemas.py       # Pydantic models
│   ├── cache.py         # 24-hour TTL cache
│   ├── errors.py        # HevyApiError + tool_guard
│   ├── formatters.py    # JSON → readable text
│   └── tools/           # workouts, routines, folders, templates, webhooks, analytics
├── tests/
└── Dockerfile
```

---

## Releases

See [CHANGELOG.md](CHANGELOG.md). Tagged releases publish to PyPI automatically.

## License

[MIT](LICENSE).

## Thanks

This project's design owes ideas to two earlier community implementations: [`chrisdoc/hevy-mcp`](https://github.com/chrisdoc/hevy-mcp) (TypeScript) and [`SrdjanCodes/hevy-mcp`](https://github.com/SrdjanCodes/hevy-mcp) (Python). Not a fork — but worth a look if you want a different language or feature mix.

`hevy-mcp` is a community project and is not affiliated with or endorsed by Hevy.
