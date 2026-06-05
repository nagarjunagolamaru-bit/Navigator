from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_bearer_token
from app.schemas.query import QueryRequest, QueryResponse
from app.services.auth_service import auth_service
from app.services.query_service import query_service

router = APIRouter(prefix="/api/employee/query", tags=["employee-query"])


@router.post("", response_model=QueryResponse)
async def employee_query(payload: QueryRequest, token: str = Depends(require_bearer_token)) -> QueryResponse:
    await auth_service.get_user_for_token(token)
    return await query_service.query(payload.question, payload.top_k)
