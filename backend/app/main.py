from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.employee_query import router as employee_query_router
from app.api.query import router as query_router
from app.core.config import settings
from app.repositories.auth_repository import auth_repository
from app.repositories.document_repository import document_repository
from app.services.auth_service import auth_service


app = FastAPI(
    title=settings.app_name,
)

allowed_origins = sorted(
    {
        settings.frontend_url.rstrip("/"),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(query_router)
app.include_router(auth_router)
app.include_router(employee_query_router)


@app.on_event("startup")
async def on_startup() -> None:
    try:
        await document_repository.initialize()
        await auth_repository.initialize()
        await auth_service.ensure_level2_admin_account()
    except Exception as exc:
        # Keep API reachable even if vector database is temporarily unavailable.
        app.state.startup_error = str(exc)
