from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text

try:
    from src.database import get_engine
except ModuleNotFoundError:
    from database import get_engine

from .security import (
    hash_password,
    hash_session_token,
    new_session_token,
    new_uuid,
    normalize_email,
    verify_password,
)


@dataclass(frozen=True)
class UserRecord:
    id: UUID
    email: str
    name: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }


def _row_to_user(row: Any) -> UserRecord:
    values = row._mapping if hasattr(row, "_mapping") else row
    return UserRecord(
        id=UUID(str(values["id"])),
        email=values["email"],
        name=values["name"],
        role=values["role"],
        is_active=bool(values["is_active"]),
        created_at=values.get("created_at") if hasattr(values, "get") else None,
        last_login_at=values.get("last_login_at") if hasattr(values, "get") else None,
    )


def ensure_auth_tables() -> None:
    engine = get_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS auth_users (
                        id UUID PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        last_login_at TIMESTAMPTZ,
                        password_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS auth_sessions (
                        id UUID PRIMARY KEY,
                        user_id UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
                        token_hash CHAR(64) NOT NULL UNIQUE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        expires_at TIMESTAMPTZ NOT NULL,
                        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        revoked_at TIMESTAMPTZ
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_active ON auth_sessions(token_hash, expires_at)"
                )
            )
    finally:
        engine.dispose()


def get_user_by_email(email: str) -> Optional[UserRecord]:
    normalized = normalize_email(email)
    engine = get_engine()
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT id, email, name, role, is_active, created_at, last_login_at
                    FROM auth_users
                    WHERE email = :email
                    """
                ),
                {"email": normalized},
            ).first()
            return _row_to_user(row) if row else None
    finally:
        engine.dispose()


def get_user_by_id(user_id: UUID | str) -> Optional[UserRecord]:
    try:
        normalized_id = UUID(str(user_id))
    except ValueError:
        return None
    engine = get_engine()
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT id, email, name, role, is_active, created_at, last_login_at
                    FROM auth_users
                    WHERE id = CAST(:user_id AS uuid)
                    """
                ),
                {"user_id": str(normalized_id)},
            ).first()
            return _row_to_user(row) if row else None
    finally:
        engine.dispose()


def authenticate_user(email: str, password: str) -> Optional[UserRecord]:
    normalized = normalize_email(email)
    engine = get_engine()
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT id, email, name, role, is_active, password_hash, created_at, last_login_at
                    FROM auth_users
                    WHERE email = :email
                    """
                ),
                {"email": normalized},
            ).first()
            if not row:
                return None
            values = row._mapping
            if not bool(values["is_active"]) or not verify_password(password, values["password_hash"]):
                return None
            return _row_to_user(row)
    finally:
        engine.dispose()


def mark_login(user_id: UUID) -> None:
    engine = get_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE auth_users SET last_login_at = NOW(), updated_at = NOW() WHERE id = CAST(:id AS uuid)"
                ),
                {"id": str(user_id)},
            )
    finally:
        engine.dispose()


def create_user(email: str, name: str, password: str, role: str = "user") -> UserRecord:
    normalized = normalize_email(email)
    if role not in {"admin", "user"}:
        raise ValueError("Papel de usuário inválido")
    if not name.strip() or len(name.strip()) > 160:
        raise ValueError("Informe um nome válido")

    user_id = new_uuid()
    password_hash = hash_password(password)
    engine = get_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO auth_users (id, email, name, password_hash, role)
                    VALUES (CAST(:id AS uuid), :email, :name, :password_hash, :role)
                    """
                ),
                {
                    "id": str(user_id),
                    "email": normalized,
                    "name": name.strip(),
                    "password_hash": password_hash,
                    "role": role,
                },
            )
        return UserRecord(user_id, normalized, name.strip(), role, True)
    finally:
        engine.dispose()


def list_users() -> list[UserRecord]:
    engine = get_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT id, email, name, role, is_active, created_at, last_login_at
                    FROM auth_users
                    ORDER BY created_at ASC
                    """
                )
            )
            return [_row_to_user(row) for row in rows]
    finally:
        engine.dispose()


def update_user(
    user_id: UUID,
    *,
    name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[UserRecord]:
    if name is not None and (not name.strip() or len(name.strip()) > 160):
        raise ValueError("Informe um nome válido")
    if role is not None and role not in {"admin", "user"}:
        raise ValueError("Papel de usuário inválido")
    changes: list[str] = []
    params: dict[str, Any] = {"id": str(user_id)}
    if name is not None:
        changes.append("name = :name")
        params["name"] = name.strip()
    if role is not None:
        changes.append("role = :role")
        params["role"] = role
    if is_active is not None:
        changes.append("is_active = :is_active")
        params["is_active"] = is_active
    if not changes:
        return get_user_by_id(user_id)

    changes.append("updated_at = NOW()")
    engine = get_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"UPDATE auth_users SET {', '.join(changes)} WHERE id = CAST(:id AS uuid)"
                ),
                params,
            )
        return get_user_by_id(user_id)
    finally:
        engine.dispose()


def reset_password(user_id: UUID, password: str) -> None:
    password_hash = hash_password(password)
    engine = get_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE auth_users
                    SET password_hash = :password_hash,
                        password_changed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = CAST(:id AS uuid)
                    """
                ),
                {"id": str(user_id), "password_hash": password_hash},
            )
            connection.execute(
                text(
                    """
                    UPDATE auth_sessions
                    SET revoked_at = NOW()
                    WHERE user_id = CAST(:id AS uuid) AND revoked_at IS NULL
                    """
                ),
                {"id": str(user_id)},
            )
    finally:
        engine.dispose()


def count_active_admins() -> int:
    engine = get_engine()
    try:
        with engine.connect() as connection:
            return int(
                connection.execute(
                    text("SELECT COUNT(*) FROM auth_users WHERE role = 'admin' AND is_active = TRUE")
                ).scalar_one()
            )
    finally:
        engine.dispose()


def create_session(user_id: UUID, ttl_seconds: int) -> str:
    raw_token = new_session_token()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    engine = get_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO auth_sessions (id, user_id, token_hash, expires_at)
                    VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :token_hash, :expires_at)
                    """
                ),
                {
                    "id": str(new_uuid()),
                    "user_id": str(user_id),
                    "token_hash": hash_session_token(raw_token),
                    "expires_at": expires_at,
                },
            )
        return raw_token
    finally:
        engine.dispose()


def get_user_by_session_token(raw_token: str) -> Optional[UserRecord]:
    if not raw_token:
        return None
    engine = get_engine()
    try:
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT u.id, u.email, u.name, u.role, u.is_active,
                           u.created_at, u.last_login_at
                    FROM auth_sessions s
                    JOIN auth_users u ON u.id = s.user_id
                    WHERE s.token_hash = :token_hash
                      AND s.revoked_at IS NULL
                      AND s.expires_at > NOW()
                      AND u.is_active = TRUE
                    """
                ),
                {"token_hash": hash_session_token(raw_token)},
            ).first()
            if not row:
                return None
            connection.execute(
                text("UPDATE auth_sessions SET last_seen_at = NOW() WHERE token_hash = :token_hash"),
                {"token_hash": hash_session_token(raw_token)},
            )
            return _row_to_user(row)
    finally:
        engine.dispose()


def revoke_session(raw_token: str) -> None:
    if not raw_token:
        return
    engine = get_engine()
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE auth_sessions SET revoked_at = NOW() WHERE token_hash = :token_hash"),
                {"token_hash": hash_session_token(raw_token)},
            )
    finally:
        engine.dispose()
