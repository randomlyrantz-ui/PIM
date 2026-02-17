import pytest
from fastapi.testclient import TestClient

from app.db import Article, SessionLocal, Source
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_dashboard_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Personal Intelligence Monitor" in response.text


def test_search_endpoint(client):
    response = client.get("/search", params={"q": "AI"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_feedback_accepts_label_keep_this(client):
    db = SessionLocal()
    try:
        source = db.query(Source).first()
        if source is None:
            source = Source(name="Test Source", url="https://example.com/feed", source_type="rss")
            db.add(source)
            db.commit()
            db.refresh(source)

        article = Article(source_id=source.id, title="Test", url="https://example.com/a1", content="leadership evidence")
        db.add(article)
        db.commit()
        db.refresh(article)
    finally:
        db.close()

    response = client.post(f"/articles/{article.id}/feedback", json={"label": "keep this"})
    assert response.status_code == 200
    assert response.json()["reinforcement"] == "positive"
