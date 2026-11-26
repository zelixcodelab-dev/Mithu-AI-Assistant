from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.security import UserContext, require_user_context
from app.database import store
from app.elevenlabs_admin import ElevenLabsAdminClient, ElevenLabsAdminError

router = APIRouter(prefix="/api/v1/admin", tags=["command-center"])
client = ElevenLabsAdminClient()


def require_admin(user: UserContext = Depends(require_user_context)) -> UserContext:
    # Platform-level role is required to administer global Mithu configuration.
    if user.scope != "platform" or user.role not in {"platform_owner", "platform_admin"}:
        raise HTTPException(status_code=403, detail="Command Center administrator access required")
    return user


def map_elevenlabs_error(exc: ElevenLabsAdminError):
    raise HTTPException(status_code=502, detail="ElevenLabs administration request failed") from exc


def db_required():
    if store.db is None:
        raise HTTPException(status_code=503, detail="Mithu metadata database is not configured")


class AgentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=100)
    first_message: str | None = Field(default=None, max_length=2000)
    language: str | None = Field(default=None, max_length=10)
    llm: str | None = Field(default=None, max_length=100)
    prompt: str | None = Field(default=None, max_length=20000)
    temperature: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)
    allow_interruptions: bool | None = None
    hinglish_mode: bool | None = None
    monitoring_enabled: bool | None = None
    max_duration_seconds: int | None = Field(default=None, ge=60, le=7200)
    record_voice: bool | None = None
    require_auth: bool | None = None
    retention_days: int | None = Field(default=None, ge=-1, le=3650)


class VoicePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice_id: str = Field(min_length=1, max_length=120)
    stability: float = Field(ge=0, le=1)
    similarity_boost: float = Field(ge=0, le=1)
    speed: float = Field(ge=.7, le=1.2)


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)
    category: str = Field(pattern="^(preference|fact|instruction)$")
    context: str = Field(pattern="^(personal|business)$")


class PermissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permission: str = Field(min_length=1, max_length=80)
    decision: str = Field(pattern="^(allow|approval|deny)$")


class PermissionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: str = Field(pattern="^(personal|business)$")
    permissions: list[PermissionInput] = Field(max_length=30)


def agent_id_from_config() -> str:
    return client.agent_id


@router.get("/overview")
async def overview(_: UserContext = Depends(require_admin)):
    try:
        config = await client.get_agent()
        conversations = await client.list_conversations(page_size=100)
        items = conversations.get("conversations", [])
        successful = sum(1 for item in items if item.get("call_successful") == "success")
        duration = [int(item.get("call_duration_secs") or 0) for item in items]
        cost = sum(float(item.get("cost_fiat") or 0) for item in items)
        return {
            "agent": {
                "agent_id": config.get("agent_id"),
                "name": config.get("name"),
                "language": (config.get("conversation_config") or {}).get("agent", {}).get("language"),
            },
            "stats": {
                "conversations": len(items),
                "success_rate": 100 * successful / len(items) if items else 0,
                "average_duration_secs": sum(duration) / len(duration) if duration else 0,
                "total_cost_usd": cost,
            },
            "services": {"api": True},
        }
    except ElevenLabsAdminError as exc:
        map_elevenlabs_error(exc)


@router.get("/agent")
async def get_agent(_: UserContext = Depends(require_admin)):
    try:
        c = await client.get_agent()
        cc = c.get("conversation_config") or {}
        a = cc.get("agent") or {}
        prompt = a.get("prompt") or {}
        privacy = c.get("platform_settings", {}).get("privacy") or {}
        return {
            "agent_id": c.get("agent_id"),
            "name": c.get("name"),
            "language": a.get("language"),
            "first_message": a.get("first_message"),
            "llm": prompt.get("llm"),
            "prompt": prompt.get("prompt"),
            "temperature": prompt.get("temperature", 0),
            "monitoring_enabled": cc.get("conversation", {}).get("monitoring_enabled", False),
            "max_duration_seconds": cc.get("conversation", {}).get("max_duration_seconds", 600),
            "record_voice": privacy.get("record_voice", True),
            "retention_days": privacy.get("retention_days", -1),
            "require_auth": c.get("auth", {}).get("enable_auth", False),
            "branch_id": c.get("branch_id"),
            "version_id": c.get("version_id"),
        }
    except ElevenLabsAdminError as exc:
        map_elevenlabs_error(exc)


@router.patch("/agent")
async def patch_agent(body: AgentPatch, _: UserContext = Depends(require_admin)):
    values = body.model_dump(exclude_none=True)
    try:
        if "name" in values:
            await client.update_metadata(name=values.pop("name"))
        if any(k in values for k in ("first_message", "language", "allow_interruptions", "hinglish_mode")):
            await client.update_behaviour(
                first_message=values.pop("first_message", None),
                language=values.pop("language", None),
                disable_first_message_interruptions=None if "allow_interruptions" not in values else not values.pop("allow_interruptions"),
                hinglish_mode=values.pop("hinglish_mode", None),
            )
        prompt_fields = {k: values.pop(k) for k in list(values) if k in {"llm", "prompt", "temperature", "max_tokens"}}
        if prompt_fields:
            await client.update_prompt(**prompt_fields)
        conversation_fields = {k: values.pop(k) for k in list(values) if k in {"monitoring_enabled", "max_duration_seconds"}}
        if conversation_fields:
            await client.update_conversation(**conversation_fields)
        privacy_fields = {k: values.pop(k) for k in list(values) if k in {"record_voice", "retention_days"}}
        operation_fields = {}
        if "require_auth" in values:
            operation_fields["auth"] = {"enable_auth": values.pop("require_auth")}
        if privacy_fields or operation_fields:
            await client.update_operations(privacy=privacy_fields or None, **operation_fields)
        return {"saved": True, "note": "ElevenLabs changes publish a new version or draft according to the workspace API."}
    except ElevenLabsAdminError as exc:
        map_elevenlabs_error(exc)


