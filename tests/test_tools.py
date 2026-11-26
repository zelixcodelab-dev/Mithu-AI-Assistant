import pytest
from app.tools import ReadOnlyTools
from app.security import UserContext


class FakeGateway:
    def __init__(self):
        self.calls = []

    async def get(self, path, user, params=None):
        self.calls.append((path, user.user_id, params or {}))
        return {"ok": True}


def make_user():
    return UserContext(
        user_id="user-1",
        tenant_id="tenant-1",
        scope="tenant",
        role="staff",
        office="HQ",
        permissions={},
        token_id="jti-1",
        identity_assertion="signed-assertion",
    )


@pytest.mark.asyncio
async def test_read_only_allowlist():
    gateway = FakeGateway()
    tools = ReadOnlyTools(gateway)
    user = make_user()
    await tools.dispatch("list_students", {"year": 2026}, user)
    await tools.dispatch("list_colleges", {}, user)
    assert gateway.calls == [
        ("/internal/ai/students", "user-1", {"year": 2026}),
        ("/internal/ai/colleges", "user-1", {}),
    ]


@pytest.mark.asyncio
async def test_write_tool_is_not_registered():
    tools = ReadOnlyTools(FakeGateway())
    with pytest.raises(ValueError):
        await tools.dispatch("delete_student", {"student_id": "student-1"}, make_user())


@pytest.mark.asyncio
async def test_student_id_rejects_path_characters():
    tools = ReadOnlyTools(FakeGateway())
    with pytest.raises(ValueError):
        await tools.dispatch("get_student", {"student_id": "../other"}, make_user())
