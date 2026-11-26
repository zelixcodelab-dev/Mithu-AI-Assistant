from dataclasses import dataclass
from typing import Any
import jwt
from fastapi import Header, HTTPException
from app.config import get_settings


@dataclass(frozen=True)
class UserContext:
    user_id: str
    tenant_id: str | None
    scope: str
    role: str
    office: str | None
    permissions: dict[str, Any]
    token_id: str
    identity_assertion: str


def verify_identity_assertion(
    assertion: str,
    *,
    public_key_pem: str,
    issuer: str,
    audience: str,
) -> UserContext:
    if not public_key_pem.strip():
        raise ValueError("Identity verification is not configured")

    claims = jwt.decode(
        assertion,
        public_key_pem,
        algorithms=["EdDSA"],
        issuer=issuer,
        audience=audience,
        options={"require": ["iss", "aud", "sub", "iat", "exp", "jti"]},
        leeway=5,
    )

    issued_at = int(claims["iat"])
    expires_at = int(claims["exp"])
    if expires_at <= issued_at or expires_at - issued_at > 120:
        raise ValueError("Identity assertion lifetime must be 120 seconds or less")

    scope = claims.get("scope")
    if scope not in {"tenant", "platform"}:
        raise ValueError("Unsupported identity scope")

    if scope == "tenant":
        if not claims.get("tenant_id"):
            raise ValueError("Tenant identity is missing tenant_id")
        if claims.get("role") not in {"super_admin", "office_admin", "user", "staff"}:
            raise ValueError("Unsupported tenant role")
    elif claims.get("role") not in {
        "platform_owner", "platform_admin", "developer", "support", "viewer"
    }:
        raise ValueError("Unsupported platform role")

    permissions = claims.get("permissions") or {}
    if not isinstance(permissions, dict):
        raise ValueError("Invalid permission claims")

    return UserContext(
        user_id=str(claims["sub"]),
        tenant_id=str(claims["tenant_id"]) if claims.get("tenant_id") else None,
        scope=scope,
        role=str(claims["role"]),
        office=str(claims["office"]) if claims.get("office") else None,
        permissions=permissions,
        token_id=str(claims["jti"]),
        identity_assertion=assertion,
    )


async def require_user_context(
    x_mithu_identity: str | None = Header(default=None, alias="X-Mithu-Identity"),
) -> UserContext:
    cfg = get_settings()
    if not x_mithu_identity:
        raise HTTPException(status_code=401, detail="Missing authenticated identity")

    try:
        return verify_identity_assertion(
            x_mithu_identity,
            public_key_pem=cfg.identity_public_key_pem,
            issuer=cfg.identity_issuer,
            audience=cfg.identity_audience,
        )
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid authenticated identity") from exc
