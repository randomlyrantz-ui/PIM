# Personal Intelligence Monitor (PIM)

Self-hosted Feedly+Leo style system for ingesting sources, scoring relevance across custom domains, summarizing with AI, and generating digest files.

## Features (V1)
- RSS/Atom + webpage ingestion with dedup by URL.
- Seeded domain model and source list from spec.
- Relevance scoring + summarization (OpenAI when configured, keyword fallback otherwise).
- Daily digest markdown generation with domain grouping, contrarian section, emerging-pattern placeholder.
- FastAPI dashboard for source/domain management and article review.
- Feedback capture (thumbs up/down), save article flag, full text search.
- APScheduler background pipeline.
- SQLite default, Docker Compose support.

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://localhost:8000.

## Config
Environment variables (`PIM_` prefix):
- `PIM_DATABASE_URL` (default `sqlite:///./pim.db`)
- `PIM_INGEST_INTERVAL_MINUTES` (default `60`)
- `PIM_DIGEST_OUTPUT_DIR` (default `sample_output`)
- `PIM_OPENAI_API_KEY` (optional)
- `PIM_OPENAI_MODEL` (default `gpt-4o-mini`)

## API highlights
- `POST /run/ingest`
- `POST /run/score`
- `POST /run/digest`
- `GET /articles`
- `GET /search?q=...`
- `POST /articles/{id}/feedback`

## Docker
```bash
docker compose up --build
```

## Seed data
- 13 initial source URLs.
- 6 initial topic domains with predefined keywords.

## Sample digest output
See `sample_output/sample_digest.md`.
