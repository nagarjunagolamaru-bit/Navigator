from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    id: UUID
    title: str
    source_url: str | None = None
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    document: DocumentMetadata
    chunk_count: int = Field(ge=0)


class DocumentListResponse(BaseModel):
    documents: list[DocumentMetadata]
