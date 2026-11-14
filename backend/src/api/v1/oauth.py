"""OAuth authorization code + PKCE with one-use, browser-bound login tickets."""

import base64
import hashlib
import json
import secrets
from typing import Annotated, Literal
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.core.database import get_db_session
from src.core.exceptions import AuthenticationError, ConflictException, ValidationException
from src.core.redis import get_redis
from src.models.auth import MemberStatus, OAuthIdentity
from src.repositories.user_repo import UserRepository
from src.schemas.auth import UserRegisterRequest
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth/oauth", tags=["Authentication"])
Provider = Literal["google", "github"]
DB = Annotated[AsyncSession, Depends(get_db_session)]


def provider_config(provider):
    if provider == "google":
        return (
            settings.GOOGLE_CLIENT_ID,
            settings.GOOGLE_CLIENT_SECRET,
            "https://accounts.google.com/o/oauth2/v2/auth",
            "https://oauth2.googleapis.com/token",
            "openid email profile",
        )
    return (
        settings.GITHUB_CLIENT_ID,
        settings.GITHUB_CLIENT_SECRET,
        "https://github.com/login/oauth/authorize",
        "https://github.com/login/oauth/access_token",
        "read:user user:email",
    )


@router.get("/providers")
async def providers():
    return [p for p in ("google", "github") if all(provider_config(p)[:2])]


@router.get("/{provider}/start")
async def start(provider: Provider):
    client_id, secret, authorize, _, scope = provider_config(provider)
    if not client_id or not secret:
        raise ValidationException("This sign-in provider is not configured")
    state, verifier, browser = (secrets.token_urlsafe(32) for _ in range(3))
    redis = await get_redis()
    await redis.set(
        f"oauth:state:{state}",
        json.dumps({"provider": provider, "verifier": verifier, "browser": browser}),
        ex=600,
    )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    redirect_uri = f"{settings.OAUTH_PUBLIC_BASE_URL}/auth/oauth/{provider}/callback"
    response = RedirectResponse(
        authorize
        + "?"
        + urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": scope,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        ),
        status_code=302,
    )
    response.set_cookie(
        "stride_oauth_browser",
        browser,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=600,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


async def fetch_identity(provider, code, verifier):
    client_id, secret, _, token_url, _ = provider_config(provider)
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            token_url,
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": secret,
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
                "redirect_uri": f"{settings.OAUTH_PUBLIC_BASE_URL}/auth/oauth/{provider}/callback",
            },
        )
        response.raise_for_status()
        access = response.json().get("access_token")
        if not access:
            raise AuthenticationError("Provider did not authorize sign-in")
        headers = {"Authorization": f"Bearer {access}", "Accept": "application/json"}
        if provider == "google":
            response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo", headers=headers
            )
            response.raise_for_status()
            info = response.json()
            if not info.get("email_verified"):
                raise AuthenticationError("A verified email is required")
            return str(info["sub"]), info["email"], info.get("name") or "Google User"
        response = await client.get("https://api.github.com/user", headers=headers)
        response.raise_for_status()
        info = response.json()
        response = await client.get("https://api.github.com/user/emails", headers=headers)
        response.raise_for_status()
        email = next(
            (e["email"] for e in response.json() if e.get("primary") and e.get("verified")), None
        )
        if not email:
            raise AuthenticationError("A verified primary email is required")
        return str(info["id"]), email, info.get("name") or info["login"]


@router.get("/{provider}/callback")
async def callback(
    provider: Provider, request: Request, db: DB, state: str = "", code: str = "", error: str = ""
):
    redis = await get_redis()
    raw = await redis.getdel(f"oauth:state:{state}")
    data = json.loads(raw) if raw else {}
    cookie = request.cookies.get("stride_oauth_browser", "")
    if (
        not data
        or data.get("provider") != provider
        or not secrets.compare_digest(data.get("browser", ""), cookie)
    ):
        raise AuthenticationError("Invalid or expired sign-in state")
    if error or not code:
        raise AuthenticationError("Sign-in was canceled by the provider")
    try:
        subject, email, name = await fetch_identity(provider, code, data["verifier"])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise AuthenticationError("Sign-in provider is unavailable") from exc
    identity = await db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == provider, OAuthIdentity.subject == subject
        )
    )
    repo = UserRepository(db)
    if identity:
        user = await repo.get_by_id(identity.user_id)
        if not user or not user.is_active:
            raise AuthenticationError("Account is inactive")
    else:
        if await repo.get_by_email(email):
            raise ConflictException(
                "An account already uses this email. Sign in with its password; provider accounts are not automatically linked."
            )
        profile, _ = await AuthService(db).register(
            UserRegisterRequest(
                email=email, password=secrets.token_urlsafe(48), full_name=name[:255]
            )
        )
        user = await repo.get_by_id(profile.id)
        db.add(OAuthIdentity(provider=provider, subject=subject, user_id=user.id))
        await db.flush()
    # Commit identity and account before issuing a ticket consumable by another request.
    await db.commit()
    ticket = secrets.token_urlsafe(32)
    await redis.set(
        f"oauth:ticket:{ticket}", json.dumps({"user_id": user.id, "browser": cookie}), ex=60
    )
    response = RedirectResponse(
        settings.WEB_BASE_URL.rstrip("/") + "/#oauth_ticket=" + ticket, status_code=302
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


class Exchange(BaseModel):
    ticket: str = Field(min_length=20, max_length=200)


@router.post("/exchange")
async def exchange(payload: Exchange, request: Request, db: DB):
    redis = await get_redis()
    raw = await redis.getdel(f"oauth:ticket:{payload.ticket}")
    data = json.loads(raw) if raw else {}
    if not data or not secrets.compare_digest(
        data.get("browser", ""), request.cookies.get("stride_oauth_browser", "")
    ):
        raise AuthenticationError("Invalid or expired login ticket")
    user = await UserRepository(db).get_by_id(data["user_id"])
    if not user or not user.is_active:
        raise AuthenticationError("Account is inactive")
    active = [m for m in user.memberships if m.status == MemberStatus.ACTIVE]
    return await AuthService(db)._generate_token_pair(
        user,
        active_org_id=active[0].org_id if active else None,
        role=active[0].role if active else None,
    )
