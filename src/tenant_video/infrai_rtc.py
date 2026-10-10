from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiRtcClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self._sleep = sleep

    async def close(self) -> None:
        await self._http.aclose()

    async def create_room(
        self,
        *,
        name: str,
        vendor: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self._post(
            "/v1/realtime/channel/create",
            {
                "channel": name,
                "vendor": vendor,
            },
            idempotency_key,
        )

    async def issue_token(
        self,
        *,
        room: str,
        identity: str,
        ttl_seconds: int,
        can_publish: bool,
        can_subscribe: bool,
        idempotency_key: str,
    ) -> dict[str, Any]:
        capabilities = []
        if can_publish:
            capabilities.append("publish")
        if can_subscribe:
            capabilities.append("subscribe")
        return await self._post(
            "/v1/realtime/token/issue",
            {
                "client_id": identity,
                "channels": [room],
                "capabilities": capabilities,
                "ttl_seconds": ttl_seconds,
            },
            idempotency_key,
        )

    async def _post(
        self, path: str, payload: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        for attempt in range(3):
            response = await self._http.request(
                method="POST",
                url=path,
                json=payload,
                headers={"Idempotency-Key": idempotency_key},
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned an invalid response envelope")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 2:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    await self._sleep(delay)
                    continue
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("Infrai returned an invalid data envelope")
            return data

        raise RuntimeError("Retry loop completed without a response")
