import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import Article, Domain, Feedback, Source, get_db, init_db
from app.schemas import DomainCreate, FeedbackCreate, SourceCreate, SourceRead
from app.seed_data import SEED_DOMAINS, SEED_SOURCES
from app.services.digest import DigestService
from app.services.ingestion import IngestionService
from app.services.llm import LLMService
from app.services.scheduler import scheduler, start_scheduler

logger = logging.getLogger(__name__)


def seed_defaults() -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        if db.query(Source).count() == 0:
            for name, url in SEED_SOURCES:
                source_type = IngestionService(db).detect_source_type(url)
                db.add(Source(name=name, url=url, source_type=source_type))
        if db.query(Domain).count() == 0:
            for domain in SEED_DOMAINS:
                db.add(Domain(name=domain["name"], description=domain["description"], keywords=", ".join(domain["keywords"])))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    seed_defaults()
    start_scheduler()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="PIM", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    articles = db.query(Article).order_by(Article.created_at.desc()).limit(20).all()
    domains = db.query(Domain).all()
    sources = db.query(Source).all()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "articles": articles,
            "domains": domains,
            "sources": sources,
        },
    )


@app.post("/sources", response_model=SourceRead)
def add_source(payload: SourceCreate, db: Session = Depends(get_db)):
    source_type = IngestionService(db).detect_source_type(payload.url)
    source = Source(name=payload.name, url=payload.url, source_type=source_type)
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@app.post("/domains")
def add_domain(payload: DomainCreate, db: Session = Depends(get_db)):
    domain = Domain(name=payload.name, description=payload.description, keywords=", ".join(payload.keywords))
    db.add(domain)
    db.commit()
    return {"status": "ok"}


@app.get("/articles")
def list_articles(db: Session = Depends(get_db)):
    output = []
    for article in db.query(Article).order_by(Article.created_at.desc()).all():
        output.append(
            {
                "id": article.id,
                "title": article.title,
                "url": article.url,
                "summary": article.summary,
                "stance": article.stance,
                "source": article.source.name,
                "published_at": article.published_at,
            }
        )
    return output


@app.post("/run/ingest")
def run_ingest(db: Session = Depends(get_db)):
    added = IngestionService(db).ingest_all_sources()
    return {"added": added}


@app.post("/run/score")
def run_scoring(db: Session = Depends(get_db)):
    processed = LLMService(db).process_unscored_articles()
    return {"processed": processed}


@app.post("/run/digest")
def run_digest(db: Session = Depends(get_db)):
    file_path = DigestService(db).generate_digest(days=1)
    return {"digest_file": file_path}


@app.post("/articles/{article_id}/save")
def save_article(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404)
    article.saved = True
    db.commit()
    return {"status": "saved"}


@app.post("/articles/{article_id}/feedback")
def feedback(article_id: int, payload: FeedbackCreate, db: Session = Depends(get_db)):
    if not db.get(Article, article_id):
        raise HTTPException(404)

    positive = payload.positive
    if positive is None and payload.label:
        label = payload.label.strip().lower()
        if label == "keep this":
            positive = True
        elif label == "discard this":
            positive = False

    if positive is None:
        raise HTTPException(status_code=400, detail="Provide positive=true|false or label='keep this'/'discard this'.")

    db.add(Feedback(article_id=article_id, positive=positive))
    db.commit()
    return {"status": "recorded", "reinforcement": "positive" if positive else "negative"}


@app.get("/search")
def search(q: str, db: Session = Depends(get_db)):
    rows = (
        db.query(Article)
        .filter((Article.title.contains(q)) | (Article.content.contains(q)) | (Article.summary.contains(q)))
        .order_by(Article.created_at.desc())
        .all()
    )
    return [{"id": a.id, "title": a.title, "url": a.url} for a in rows]


@app.post("/sources/add", response_class=HTMLResponse)
def add_source_form(name: str = Form(...), url: str = Form(...), db: Session = Depends(get_db)):
    source_type = IngestionService(db).detect_source_type(url)
    db.add(Source(name=name, url=url, source_type=source_type))
    db.commit()
    return "<p>Source added. <a href='/'>Back</a></p>"


@app.post("/domains/add", response_class=HTMLResponse)
def add_domain_form(name: str = Form(...), description: str = Form(...), keywords: str = Form(""), db: Session = Depends(get_db)):
    db.add(Domain(name=name, description=description, keywords=keywords))
    db.commit()
    return "<p>Domain added. <a href='/'>Back</a></p>"
