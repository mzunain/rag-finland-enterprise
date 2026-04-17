from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime

PBKDF2_ITERATIONS = 120_000
PBKDF2_ALGORITHM = "sha256"


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def month_window_start(now: datetime | None = None) -> datetime:
    current = now or utc_now()
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(PBKDF2_ALGORITHM, password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${iterations}${salt}${digest}".format(
        iterations=PBKDF2_ITERATIONS,
        salt=base64.urlsafe_b64encode(salt).decode("ascii"),
        digest=base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    if not encoded_hash:
        return False
    try:
        scheme, iterations_str, salt_b64, digest_b64 = encoded_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
    except (ValueError, TypeError, base64.binascii.Error):
        return False

    actual = hashlib.pbkdf2_hmac(PBKDF2_ALGORITHM, password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def hash_api_key(raw_key: str) -> str:
    if not raw_key:
        raise ValueError("API key cannot be empty")
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
