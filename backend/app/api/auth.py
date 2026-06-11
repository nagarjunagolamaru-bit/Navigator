from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.services.auth_service import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def require_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header.")

    token_type, _, token = authorization.partition(" ")
    if token_type.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header.")
    return token


async def require_admin_token(token: str = Depends(require_bearer_token)) -> str:
    await auth_service.get_admin_user_for_token(token)
    return token


async def require_documents_delete_admin_token(token: str = Depends(require_bearer_token)) -> str:
    admin_user = await auth_service.get_admin_user_for_token(token)
    if admin_user.username.lower() != "level1_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Level1 admin can delete documents.")
    return token


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> AuthResponse:
    return await auth_service.register(username=payload.username, email=payload.email, password=payload.password)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    return await auth_service.login(identifier=payload.identifier, password=payload.password)


@router.get("/me", response_model=UserResponse)
async def me(token: str = Depends(require_bearer_token)) -> UserResponse:
    user = await auth_service.get_user_for_token(token)
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(token: str = Depends(require_bearer_token)) -> None:
    await auth_service.logout(token)
