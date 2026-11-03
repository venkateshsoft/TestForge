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


def test_telecom_cnf_requirement_generates_domain_aware_coverage(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TESTFORGE_DATA_DIR", str(tmp_path))
    telecom = payload() | {
        "title": "Nokia CNF rolling upgrade",
        "description": (
            "Validate a Nokia CNF rolling upgrade through Helm and Kubernetes. Verify pod readiness "
            "and liveness probes, rolling deployment status, traffic continuity through Envoy routing, "
            "subscriber session consistency, pod failure and recovery, performance and scalability, "
            "rollback, regression, monitoring, logs, metrics and tracing."
        ),
        "domain": "Kubernetes / Cloud Native",
    }
    response = client.post("/api/v1/generations", json=telecom)
    assert response.status_code == 201
    body = response.json()
    titles = {case["title"] for case in body["test_cases"]}
    assert len(titles) == body["coverage_summary"]["total_scenarios"]
    assert body["coverage_summary"]["total_scenarios"] >= 8
    for expected in (
        "Validate Helm lifecycle",
        "Validate readiness and liveness probes",
        "Validate rolling deployment",
        "Verify traffic continuity",
        "Validate pod failure and recovery",
        "Validate Envoy traffic routing",
        "Validate performance and scalability",
        "Validate rollback",
        "Run regression coverage",
        "Validate monitoring and observability",
    ):
        assert expected in titles
    assert all(case["requirement"] and case["validation_evidence"] for case in body["test_cases"])
    assert any("specs/scenario_matrix.md" == item["path"] for item in body["files"])


def test_narrow_api_requirement_does_not_get_infrastructure_scenarios(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TESTFORGE_DATA_DIR", str(tmp_path))
    narrow = payload() | {
        "title": "Read-only user lookup",
        "description": "Validate that a documented API request returns the expected response.",
        "domain": "API",
    }
    response = client.post("/api/v1/generations", json=narrow)
    assert response.status_code == 201
    body = response.json()
    assert body["coverage_summary"]["total_scenarios"] == 2
    assert all(case["category"] in {"Functional", "API validation"} for case in body["test_cases"])
