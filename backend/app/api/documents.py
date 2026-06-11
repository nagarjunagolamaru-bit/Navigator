from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.auth import require_admin_token, require_documents_delete_admin_token
from app.schemas.document import DocumentListResponse, DocumentMetadata, DocumentUploadResponse
from app.services.document_service import document_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    _token: str = Depends(require_admin_token),
    file: UploadFile | None = File(default=None),
    source_url: str | None = Form(default=None),
) -> DocumentUploadResponse:
    if file is None and not source_url:
        raise HTTPException(status_code=400, detail="Provide a PDF file or a source URL.")

    try:
        if file is not None:
            content_type = (file.content_type or "").lower()
            filename = (file.filename or "").lower()
            has_pdf_content_type = content_type in {"application/pdf", "application/x-pdf"}
            is_pdf_octet_stream = content_type == "application/octet-stream" and filename.endswith(".pdf")
            if not (has_pdf_content_type or is_pdf_octet_stream):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Only PDF files are supported. Please upload a .pdf file. "
                        "If you want to import from a link, use the Source URL field with a PDF URL."
                    ),
                )
            payload = await file.read()
            document, chunk_count = await document_service.ingest_pdf(
                filename=file.filename or "uploaded-document",
                payload=payload,
                source_url=source_url,
            )
        else:
            document, chunk_count = await document_service.ingest_pdf_from_url(source_url or "")
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Upload failed due to a server error. Please try again with a valid PDF.",
        ) from exc

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
async def list_documents(_token: str = Depends(require_admin_token)) -> DocumentListResponse:
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
async def delete_document(document_id: str, _token: str = Depends(require_documents_delete_admin_token)) -> None:
    try:
        deleted = await document_service.delete_document(document_id)
    except Exception as exc:
        import traceback
        error_detail = f"{exc.__class__.__name__}: {str(exc)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
