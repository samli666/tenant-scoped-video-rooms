from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from tenant_video.infrai_rtc import InfraiError, InfraiRtcClient
from tenant_video.tenant_sessions import (
    AccountNotActive,
    AccountState,
    SessionIssuer,
    TenantDirectory,
)


class OnboardTenant(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)


class ChangeAccountState(BaseModel):
    state: AccountState


class OpenRoom(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    vendor: str = Field(min_length=1, max_length=32)


class AdmitMember(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    member_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=80)
    role: Literal["host", "guest"]


directory = TenantDirectory()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    api_key = os.environ["INFRAI_API_KEY"]
    rtc = InfraiRtcClient(api_key)
    app.state.rtc = rtc
    yield
    await rtc.close()


app = FastAPI(title="Tenant Video Sessions", lifespan=lifespan)


def issuer(request: Request) -> SessionIssuer:
    return SessionIssuer(directory, request.app.state.rtc)


@app.exception_handler(AccountNotActive)
async def inactive_account_handler(request: Request, exc: AccountNotActive):
    return await http_error(409, "account_not_active", str(exc))


@app.exception_handler(InfraiError)
async def infrai_error_handler(request: Request, exc: InfraiError):
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return await http_error(status, exc.code, str(exc))


async def http_error(status: int, code: str, message: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status, content={"detail": {"code": code, "message": message}})


@app.post("/tenants", status_code=201)
async def onboard_tenant(body: OnboardTenant):
    return directory.onboard(body.tenant_id)


@app.patch("/tenants/{tenant_id}")
async def change_state(tenant_id: str, body: ChangeAccountState):
    try:
        return directory.set_state(tenant_id, body.state)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="tenant_not_found") from exc


@app.post("/tenants/{tenant_id}/rooms", status_code=201)
async def open_room(tenant_id: str, body: OpenRoom, request: Request):
    try:
        return await issuer(request).open_room(tenant_id, body.session_id, body.vendor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="tenant_not_found") from exc


@app.post("/tenants/{tenant_id}/tokens")
async def issue_member_token(tenant_id: str, body: AdmitMember, request: Request):
    try:
        return await issuer(request).admit_member(
            tenant_id,
            body.session_id,
            body.member_id,
            body.display_name,
            body.role,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="tenant_not_found") from exc
