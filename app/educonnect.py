from typing import Any
import httpx
from app.config import get_settings
from app.security import UserContext


class EduConnectUnavailable(RuntimeError):
    pass


class EduConnectReadClient:
    """Calls the authenticated internal gateway; this service never connects to EduConnect MongoDB."""

    READ_PATHS = {
        "/internal/ai/colleges",
        "/internal/ai/students",
        "/internal/ai/leads",
    }

    def __init__(self):
        self.settings = get_settings()

    async def get(
        self,
        path: str,
        user: UserContext,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if not self.settings.educonnect_api_enabled:
            raise EduConnectUnavailable("Live EduConnect tools are not enabled.")
        if not self.settings.educonnect_internal_api_url or not self.settings.educonnect_service_token:
            raise EduConnectUnavailable("EduConnect gateway is not configured.")

        allowed = path in self.READ_PATHS or (
            path.startswith("/internal/ai/students/") and path.count("/") == 4
        )
        if not allowed or ".." in path:
            raise ValueError("Internal read endpoint is not allow-listed.")

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.settings.educonnect_internal_api_url.rstrip('/')}{path}",
                params=params or {},
                headers={
                    "Authorization": f"Bearer {self.settings.educonnect_service_token}",
                    # The main app must validate this signature itself. It must not
                    # trust unsigned X-Mithu-Role / X-Mithu-Tenant headers.
                    "X-Mithu-Identity": user.identity_assertion,
                },
            )
            response.raise_for_status()
            return response.json()
