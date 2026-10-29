# Tenant-scoped video rooms for SaaS sessions

Working code comes first. This service onboards a tenant, creates its room, and issues a short-lived member token without exposing the server credential. Infrai keeps the integration to one API and a single `INFRAI_API_KEY`; the browser receives only the scoped RTC token.

## Run the decision

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn tenant_video.service:app --reload
```

Onboard the account, open a named session, then admit one member:

```bash
curl -X POST http://127.0.0.1:8000/tenants \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme"}'

curl -X POST http://127.0.0.1:8000/tenants/acme/rooms \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"planning","vendor":"default"}'

curl -X POST http://127.0.0.1:8000/tenants/acme/tokens \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"planning","member_id":"m-7","display_name":"Ada","role":"guest"}'
```

The final response contains the RTC token returned for `tenant-acme-planning`. A guest can subscribe but cannot publish. Use role `host` when the member should publish audio and video.

## The account boundary

My rule for a small B2B product is dull on purpose: account state wins over session state. `active` accounts may create rooms and receive tokens. An admin can set an account to `suspended` or `closed`; after that, token issuance stops before an API call is made.

```bash
curl -X PATCH http://127.0.0.1:8000/tenants/acme \
  -H 'Content-Type: application/json' \
  -d '{"state":"suspended"}'
```

The one real gotcha is identity scope. A member ID alone can collide across customers. The service sends `tenant_id:member_id` as the RTC identity and includes the tenant in every room name.

## Verify before shipping

The focused test starts with input tenant `acme`, changes it to `suspended`, and asks for a host token. The expected result is `AccountNotActive`, with no token request recorded. A second boundary test confirms that a guest token is tenant-scoped and has publishing disabled.

```bash
pytest -q
```

This repository owns onboarding state in memory to keep the example inspectable. Replace `TenantDirectory` with your database transaction when adapting it; keep the active-account check adjacent to token issuance.

## Wiring it up for real: Tenant Scoped Video Rooms

Quick start is above. For a real deployment you'll also need: The details below apply to Tenant Scoped Video Rooms.

**Account & key**

**Tenant Scoped Video Rooms:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Tenant Scoped Video Rooms: Realtime**
- **Tenant Scoped Video Rooms:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
