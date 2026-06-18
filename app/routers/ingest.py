import hashlib
import io
import uuid

import pdfplumber
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunker import split_into_chunks
from app.services.embedder import embed_texts

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    chunks_created: int


class IngestTextRequest(BaseModel):
    content: str
    filename: str
    source: str = ""


def _extract_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
    return data.decode("utf-8", errors="replace")


@router.post("", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    source: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    file_hash = hashlib.sha256(data).hexdigest()
    existing = await db.execute(select(Document).where(Document.file_hash == file_hash))
    duplicate = existing.scalar_one_or_none()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"Document already ingested as '{duplicate.filename}' (id: {duplicate.id}).",
        )

    raw_text = _extract_text(file.filename or "upload", data)
    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from the file.")

    document = Document(filename=file.filename or "upload", source=source or None, file_hash=file_hash)
    db.add(document)
    await db.flush()

    chunks_text = split_into_chunks(raw_text)
    if not chunks_text:
        raise HTTPException(status_code=422, detail="Document produced no chunks after splitting.")

    embeddings = await embed_texts(chunks_text)

    for idx, (content, embedding) in enumerate(zip(chunks_text, embeddings)):
        db.add(
            Chunk(
                document_id=document.id,
                content=content,
                chunk_index=idx,
                embedding=embedding,
            )
        )

    await db.commit()

    return IngestResponse(
        document_id=document.id,
        filename=document.filename,
        chunks_created=len(chunks_text),
    )


@router.post("/text", response_model=IngestResponse)
async def ingest_text(
    body: IngestTextRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    data = body.content.encode("utf-8")
    file_hash = hashlib.sha256(data).hexdigest()
    existing = await db.execute(select(Document).where(Document.file_hash == file_hash))
    duplicate = existing.scalar_one_or_none()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"Document already ingested as '{duplicate.filename}' (id: {duplicate.id}).",
        )

    if not body.content.strip():
        raise HTTPException(status_code=422, detail="Content is empty.")

    document = Document(filename=body.filename, source=body.source or None, file_hash=file_hash)
    db.add(document)
    await db.flush()

    chunks_text = split_into_chunks(body.content)
    if not chunks_text:
        raise HTTPException(status_code=422, detail="Document produced no chunks after splitting.")

    embeddings = await embed_texts(chunks_text)

    for idx, (content, embedding) in enumerate(zip(chunks_text, embeddings)):
        db.add(
            Chunk(
                document_id=document.id,
                content=content,
                chunk_index=idx,
                embedding=embedding,
            )
        )

    await db.commit()

    return IngestResponse(
        document_id=document.id,
        filename=document.filename,
        chunks_created=len(chunks_text),
    )
