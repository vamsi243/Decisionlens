from fastapi.testclient import TestClient

from service.main import app


def test_health() -> None:
    res = TestClient(app).get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_hello() -> None:
    res = TestClient(app).get("/")
    assert "Decision Lens" in res.json()["message"]
