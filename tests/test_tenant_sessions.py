from __future__ import annotations

import pytest

from tenant_video.tenant_sessions import (
    AccountNotActive,
    AccountState,
    SessionIssuer,
    TenantDirectory,
)


class RecordingRtc:
    def __init__(self) -> None:
        self.token_requests: list[dict] = []

    async def issue_token(self, **request):
        self.token_requests.append(request)
        return {"token": "signed-member-token"}


@pytest.mark.asyncio
async def test_suspended_tenant_cannot_receive_a_new_member_token():
    directory = TenantDirectory()
    directory.onboard("acme")
    directory.set_state("acme", AccountState.SUSPENDED)
    rtc = RecordingRtc()
    sessions = SessionIssuer(directory, rtc)  # type: ignore[arg-type]

    with pytest.raises(AccountNotActive):
        await sessions.admit_member("acme", "planning", "m-7", "Ada", "host")

    assert rtc.token_requests == []


@pytest.mark.asyncio
async def test_guest_token_is_tenant_scoped_and_cannot_publish():
    directory = TenantDirectory()
    directory.onboard("acme")
    rtc = RecordingRtc()
    sessions = SessionIssuer(directory, rtc)  # type: ignore[arg-type]

    result = await sessions.admit_member("acme", "planning", "m-7", "Ada", "guest")

    assert result == {"token": "signed-member-token"}
    assert rtc.token_requests == [
        {
            "room": "tenant-acme-planning",
            "identity": "acme:m-7",
            "ttl_seconds": 900,
            "can_publish": False,
            "can_subscribe": True,
            "idempotency_key": "token:acme:planning:m-7:guest",
        }
    ]
