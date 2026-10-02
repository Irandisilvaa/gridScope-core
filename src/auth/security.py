from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from uuid import UUID, uuid4


PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(email: str) -> str:
    normalized = str(email).strip().casefold()
    if len(normalized) > 254 or not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Informe um e-mail válido")
    return normalized


def validate_password(password: str) -> str:
    if not isinstance(password, str):
        raise ValueError("A senha deve ser texto")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"A senha deve ter pelo menos {PASSWORD_MIN_LENGTH} caracteres")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"A senha deve ter no máximo {PASSWORD_MAX_LENGTH} caracteres")
    if "\x00" in password:
        raise ValueError("A senha contém um caractere inválido")
    return password


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    validate_password(password)
    salt = os.urandom(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        maxmem=64 * 1024 * 1024,
        dklen=32,
    )
    return f"scrypt$v=1$n=16384$r=8$p=1${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        validate_password(password)
        scheme, version, n_value, r_value, p_value, salt_value, digest_value = encoded.split("$")
        if scheme != "scrypt" or version != "v=1":
            return False
        n = int(n_value.removeprefix("n="))
        r = int(r_value.removeprefix("r="))
        p = int(p_value.removeprefix("p="))
        salt = _b64decode(salt_value)
        expected = _b64decode(digest_value)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=64 * 1024 * 1024,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError, IndexError, OverflowError):
        return False


def new_uuid() -> UUID:
    return uuid4()


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
