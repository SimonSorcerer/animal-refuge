import json

import anthropic
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.prompts.qa import SYSTEM_PROMPT, build_user_message
from app.services.retriever import retrieve

router = APIRouter(prefix="/query", tags=["query"])

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


class QueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)


class SourceRef(BaseModel):
    document: str
    chunk_index: int
    relevance_score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceRef]


@router.post("", response_model=QueryResponse)
async def query_knowledge_base(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    hits = await retrieve(body.question, db, top_k=body.top_k)

    if not hits:
        return QueryResponse(
            answer="I don't have any relevant information in the knowledge base to answer that question.",
            sources=[],
        )

    message = await _client.messages.create(
        model=settings.llm_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message([h["content"] for h in hits], body.question)}],
    )

    answer = message.content[0].text if message.content else ""

    return QueryResponse(
        answer=answer,
        sources=[
            SourceRef(
                document=h["document"],
                chunk_index=h["chunk_index"],
                relevance_score=h["relevance_score"],
            )
            for h in hits
        ],
    )


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("/stream")
async def query_stream(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    hits = await retrieve(body.question, db, top_k=body.top_k)

    async def generate():
        if not hits:
            yield _sse({"type": "delta", "text": "I don't have any relevant information in the knowledge base to answer that question."})
            yield _sse({"type": "sources", "sources": []})
            yield _sse({"type": "done"})
            return

        sources = [
            {"document": h["document"], "chunk_index": h["chunk_index"], "relevance_score": h["relevance_score"]}
            for h in hits
        ]
        yield _sse({"type": "sources", "sources": sources})

        try:
            async with _client.messages.stream(
                model=settings.llm_model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_message([h["content"] for h in hits], body.question)}],
            ) as stream:
                async for text in stream.text_stream:
                    yield _sse({"type": "delta", "text": text})
        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})

        yield _sse({"type": "done"})

    return StreamingResponse(generate(), media_type="text/event-stream")
