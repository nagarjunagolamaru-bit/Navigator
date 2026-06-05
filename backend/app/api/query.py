from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_admin_token
from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_service import query_service

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest, _token: str = Depends(require_admin_token)) -> QueryResponse:
    try:
        return await query_service.query(request.question, request.top_k)
    except Exception as exc:
        import traceback
        error_detail = f"{exc.__class__.__name__}: {str(exc)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail) from exc
