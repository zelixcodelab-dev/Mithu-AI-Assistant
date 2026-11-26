from __future__ import annotations

import base64
from typing import Any
import httpx

from app.config import get_settings


class ElevenLabsAdminError(RuntimeError):
    pass


class ElevenLabsAdminClient:
    """Server-only ElevenLabs administration client. The API key never reaches browser code."""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = "https://api.elevenlabs.io/v1"
        self.timeout = 20.0

    @property
    def agent_id(self):
        if not self.settings.elevenlabs_agent_id:
            raise ElevenLabsAdminError("ELEVENLABS_AGENT_ID is not configured on the Mithu server.")
        return self.settings.elevenlabs_agent_id

    def _headers(self):
        if not self.settings.elevenlabs_api_key:
            raise ElevenLabsAdminError("ELEVENLABS_API_KEY is not configured on the Mithu server.")
        return {"xi-api-key": self.settings.elevenlabs_api_key, "Content-Type": "application/json"}

    async def request(self, method: str, path: str, *, params=None, body=None):
        headers = self._headers()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method, self.base_url + path, headers=headers, params=params, json=body
                )
        except httpx.HTTPError as exc:
            raise ElevenLabsAdminError("Could not connect to ElevenLabs.") from exc
        if response.status_code >= 400:
            raise ElevenLabsAdminError(f"ElevenLabs API returned {response.status_code}")
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ElevenLabsAdminError("ElevenLabs returned an invalid response.") from exc

    async def get_agent(self):
        return await self.request("GET", f"/convai/agents/{self.agent_id}")

    async def list_conversations(self, **params):
        return await self.request("GET", "/convai/conversations", params={"agent_id": self.agent_id, **params})

    async def get_conversation(self, conversation_id: str):
        return await self.request("GET", f"/convai/conversations/{conversation_id}")

    async def update_metadata(self, *, name: str):
        return await self.request(
            "PATCH", f"/convai/agents/{self.agent_id}", body={"name": name}
        )

    async def update_behaviour(self, **kwargs):
        payload = {"agent": {k: v for k, v in kwargs.items() if v is not None}}
        return await self.request("PATCH", f"/convai/agents/{self.agent_id}", body=payload)

    async def update_prompt(self, **kwargs):
        payload = {"agent": {"prompt": {k: v for k, v in kwargs.items() if v is not None}}}
        return await self.request("PATCH", f"/convai/agents/{self.agent_id}", body=payload)

    async def update_conversation(self, **kwargs):
        payload = {"conversation": {k: v for k, v in kwargs.items() if v is not None}}
        return await self.request("PATCH", f"/convai/agents/{self.agent_id}", body=payload)

    async def update_voice(self, **kwargs):
        return await self.request(
            "PATCH", f"/convai/agents/{self.agent_id}", body={"tts": kwargs}
        )

    async def update_operations(self, **kwargs):
        return await self.request(
            "PATCH", f"/convai/agents/{self.agent_id}", body={"platform_settings": kwargs}
        )

    async def list_voices(self):
        result = await self.request("GET", "/voices")
        return result.get("voices", [])

    async def voice_preview(self, voice_id: str):
        # Generate preview audio server-side, then return a short-lived audio data URL.
        # The key is never sent to the browser. This uses a small fixed sample string.
        if not voice_id or len(voice_id) > 120:
            raise ElevenLabsAdminError("Invalid voice ID.")
        headers = self._headers()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/text-to-speech/{voice_id}",
                headers=headers,
                json={
                    "text": "Hello, I am Mithu. How can I help you today?",
                    "model_id": "eleven_turbo_v2_5",
                    "output_format": "mp3_44100_128",
                },
            )
        if response.status_code >= 400:
            raise ElevenLabsAdminError(f"ElevenLabs voice preview returned {response.status_code}")
        encoded = base64.b64encode(response.content).decode("ascii")
        return {"audio_url": f"data:audio/mpeg;base64,{encoded}"}
