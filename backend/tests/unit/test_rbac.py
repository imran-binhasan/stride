"""Unit tests for password hashing, JWT encoding/decoding, and RBAC hierarchy."""

import pytest
from src.core.exceptions import AuthenticationError
from src.core.rbac import AuthContext
from src.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from src.models.auth import OrgRole, User


def test_password_hashing():
    raw_pass = "SuperSecretPassword123!"
    hashed = hash_password(raw_pass)
    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_lifecycle():
    user_id = "user-12345"
    claims = {"email": "dev@a3zen.io", "role": "ORG_ADMIN"}
    token = create_access_token(subject=user_id, claims=claims)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["email"] == "dev@a3zen.io"
    assert payload["role"] == "ORG_ADMIN"


def test_invalid_jwt_raises_error():
    with pytest.raises(AuthenticationError):
        decode_access_token("invalid.bearer.token")


def test_refresh_token_entropy():
    rt1 = generate_refresh_token()
    rt2 = generate_refresh_token()
    assert len(rt1) >= 48
    assert rt1 != rt2


def test_rbac_hierarchy_checks():
    user = User(id="u1", email="test@test.com", full_name="Test User", hashed_password="x")

    # Org Owner has access to all min_roles
    owner_ctx = AuthContext(user=user, org_id="org1", role=OrgRole.ORG_OWNER)
    assert owner_ctx.has_min_role(OrgRole.ORG_OWNER) is True
    assert owner_ctx.has_min_role(OrgRole.ORG_ADMIN) is True
    assert owner_ctx.has_min_role(OrgRole.PROJECT_MANAGER) is True
    assert owner_ctx.has_min_role(OrgRole.MEMBER) is True

    # Member cannot act as Project Manager or Admin
    member_ctx = AuthContext(user=user, org_id="org1", role=OrgRole.MEMBER)
    assert member_ctx.has_min_role(OrgRole.MEMBER) is True
    assert member_ctx.has_min_role(OrgRole.PROJECT_MANAGER) is False
    assert member_ctx.has_min_role(OrgRole.ORG_ADMIN) is False
    assert member_ctx.has_min_role(OrgRole.ORG_OWNER) is False

    # SuperAdmin bypasses any role restrictions
    super_ctx = AuthContext(user=user, org_id="org1", role=None, is_superadmin=True)
    assert super_ctx.has_min_role(OrgRole.ORG_OWNER) is True
