from __future__ import annotations

import httpx
import pytest

from tenant_video.infrai_rtc import InfraiRtcClient


@pytest.mark.asyncio
async def test_rate_limit_envelope_retries_with_same_idempotency_key():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"ok": False, "data": None, "error": {"code": "busy"}, "metadata": {}},
            )
        return httpx.Response(
            200,
            json={"ok": True, "data": {"name": "tenant-acme-planning"}, "error": None, "metadata": {}},
        )

    client = InfraiRtcClient("test-key", transport=httpx.MockTransport(handler))
    try:
        result = await client.create_room(
            name="tenant-acme-planning",
            vendor="default",
            idempotency_key="room:acme:planning",
        )
    finally:
        await client.close()

    assert result == {"name": "tenant-acme-planning"}
    assert len(requests) == 2
    assert {request.headers["Idempotency-Key"] for request in requests} == {"room:acme:planning"}
    assert requests[-1].url.path == "/v1/realtime/channel/create"
    assert requests[-1].content == b'{"channel":"tenant-acme-planning","vendor":"default"}'