@router.patch("/agent/voice")
async def patch_voice(body: VoicePatch, _: UserContext = Depends(require_admin)):
    try:
        await client.update_voice(
            voice_id=body.voice_id,
            stability=body.stability,
            similarity_boost=body.similarity_boost,
            speed=body.speed,
        )
        return {"saved": True}
    except ElevenLabsAdminError as exc:
        map_elevenlabs_error(exc)


@router.get("/voices")
async def voices(_: UserContext = Depends(require_admin)):
    try:
        results = await client.list_voices()
        return {"voices": results}
    except ElevenLabsAdminError as exc:
        map_elevenlabs_error(exc)


@router.get("/voices/{voice_id}/preview")
async def voice_preview(voice_id: str, _: UserContext = Depends(require_admin)):
    try:
        return await client.voice_preview(voice_id)
    except ElevenLabsAdminError as exc:
        map_elevenlabs_error(exc)


@router.get("/conversations")
async def conversations(_: UserContext = Depends(require_admin)):
    try:
        result = await client.list_conversations(page_size=100, summary_mode="include")
        rows = []
        for c in result.get("conversations", []):
            rows.append({
                "conversation_id": c.get("conversation_id"),
                "title": c.get("call_summary_title") or "Conversation",
                "language": c.get("main_language"),
                "duration_secs": c.get("call_duration_secs", 0),
                "call_successful": c.get("call_successful"),
                "cost_usd": c.get("cost_fiat"),
                "start_time": c.get("start_time_unix_secs"),
            })
        return {"conversations": rows}
    except ElevenLabsAdminError as exc:
        map_elevenlabs_error(exc)


@router.get("/conversations/{conversation_id}")
async def conversation_detail(conversation_id: str, _: UserContext = Depends(require_admin)):
    try:
        c = await client.get_conversation(conversation_id)
        meta = c.get("metadata") or {}
        return {
            "conversation_id": conversation_id,
            "title": c.get("analysis", {}).get("call_summary_title"),
            "language": meta.get("main_language"),
            "duration_secs": meta.get("call_duration_secs", 0),
            "call_successful": c.get("analysis", {}).get("call_successful"),
            "transcript": c.get("transcript", []),
        }
    except ElevenLabsAdminError as exc:
        map_elevenlabs_error(exc)


@router.get("/usage")
async def usage(_: UserContext = Depends(require_admin)):
    try:
        result = await client.list_conversations(page_size=100)
        rows = result.get("conversations", [])
        return {
            "account_balance": None,
            "account_balance_note": "The account-level credit balance is not available in the connected agent API.",
            "conversation_cost_usd": sum(float(c.get("cost_fiat") or 0) for c in rows),
            "conversation_count": len(rows),
        }
    except ElevenLabsAdminError as exc:
        map_elevenlabs_error(exc)


@router.get("/memories")
async def memories(context: str = Query(pattern="^(personal|business)$"), user: UserContext = Depends(require_admin)):
    db_required()
    cursor = store.db.memories.find({"context": context}).sort("updated_at", -1).limit(300)
    return {"memories": [{**m, "id": str(m.pop("_id"))} async for m in cursor]}


@router.post("/memories", status_code=201)
async def add_memory(body: MemoryInput, user: UserContext = Depends(require_admin)):
    db_required()
    now = datetime.now(timezone.utc)
    doc = {**body.model_dump(), "created_at": now, "updated_at": now, "created_by": user.user_id}
    result = await store.db.memories.insert_one(doc)
    return {"id": str(result.inserted_id), **body.model_dump()}


@router.patch("/memories/{memory_id}")
async def update_memory(memory_id: str, body: MemoryInput, _: UserContext = Depends(require_admin)):
    db_required()
    from bson import ObjectId
    if not ObjectId.is_valid(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    result = await store.db.memories.update_one({"_id": ObjectId(memory_id)}, {"$set": {**body.model_dump(), "updated_at": datetime.now(timezone.utc)}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"id": memory_id, **body.model_dump()}


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, _: UserContext = Depends(require_admin)):
    db_required()
    from bson import ObjectId
    if not ObjectId.is_valid(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    result = await store.db.memories.delete_one({"_id": ObjectId(memory_id)})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Memory not found")
    return None


@router.get("/permissions")
async def get_permissions(_: UserContext = Depends(require_admin)):
    db_required()
    rows = await store.db.permission_policies.find({}).to_list(100)
    for row in rows:
        row["id"] = str(row.pop("_id"))
    result = {"personal": [], "business": []}
    for row in rows:
        result[row["context"]] = row.get("permissions", [])
    return {"permissions": result}


@router.put("/permissions")
async def put_permissions(body: PermissionUpdate, user: UserContext = Depends(require_admin)):
    db_required()
    now = datetime.now(timezone.utc)
    await store.db.permission_policies.update_one(
        {"context": body.context},
        {"$set": {"permissions": [p.model_dump() for p in body.permissions], "updated_at": now, "updated_by": user.user_id}},
        upsert=True,
    )
    return {"saved": True, "context": body.context}


@router.post("/monitoring/session")
async def monitoring_session(_: UserContext = Depends(require_admin)):
    # A signed URL is deliberately not fabricated. A token-exchange endpoint must
    # be added to ElevenLabsAdminClient when the workspace grants that API scope.
    raise HTTPException(status_code=501, detail="Signed live-monitor session creation is not enabled in this connector.")
