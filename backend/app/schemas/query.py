from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class QuerySource(BaseModel):
    document_id: str
    title: str
    source_url: str | None = None
    chunk_index: int
    excerpt: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[QuerySource]
