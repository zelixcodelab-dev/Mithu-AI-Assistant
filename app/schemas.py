from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Language = Literal["ml", "manglish", "en", "auto"]

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=12000)
    session_id: str | None = Field(default=None, max_length=100)
    language: Language = "auto"

class ChatResponse(BaseModel):
    session_id: str
    answer: str
    language: str
    tools_used: list[str] = Field(default_factory=list)

class VoiceCapability(BaseModel):
    enabled: bool = False
    provider: Literal["elevenlabs"] = "elevenlabs"
    mode: Literal["realtime_conversational_ai"] = "realtime_conversational_ai"
    default_voice_style: str = "female"
    languages: list[str] = Field(default_factory=lambda: ["Malayalam", "Manglish", "English"])
    note: str = "Configure an ElevenLabs Conversational AI agent to enable live voice."

class VoiceSessionResponse(BaseModel):
    signed_url: str
    agent_id: str
    expires_in_seconds: int = 900
    server_location: str = "in-residency"
