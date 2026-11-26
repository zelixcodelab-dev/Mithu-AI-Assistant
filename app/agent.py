import json
from openai import AsyncOpenAI
from app.config import get_settings
from app.prompts import SYSTEM_PROMPT
from app.security import UserContext
from app.tools import ReadOnlyTools


TOOLS = [
    {
        "type": "function",
        "name": "list_colleges",
        "description": "List colleges available in the caller's EduConnect tenant. Confidential fields are removed by the application backend.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "list_students",
        "description": "List only students visible to the authenticated caller; backend enforces tenant, office and linked-client visibility.",
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
        "description": "List leads visible to caller. Staff see assigned leads; office admins see their office; super admins see tenant-wide results.",
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
        "description": "Fetch one student only after the EduConnect backend checks visibility for this caller.",
        "parameters": {
            "type": "object",
            "properties": {"student_id": {"type": "string"}},
            "required": ["student_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


class MithuAgent:
    def __init__(self, tools: ReadOnlyTools | None = None):
        cfg = get_settings()
        self.model = cfg.openai_model
        self.client = AsyncOpenAI(api_key=cfg.openai_api_key) if cfg.openai_api_key else None
        self.tools = tools or ReadOnlyTools()

    async def respond(self, message: str, user: UserContext, language: str):
        if not self.client:
            return (
                "Mithu AI is not configured yet. Please set the server-side OpenAI API key.",
                [],
            )

        instructions = f"{SYSTEM_PROMPT}\nReply in {language}."
        response = await self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=message,
            tools=TOOLS,
        )

        used = []
        for _ in range(4):
            calls = [
                item for item in response.output
                if getattr(item, "type", None) == "function_call"
            ]
            if not calls:
                return (
                    response.output_text or "I couldn't prepare a response. Please try again.",
                    used,
                )

            outputs = []
            for call in calls:
                args = json.loads(call.arguments or "{}")
                result = await self.tools.dispatch(call.name, args, user)
                used.append(call.name)
                outputs.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result, ensure_ascii=False, default=str),
                })

            response = await self.client.responses.create(
                model=self.model,
                instructions=instructions,
                previous_response_id=response.id,
                input=outputs,
                tools=TOOLS,
            )

        return "I couldn't complete that request safely. Please try a smaller question.", used
