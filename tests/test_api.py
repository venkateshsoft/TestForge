from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload() -> dict:
    return {
        "title": "Duplicate patient registration",
        "description": "Two simultaneous requests must create only one logical patient record.",
        "domain": "API",
        "language": "Python",
        "framework": "pytest + Requests",
        "environment": "test",
        "authentication": "environment variable",
        "generation_mode": "Generate a complete automation framework",
    }


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.json()["status"] == "ok"
    assert response.headers["x-request-id"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_generate_validate_and_download(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TESTFORGE_DATA_DIR", str(tmp_path))
    response = client.post("/api/v1/generations", json=payload())
    assert response.status_code == 201
    body = response.json()
    assert body["interpretation"]["assumptions"]
    assert any(item["path"] == "tests/conftest.py" for item in body["files"])
    generation_id = body["id"]
    validated = client.post(f"/api/v1/projects/{generation_id}/validate")
    assert validated.status_code == 200
    assert validated.json()["validation"]["status"] == "passed"
    archive = client.get(f"/api/v1/projects/{generation_id}/download")
    assert archive.status_code == 200
    assert archive.headers["content-type"] == "application/zip"


def test_secret_like_input_is_rejected() -> None:
    bad = payload() | {"description": "password=super-secret should never be submitted to AI"}
    assert client.post("/api/v1/generations", json=bad).status_code == 422
