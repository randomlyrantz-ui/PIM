from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.db import SessionLocal
from app.services.digest import DigestService
from app.services.ingestion import IngestionService
from app.services.llm import LLMService

scheduler = BackgroundScheduler()


def run_pipeline() -> None:
    db = SessionLocal()
    try:
        ingested = IngestionService(db).ingest_all_sources()
        processed = LLMService(db).process_unscored_articles()
        if ingested or processed:
            DigestService(db).generate_digest(days=1)
    finally:
        db.close()


def start_scheduler() -> None:
    scheduler.add_job(run_pipeline, "interval", minutes=settings.ingest_interval_minutes, id="ingestion")
    scheduler.start()
