from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from uuid import UUID

from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine


@dataclass(slots=True)
class ChunkRecord:
    document_id: UUID
    chunk_index: int
    chunk_text: str
    score: float


@dataclass(slots=True)
class DocumentRecord:
    id: UUID
    title: str
    source_url: str | None
    created_at: datetime


class DocumentRepository:
    def __init__(self) -> None:
        self._vector_enabled = True

    async def initialize(self) -> None:
        async with engine.connect() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            await conn.commit()
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn.commit()
                self._vector_enabled = True
            except Exception:
                # Fallback for local PostgreSQL installations without pgvector.
                await conn.rollback()
                self._vector_enabled = False
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        id UUID PRIMARY KEY,
                        title TEXT NOT NULL,
                        source_url TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            if self._vector_enabled:
                await conn.execute(
                    text(
                        f"""
                        CREATE TABLE IF NOT EXISTS document_chunks (
                            id UUID PRIMARY KEY,
                            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                            chunk_text TEXT NOT NULL,
                            embedding VECTOR({settings.embedding_dimensions}) NOT NULL,
                            chunk_index INTEGER NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                )
            else:
                await conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS document_chunks (
                            id UUID PRIMARY KEY,
                            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                            chunk_text TEXT NOT NULL,
                            embedding DOUBLE PRECISION[] NOT NULL,
                            chunk_index INTEGER NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id)"
                )
            )
            await conn.commit()

    async def add_document(
        self,
        *,
        title: str,
        source_url: str | None,
        chunks: list[tuple[int, str, list[float]]],
    ) -> tuple[DocumentRecord, int]:
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        INSERT INTO documents (id, title, source_url)
                        VALUES (gen_random_uuid(), :title, :source_url)
                        RETURNING id, title, source_url, created_at
                        """
                    ),
                    {"title": title, "source_url": source_url},
                )
            ).mappings().one()

            for chunk_index, chunk_text, embedding in chunks:
                if self._vector_enabled:
                    embedding_vector = "[" + ",".join(str(value) for value in embedding) + "]"
                    await conn.execute(
                        text(
                            """
                            INSERT INTO document_chunks (id, document_id, chunk_text, embedding, chunk_index)
                            VALUES (gen_random_uuid(), :document_id, :chunk_text, :embedding::vector, :chunk_index)
                            """
                        ),
                        {
                            "document_id": row["id"],
                            "chunk_text": chunk_text,
                            "embedding": embedding_vector,
                            "chunk_index": chunk_index,
                        },
                    )
                else:
                    await conn.execute(
                        text(
                            """
                            INSERT INTO document_chunks (id, document_id, chunk_text, embedding, chunk_index)
                            VALUES (gen_random_uuid(), :document_id, :chunk_text, :embedding, :chunk_index)
                            """
                        ),
                        {
                            "document_id": row["id"],
                            "chunk_text": chunk_text,
                            "embedding": embedding,
                            "chunk_index": chunk_index,
                        },
                    )

        return (
            DocumentRecord(
                id=row["id"],
                title=row["title"],
                source_url=row["source_url"],
                created_at=row["created_at"],
            ),
            len(chunks),
        )

    async def list_documents(self) -> list[DocumentRecord]:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT id, title, source_url, created_at
                        FROM documents
                        ORDER BY created_at DESC
                        """
                    )
                )
            ).mappings().all()

        return [
            DocumentRecord(
                id=row["id"],
                title=row["title"],
                source_url=row["source_url"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def delete_document(self, document_id: UUID) -> bool:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("DELETE FROM documents WHERE id = :document_id"),
                {"document_id": document_id},
            )
            return result.rowcount > 0

    async def search_chunks(self, *, query_embedding: list[float], top_k: int) -> list[ChunkRecord]:
        if self._vector_enabled:
            embedding_vector = "[" + ",".join(str(value) for value in query_embedding) + "]"
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT d.id AS document_id,
                                   c.chunk_index,
                                   c.chunk_text,
                                   (1 - (c.embedding <=> :embedding::vector)) AS similarity
                            FROM document_chunks c
                            JOIN documents d ON d.id = c.document_id
                            ORDER BY c.embedding <=> :embedding::vector
                            LIMIT :top_k
                            """
                        ),
                        {"embedding": embedding_vector, "top_k": top_k},
                    )
                ).mappings().all()

            return [
                ChunkRecord(
                    document_id=row["document_id"],
                    chunk_index=row["chunk_index"],
                    chunk_text=row["chunk_text"],
                    score=float(row["similarity"]),
                )
                for row in rows
            ]

        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT document_id, chunk_index, chunk_text, embedding
                        FROM document_chunks
                        """
                    )
                )
            ).mappings().all()

        ranked = [
            ChunkRecord(
                document_id=row["document_id"],
                chunk_index=row["chunk_index"],
                chunk_text=row["chunk_text"],
                score=self._cosine_similarity(query_embedding, row["embedding"]),
            )
            for row in rows
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:top_k]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(lv * rv for lv, rv in zip(left, right, strict=False))
        left_mag = math.sqrt(sum(value * value for value in left))
        right_mag = math.sqrt(sum(value * value for value in right))
        if left_mag == 0 or right_mag == 0:
            return 0.0
        return dot / (left_mag * right_mag)

    async def get_document(self, document_id: UUID) -> DocumentRecord | None:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT id, title, source_url, created_at
                        FROM documents
                        WHERE id = :document_id
                        """
                    ),
                    {"document_id": document_id},
                )
            ).mappings().first()

        if row is None:
            return None

        return DocumentRecord(
            id=row["id"],
            title=row["title"],
            source_url=row["source_url"],
            created_at=row["created_at"],
        )

    async def get_document_chunks(self, document_id: UUID) -> list[tuple[int, str]]:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT chunk_index, chunk_text
                        FROM document_chunks
                        WHERE document_id = :document_id
                        ORDER BY chunk_index ASC
                        """
                    ),
                    {"document_id": document_id},
                )
            ).mappings().all()

        return [(int(row["chunk_index"]), str(row["chunk_text"])) for row in rows]


document_repository = DocumentRepository()
