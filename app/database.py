from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings


class MithuStore:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        cfg = get_settings()
        if not cfg.mithu_mongodb_uri:
            return

        self.client = AsyncIOMotorClient(
            cfg.mithu_mongodb_uri,
            serverSelectionTimeoutMS=3000,
        )
        self.db = self.client[cfg.mithu_database_name]
        await self.db.command("ping")
        await self.db.sessions.create_index("session_id", unique=True)
        await self.db.sessions.create_index([("user_id", 1), ("updated_at", -1)])

    async def close(self):
        if self.client:
            self.client.close()
        self.client = None
        self.db = None


store = MithuStore()
