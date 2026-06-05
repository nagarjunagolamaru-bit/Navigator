from __future__ import annotations

from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import settings


class LLMService:
	_NO_ANSWER_MESSAGE = "I could not find relevant information in the available knowledge base."

	def __init__(self) -> None:
		self._client: AsyncOpenAI | None = None
		prompt_path = Path(__file__).resolve().parent / "prompts" / "query_answer_system.txt"
		self._system_prompt = prompt_path.read_text(encoding="utf-8").strip()

	def _get_client(self) -> AsyncOpenAI:
		if self._client is not None:
			return self._client

		api_key = settings.llm_api_key or settings.openai_api_key
		if not api_key:
			raise RuntimeError("LLM_API_KEY or OPENAI_API_KEY is required for query answering.")

		kwargs: dict[str, str] = {"api_key": api_key}
		if settings.llm_api_base_url:
			kwargs["base_url"] = settings.llm_api_base_url

		self._client = AsyncOpenAI(**kwargs)
		return self._client

	async def answer_from_context(self, *, question: str, contexts: list[str]) -> str:
		if not contexts:
			return self._NO_ANSWER_MESSAGE

		context_block = "\n\n".join(f"Context {idx}:\n{text}" for idx, text in enumerate(contexts, start=1))
		user_prompt = (
			f"Question:\n{question}\n\n"
			f"Retrieved context:\n{context_block}\n\n"
			"Answer using only the retrieved context. If the context does not clearly answer the question, "
			f"respond exactly with: {self._NO_ANSWER_MESSAGE}"
		)

		response = await self._get_client().chat.completions.create(
			model=settings.llm_model,
			temperature=0,
			messages=[
				{"role": "system", "content": self._system_prompt},
				{"role": "user", "content": user_prompt},
			],
		)
		content = (response.choices[0].message.content or "").strip()
		return content or self._NO_ANSWER_MESSAGE


llm_service = LLMService()
