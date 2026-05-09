"""
Auth — single-password protection.

Token: HMAC-SHA256 over expiry timestamp, signed with APP_PASSWORD.
Format: {expiry_unix}.{hex_signature}
TTL: 7 dni.

Brak DB, brak sesji — token weryfikowany za pomocą HMAC z konfigurowalnym sekretem.
Zmiana APP_PASSWORD automatycznie unieważnia wszystkie aktywne tokeny.
"""

import hmac
import hashlib
import time
from typing import Optional

from app.core.config import get_settings

TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 dni


def is_auth_enabled() -> bool:
    """Auth aktywny jeśli APP_PASSWORD jest ustawione."""
    return bool(get_settings().app_password)


def _secret() -> bytes:
    return get_settings().app_password.encode()


def verify_password(password: str) -> bool:
    expected = get_settings().app_password
    if not expected:
        return False
    return hmac.compare_digest(password, expected)


def make_token(ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
    expiry = str(int(time.time()) + ttl_seconds)
    sig = hmac.new(_secret(), expiry.encode(), hashlib.sha256).hexdigest()
    return f"{expiry}.{sig}"


def verify_token(token: Optional[str]) -> bool:
    if not token:
        return False
    try:
        expiry_str, sig = token.split(".", 1)
        expected = hmac.new(_secret(), expiry_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        return time.time() < int(expiry_str)
    except (ValueError, AttributeError):
        return False
