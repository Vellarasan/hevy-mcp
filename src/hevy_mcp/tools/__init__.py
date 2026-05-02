"""Tool registration. Each module exposes `register(mcp, ctx)` to attach its tools."""

from . import analytics, folders, routines, templates, webhooks, workouts


def register_all(mcp, ctx) -> None:
    workouts.register(mcp, ctx)
    routines.register(mcp, ctx)
    folders.register(mcp, ctx)
    templates.register(mcp, ctx)
    webhooks.register(mcp, ctx)
    analytics.register(mcp, ctx)
