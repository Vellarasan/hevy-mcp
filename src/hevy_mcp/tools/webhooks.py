"""Webhook subscription tools (stretch). Hevy supports a single subscription per key."""

from __future__ import annotations

from typing import Any

from ..errors import tool_guard


def register(mcp, ctx) -> None:
    client = ctx.client

    @mcp.tool()
    @tool_guard
    async def get_webhook_subscription() -> dict[str, Any]:
        """Return the user's current webhook subscription, if any."""
        return {"data": await client.get("/webhook-subscription")}

    @mcp.tool()
    @tool_guard
    async def create_webhook_subscription(url: str, event_type: str = "workout_created") -> dict[str, Any]:
        """Create or replace the user's webhook subscription.

        - `url`: HTTPS endpoint Hevy will POST events to.
        - `event_type`: e.g. "workout_created". Hevy only accepts one subscription per key.
        """
        return {"data": await client.post("/webhook-subscription",
                                            json={"url": url, "eventType": event_type})}

    @mcp.tool()
    @tool_guard
    async def delete_webhook_subscription() -> dict[str, Any]:
        """Delete the active webhook subscription."""
        await client.delete("/webhook-subscription")
        return {"text": "Webhook subscription deleted."}
