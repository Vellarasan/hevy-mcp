"""Uniform error shaping for tool responses.

Every tool wraps its body with `tool_guard` so failures come back to Claude as a
structured `{error, hint}` payload instead of a raw exception. The hint is the
single most useful field for Claude — it should suggest a concrete next tool call
or fix, not just describe the failure.
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Awaitable, Callable

import httpx

log = logging.getLogger("hevy_mcp")


class HevyApiError(Exception):
    def __init__(self, status: int, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.hint = hint or _default_hint(status)


def _default_hint(status: int) -> str:
    if status == 401:
        return "HEVY_API_KEY is missing or invalid. Verify the key at hevy.com/settings?developer."
    if status == 403:
        return "Hevy returned 403. The API requires an active Hevy PRO subscription."
    if status == 404:
        return "The requested resource was not found. Double-check the id with the matching `list_*` or `get_*` tool."
    if status == 409:
        return "Conflict — likely a duplicate. Use the corresponding `list_*` tool to check, then update instead of create."
    if status == 422:
        return "Hevy rejected the payload as invalid. Re-check required fields and exercise_template_id values."
    if status == 429:
        return "Rate limited. Wait the seconds reported by Retry-After before retrying."
    if 500 <= status < 600:
        return "Hevy is having a problem. Retry in a moment; if it persists, check status.hevyapp.com."
    return "Inspect the error message and retry with corrected input."


def tool_guard(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator: convert exceptions into `{error, hint}` and emit structured logs."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        name = func.__name__
        try:
            result = await func(*args, **kwargs)
            log.info("tool=%s status=ok duration_ms=%.1f", name, (time.monotonic() - start) * 1000)
            return result
        except HevyApiError as e:
            log.warning(
                "tool=%s status=hevy_error http=%d duration_ms=%.1f msg=%s",
                name, e.status, (time.monotonic() - start) * 1000, e.message,
            )
            return {"error": e.message, "hint": e.hint, "http_status": e.status}
        except httpx.TimeoutException:
            log.warning("tool=%s status=timeout duration_ms=%.1f", name, (time.monotonic() - start) * 1000)
            return {
                "error": "Hevy API request timed out.",
                "hint": "Retry the call. If it keeps timing out, reduce page_size or scope.",
            }
        except ValueError as e:
            log.warning("tool=%s status=bad_input duration_ms=%.1f msg=%s", name, (time.monotonic() - start) * 1000, e)
            return {"error": str(e), "hint": "Re-read the tool's input schema and adjust the arguments."}
        except Exception as e:  # noqa: BLE001 — last-resort guard so Claude never sees a stack trace
            log.exception("tool=%s status=internal_error duration_ms=%.1f", name, (time.monotonic() - start) * 1000)
            return {
                "error": f"Unexpected internal error: {type(e).__name__}: {e}",
                "hint": "This is a bug in hevy-mcp. Retry once; if it persists, file an issue with the tool name and inputs.",
            }

    return wrapper
