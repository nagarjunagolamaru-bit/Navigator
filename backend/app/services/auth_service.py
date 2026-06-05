from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status

from app.repositories.auth_repository import UserRecord, auth_repository
from app.schemas.auth import AuthResponse, UserResponse


class AuthService:
    _SESSION_TTL_HOURS = 12

    async def register(self, *, username: str, email: str, password: str) -> AuthResponse:
        normalized_username = username.strip()
        if len(normalized_username) < 2:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Username is too short.")

        normalized_email = email.strip().lower()
        existing = await auth_repository.get_user_by_email(normalized_email)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")

        password_salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, password_salt)
        user = await auth_repository.create_user(
            username=normalized_username,
            email=normalized_email,
            password_hash=password_hash,
            password_salt=password_salt,
        )

        token = await self._issue_session(user.id)
        return AuthResponse(token=token, user=self._to_user_response(user))

    async def login(self, *, identifier: str, password: str) -> AuthResponse:
        normalized_identifier = identifier.strip()
        user = await auth_repository.get_user_by_email(normalized_identifier)
        if user is None:
            user = await auth_repository.get_user_by_username(normalized_identifier)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username/email or password.")

        candidate_hash = self._hash_password(password, user.password_salt)
        if not secrets.compare_digest(candidate_hash, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username/email or password.")

        token = await self._issue_session(user.id)
        return AuthResponse(token=token, user=self._to_user_response(user))

    async def logout(self, token: str) -> None:
        await auth_repository.delete_session(token)

    async def get_user_for_token(self, token: str) -> UserRecord:
        session = await auth_repository.get_session(token)
        if session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")

        if session.expires_at < datetime.now(tz=UTC):
            await auth_repository.delete_session(token)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")

        user = await auth_repository.get_user_by_id(session.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")

        return user

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 600_000)
        return derived.hex()

    async def _issue_session(self, user_id: UUID) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(tz=UTC) + timedelta(hours=self._SESSION_TTL_HOURS)
        await auth_repository.create_session(token=token, user_id=user_id, expires_at=expires_at)
        return token

    @staticmethod
    def _to_user_response(user: UserRecord) -> UserResponse:
        return UserResponse(id=str(user.id), username=user.username, email=user.email, created_at=user.created_at)


auth_service = AuthService()
