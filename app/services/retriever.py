from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document
from app.services.embedder import embed_query


async def retrieve(
    question: str,
    db: AsyncSession,
    top_k: int = 5,
) -> list[dict]:
    query_embedding = await embed_query(question)

    stmt = (
        select(
            Chunk.content,
            Chunk.chunk_index,
            Document.filename,
            (1 - Chunk.embedding.cosine_distance(query_embedding)).label("score"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.embedding.is_not(None))
        .order_by(text("score DESC"))
        .limit(top_k)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "content": row.content,
            "chunk_index": row.chunk_index,
            "document": row.filename,
            "relevance_score": round(float(row.score), 4),
        }
        for row in rows
    ]
