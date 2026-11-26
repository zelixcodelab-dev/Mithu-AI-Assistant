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
    mode: Literal["live_websocket"] = "live_websocket"
    note: str = "Voice input and output use the secured Live WebSocket bridge."
