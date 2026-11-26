# Mithu AI — EduConnect Pro assistant

Malayalam-first conversational assistant for EduConnect Pro, with a separate personal-assistant mode and a realtime voice interface powered by ElevenLabs Conversational AI.

## Scope
- Malayalam, Manglish and English text chat
- Realtime browser voice conversations through ElevenLabs Conversational AI
- Server-issued, short-lived ElevenLabs signed URLs; API keys never reach the browser
- OpenAI Responses API orchestration for the existing text assistant
- Allow-listed read-only EduConnect gateway tools (disabled until configured)
- Separate MongoDB database for Mithu metadata
- Docker-ready FastAPI service and standalone React/Vite web client

## Architecture and integration boundary
Mithu is a separate service. It does not connect directly to EduConnect MongoDB, tenant databases, platform databases or EduConnect's JWT secret. The existing EduConnect integration remains a separate authenticated gateway using short-lived Ed25519 identity assertions. The voice-session endpoint validates the same identity assertion before issuing a temporary ElevenLabs signed URL.

Personal assistant and business assistant behavior should be configured in the ElevenLabs agent prompt. EduConnect tools must remain server-side, allow-listed and read-only unless a separately reviewed write workflow is explicitly implemented.

## ElevenLabs setup
1. Create a Conversational AI agent in the ElevenLabs dashboard.
2. Configure its default voice as a female voice you are licensed to use.
3. Configure the agent prompt to support Malayalam, Manglish and English, and to distinguish personal requests from EduConnect business requests.
4. Enable authentication for the agent.
5. Add `ELEVENLABS_API_KEY` and `ELEVENLABS_AGENT_ID` to the Mithu backend hosting environment. Never add the API key to the web app or commit it.
6. Set `ELEVENLABS_SERVER_LOCATION` to `in-residency` if your ElevenLabs account/agent supports that region; otherwise use the region available to your account.

The backend endpoint `POST /api/v1/voice/session` requires `X-Mithu-Identity` and returns a short-lived signed URL. Signed URLs expire after 15 minutes; they are temporary secrets and must not be logged or persisted.

## Local run — backend
```bash
cp .env.example .env
# Configure OPENAI_API_KEY, identity public key and ElevenLabs credentials server-side.
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100
```

## Local run — web client
```bash
cd web
npm install
cp .env.example .env
npm run dev
```

The web client expects an authenticated host integration to provide a short-lived identity assertion through `window.mithuAuth.getIdentityAssertion()`. This keeps EduConnect authentication separate and avoids storing identity assertions in localStorage/sessionStorage. The integration host should inject this bridge after authenticating the user. Set `VITE_MITHU_API_URL` to the Mithu API URL.

## API
- `GET /health` — service health
- `GET /api/v1/voice/capabilities` — voice configuration status
- `POST /api/v1/voice/session` — authenticated short-lived ElevenLabs signed URL
- `POST /api/v1/chat` — authenticated text assistant

## Security
1. No direct EduConnect MongoDB access. Only `MITHU_MONGODB_URI` is used, with database name `educonnect_mithu`.
2. No reuse of EduConnect's `JWT_SECRET`. Mithu verifies short-lived Ed25519 identity assertions using `IDENTITY_PUBLIC_KEY_PEM`.
3. Browser-supplied role, tenant, office, permissions and student IDs are never authorization.
4. EduConnect integration is disabled by default. Only GET tool paths under `/internal/ai/` are accepted.
5. The EduConnect API must re-check identity, tenant, role, office and record visibility for every tool call.
6. No access tokens, raw student documents, full phone numbers, Aadhaar, fees or internal notes in logs.
7. Tests use in-memory fakes; they do not connect to EduConnect production data.
8. ElevenLabs API keys remain server-side. Signed URLs are returned with no-store headers.
9. Browser audio is captured only after the user explicitly starts a voice session.

## Required EduConnect-side integration
The EduConnect backend must authenticate its existing JWT using its existing `get_current_user` dependency, derive user and tenant context from server-side state, then issue a short-lived Ed25519 assertion with issuer, audience, subject, tenant, scope, role, office, permissions, issued-at, expiry and token ID. Use a 60–120 second validity window. The backend must proxy requests and apply the existing visibility logic.

No direct access to EduConnect's tenant databases, platform database or JWT signing secret should ever be granted to Mithu.

## Existing EduConnect application facts
EduConnect Pro currently uses React (Create React App/Craco), React Router 7 and Axios; its FastAPI backend is hosted separately. MongoDB Motor uses tenant-per-database routing. The EduConnect integration must remain behind its own authenticated gateway, not be merged into Mithu's database layer.

## Deployment
Deploy the FastAPI service and web client separately. Bind the API to the host-provided `PORT` or 8100. Store all secrets only in hosting-provider environment variables. Do not attach the existing EduConnect database.

Run tests with `pytest -q`.