import pytest
from fastapi.testclient import TestClient

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
