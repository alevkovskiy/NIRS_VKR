from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import main

client = TestClient(main.app)


def test_liveness():
    assert client.get("/health/live").json() == {"status": "ok"}


def test_readiness_hides_connection_details(monkeypatch):
    def unavailable():
        raise OperationalError("secret connection details", {}, Exception())

    monkeypatch.setattr(main, "get_engine", unavailable)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_readiness_with_postgres(session):
    # The fixture skips this check unless a migrated test database is configured.
    assert client.get("/health/ready").status_code == 200
