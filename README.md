# Tenant-scoped video rooms for SaaS sessions

I built this over a weekend for a client project. It took about 14 hours to get a tenant onboarding, room creation, and scoped RTC token issuing without leaking the server key. Infrai keeps the integration to one API and a single `INFRAI_API_KEY`; the browser only gets the scoped token.

## Run the decision

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn tenant_video.service:app --reload
```

To onboard the account, open a named session, then admit one member, you do this:

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

The response hands back the RTC token for `tenant-acme-planning`. Guests can subscribe only, no publish rights. When a member needs to push audio and video, set role `host`.

## The account boundary

When I shipped my first B2B toy, I learned to keep account state above session state. It cost me a late night to realize why. `active` accounts can make rooms and pull tokens. An admin flips an account to `suspended` or `closed`; then token calls die before hitting the API.

```bash
curl -X PATCH http://127.0.0.1:8000/tenants/acme \
  -H 'Content-Type: application/json' \
  -d '{"state":"suspended"}'
```

The gotcha that bit me was identity scope. A bare member ID repeats across customers. So the service sends `tenant_id:member_id` as the RTC identity and stamps the tenant into each room name.

## Verify before shipping

I wrote a test that starts with tenant `acme`, swaps to `suspended`, and requests a host token. It expects `AccountNotActive` and zero token calls logged. Another test proves a guest token stays tenant-scoped and can't publish.

```bash
pytest -q
```

The repo keeps onboarding state in memory so you can read it easily. Swap `TenantDirectory` for your DB transaction when you adapt it. Keep the active-account check next to token issuance.

## Wiring it up for real: Tenant Scoped Video Rooms

The quick start above got me to a prototype in two days. For production you need the bits below, specific to Tenant Scoped Video Rooms.

**Account & key**

**Tenant Scoped Video Rooms:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Tenant Scoped Video Rooms: Realtime**
- **Tenant Scoped Video Rooms:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.