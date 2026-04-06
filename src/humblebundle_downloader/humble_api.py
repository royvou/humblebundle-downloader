from __future__ import annotations

import asyncio

import httpx


class HumbleApiError(RuntimeError):
    """Raised for Humble API failures."""


class AuthError(HumbleApiError):
    """Raised when the configured session is invalid."""


class OrderKeyError(HumbleApiError):
    """Raised when an order key is missing or invalid."""


def _extract_gamekeys(payload: object) -> list[str]:
    if not isinstance(payload, list):
        raise HumbleApiError("Unexpected response from /api/v1/user/order.")

    gamekeys: list[str] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        gamekey = entry.get("gamekey")
        if isinstance(gamekey, str) and gamekey.strip():
            gamekeys.append(gamekey.strip())
    return gamekeys


class HumbleApiClient:
    def __init__(
        self, session: str, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://www.humblebundle.com",
            cookies={"_simpleauth_sess": session},
            follow_redirects=True,
            timeout=httpx.Timeout(60.0),
            headers={
                "user-agent": "humblebundle-downloader/0.1.0",
                "accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            },
            transport=transport,
        )

    async def __aenter__(self) -> "HumbleApiClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def test_auth(self) -> None:
        response = await self._client.get("/api/v1/user/order")
        if response.status_code == 401:
            raise AuthError("HB_SESSION is invalid or expired.")
        if response.status_code >= 400:
            raise HumbleApiError(
                f"Failed to validate HB_SESSION ({response.status_code})."
            )

        _extract_gamekeys(response.json())

    async def discover_order_keys(self) -> list[str]:
        response = await self._client.get("/api/v1/user/order")
        if response.status_code == 401:
            raise AuthError("HB_SESSION is invalid or expired.")
        if response.status_code >= 400:
            raise HumbleApiError(
                f"Failed to discover account orders ({response.status_code})."
            )
        return _extract_gamekeys(response.json())

    async def fetch_order(self, order_key: str) -> dict[str, object]:
        response = await self._client.get(
            f"/api/v1/order/{order_key}", params={"all_tpkds": "true"}
        )

        if response.status_code == 401:
            raise AuthError("HB_SESSION is invalid or expired.")
        if response.status_code == 404:
            raise OrderKeyError(f"Order key '{order_key}' was not found.")
        if response.status_code >= 400:
            raise HumbleApiError(
                f"Failed to fetch order '{order_key}' ({response.status_code})."
            )

        payload = response.json()
        if isinstance(payload, dict) and payload.get("_errors"):
            raise HumbleApiError(f"Humble API returned an error for '{order_key}'.")
        return payload

    async def fetch_orders(
        self, order_keys: list[str], *, concurrency: int = 2
    ) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
        semaphore = asyncio.Semaphore(concurrency)
        results: dict[str, dict[str, object]] = {}
        errors: dict[str, str] = {}

        async def fetch_one(order_key: str) -> None:
            async with semaphore:
                try:
                    results[order_key] = await self.fetch_order(order_key)
                except HumbleApiError as exc:
                    errors[order_key] = str(exc)

        await asyncio.gather(*(fetch_one(order_key) for order_key in order_keys))
        return results, errors
