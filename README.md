# smart-engine

The goal of this project is to become an event-driven smart notification engine.

Core idea:

- ingest behavior and donation events from other services
- convert event context into vectors (embeddings)
- store and search those vectors in a vector database
- match new donations with user interests
- publish notification commands for matched users

Current state:

- the service is intentionally minimal
- the codebase structure is prepared for adding models, schemas, and services as the engine grows

## Tech Stack

- Python 3.11+
- FastAPI
- Uvicorn
- uv (dependency and environment management)

## Requirements

- Python 3.11 or newer
- `uv` installed

Install `uv` (if needed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Run Locally

```bash
uv sync
uv run uvicorn app.main:app --reload
```

App URL:

- http://127.0.0.1:8000

## API

### Health Check

- `GET /health`
- Response: `204 No Content`

Quick test:

```bash
curl -i http://127.0.0.1:8000/health
```
## Next Step

When you’re ready, this base can be extended with:

- event consumers (Redis Pub/Sub)
- vector storage/search
- notification matching workflows


