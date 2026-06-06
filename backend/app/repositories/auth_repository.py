from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine


@dataclass(slots=True)
class UserRecord:
    id: UUID
    username: str
    email: str
    is_admin: bool
    password_hash: str
    password_salt: str
    created_at: datetime


@dataclass(slots=True)
class SessionRecord:
    token: str
    user_id: UUID
    expires_at: datetime


class AuthRepository:
    async def initialize(self) -> None:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS employee_users (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        username TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE,
                        is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                        password_hash TEXT NOT NULL,
                        password_salt TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            await conn.execute(
                text("ALTER TABLE employee_users ADD COLUMN IF NOT EXISTS username TEXT")
            )
            await conn.execute(
                text("ALTER TABLE employee_users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE")
            )
            await conn.execute(
                text("ALTER TABLE employee_users ALTER COLUMN id SET DEFAULT gen_random_uuid()")
            )
            await conn.execute(
                text(
                    """
                    UPDATE employee_users
                    SET username = split_part(email, '@', 1)
                    WHERE username IS NULL OR btrim(username) = ''
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    UPDATE employee_users
                    SET is_admin = TRUE
                    WHERE lower(username) = lower(:admin_username)
                    """
                ),
                {"admin_username": settings.admin_username},
            )
            await conn.execute(
                text("ALTER TABLE employee_users ALTER COLUMN username SET NOT NULL")
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS employee_sessions (
                        token TEXT PRIMARY KEY,
                        user_id UUID NOT NULL REFERENCES employee_users(id) ON DELETE CASCADE,
                        expires_at TIMESTAMPTZ NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_employee_sessions_user_id ON employee_sessions(user_id)")
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_employee_sessions_expires_at ON employee_sessions(expires_at)")
            )

    async def create_user(self, *, username: str, email: str, password_hash: str, password_salt: str) -> UserRecord:
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        INSERT INTO employee_users (username, email, is_admin, password_hash, password_salt)
                        VALUES (:username, :email, FALSE, :password_hash, :password_salt)
                        RETURNING id, username, email, is_admin, password_hash, password_salt, created_at
                        """
                    ),
                    {
                        "username": username,
                        "email": email,
                        "password_hash": password_hash,
                        "password_salt": password_salt,
                    },
                )
            ).mappings().one()

        return UserRecord(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            is_admin=row["is_admin"],
            password_hash=row["password_hash"],
            password_salt=row["password_salt"],
            created_at=row["created_at"],
        )

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT id, username, email, is_admin, password_hash, password_salt, created_at
                        FROM employee_users
                        WHERE lower(email) = lower(:email)
                        """
                    ),
                    {"email": email},
                )
            ).mappings().first()

        if row is None:
            return None

        return UserRecord(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            is_admin=row["is_admin"],
            password_hash=row["password_hash"],
            password_salt=row["password_salt"],
            created_at=row["created_at"],
        )

    async def get_user_by_username(self, username: str) -> UserRecord | None:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT id, username, email, is_admin, password_hash, password_salt, created_at
                        FROM employee_users
                        WHERE lower(username) = lower(:username)
                        """
                    ),
                    {"username": username},
                )
            ).mappings().first()

        if row is None:
            return None

        return UserRecord(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            is_admin=row["is_admin"],
            password_hash=row["password_hash"],
            password_salt=row["password_salt"],
            created_at=row["created_at"],
        )

    async def create_session(self, *, token: str, user_id: UUID, expires_at: datetime) -> SessionRecord:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO employee_sessions (token, user_id, expires_at)
                    VALUES (:token, :user_id, :expires_at)
                    ON CONFLICT (token) DO UPDATE
                    SET user_id = EXCLUDED.user_id,
                        expires_at = EXCLUDED.expires_at
                    """
                ),
                {"token": token, "user_id": user_id, "expires_at": expires_at},
            )

        return SessionRecord(token=token, user_id=user_id, expires_at=expires_at)

    async def get_session(self, token: str) -> SessionRecord | None:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT token, user_id, expires_at
                        FROM employee_sessions
                        WHERE token = :token
                        """
                    ),
                    {"token": token},
                )
            ).mappings().first()

        if row is None:
            return None

        return SessionRecord(token=row["token"], user_id=row["user_id"], expires_at=row["expires_at"])

    async def delete_session(self, token: str) -> None:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM employee_sessions WHERE token = :token"), {"token": token})

    async def get_user_by_id(self, user_id: UUID) -> UserRecord | None:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT id, username, email, is_admin, password_hash, password_salt, created_at
                        FROM employee_users
                        WHERE id = :user_id
                        """
                    ),
                    {"user_id": user_id},
                )
            ).mappings().first()

        if row is None:
            return None

        return UserRecord(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            is_admin=row["is_admin"],
            password_hash=row["password_hash"],
            password_salt=row["password_salt"],
            created_at=row["created_at"],
        )


auth_repository = AuthRepository()
