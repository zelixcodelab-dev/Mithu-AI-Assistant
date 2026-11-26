# Mithu AI — EduConnect Pro assistant

Malayalam-first conversational assistant for EduConnect Pro.

## Scope
- Malayalam, Manglish and English text chat
- OpenAI Responses API orchestration
- Allow-listed read-only EduConnect gateway tools (disabled until configured)
- Separate MongoDB database for Mithu metadata
- Voice adapter boundary prepared for a later speech release
- Docker-ready FastAPI service

## Security
1. No direct EduConnect MongoDB access. Only `MITHU_MONGODB_URI` is used, with database name `educonnect_mithu`.
2. No reuse of EduConnect's `JWT_SECRET`. Mithu verifies short-lived Ed25519 identity assertions using `IDENTITY_PUBLIC_KEY_PEM`.
3. Browser-supplied role, tenant, office, permissions and student IDs are never authorization.
4. EduConnect integration is disabled by default. Only GET tool paths under `/internal/ai/` are accepted.
5. The EduConnect API must re-check identity, tenant, role, office and record visibility for every tool call.
6. No access tokens, raw student documents, full phone numbers, Aadhaar, fees or internal notes in logs.
7. Tests use in-memory fakes; they do not connect to EduConnect production data.

## Local run
```bash
cp .env.example .env
# Set OPENAI_API_KEY server-side. Add a separate test Mongo URI only if persistence is needed.
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100
```

Health check: `GET /health`.

## Required EduConnect-side integration
The EduConnect backend must authenticate its existing JWT using its existing `get_current_user` dependency, derive user and tenant context from server-side state, then issue a short-lived Ed25519 assertion with issuer, audience, subject, tenant, scope, role, office, permissions, issued-at, expiry and token ID. Use a 60–120 second validity window. The backend must proxy requests and apply the existing visibility logic.

No direct access to EduConnect's tenant databases, platform database or JWT signing secret should ever be granted to Mithu.

## Current app-specific facts
EduConnect Pro currently uses:
- React (Create React App/Craco), React Router 7, Axios; Vercel config is in `frontend/vercel.json`.
- FastAPI entry point `backend/server.py`, hosted separately (Render blueprint at root `render.yaml`, Python service root `backend`).
- MongoDB Motor with tenant-per-database routing in `backend/db.py`; shared platform DB is separate.
- JWT HS256, cookie + Bearer-token support, current-user resolution and tenant context binding in `backend/auth_lib.py`.
- Tenant roles: `super_admin`, `office_admin`, `user`, `staff`; platform scope is separately identified.
- Student visibility is explicitly different by role in `backend/routers/students.py`; leads are super-admin-wide, office-admin office-scoped, and staff assignment-scoped in `backend/routers/leads.py`.
- College `sc_rates` are confidential and stripped for non-super-admins in `backend/routers/colleges.py`.

## Limitations until the integration branch is reviewed
The service does not become connected to live EduConnect records merely by deployment. The companion branch must implement the identity-assertion issuer and read-only internal gateway first. This service currently has no write tools or direct DB access.

## Deploy
Use a separate Docker/container service. Bind to host-provided `PORT` or 8100. Store secrets only in the hosting provider. Do not attach the existing EduConnect database.

Run tests with `pytest -q`.
