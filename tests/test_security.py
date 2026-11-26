from datetime import datetime, timedelta, timezone
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from app.security import verify_identity_assertion


def make_keys():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private, public


def make_token(private, **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "iss": "educonnect-pro",
        "aud": "mithu-ai",
        "sub": "user-1",
        "scope": "tenant",
        "tenant_id": "tenant-1",
        "role": "office_admin",
        "office": "HQ",
        "permissions": {"students": "view"},
        "iat": now,
        "exp": now + timedelta(seconds=90),
        "jti": "assertion-1",
    }
    claims.update(overrides)
    return jwt.encode(claims, private, algorithm="EdDSA")


def test_valid_tenant_identity():
    private, public = make_keys()
    token = make_token(private)
    ctx = verify_identity_assertion(
        token,
        public_key_pem=public,
        issuer="educonnect-pro",
        audience="mithu-ai",
    )
    assert (ctx.user_id, ctx.tenant_id, ctx.role) == ("user-1", "tenant-1", "office_admin")
    assert ctx.identity_assertion == token


def test_invalid_signature_is_rejected():
    _, public = make_keys()
    other, _ = make_keys()
    token = make_token(other)
    with pytest.raises(jwt.InvalidTokenError):
        verify_identity_assertion(
            token,
            public_key_pem=public,
            issuer="educonnect-pro",
            audience="mithu-ai",
        )


def test_missing_tenant_is_rejected():
    private, public = make_keys()
    token = make_token(private, tenant_id=None)
    with pytest.raises(ValueError):
        verify_identity_assertion(
            token,
            public_key_pem=public,
            issuer="educonnect-pro",
            audience="mithu-ai",
        )


def test_assertion_lifetime_over_120_seconds_is_rejected():
    private, public = make_keys()
    now = datetime.now(timezone.utc)
    token = make_token(private, iat=now, exp=now + timedelta(minutes=3))
    with pytest.raises(ValueError):
        verify_identity_assertion(
            token,
            public_key_pem=public,
            issuer="educonnect-pro",
            audience="mithu-ai",
        )
