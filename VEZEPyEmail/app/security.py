from __future__ import annotations
import os
from typing import List, Optional, Dict, Any
from fastapi import Header, HTTPException
from authlib.jose import JsonWebToken


def _fail(detail: str, code: int = 401):
    raise HTTPException(status_code=code, detail=detail)


def _parse_bearer(authorization: Optional[str], access_token: Optional[str]) -> str:
    if access_token:
        return access_token
    if not authorization:
        _fail("Missing Authorization header or access_token")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        _fail("Invalid Authorization header")
    return parts[1]


def _verify_jwt(token: str) -> Dict[str, Any]:
    # Demo bypass for local/dev/CI
    if token == "demo" or os.getenv("VEZE_JWT_DEMO") == "1":
        return {
            "iss": os.getenv("VEZE_JWT_ISS", "https://auth.local/"),
            "aud": os.getenv("VEZE_EMAIL_AUD", "veze-email"),
            "sub": "demo-user",
            "scope": "email.read game.read_mail",
        }

    secret = os.getenv("VEZE_JWT_SECRET")
    if not secret:
        _fail("JWT secret not configured (VEZE_JWT_SECRET)")
    iss = os.getenv("VEZE_JWT_ISS", "https://auth.local/")
    aud = os.getenv("VEZE_EMAIL_AUD", "veze-email")

    jwt = JsonWebToken(["HS256"])  # symmetric demo
    try:
        claims = jwt.decode(token, secret)
        claims.validate()
    except Exception as e:
        _fail(f"Invalid token: {e}")

    if claims.get("iss") != iss:
        _fail("Invalid issuer", 403)
    # aud may be single or list
    claim_aud = claims.get("aud")
    if isinstance(claim_aud, list):
        if aud not in claim_aud:
            _fail("Invalid audience", 403)
    elif claim_aud != aud:
        _fail("Invalid audience", 403)
    return dict(claims)


def _has_scopes(claims: Dict[str, Any], required: List[str]) -> bool:
    scopes: List[str] = []
    if "scope" in claims and isinstance(claims["scope"], str):
        scopes = claims["scope"].split()
    elif "scp" in claims and isinstance(claims["scp"], list):
        scopes = claims["scp"]
    return all(s in scopes for s in required)


def require_scopes(required: List[str]):
    async def _dependency(
        authorization: Optional[str] = Header(None),
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        token = _parse_bearer(authorization, access_token)
        claims = _verify_jwt(token)
        if not _has_scopes(claims, required):
            _fail("Insufficient scope", 403)
        return claims

    return _dependency
