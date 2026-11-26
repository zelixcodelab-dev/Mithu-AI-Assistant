# Mithu AI Command Center

The Command Center is an administrative interface mounted at `/command-center`. It is intentionally separate from the conversation UI and from the EduConnect integration.

## Architecture
- Existing FastAPI service: unchanged as the conversation API.
- Static responsive administration UI: `command-center/`.
- Admin endpoints: `app/command_center.py`, protected by the existing EdDSA identity assertion and a platform-admin role check.
- ElevenLabs API: server-side only; API keys must never be sent to the browser.
- Memory and permission policy: separate MongoDB collections within the dedicated Mithu database.
- EduConnect: existing read-only gateway remains separately configured and disabled by default.

## Environment additions
```env
ELEVENLABS_API_KEY=
ELEVENLABS_AGENT_ID=
# The Command Center is served same-origin by default.
```

Configure the API key only in the server environment. Do not commit the real key.

## Run
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100
```
Open `http://localhost:8100/command-center/`.

## Admin identity
The signed identity assertion must use the existing Mithu verifier and represent a platform-scoped `platform_owner` or `platform_admin`. Tenant users and business-mode users are not automatically administrators of the Command Center.

## Integration limitations
- Live WebSocket monitor signed-URL exchange is not implemented by the current connected ElevenLabs administration connector. The UI shows this as unavailable, not as live.
- The connected connector exposes conversation cost but not account-level credit balance. Remaining workspace credits therefore remain unavailable until an account-usage integration is added.
- ElevenLabs agent changes are versioned. Production publishing and traffic-split actions are intentionally not exposed as one-click browser actions.
- The existing main-branch ElevenLabs draft should be reviewed before applying settings.
