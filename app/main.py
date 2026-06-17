from fastapi import FastAPI

from app.routers import documents, ingest, query

app = FastAPI(
    title="Wildlife RAG API",
    description="Ask natural language questions about endangered wildlife species.",
    version="0.1.0",
)

app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(documents.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
