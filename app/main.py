from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4
import logging
import httpx
from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import store
from app.schemas import ChatRequest, ChatResponse, VoiceCapability, VoiceSessionResponse
from app.security import UserContext, require_user_context
from app.agent import MithuAgent
from app.language import detect_language
from app.educonnect import EduConnectUnavailable

cfg = get_settings()
log = logging.getLogger("mithu")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await store.connect()
    except Exception:
        log.exception("Mithu metadata store unavailable; continuing without persistence")
        await store.close()
    yield
    await store.close()

app = FastAPI(title="Mithu AI", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Mithu-Identity"],
)
agent = MithuAgent()

@app.get("/health")
async def health():
    return {
        "service": cfg.service_name,
        "status": "ok",
        "environment": cfg.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/api/v1/voice/capabilities", response_model=VoiceCapability)
async def voice_capabilities():
    configured = bool(cfg.elevenlabs_api_key and cfg.elevenlabs_agent_id)
    return VoiceCapability(
        enabled=configured,
        note="Realtime voice is configured." if configured else
             "Set ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID on the server.",
    )

@app.post("/api/v1/voice/session", response_model=VoiceSessionResponse)
async def create_voice_session(
    response: Response,
    user: UserContext = Depends(require_user_context),
):
    """Issue a temporary ElevenLabs signed URL only to an authenticated user."""
    del user  # Identity verification is the authorization gate; no identity is sent to ElevenLabs.
    if not cfg.elevenlabs_api_key or not cfg.elevenlabs_agent_id:
        raise HTTPException(status_code=503, detail="Realtime voice is not configured")
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            upstream = await client.get(
                "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url",
                params={"agent_id": cfg.elevenlabs_agent_id},
                headers={"xi-api-key": cfg.elevenlabs_api_key},
            )
        if upstream.status_code >= 400:
            log.warning("ElevenLabs signed URL request failed with status %s", upstream.status_code)
            raise HTTPException(status_code=502, detail="Unable to start a voice session")
        signed_url = upstream.json().get("signed_url")
        if not isinstance(signed_url, str) or not signed_url.startswith("wss://"):
            raise HTTPException(status_code=502, detail="ElevenLabs returned an invalid session URL")
    except httpx.HTTPError as exc:
        log.warning("ElevenLabs session request failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Voice provider is temporarily unavailable") from exc
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    return VoiceSessionResponse(
        signed_url=signed_url,
        agent_id=cfg.elevenlabs_agent_id,
        server_location=cfg.elevenlabs_server_location,
    )

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, user: UserContext = Depends(require_user_context)):
    language = detect_language(payload.message, payload.language)
    session_id = payload.session_id or str(uuid4())
    try:
        answer, used = await agent.respond(payload.message, user, language)
    except EduConnectUnavailable as exc:
        answer, used = str(exc), []
    except Exception:
        log.exception("Mithu request failed")
        raise HTTPException(status_code=502, detail="Mithu could not complete the request")
    if store.db is not None and cfg.mithu_store_conversations:
        now = datetime.now(timezone.utc)
        await store.db.sessions.update_one(
            {"session_id": session_id, "user_id": user.user_id, "tenant_id": user.tenant_id},
            {"$set": {"updated_at": now, "last_language": language},
             "$setOnInsert": {"created_at": now, "user_id": user.user_id,
                              "tenant_id": user.tenant_id, "session_id": session_id}},
            upsert=True,
        )
    return ChatResponse(session_id=session_id, answer=answer, language=language, tools_used=used)
