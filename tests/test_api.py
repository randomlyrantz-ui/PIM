from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app


init_db()
client = TestClient(app)


def test_dashboard_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "Personal Intelligence Monitor" in response.text


def test_search_endpoint():
    response = client.get("/search", params={"q": "AI"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
