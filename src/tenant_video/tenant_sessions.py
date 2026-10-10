from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tenant_video.infrai_rtc import InfraiRtcClient


class AccountState(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class AccountNotActive(Exception):
    pass


@dataclass(frozen=True)
class TenantAccount:
    tenant_id: str
    state: AccountState


class TenantDirectory:
    def __init__(self) -> None:
        self._accounts: dict[str, TenantAccount] = {}

    def onboard(self, tenant_id: str) -> TenantAccount:
        account = TenantAccount(tenant_id=tenant_id, state=AccountState.ACTIVE)
        self._accounts[tenant_id] = account
        return account

    def set_state(self, tenant_id: str, state: AccountState) -> TenantAccount:
        account = self.get(tenant_id)
        updated = TenantAccount(tenant_id=account.tenant_id, state=state)
        self._accounts[tenant_id] = updated
        return updated

    def get(self, tenant_id: str) -> TenantAccount:
        return self._accounts[tenant_id]


class SessionIssuer:
    def __init__(self, directory: TenantDirectory, rtc: InfraiRtcClient) -> None:
        self._directory = directory
        self._rtc = rtc

    async def open_room(self, tenant_id: str, session_id: str, vendor: str) -> dict:
        self._require_active(tenant_id)
        room_name = f"tenant-{tenant_id}-{session_id}"
        return await self._rtc.create_room(
            name=room_name,
            vendor=vendor,
            idempotency_key=f"room:{tenant_id}:{session_id}",
        )

    async def admit_member(
        self,
        tenant_id: str,
        session_id: str,
        member_id: str,
        display_name: str,
        role: str,
    ) -> dict:
        self._require_active(tenant_id)
        return await self._rtc.issue_token(
            room=f"tenant-{tenant_id}-{session_id}",
            identity=f"{tenant_id}:{member_id}",
            ttl_seconds=900,
            can_publish=role == "host",
            can_subscribe=True,
            idempotency_key=f"token:{tenant_id}:{session_id}:{member_id}:{role}",
        )

    def _require_active(self, tenant_id: str) -> None:
        if self._directory.get(tenant_id).state is not AccountState.ACTIVE:
            raise AccountNotActive(f"Tenant {tenant_id} is not active")
