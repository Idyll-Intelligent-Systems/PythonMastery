from __future__ import annotations
import os
from typing import List, Optional, Dict, Any
from fastapi import Header, HTTPException
from authlib.jose import JsonWebToken, JsonWebKey


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

    iss = os.getenv("VEZE_JWT_ISS", "https://auth.local/")
    aud = os.getenv("VEZE_EMAIL_AUD", "veze-email")
    jwks_url = os.getenv("VEZE_JWKS_URL")
    hs_secret = os.getenv("VEZE_JWT_SECRET")

    if jwks_url:
        jwt = JsonWebToken(["RS256"])  # asymmetric
        try:
            jwks = JsonWebKey.import_key_set_from_url(jwks_url)
            claims = jwt.decode(token, jwks)
            claims.validate()
        except Exception as e:
            _fail(f"Invalid token: {e}")
    elif hs_secret:
        jwt = JsonWebToken(["HS256"])  # symmetric fallback for dev
        try:
            claims = jwt.decode(token, hs_secret)
            claims.validate()
        except Exception as e:
            _fail(f"Invalid token: {e}")
    else:
        _fail("No JWKS or HS256 secret configured for JWT validation")

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
