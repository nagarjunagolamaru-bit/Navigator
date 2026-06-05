from __future__ import annotations

import html
from io import BytesIO
import os
import re
from urllib.parse import unquote
from urllib.parse import parse_qs, urlparse

import httpx
from pypdf import PdfReader

from app.ai.embeddings import embedding_service
from app.repositories.document_repository import DocumentRecord, document_repository


class DocumentService:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def ingest_pdf(
        self,
        *,
        filename: str,
        payload: bytes,
        source_url: str | None,
    ) -> tuple[DocumentRecord, int]:
        text = self._extract_text(payload)
        chunks = self._chunk_text(text)
        embeddings = await embedding_service.embed_texts(chunks)
        chunk_records = [(idx, chunk, embedding) for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))]

        title = filename.rsplit(".", 1)[0] if "." in filename else filename
        return await document_repository.add_document(
            title=title,
            source_url=source_url,
            chunks=chunk_records,
        )

    async def ingest_pdf_from_url(self, source_url: str) -> tuple[DocumentRecord, int]:
        normalized_url = source_url.strip()
        if not normalized_url:
            raise ValueError("Source URL is required for URL-based upload.")

        download_url = self._normalize_pdf_url(normalized_url)
        payload, final_url, content_type, content_disposition = await self._download_pdf(download_url)

        # Some services return octet-stream; validate using header bytes.
        if "pdf" not in content_type and not payload.startswith(b"%PDF"):
            raise ValueError(
                "The URL did not return a PDF file. Ensure the Google Drive file is shared as 'Anyone with the link'."
            )

        filename = self._derive_filename(final_url, content_disposition)
        return await self.ingest_pdf(
            filename=filename,
            payload=payload,
            source_url=normalized_url,
        )

    async def list_documents(self) -> list[DocumentRecord]:
        return await document_repository.list_documents()

    async def delete_document(self, document_id: str) -> bool:
        from uuid import UUID

        return await document_repository.delete_document(UUID(document_id))

    def _extract_text(self, payload: bytes) -> str:
        reader = PdfReader(BytesIO(payload))
        parts: list[str] = []
        for page in reader.pages:
            parts.append((page.extract_text() or "").strip())

        text = "\n".join(part for part in parts if part)
        if not text:
            raise ValueError("Unable to extract text from PDF.")
        return text

    def _chunk_text(self, text: str) -> list[str]:
        if len(text) <= self._chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        step = self._chunk_size - self._chunk_overlap

        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += step

        return chunks

    async def _download_pdf(self, url: str) -> tuple[bytes, str, str, str]:
        timeout = httpx.Timeout(45.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)

            # Google Drive may return an HTML confirmation page for downloads.
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type and "drive.google.com" in str(response.url):
                confirm_url = self._extract_drive_confirm_url(response.text)
                if confirm_url:
                    response = await client.get(confirm_url)

        if response.status_code >= 400:
            raise ValueError(f"Failed to download PDF. HTTP {response.status_code}.")

        payload = response.content
        if not payload:
            raise ValueError("Downloaded file is empty.")

        final_url = str(response.url)
        content_type = response.headers.get("content-type", "").lower()
        content_disposition = response.headers.get("content-disposition", "")
        return payload, final_url, content_type, content_disposition

    def _normalize_pdf_url(self, url: str) -> str:
        parsed = urlparse(url)

        if "docs.google.com" in parsed.netloc:
            # Convert Google Docs/Sheets/Slides links to PDF export URLs.
            doc_match = re.search(r"/(document|spreadsheets|presentation)/d/([^/]+)", parsed.path)
            if doc_match:
                kind, file_id = doc_match.groups()
                if kind == "document":
                    return f"https://docs.google.com/document/d/{file_id}/export?format=pdf"
                if kind == "spreadsheets":
                    return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=pdf"
                if kind == "presentation":
                    return f"https://docs.google.com/presentation/d/{file_id}/export/pdf"

        if "drive.google.com" not in parsed.netloc:
            return url

        file_match = re.search(r"/file/d/([^/]+)", parsed.path)
        if file_match:
            file_id = file_match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"

        query = parse_qs(parsed.query)
        file_id = (query.get("id") or [None])[0]
        if file_id:
            return f"https://drive.google.com/uc?export=download&id={file_id}"

        return url

    def _extract_drive_confirm_url(self, html_text: str) -> str | None:
        # Most Drive interstitial pages contain a relative confirm URL in an href.
        href_match = re.search(r'href="(/uc\?export=download[^"]+)"', html_text)
        if href_match:
            return "https://drive.google.com" + html.unescape(href_match.group(1)).replace("&amp;", "&")

        # Some pages provide a form action endpoint to proceed with download.
        action_match = re.search(r'action="(https://drive\\.usercontent\\.google\\.com/download[^"]+)"', html_text)
        if action_match:
            return html.unescape(action_match.group(1)).replace("&amp;", "&")

        return None

    def _derive_filename(self, url: str, content_disposition: str) -> str:
        from_header = self._filename_from_content_disposition(content_disposition)
        if from_header:
            return from_header

        path = urlparse(url).path
        base = unquote(os.path.basename(path)).strip()
        if base and base.lower().endswith(".pdf"):
            return base
        return "remote-document.pdf"

    def _filename_from_content_disposition(self, content_disposition: str) -> str | None:
        if not content_disposition:
            return None

        # RFC 5987 format: filename*=UTF-8''encoded-name.pdf
        extended = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, re.IGNORECASE)
        if extended:
            candidate = unquote(extended.group(1)).strip().strip('"')
            if candidate:
                return candidate

        basic = re.search(r'filename="?([^";]+)"?', content_disposition, re.IGNORECASE)
        if basic:
            candidate = basic.group(1).strip()
            if candidate:
                return candidate

        return None


document_service = DocumentService()
