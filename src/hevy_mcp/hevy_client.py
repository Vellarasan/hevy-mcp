"""Thin async HTTP client over the Hevy REST API.

Responsibilities:
    * Inject the api-key header.
    * Translate HTTP failures into HevyApiError so the tool layer can format them.
    * Retry once on 429 honoring Retry-After (capped) and on transient 5xx.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

from .errors import HevyApiError

log = logging.getLogger("hevy_mcp.client")

DEFAULT_BASE = "https://api.hevyapp.com/v1"
DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
MAX_RETRY_AFTER = 30.0  # cap so we don't block Claude for ages


class HevyClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("HEVY_API_KEY", "")
        self.base_url = (base_url or os.environ.get("HEVY_API_BASE") or DEFAULT_BASE).rstrip("/")
        if not self.api_key:
            # We don't raise here — the server may be configured per-request in remote
            # mode. The first call will surface a 401 with a helpful hint.
            log.warning("HEVY_API_KEY not set; remote-mode requests must supply one.")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": "hevy-mcp/0.1.0"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---- core request ---- #

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        api_key_override: str | None = None,
    ) -> Any:
        key = api_key_override or self.api_key
        if not key:
            raise HevyApiError(401, "No Hevy API key configured.",
                               "Set HEVY_API_KEY in the environment or pass it via the connector.")

        headers = {"api-key": key, "Accept": "application/json"}
        if json is not None:
            headers["Content-Type"] = "application/json"

        # Compact request body if present — strip None to keep payloads clean.
        clean_json = _strip_nones(json) if json is not None else None

        for attempt in range(2):
            try:
                resp = await self._client.request(
                    method, path, params=params, json=clean_json, headers=headers
                )
            except httpx.RequestError as e:
                raise HevyApiError(0, f"Network error talking to Hevy: {e}",
                                   "Check connectivity, then retry.") from e

            if resp.status_code == 429 and attempt == 0:
                retry_after = _retry_after_seconds(resp)
                log.info("hevy 429; sleeping %.2fs before retry", retry_after)
                await asyncio.sleep(retry_after)
                continue
            if 500 <= resp.status_code < 600 and attempt == 0:
                await asyncio.sleep(0.5)
                continue
            break

        if resp.status_code >= 400:
            msg = _extract_error_message(resp)
            raise HevyApiError(resp.status_code, msg)

        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError as e:
            raise HevyApiError(resp.status_code, f"Hevy returned non-JSON: {e}") from e

    # ---- convenience ---- #

    async def get(self, path: str, **kw: Any) -> Any:
        return await self.request("GET", path, **kw)

    async def post(self, path: str, **kw: Any) -> Any:
        return await self.request("POST", path, **kw)

    async def put(self, path: str, **kw: Any) -> Any:
        return await self.request("PUT", path, **kw)

    async def delete(self, path: str, **kw: Any) -> Any:
        return await self.request("DELETE", path, **kw)


def _retry_after_seconds(resp: httpx.Response) -> float:
    raw = resp.headers.get("Retry-After")
    if not raw:
        return 1.0
    try:
        return min(float(raw), MAX_RETRY_AFTER)
    except ValueError:
        return 1.0


def _extract_error_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict):
            for k in ("error", "message", "detail"):
                if k in body and isinstance(body[k], str):
                    return f"Hevy {resp.status_code}: {body[k]}"
        return f"Hevy {resp.status_code}: {body}"
    except ValueError:
        return f"Hevy {resp.status_code}: {resp.text[:200] or resp.reason_phrase}"


def _strip_nones(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_nones(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nones(v) for v in obj]
    return obj
