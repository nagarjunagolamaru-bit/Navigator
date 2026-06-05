from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.document import DocumentListResponse, DocumentMetadata, DocumentUploadResponse
from app.services.document_service import document_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile | None = File(default=None),
    source_url: str | None = Form(default=None),
) -> DocumentUploadResponse:
    if file is None and not source_url:
        raise HTTPException(status_code=400, detail="Provide a PDF file or a source URL.")

    try:
        if file is not None:
            if file.content_type not in {"application/pdf", "application/x-pdf", "application/octet-stream"}:
                raise HTTPException(status_code=400, detail="Only PDF uploads are supported.")
            payload = await file.read()
            document, chunk_count = await document_service.ingest_pdf(
                filename=file.filename or "uploaded-document",
                payload=payload,
                source_url=source_url,
            )
        else:
            document, chunk_count = await document_service.ingest_pdf_from_url(source_url or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        import traceback
        error_detail = f"{exc.__class__.__name__}: {str(exc)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail) from exc

    return DocumentUploadResponse(
        document=DocumentMetadata(
            id=document.id,
            title=document.title,
            source_url=document.source_url,
            created_at=document.created_at,
        ),
        chunk_count=chunk_count,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents() -> DocumentListResponse:
    try:
        docs = await document_service.list_documents()
    except Exception as exc:
        import traceback
        error_detail = f"{exc.__class__.__name__}: {str(exc)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail) from exc
    return DocumentListResponse(
        documents=[
            DocumentMetadata(
                id=doc.id,
                title=doc.title,
                source_url=doc.source_url,
                created_at=doc.created_at,
            )
            for doc in docs
        ]
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str) -> None:
    try:
        deleted = await document_service.delete_document(document_id)
    except Exception as exc:
        import traceback
        error_detail = f"{exc.__class__.__name__}: {str(exc)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
