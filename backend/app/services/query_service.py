from __future__ import annotations

import re
from uuid import UUID

from app.ai.embeddings import embedding_service
from app.ai.llm import llm_service
from app.core.config import settings
from app.repositories.document_repository import document_repository
from app.schemas.query import QueryResponse, QuerySource


class QueryService:
    _NO_ANSWER_MESSAGE = "I could not find relevant information in the available knowledge base."
    _TIME_PATTERN = re.compile(r"\b\d{1,2}:\d{2}\b")
    _STOP_WORDS = {
        "the",
        "and",
        "for",
        "with",
        "what",
        "when",
        "where",
        "which",
        "that",
        "this",
        "from",
        "into",
        "were",
        "was",
        "are",
        "how",
        "many",
    }

    async def query(self, question: str, top_k: int | None = None) -> QueryResponse:
        normalized = question.strip()
        if not normalized:
            return QueryResponse(answer=self._NO_ANSWER_MESSAGE, sources=[])

        requested_top_k = top_k or settings.retrieval_top_k
        question_terms = self._tokenize(normalized)

        query_embedding = (await embedding_service.embed_texts([normalized]))[0]
        chunk_matches = await document_repository.search_chunks(
            query_embedding=query_embedding,
            top_k=max(requested_top_k * 2, requested_top_k),
        )

        ranked: list[tuple[QuerySource, float, str]] = []
        for chunk in chunk_matches:
            doc = await document_repository.get_document(chunk.document_id)
            if doc is None:
                continue

            semantic_score = max(chunk.score, 0.0)
            keyword_score = self._keyword_overlap(question_terms, chunk.chunk_text)
            blended_score = (semantic_score * 0.8) + (keyword_score * 0.2)

            # Require either meaningful semantic similarity or keyword evidence.
            min_semantic = max(settings.min_relevance_threshold, 0.2)
            if semantic_score < min_semantic and keyword_score == 0.0:
                continue

            source = QuerySource(
                document_id=str(doc.id),
                title=doc.title,
                source_url=doc.source_url,
                chunk_index=chunk.chunk_index,
                excerpt=self._best_excerpt(chunk.chunk_text, question_terms),
                score=round(blended_score, 4),
            )
            ranked.append((source, blended_score, chunk.chunk_text))

        ranked.sort(key=lambda item: item[1], reverse=True)
        selected_rows = ranked[:requested_top_k]
        selected = [source for source, _, _ in selected_rows]

        if not selected:
            return QueryResponse(answer=self._NO_ANSWER_MESSAGE, sources=[])

        min_selected_score = max(settings.min_relevance_threshold, 0.25)
        if selected[0].score < min_selected_score:
            return QueryResponse(answer=self._NO_ANSWER_MESSAGE, sources=[])

        primary_source = [selected[0]]

        if self._is_supplier_inventory_question(normalized):
            answer = await self._answer_supplier_inventory(normalized, selected)
            return QueryResponse(answer=answer, sources=primary_source)

        if self._is_policy_premium_question(normalized):
            answer = await self._answer_policy_premium(selected)
            if answer != self._NO_ANSWER_MESSAGE:
                return QueryResponse(answer=answer, sources=primary_source)

        if self._is_policy_fact_question(normalized):
            answer = await self._answer_policy_fact(normalized, selected)
            if answer != self._NO_ANSWER_MESSAGE:
                return QueryResponse(answer=answer, sources=primary_source)

        answer = await llm_service.answer_from_context(
            question=normalized,
            contexts=[chunk_text for _, _, chunk_text in selected_rows],
        )
        return QueryResponse(answer=answer, sources=primary_source)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {
            term
            for term in re.findall(r"[a-zA-Z0-9]+", text.lower())
            if len(term) >= 3 and term not in QueryService._STOP_WORDS
        }

    def _keyword_overlap(self, question_terms: set[str], chunk_text: str) -> float:
        if not question_terms:
            return 0.0
        chunk_terms = self._tokenize(chunk_text)
        if not chunk_terms:
            return 0.0
        overlap = len(question_terms & chunk_terms)
        return overlap / len(question_terms)

    def _best_excerpt(self, chunk_text: str, question_terms: set[str], max_len: int = 350) -> str:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", chunk_text) if part.strip()]
        if not sentences:
            return chunk_text[:max_len]

        if not question_terms:
            return sentences[0][:max_len]

        best_sentence = max(
            sentences,
            key=lambda sentence: len(question_terms & self._tokenize(sentence)),
        )
        return best_sentence[:max_len]

    def _fallback_answer(self, sources: list[QuerySource]) -> str:
        lines = ["I found relevant snippets, but the document appears table-heavy. Closest matches:"]
        for idx, source in enumerate(sources[:3], start=1):
            lines.append(f"{idx}. {source.excerpt}")
        return "\n".join(lines)

    @staticmethod
    def _is_policy_fact_question(question: str) -> bool:
        lowered = question.lower()
        hints = (
            "policy number",
            "sum assured",
            "payment frequency",
            "top up premium",
            "financial year",
            "premium paid",
        )
        return any(hint in lowered for hint in hints)

    async def _answer_policy_fact(self, question: str, sources: list[QuerySource]) -> str:
        full_text = await self._load_full_text_from_sources(sources)
        if not full_text:
            return self._NO_ANSWER_MESSAGE

        facts = self._extract_policy_facts(full_text)
        if not facts:
            return self._NO_ANSWER_MESSAGE

        lowered = question.lower()
        if "policy number" in lowered and facts.get("policy_number"):
            return f"Detected policy number: {facts['policy_number']}."
        if "sum assured" in lowered and facts.get("sum_assured"):
            return f"Detected sum assured: {facts['sum_assured']}."
        if "payment frequency" in lowered and facts.get("payment_frequency"):
            return f"Detected premium payment frequency: {facts['payment_frequency']}."
        if "top up premium" in lowered and facts.get("top_up_premium"):
            return f"Detected top up premium paid: {facts['top_up_premium']}."
        if "financial year" in lowered and facts.get("financial_year_premium"):
            return f"Detected premium paid during financial year: {facts['financial_year_premium']}."
        if "premium paid" in lowered and facts.get("financial_year_premium"):
            return f"Detected premium paid during financial year: {facts['financial_year_premium']}."
        if "premium paid" in lowered and not facts.get("financial_year_premium"):
            premium_answer = await self._answer_policy_premium(sources)
            if premium_answer != self._NO_ANSWER_MESSAGE:
                return premium_answer

        # Multi-fact summary when question is broad.
        lines: list[str] = []
        if facts.get("policy_number"):
            lines.append(f"Policy number: {facts['policy_number']}")
        if facts.get("sum_assured"):
            lines.append(f"Sum assured: {facts['sum_assured']}")
        if facts.get("payment_frequency"):
            lines.append(f"Premium payment frequency: {facts['payment_frequency']}")
        if facts.get("financial_year_premium"):
            lines.append(f"Premium paid during financial year: {facts['financial_year_premium']}")
        if facts.get("top_up_premium"):
            lines.append(f"Top up premium paid: {facts['top_up_premium']}")

        return "\n".join(lines) if lines else self._NO_ANSWER_MESSAGE

    async def _load_full_text_from_sources(self, sources: list[QuerySource]) -> str:
        if not sources:
            return ""

        try:
            document_id = UUID(sources[0].document_id)
        except ValueError:
            return ""

        chunks = await document_repository.get_document_chunks(document_id)
        if not chunks:
            return ""
        return "\n".join(text for _, text in chunks)

    def _extract_policy_facts(self, text: str) -> dict[str, str]:
        compact = re.sub(r"\s+", " ", text)
        facts: dict[str, str] = {}

        policy_number = self._first_group(compact, r"(?i)policy\s*number\s*[:\-]?\s*([A-Z0-9]{8,20})")
        if policy_number:
            facts["policy_number"] = policy_number

        sum_assured = self._first_group(compact, r"(?i)sum\s+assured\s*[:\-]?\s*([0-9,]+\.?[0-9]{0,2})")
        if sum_assured:
            facts["sum_assured"] = self._format_amount_text(sum_assured)

        payment_frequency = self._first_group(
            compact,
            r"(?i)(?:premium\s+payment\s+frequency|payment\s+frequency)\s*[:\-]?\s*([A-Za-z ]{3,24})",
        )
        if payment_frequency:
            facts["payment_frequency"] = payment_frequency.strip().title()

        fy_premium: str | None = None
        for match in re.finditer(
            r"(?i)([^:]{0,120}premium\s+paid\s+during\s+the\s+financial\s+year[^:]{0,40})\s*:\s*([0-9,]+\.?[0-9]{0,2})",
            compact,
        ):
            label = match.group(1).lower()
            if "top up" in label:
                continue
            fy_premium = match.group(2)
            break
        if fy_premium:
            facts["financial_year_premium"] = self._format_amount_text(fy_premium)

        topup_premium = self._first_group(
            compact,
            r"(?i)total\s+amount\s+of\s+top\s*up\s+premium\s+paid\s+during\s+the\s+financial\s+year\s*\d{4}\s*-\s*\d{4}\s*:\s*([0-9,]+\.?[0-9]{0,2})",
        )
        if topup_premium:
            facts["top_up_premium"] = self._format_amount_text(topup_premium)

        return facts

    @staticmethod
    def _first_group(text: str, pattern: str) -> str | None:
        match = re.search(pattern, text)
        if not match:
            return None
        return match.group(1).strip()

    @staticmethod
    def _format_amount_text(value: str) -> str:
        parsed = QueryService._parse_amount(value)
        if parsed is None:
            return value
        return f"{parsed:,.2f}"

    @staticmethod
    def _is_policy_premium_question(question: str) -> bool:
        lowered = question.lower()
        has_policy = "policy" in lowered
        has_premium = "premium" in lowered
        return has_policy and has_premium

    async def _answer_policy_premium(self, sources: list[QuerySource]) -> str:
        if not sources:
            return self._NO_ANSWER_MESSAGE

        try:
            document_id = UUID(sources[0].document_id)
        except ValueError:
            return self._NO_ANSWER_MESSAGE

        chunks = await document_repository.get_document_chunks(document_id)
        if not chunks:
            return self._NO_ANSWER_MESSAGE

        full_text = "\n".join(text for _, text in chunks)
        compact = re.sub(r"\s+", " ", full_text)

        candidates: list[tuple[float, str]] = []

        for match in re.finditer(
            r"(?i)([A-Za-z\s]{0,80}premium[\w\s]{0,80})\s*:\s*([0-9][0-9,]*\.?[0-9]{0,2})",
            compact,
        ):
            label = re.sub(r"\s+", " ", match.group(1)).strip()
            parsed = self._parse_amount(match.group(2))
            if parsed is not None:
                candidates.append((parsed, label))

        # Common statement format in premium certificates.
        for match in re.finditer(
            r"(?i)financial\s+year\s*\d{4}\s*-\s*\d{4}\s*:\s*([0-9][0-9,]*\.?[0-9]{0,2})",
            compact,
        ):
            parsed = self._parse_amount(match.group(1))
            if parsed is not None:
                candidates.append((parsed, "financial year premium"))

        if not candidates:
            return self._NO_ANSWER_MESSAGE

        filtered = [
            amount
            for amount, label in candidates
            if "top up" not in label.lower() and "excess" not in label.lower()
        ]

        if not filtered:
            filtered = [amount for amount, _ in candidates]

        non_zero = [amount for amount in filtered if amount > 0]
        premium = max(non_zero) if non_zero else max(filtered)
        return f"Detected policy premium amount: {premium:,.2f}."

    @staticmethod
    def _parse_amount(value: str) -> float | None:
        cleaned = value.replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _is_supplier_inventory_question(question: str) -> bool:
        normalized = question.lower()
        asks_supplier = any(token in normalized for token in ("supplier", "suppliers"))
        if not asks_supplier:
            return False

        asks_count = any(
            token in normalized
            for token in ("how many", "number of", "count", "mnay", "many")
        )
        asks_names = any(token in normalized for token in ("name", "names", "list"))
        return asks_count or asks_names

    async def _answer_supplier_inventory(self, question: str, sources: list[QuerySource]) -> str:
        if not sources:
            return self._NO_ANSWER_MESSAGE

        try:
            document_id = UUID(sources[0].document_id)
        except ValueError:
            return self._fallback_answer(sources)

        chunks = await document_repository.get_document_chunks(document_id)
        if not chunks:
            return self._fallback_answer(sources)

        ordered_text = "\n".join(text for _, text in chunks)
        names = self._extract_supplier_names(ordered_text)
        if not names:
            return self._fallback_answer(sources)

        normalized_question = question.lower()
        wants_names = any(token in normalized_question for token in ("name", "names", "list"))
        wants_count = any(
            token in normalized_question
            for token in ("how many", "number of", "count", "mnay", "many")
        )

        if wants_names and wants_count:
            lines = [
                f"I identified {len(names)} suppliers in \"{sources[0].title}\".",
                "Supplier names:",
            ]
            lines.extend(f"- {name}" for name in names)
            return "\n".join(lines)

        if wants_names:
            lines = ["Supplier names:"]
            lines.extend(f"- {name}" for name in names)
            return "\n".join(lines)

        return f"I identified {len(names)} suppliers in \"{sources[0].title}\"."

    def _extract_supplier_names(self, text: str) -> list[str]:
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
        extracted: list[str] = []
        seen: set[str] = set()

        idx = 0
        while idx < len(lines):
            line = lines[idx]
            if self._has_time(line):
                idx += 1
                continue

            next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
            next_two = lines[idx + 2] if idx + 2 < len(lines) else ""

            # Common pattern: supplier name line, then time line.
            is_supplier_row = self._has_time(next_line)
            candidate = line

            # Multi-line supplier names: current + continuation, then time line.
            used_continuation = False
            if not is_supplier_row and self._looks_like_name_continuation(next_line) and self._has_time(next_two):
                candidate = f"{line} {next_line}"
                is_supplier_row = True
                used_continuation = True

            if not is_supplier_row:
                idx += 1
                continue

            normalized = self._normalize_supplier_name(candidate)
            if not normalized or not self._is_valid_supplier_name(normalized):
                idx += 2 if used_continuation else 1
                continue

            key = normalized.casefold()
            if key in seen:
                idx += 2 if used_continuation else 1
                continue
            seen.add(key)
            extracted.append(normalized)
            idx += 2 if used_continuation else 1

        return self._remove_name_fragments(extracted)

    def _has_time(self, value: str) -> bool:
        if not value:
            return False
        return bool(self._TIME_PATTERN.search(value) or "pm et" in value.lower() or "am et" in value.lower())

    def _looks_like_name_continuation(self, value: str) -> bool:
        if not value:
            return False
        if self._has_time(value):
            return False
        if "$" in value or any(ch.isdigit() for ch in value):
            return False
        return len(value) <= 45

    @staticmethod
    def _normalize_supplier_name(name: str) -> str:
        compact = re.sub(r"\s+", " ", name).strip(" ,.-")
        cleaned = re.sub(
            r"(?i)\b(?:ACH/EFT|Credit Card|Check by Fax|Check|Prepay|Wire|"
            r"Accepts Digital Payments via|Payments via|Due Upon Receipt|UPS|FEDEX|USPS|"
            r"Ground|2-Day|Next Day|Net\s*\d+|EOM|Monthly)\b",
            " ",
            compact,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
        return cleaned or compact

    @staticmethod
    def _is_valid_supplier_name(name: str) -> bool:
        if not name or any(ch.isdigit() for ch in name):
            return False

        lower = name.lower()
        stop_words = {
            "ground",
            "next",
            "day",
            "ups",
            "fedex",
            "prepay",
            "receipt",
            "net",
            "accepts",
            "digital",
            "payments",
            "via",
            "credit",
            "card",
            "ach",
            "eft",
            "check",
            "wire",
        }

        tokens = [token for token in re.findall(r"[a-zA-Z]+", lower) if token]
        if not tokens:
            return False

        if lower.startswith("by ") or lower.startswith("fax") or lower.startswith("("):
            return False

        invalid_singletons = {"supply", "independent", "lllc", "llc", "fax", "by"}
        if len(tokens) == 1 and tokens[0] in invalid_singletons:
            return False

        if len(tokens) == 1 and len(tokens[0]) <= 2:
            return False

        if all(token in stop_words for token in tokens):
            return False

        if any(token in stop_words for token in tokens):
            return False

        if "ground" in lower and "next" in lower:
            return False

        if len(tokens) > 8:
            return False

        return True

    def _remove_name_fragments(self, names: list[str]) -> list[str]:
        if not names:
            return names

        canonical = [(name, self._canonical_name(name)) for name in names]
        keep: list[str] = []

        for name, can in canonical:
            if not can:
                continue
            is_fragment = False
            for other_name, other_can in canonical:
                if name == other_name:
                    continue
                if len(can) < len(other_can) and (can in other_can):
                    is_fragment = True
                    break
            if not is_fragment:
                keep.append(name)

        # Preserve order while deduplicating after fragment removal.
        out: list[str] = []
        seen: set[str] = set()
        for name in keep:
            key = self._canonical_name(name)
            if key in seen:
                continue
            seen.add(key)
            out.append(name)
        return out

    @staticmethod
    def _canonical_name(name: str) -> str:
        lowered = name.lower()
        lowered = re.sub(r"[^a-z]+", "", lowered)
        return lowered


query_service = QueryService()
