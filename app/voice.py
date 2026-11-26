import asyncio
import json
import logging
from typing import Any

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect as websocket_connect

from app.config import get_settings
from app.security import verify_identity_assertion
from app.tools import ReadOnlyTools

log = logging.getLogger("mithu.voice")
router = APIRouter()
tools = ReadOnlyTools()

VOICE_PROTOCOL = "mithu.voice.v1"
VOICE_URL = "wss://api.openai.com/v1/live/sessions"

LIVE_TOOLS = [
    {
        "type": "function",
        "name": "list_colleges",
        "description": "Get the current college catalogue for the authenticated EduConnect workspace. The application backend applies tenant permissions and removes confidential revenue fields.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "list_students",
        "description": "List only student records that the authenticated user is permitted to see. The EduConnect backend enforces role, tenant, office and linked-client scope.",
        "parameters": {
            "type": "object",
            "properties": {"year": {"type": ["integer", "null"]}},
            "required": ["year"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "list_leads",
        "description": "List only leads visible to the authenticated user. Staff are limited to assigned leads; office admins to their office.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": ["string", "null"]},
                "year": {"type": ["integer", "null"]},
            },
            "required": ["status", "year"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_student",
        "description": "Fetch one student only if the EduConnect backend confirms that this caller can view the record.",
        "parameters": {
            "type": "object",
            "properties": {"student_id": {"type": "string"}},
            "required": ["student_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

ALLOWED_BROWSER_EVENTS = {
    "session.input_audio.append",
    "session.input_audio.commit",
    "session.input_audio.mute",
    "session.input_audio.unmute",
    "response.cancel",
}


def _session_configuration(cfg) -> dict[str, Any]:
    from app.voice_prompts import VOICE_SYSTEM_PROMPT

    responses = {
        "model": cfg.mithu_responses_model,
        "instructions": (
            "You are Mithu's private EduConnect data assistant. "
            "Use only the registered read-only functions for live workspace facts. "
            "Never guess. Never disclose fields returned by tools unless necessary "
            "for the caller's request. Respect every server authorization decision. "
            "If a tool fails or returns forbidden/not found, say that you could not "
            "retrieve the information. All data functions are read-only."
        ),
        "tools": LIVE_TOOLS if cfg.educonnect_api_enabled else [],
        "tool_choice": "auto" if cfg.educonnect_api_enabled else "none",
    }
    return {
        "model": cfg.mithu_live_model,
        "instructions": VOICE_SYSTEM_PROMPT,
        "audio": {
            "format": {"type": "audio/pcm", "rate": 24000},
            "input": {
                "transcription": {"model": "gpt-4o-mini-transcribe"},
                "turn_detection": {
                    "type": "server_vad",
                    "create_response": True,
                    "interrupt_response": True,
                },
            },
            "output": {"voice": cfg.mithu_live_voice},
        },
        "delegation": {
            "type": "responses",
            "responses": responses,
        },
    }


async def _send_json(socket, event: dict[str, Any]) -> None:
    await socket.send(json.dumps(event, ensure_ascii=False, separators=(",", ":")))


async def _run_tool_call(upstream, item: dict, user) -> None:
    call_id = item.get("call_id")
    name = item.get("name")
    raw_args = item.get("arguments") or "{}"

    try:
        args = json.loads(raw_args)
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be an object")
        result = await tools.dispatch(name, args, user)
        output = json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        log.warning("Voice tool failed name=%s user_id=%s error_type=%s", name, user.user_id, type(exc).__name__)
        output = json.dumps({
            "ok": False,
            "message": "The requested EduConnect information is currently unavailable or not permitted for this account.",
        })

    await _send_json(upstream, {
        "type": "response.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": output,
        },
    })
    await _send_json(upstream, {"type": "response.create"})


async def _forward_to_openai(browser: WebSocket, upstream) -> None:
    while True:
        message = await browser.receive_text()
        if len(message) > 180_000:
            await browser.send_json({"type": "mithu.error", "message": "Audio frame is too large."})
            continue
        try:
            event = json.loads(message)
        except json.JSONDecodeError:
            await browser.send_json({"type": "mithu.error", "message": "Invalid voice event."})
            continue
        if not isinstance(event, dict) or event.get("type") not in ALLOWED_BROWSER_EVENTS:
            await browser.send_json({"type": "mithu.error", "message": "That voice command is not allowed."})
            continue
        if event.get("type") == "session.input_audio.append":
            audio = event.get("audio")
            if not isinstance(audio, str) or len(audio) > 160_000:
                await browser.send_json({"type": "mithu.error", "message": "Invalid audio frame."})
                continue
        await _send_json(upstream, event)


async def _forward_from_openai(browser: WebSocket, upstream, user) -> None:
    while True:
        raw = await upstream.recv()
        event = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
        event_type = event.get("type")

        # Responses delegation events are handled on the trusted server.
        if event_type == "response.event":
            nested = event.get("event") or {}
            if nested.get("type") == "response.output_item.done":
                item = nested.get("item") or {}
                if item.get("type") == "function_call":
                    await _run_tool_call(upstream, item, user)
            # Do not disclose internal function arguments, results or tool traces.
            continue

        # Browser gets only Live voice events and transcripts, never tool internals.
        if event_type in {
            "session.started",
            "session.updated",
            "session.input_transcript.delta",
            "session.input_transcript.completed",
            "session.output_transcript.delta",
            "session.output_transcript.done",
            "session.output_audio.delta",
            "session.output_audio_transcript.delta",
            "session.output_audio_transcript.done",
            "session.output_audio.clear",
            "session.error",
            "session.closed",
            "error",
        }:
            await browser.send_json(event)
            if event_type in {"session.closed"}:
                return


@router.websocket("/api/v1/voice/ws")
async def mithu_voice_socket(websocket: WebSocket):
    cfg = get_settings()
    subprotocols = websocket.scope.get("subprotocols", [])
    assertion = next(
        (p[len("identity."):] for p in subprotocols if p.startswith("identity.")),
        None,
    )
    if not assertion:
        await websocket.close(code=4401, reason="Missing voice identity")
        return
    try:
        user = verify_identity_assertion(
            assertion,
            public_key_pem=cfg.identity_public_key_pem,
            issuer=cfg.identity_issuer,
            audience=cfg.identity_audience,
        )
    except (jwt.PyJWTError, ValueError):
        await websocket.close(code=4401, reason="Invalid voice identity")
        return

    if not cfg.openai_api_key:
        await websocket.close(code=1011, reason="Voice service is not configured")
        return

    await websocket.accept(subprotocol=VOICE_PROTOCOL)

    try:
        async with websocket_connect(
            VOICE_URL,
            additional_headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
            open_timeout=20,
            ping_interval=20,
            ping_timeout=20,
            max_size=8 * 1024 * 1024,
        ) as upstream:
            await _send_json(upstream, {
                "type": "session.start",
                "session": _session_configuration(cfg),
            })

            # Wait for a confirmed session start before accepting microphone frames.
            while True:
                raw = await asyncio.wait_for(upstream.recv(), timeout=25)
                event = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
                if event.get("type") == "session.started":
                    await websocket.send_json({"type": "mithu.ready"})
                    await websocket.send_json(event)
                    break
                if event.get("type") == "error":
                    await websocket.send_json({"type": "mithu.error", "message": "Mithu could not start the voice session."})
                    await websocket.close(code=1011)
                    return

            browser_task = asyncio.create_task(_forward_to_openai(websocket, upstream))
            openai_task = asyncio.create_task(_forward_from_openai(websocket, upstream, user))
            done, pending = await asyncio.wait(
                {browser_task, openai_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                exc = task.exception()
                if exc and not isinstance(exc, (WebSocketDisconnect, asyncio.CancelledError)):
                    log.warning("Voice bridge ended user_id=%s error_type=%s", user.user_id, type(exc).__name__)
            try:
                await _send_json(upstream, {"type": "session.close"})
            except Exception:
                pass
    except asyncio.TimeoutError:
        try:
            await websocket.send_json({"type": "mithu.error", "message": "Mithu voice session timed out while connecting."})
            await websocket.close(code=1011)
        except Exception:
            pass
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.exception("Voice websocket failed error_type=%s", type(exc).__name__)
        try:
            await websocket.send_json({"type": "mithu.error", "message": "Mithu voice connection was interrupted."})
            await websocket.close(code=1011)
        except Exception:
            pass
