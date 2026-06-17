# Wildlife RAG API

A RAG (Retrieval-Augmented Generation) API for querying information about endangered wildlife species. Upload conservation documents (IUCN Red List assessments, WWF factsheets, CITES appendices) and ask natural language questions against them.

```
PDF/TXT → text extraction → chunking → embeddings → pgvector
                                                         ↓
answer ← Claude LLM ← prompt + retrieved chunks ← similarity search ← query embedding
```

## Quick start

```bash
# 1. Start PostgreSQL with pgvector
docker-compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# fill in ANTHROPIC_API_KEY and OPENAI_API_KEY

# 4. Run migrations
alembic upgrade head

# 5. Drop seed documents into /documents, then ingest them
python scripts/seed.py

# 6. Start the API
uvicorn app.main:app --reload
```

Interactive docs: http://localhost:8000/docs

## Example query

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the main threats facing snow leopards?", "top_k": 5}' \
  | jq .
```

```json
{
  "answer": "Snow leopards (Panthera uncia) face several major threats: habitat loss and degradation due to expanding livestock grazing, retaliatory killing by herders following livestock depredation, poaching for the illegal wildlife trade (pelts and bones used in traditional medicine), and prey depletion. Climate change is an emerging long-term threat, projected to shrink suitable high-altitude habitat by up to 30% over the coming decades.",
  "sources": [
    {
      "document": "iucn_snow_leopard.pdf",
      "chunk_index": 7,
      "relevance_score": 0.934
    }
  ]
}
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ingest` | Upload a PDF or TXT document |
| `POST` | `/query` | Ask a question against the knowledge base |
| `GET` | `/documents` | List all ingested documents |
| `DELETE` | `/documents/{id}` | Remove a document and its chunks |
| `GET` | `/health` | Health check |

## Seed documents

Place PDF or TXT files in `/documents`. Suggested sources:

- [IUCN Red List](https://www.iucnredlist.org) — species assessments
- [WWF Species Factsheets](https://www.worldwildlife.org/species)
- [CITES Appendices](https://cites.org/eng/app/appendices.php)
