"""hevy-mcp server entrypoint.

Exposes the same tool surface over two transports from one binary:

    hevy-mcp                 # stdio, for Claude Desktop
    hevy-mcp --http          # Streamable HTTP, for claude.ai custom connectors
                             # bind via HEVY_MCP_HOST / HEVY_MCP_PORT or --host/--port

In HTTP mode we also accept a per-request `X-Hevy-Api-Key` header so the same
deployment can serve multiple users without baking a key into the env.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from .cache import TTLCache
from .hevy_client import HevyClient
from .tools import register_all


@dataclass
class AppContext:
    client: HevyClient
    template_cache: TTLCache


def _configure_logging() -> None:
    level = os.environ.get("HEVY_MCP_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}',
        stream=sys.stderr,
    )


def build_server() -> tuple[FastMCP, AppContext]:
    _configure_logging()
    client = HevyClient()
    ctx = AppContext(client=client, template_cache=TTLCache(ttl_seconds=24 * 60 * 60))

    mcp = FastMCP(
        name="hevy-mcp",
        instructions=(
            "Tools to read and write a user's data on Hevy (workout-tracking app). "
            "When the user asks to build or modify a routine from natural language, "
            "ALWAYS resolve exercise names to template ids via `search_exercise_templates` "
            "before calling `create_routine` or `update_routine`. Do not invent ids. "
            "Workout list pages are capped at 10 items by Hevy."
        ),
    )
    register_all(mcp, ctx)
    return mcp, ctx


def main() -> None:
    parser = argparse.ArgumentParser(prog="hevy-mcp")
    parser.add_argument("--http", action="store_true", help="Run Streamable HTTP transport (for remote connector use).")
    parser.add_argument("--host", default=os.environ.get("HEVY_MCP_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("HEVY_MCP_PORT", "8000")))
    parser.add_argument("--path", default=os.environ.get("HEVY_MCP_PATH", "/mcp"),
                        help="HTTP path the MCP endpoint is mounted at.")
    args = parser.parse_args()

    mcp, _ctx = build_server()

    if args.http:
        # Streamable HTTP — the current MCP transport for remote connectors.
        # We override host/port via FastMCP settings before run().
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.streamable_http_path = args.path
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
