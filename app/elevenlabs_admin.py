from __future__ import annotations

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
        return self.settings.elevenlabs_agent_id

    def _headers(self):
        if not self.settings.elevenlabs_api_key:
            raise ElevenLabsAdminError("ELEVENLABS_API_KEY is not configured on the Mithu server.")
        return {"xi-api-key": self.settings.elevenlabs_api_key, "Content-Type": "application/json"}

    async def request(self, method: str, path: str, *, params=None, body=None):
        headers = self._headers()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, self.base_url + path, headers=headers, params=params, json=body)
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
        return await self.request("PATCH", f"/convai/agents/{self.agent_id}", body={"name": name})

    async def update_behaviour(self, **kwargs):
        payload = {k: v for k, v in kwargs.items() if v is not None}
        return await self.request("PATCH", f"/convai/agents/{self.agent_id}/settings", body={"agent": payload})

    async def update_prompt(self, **kwargs):
        payload = {k: v for k, v in kwargs.items() if v is not None}
        return await self.request("PATCH", f"/convai/agents/{self.agent_id}/settings", body={"prompt": payload})

    async def update_conversation(self, **kwargs):
        payload = {k: v for k, v in kwargs.items() if v is not None}
        return await self.request("PATCH", f"/convai/agents/{self.agent_id}/settings", body={"conversation": payload})

    async def update_voice(self, **kwargs):
        return await self.request("PATCH", f"/convai/agents/{self.agent_id}/settings", body={"tts": kwargs})

    async def update_operations(self, **kwargs):
        return await self.request("PATCH", f"/convai/agents/{self.agent_id}/settings", body={"platform_settings": kwargs})

    async def list_voices(self):
        result = await self.request("GET", "/voices")
        return result.get("voices", [])

    async def voice_preview(self, voice_id: str):
        # Use the TTS endpoint to create a very short preview on demand.
        # Preview speech is intentionally not generated until the user presses play.
        result = await self.request("POST", f"/text-to-speech/{voice_id}", body={
            "text": "Hello, I am Mithu. How can I help you today?",
            "model_id": "eleven_turbo_v2_5",
        })
        return result
