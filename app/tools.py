import re
from app.educonnect import EduConnectReadClient
from app.security import UserContext


class ReadOnlyTools:
    def __init__(self, client: EduConnectReadClient | None = None):
        self.client = client or EduConnectReadClient()

    async def dispatch(self, name: str, args: dict, user: UserContext):
        if name == "list_colleges":
            return await self.client.get("/internal/ai/colleges", user)

        if name == "list_students":
            year = args.get("year")
            params = {"year": year} if year is not None else {}
            return await self.client.get("/internal/ai/students", user, params)

        if name == "list_leads":
            params = {
                key: value
                for key, value in {
                    "status": args.get("status"),
                    "year": args.get("year"),
                }.items()
                if value is not None
            }
            return await self.client.get("/internal/ai/leads", user, params)

        if name == "get_student":
            student_id = args["student_id"]
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", student_id):
                raise ValueError("Invalid student identifier")
            return await self.client.get(f"/internal/ai/students/{student_id}", user)

        raise ValueError("Unknown read-only tool")
