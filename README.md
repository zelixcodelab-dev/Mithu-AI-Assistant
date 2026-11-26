# Mithu AI — EduConnect Pro voice assistant

Malayalam-first live voice assistant for EduConnect Pro, with English and Manglish support.

## Current implementation
- GPT-Live full-duplex voice over a server-side WebSocket bridge
- Browser microphone capture and PCM16 24 kHz streaming
- Spoken responses streamed back to the browser
- Malayalam, Manglish and English speaking instructions
- Input and output transcript events
- Responses delegation for registered read-only EduConnect tools
- Short-lived Ed25519 identity assertion from the existing EduConnect API
- Separate Mithu metadata database; no direct EduConnect DB access
- Docker-ready FastAPI service

## Architecture
1. React browser requests a short-lived voice identity assertion from EduConnect using its existing authenticated Axios client.
2. The browser opens a WebSocket to Mithu and sends the assertion as a WebSocket subprotocol, not as a URL query parameter.
3. Mithu verifies the Ed25519 signature, issuer, audience, expiry, role and tenant.
4. Mithu opens a trusted server-to-server WebSocket to `wss://api.openai.com/v1/live/sessions`. The OpenAI API key stays on the Mithu server.
5. Mithu bridges raw PCM16 audio and transcript events. Function calls from Responses delegation are executed by the server-side allow-listed read-only tools.

## Security
- Never point `MITHU_MONGODB_URI` at EduConnect databases.
- Never give Mithu the EduConnect `MONGO_URL` or JWT signing secret.
- EduConnect issues the identity assertion only after its existing `get_current_user` authentication dependency has resolved the caller.
- Mithu accepts only EdDSA assertions with the expected issuer/audience and a maximum 120-second lifetime.
- Browser messages are allow-listed; no browser-supplied role or tenant becomes authorization.
- Only read-only AI tools are registered. Tool access is disabled unless `EDUCONNECT_API_ENABLED=true`.
- Tool calls must still be checked by the EduConnect API for the user's current tenant/office/student permissions.
- Raw audio and transcripts are not persisted by this initial voice service. Session metadata only is stored if the separate Mithu database is configured.

## Local run
```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100
```

Health: `GET /health`. Voice WebSocket: `/api/v1/voice/ws`.

## Environment
Set in the separate Mithu service:
- `OPENAI_API_KEY`
- `MITHU_LIVE_MODEL=gpt-live-1.1`
- `MITHU_RESPONSES_MODEL=gpt-6-luna`
- `MITHU_LIVE_VOICE=marin`
- `IDENTITY_PUBLIC_KEY_PEM` (public half of EduConnect's Ed25519 key pair)
- `MITHU_MONGODB_URI` (only if voice session metadata should be persisted)
- `CORS_ORIGINS` for the approved EduConnect browser origins

In EduConnect backend:
- `MITHU_IDENTITY_PRIVATE_KEY_PEM` (private half of the Ed25519 key pair)
- `MITHU_VOICE_ENABLED=true`
- `MITHU_VOICE_SERVICE_URL` (Mithu service HTTPS base URL)
- `MITHU_VOICE_WS_URL` (Mithu service WSS endpoint, e.g. `wss://mithu.example.com/api/v1/voice/ws`)

The private key and OpenAI key must be kept in the hosting secret manager. The public key may be configured on Mithu. Generate a fresh key pair for this integration; never reuse the EduConnect JWT secret.

## Important: EduConnect read-only gateway
The existing application still needs its dedicated internal AI gateway endpoints. Until those are implemented and reviewed, keep `EDUCONNECT_API_ENABLED=false`. Voice chat works for general education guidance, but live student, lead and college lookups will not be available.

## Browser audio
The client requires HTTPS (or localhost), microphone permission, and a browser with Web Audio and WebSocket support. Audio is streamed as mono PCM16LE at 24 kHz. The frontend holds transcripts only in memory for the active widget; it does not upload or save audio recordings.

## Deployment
Run this as an independent Docker service. Do not deploy to the EduConnect service or connect it to the EduConnect database. Configure secrets through the hosting provider. Tests should use synthetic user assertions and fake EduConnect gateways only.

Run tests: `pytest -q`.
