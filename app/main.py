from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4
import logging

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import store
from app.schemas import ChatRequest, ChatResponse, VoiceCapability
from app.security import UserContext, require_user_context
from app.agent import MithuAgent
from app.language import detect_language
from app.educonnect import EduConnectUnavailable
from app.voice import router as voice_router

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


app = FastAPI(title="Mithu AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Mithu-Identity"],
)
agent = MithuAgent()
app.include_router(voice_router)


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
    return VoiceCapability(
        enabled=bool(cfg.openai_api_key and cfg.identity_public_key_pem),
        mode="live_websocket",
        note="Mithu Live voice uses a secured server-side WebSocket bridge." if cfg.openai_api_key and cfg.identity_public_key_pem else "Voice is not configured: OpenAI key and identity verification key are required.",
    )


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    user: UserContext = Depends(require_user_context),
):
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
            {
                "session_id": session_id,
                "user_id": user.user_id,
                "tenant_id": user.tenant_id,
            },
            {
                "$set": {"updated_at": now, "last_language": language},
                "$setOnInsert": {
                    "created_at": now,
                    "user_id": user.user_id,
                    "tenant_id": user.tenant_id,
                    "session_id": session_id,
                },
            },
            upsert=True,
        )

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        language=language,
        tools_used=used,
    )
