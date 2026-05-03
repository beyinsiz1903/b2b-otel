import hashlib
import hmac
from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.db import db


def pms_hash_key(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def pms_constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


async def pms_auth_by_api_key(authorization: Optional[str]) -> Dict[str, Any]:
    """PMS sistemi için Bearer API key doğrulaması."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token gerekli")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Geçersiz token")
    token_hash = pms_hash_key(token)
    integ = await db.pms_integrations.find_one({"api_key_hash": token_hash, "status": "active"})
    if not integ:
        raise HTTPException(status_code=401, detail="Geçersiz veya pasif API anahtarı")
    return integ


def pms_verify_hmac(secret: str, body_bytes: bytes, signature_header: Optional[str]) -> None:
    """X-CapX-Signature: sha256=<hex> formatını doğrula."""
    if not signature_header:
        raise HTTPException(status_code=401, detail="X-CapX-Signature header eksik")
    sig = signature_header.strip()
    if sig.startswith("sha256="):
        sig = sig[len("sha256="):]
    expected = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    if not pms_constant_time_eq(expected, sig):
        raise HTTPException(status_code=401, detail="İmza doğrulanamadı")
