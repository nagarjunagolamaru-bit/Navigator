from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import settings


class EmbeddingService:
	def __init__(self) -> None:
		self._client: AsyncOpenAI | None = None

	def _get_client(self) -> AsyncOpenAI:
		if self._client is not None:
			return self._client

		api_key = settings.openai_api_key or settings.llm_api_key
		if not api_key:
			raise RuntimeError("OPENAI_API_KEY or LLM_API_KEY is required for embeddings.")

		kwargs: dict[str, str] = {"api_key": api_key}
		if settings.llm_api_base_url:
			kwargs["base_url"] = settings.llm_api_base_url

		self._client = AsyncOpenAI(**kwargs)
		return self._client

	async def embed_texts(self, texts: list[str]) -> list[list[float]]:
		if not texts:
			return []

		response = await self._get_client().embeddings.create(
			model=settings.embedding_model,
			input=texts,
			dimensions=settings.embedding_dimensions,
		)
		return [item.embedding for item in response.data]


embedding_service = EmbeddingService()
