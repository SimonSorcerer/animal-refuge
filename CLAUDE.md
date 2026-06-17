# Wildlife RAG — Claude Code Instructions

## Project overview

A RAG (Retrieval-Augmented Generation) API that lets users ask natural language questions about endangered wildlife species. The knowledge base is seeded from public conservation documents (IUCN Red List assessments, WWF species factsheets, CITES appendices). Built with FastAPI + PostgreSQL + pgvector + Anthropic/OpenAI embeddings.

This is a portfolio project. Code should be clean, well-structured, and README-friendly.

---

## Tech stack

- **Python 3.12+**
- **FastAPI** — API framework
- **PostgreSQL + pgvector** — vector storage and similarity search
- **SQLAlchemy 2.x** (async) — ORM
- **Alembic** — migrations
- **Anthropic SDK** — embeddings + LLM responses (prefer `claude-sonnet-4-6` for chat, `voyage-3` or OpenAI `text-embedding-3-small` for embeddings)
- **pdfplumber or pypdf** — PDF text extraction
- **Docker + docker-compose** — local dev environment

---

## Project structure

```
wildlife-rag/
├── app/
│   ├── main.py               # FastAPI app entrypoint
│   ├── config.py             # Settings via pydantic-settings
│   ├── database.py           # Async SQLAlchemy engine + session
│   ├── models/
│   │   ├── document.py       # Document ORM model
│   │   └── chunk.py          # Chunk ORM model with vector column
│   ├── routers/
│   │   ├── ingest.py         # POST /ingest endpoint
│   │   └── query.py          # POST /query endpoint
│   ├── services/
│   │   ├── chunker.py        # Text splitting logic
│   │   ├── embedder.py       # Embedding generation
│   │   └── retriever.py      # pgvector similarity search
│   └── prompts/
│       └── qa.py             # LLM prompt templates
├── alembic/                  # DB migrations
├── documents/                # Seed documents (PDFs, txt)
├── scripts/
│   └── seed.py               # Script to ingest seed documents
├── tests/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
└── README.md
```

---

## Data model

```sql
-- documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    source TEXT,           -- e.g. "IUCN", "WWF", "CITES"
    uploaded_at TIMESTAMPTZ DEFAULT now()
);

-- chunks table
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding vector(1536),   -- dimension matches embedding model
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops);
```

---

## API endpoints

### POST /ingest

Upload a document file (PDF or txt). The service:

1. Extracts text
2. Splits into chunks (~500 tokens, ~50 token overlap)
3. Generates embeddings for each chunk
4. Stores document + chunks in PostgreSQL

Request: `multipart/form-data` with `file` and optional `source` field.

Response:

```json
{
    "document_id": "uuid",
    "filename": "iucn_giraffe.pdf",
    "chunks_created": 42
}
```

### POST /query

Ask a natural language question.

Request:

```json
{
    "question": "Which big cat species are critically endangered and what are the main threats?",
    "top_k": 5
}
```

Response:

```json
{
    "answer": "...",
    "sources": [
        {
            "document": "iucn_felidae.pdf",
            "chunk_index": 12,
            "relevance_score": 0.91
        }
    ]
}
```

### GET /documents

List all ingested documents.

### DELETE /documents/{id}

Remove a document and all its chunks.

---

## RAG pipeline detail

**Chunking strategy:**

- Split on paragraphs first, then by token count
- Preserve sentence boundaries — do not cut mid-sentence
- Include ~50 token overlap between adjacent chunks to avoid context loss at boundaries

**Embedding:**

- Use the same model for ingestion and query — never mix models
- Embed the raw chunk content (no metadata prefix needed at MVP)

**Retrieval:**

- Cosine similarity search via pgvector
- Return top_k=5 chunks by default
- Include the source document name and chunk index in results

**Prompt construction:**

```
You are a wildlife conservation assistant. Answer the user's question using only the context provided below. If the answer is not contained in the context, say so clearly — do not hallucinate.

Context:
{retrieved_chunks}

Question: {user_question}

Answer:
```

---

## Seed documents

Place seed documents in `/documents`. Suggested sources:

- IUCN Red List species assessments (PDF) — https://www.iucnredlist.org
- WWF species factsheets — https://www.worldwildlife.org/species
- CITES appendices — https://cites.org/eng/app/appendices.php

Cover a range of taxonomic groups: mammals, birds, reptiles, marine species. Aim for 10–20 documents for a meaningful demo.

---

## Local dev setup

```bash
# Start PostgreSQL with pgvector
docker-compose up -d

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Seed documents
python scripts/seed.py

# Start API
uvicorn app.main:app --reload
```

`docker-compose.yml` should use `pgvector/pgvector:pg16` image.

---

## Environment variables (.env.example)

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/wildlife_rag
ANTHROPIC_API_KEY=
OPENAI_API_KEY=          # optional, for embeddings if using OpenAI
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
LLM_MODEL=claude-sonnet-4-6
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

---

## Code style

- Type hints everywhere
- Async throughout (async SQLAlchemy, async FastAPI endpoints)
- Pydantic v2 for request/response models
- No business logic in routers — delegate to services
- Keep prompts in `app/prompts/` not inline in route handlers
- `.env` via `pydantic-settings` — no hardcoded config

---

## README requirements

The README should include:

- One-paragraph project description
- Architecture diagram or simple ASCII flow: `PDF → chunks → embeddings → pgvector → query → LLM → answer`
- Example query and response (use giraffes or snow leopards — visually compelling)
- Quick start instructions
- Screenshot or `curl` example if no frontend

---

## Out of scope for MVP

- Authentication
- Frontend UI (API only)
- Streaming responses
- Multi-turn conversation / chat history
- Re-ranking retrieved chunks
- Hybrid search (keyword + vector)

These can be added incrementally but should not block the first working version.
