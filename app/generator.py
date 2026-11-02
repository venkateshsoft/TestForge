from __future__ import annotations

import os
import re

from .models import (
    Domain,
    GeneratedFile,
    RequirementInterpretation,
    ScenarioRequest,
    StoredGeneration,
    TestCase,
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:48] or "scenario"


def _infer_sut(request: ScenarioRequest) -> str:
    if request.domain == Domain.HEALTHCARE:
        return "Healthcare PMS / RCM workflow and its integrated services"
    if request.domain == Domain.KUBERNETES:
        return "Cloud-native service deployed on Kubernetes"
    return request.title


def analyze(request: ScenarioRequest) -> tuple[RequirementInterpretation, list[TestCase]]:
    description = request.description.lower()
    concurrent = any(word in description for word in ("concurrent", "simultaneous", "race"))
    duplicate = any(word in description for word in ("duplicate", "idempotency", "same patient"))
    resilience = any(word in description for word in ("retry", "timeout", "resilience", "unavailable"))

    cases = [
        TestCase(
            id="TF-001",
            title="Validate registration happy path",
            category="Positive",
            priority="High",
            preconditions=["Documented API contract and non-production test environment are configured"],
            steps=["Submit configured valid payload", "Assert documented success status", "Validate JSON response"],
            expected="Registration returns a configured success status and a valid response body.",
        ),
        TestCase(
            id="TF-002",
            title="Reject invalid registration input",
            category="Negative",
            priority="High",
            preconditions=["Invalid payload and expected client-error statuses are configured"],
            steps=["Submit configured invalid payload", "Assert documented client-error status"],
            expected="Invalid input is rejected with a configured client-error status.",
        ),
    ]
    if duplicate or concurrent:
        cases.append(
            TestCase(
                id="TF-003",
                title="Verify concurrent duplicate registration",
                category="Concurrency",
                priority="Critical",
                preconditions=[
                    "Registration payload, identity field, and read-back endpoint are configured"
                ],
                steps=[
                    "Send identical requests concurrently",
                    "Validate response statuses",
                    "Read records by logical identity",
                    "Assert exactly one matching record exists",
                ],
                expected="Concurrent duplicate submissions result in exactly one logical record.",
            )
        )
    if resilience:
        cases.append(
            TestCase(
                id="TF-004",
                title="Verify configured timeout behavior",
                category="Resilience",
                priority="Medium",
                preconditions=["Timeout contract and test endpoint are configured"],
                steps=["Send request with configured timeout", "Assert documented timeout/response behavior"],
                expected="Timeout handling follows the configured contract; retry policy requires a separately documented test.",
            )
        )

    interpretation = RequirementInterpretation(
        objective=f"Validate: {request.title}",
        system_under_test=_infer_sut(request),
        facts=[request.description],
        assumptions=[
            "Endpoints, payloads, credentials, expected statuses, and identity fields must come from the real API contract.",
            "Concurrency verification requires a read-back endpoint that accurately reflects persisted records.",
            "Tests use synthetic data in a non-production environment.",
        ],
        acceptance_criteria=[
            "Configured HTTP statuses are asserted explicitly.",
            "Unexpected status codes and malformed JSON produce actionable failures.",
            "Concurrency tests verify the logical-record count through a configured read-back endpoint.",
            "No credentials are embedded in generated source.",
        ],
        risks=[
            "The scenario does not provide a verified API schema or endpoint catalog.",
            "Cross-pod routing cannot be proven without routing/observability configuration.",
        ],
        open_questions=[
            "What are the registration endpoint, payload, authentication method, and response schema?",
            "How can the persisted patient be queried by its logical identity?",
            "Which status codes are documented for success, duplicate requests, and invalid input?",
        ],
    )
    return interpretation, cases


def _test_source(cases: list[TestCase]) -> str:
    parts = [r'''from __future__ import annotations

import json
import os


def _status_codes(name: str, default: str) -> set[int]:
    import pytest
    try:
        result = {int(x.strip()) for x in os.getenv(name, default).split(",") if x.strip()}
    except ValueError as exc:
        pytest.fail(f"{name} must contain comma-separated HTTP status codes: {exc}")
    if not result:
        pytest.fail(f"{name} must contain at least one status code")
    return result


def _path(value, dotted_path: str):
    current = value
    for part in dotted_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
        else:
            return None
    return current


def _payload(name: str):
    import pytest
    raw = os.getenv(name)
    if not raw:
        pytest.skip(f"Set {name} using the documented API contract")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.fail(f"{name} must contain valid JSON: {exc}")


def _json_if_present(response):
    import pytest
    if response.content:
        try:
            response.json()
        except ValueError as exc:
            pytest.fail(f"Expected JSON response: {response.text[:500]} ({exc})")


''']
    categories = {case.category for case in cases}
    if "Positive" in categories:
        parts.append(r'''def test_registration_happy_path(api_client):
    import pytest
    endpoint = os.getenv("TESTFORGE_REGISTER_ENDPOINT")
    if not endpoint:
        pytest.skip("Set TESTFORGE_REGISTER_ENDPOINT from the API contract")
    payload = _payload("TESTFORGE_REGISTER_PAYLOAD_JSON")
    expected = _status_codes("TESTFORGE_SUCCESS_STATUS_CODES", "200,201")
    response = api_client.post(endpoint, json=payload)
    assert response.status_code in expected, (
        f"Expected {sorted(expected)}, got {response.status_code}: {response.text[:1000]}"
    )
    _json_if_present(response)


''')
    if "Negative" in categories:
        parts.append(r'''def test_invalid_registration_is_rejected(api_client):
    import pytest
    endpoint = os.getenv("TESTFORGE_REGISTER_ENDPOINT")
    if not endpoint:
        pytest.skip("Set TESTFORGE_REGISTER_ENDPOINT from the API contract")
    payload = _payload("TESTFORGE_INVALID_PAYLOAD_JSON")
    expected = _status_codes("TESTFORGE_CLIENT_ERROR_STATUS_CODES", "400,422")
    response = api_client.post(endpoint, json=payload)
    assert response.status_code in expected, (
        f"Expected client error {sorted(expected)}, got {response.status_code}: "
        f"{response.text[:1000]}"
    )


''')
    if "Concurrency" in categories:
        parts.append(r'''def test_concurrent_duplicate_registration_creates_one_record(api_client):
    from concurrent.futures import ThreadPoolExecutor
    import pytest

    endpoint = os.getenv("TESTFORGE_REGISTER_ENDPOINT")
    lookup_endpoint = os.getenv("TESTFORGE_LOOKUP_ENDPOINT")
    identity_path = os.getenv("TESTFORGE_IDENTITY_PATH")
    records_path = os.getenv("TESTFORGE_LOOKUP_RECORDS_PATH")
    record_identity_path = os.getenv("TESTFORGE_LOOKUP_IDENTITY_FIELD")
    missing = [key for key, value in {
        "TESTFORGE_REGISTER_ENDPOINT": endpoint,
        "TESTFORGE_LOOKUP_ENDPOINT": lookup_endpoint,
        "TESTFORGE_IDENTITY_PATH": identity_path,
        "TESTFORGE_LOOKUP_RECORDS_PATH": records_path,
        "TESTFORGE_LOOKUP_IDENTITY_FIELD": record_identity_path,
    }.items() if not value]
    if missing:
        pytest.skip("Configure API contract settings: " + ", ".join(missing))

    payload = _payload("TESTFORGE_REGISTER_PAYLOAD_JSON")
    identity = _path(payload, identity_path)
    if identity in (None, ""):
        pytest.fail(f"TESTFORGE_IDENTITY_PATH={identity_path!r} not found in request payload")
    workers = int(os.getenv("TESTFORGE_CONCURRENCY_WORKERS", "8"))
    if workers < 2 or workers > 100:
        pytest.fail("TESTFORGE_CONCURRENCY_WORKERS must be between 2 and 100")
    accepted = _status_codes("TESTFORGE_CONCURRENT_ACCEPTED_STATUS_CODES", "200,201,409")

    def send():
        session = api_client.new_session()
        url = f"{api_client.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        timeout = float(os.getenv("TESTFORGE_TIMEOUT_SECONDS", "10"))
        return session.post(url, json=payload, timeout=timeout)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        responses = list(pool.map(lambda _: send(), range(workers)))
    unexpected = [(r.status_code, r.text[:300]) for r in responses if r.status_code not in accepted]
    assert not unexpected, f"Unexpected response(s); accepted={sorted(accepted)}: {unexpected[:3]}"

    lookup = api_client.get(
        lookup_endpoint,
        params={os.getenv("TESTFORGE_LOOKUP_QUERY_PARAM", "identity"): identity},
    )
    assert lookup.status_code == 200, (
        f"Read-back lookup failed: {lookup.status_code}: {lookup.text[:1000]}"
    )
    try:
        body = lookup.json()
    except ValueError as exc:
        pytest.fail(f"Lookup endpoint did not return JSON: {exc}")
    records = _path(body, records_path)
    if isinstance(records, dict):
        records = [records]
    assert isinstance(records, list), "TESTFORGE_LOOKUP_RECORDS_PATH must resolve to a list or record"
    matches = [item for item in records if _path(item, record_identity_path) == identity]
    assert len(matches) == 1, (
        f"Expected exactly one logical record for {identity!r}, found {len(matches)}. "
        "Check the lookup response paths and endpoint behavior."
    )


''')
    if "Resilience" in categories:
        parts.append(r'''def test_registration_timeout_behavior(api_client):
    import requests
    import pytest
    endpoint = os.getenv("TESTFORGE_REGISTER_ENDPOINT")
    if not endpoint:
        pytest.skip("Set TESTFORGE_REGISTER_ENDPOINT from the API contract")
    payload = _payload("TESTFORGE_REGISTER_PAYLOAD_JSON")
    timeout = float(os.getenv("TESTFORGE_TIMEOUT_SECONDS", "10"))
    if os.getenv("TESTFORGE_EXPECT_TIMEOUT", "false").lower() == "true":
        with pytest.raises(requests.Timeout):
            api_client.post(endpoint, json=payload, timeout=timeout)
    else:
        response = api_client.post(endpoint, json=payload, timeout=timeout)
        assert response.status_code < 500, (
            f"Unexpected server error {response.status_code}: {response.text[:1000]}"
        )


''')
    return "".join(parts)


def build_files(
    request: ScenarioRequest,
    interpretation: RequirementInterpretation,
    cases: list[TestCase],
) -> list[GeneratedFile]:
    slug = _slug(request.title)
    readme = f'''# TestForge generated project

## Scenario
{request.description}

## Configuration
Use synthetic data and a non-production environment. The generator does not invent undocumented API paths,
payload fields, or response contracts. Set the variables below from the real API documentation.

The concurrency test sends identical requests through independent HTTP sessions, then queries a configured
read-back endpoint and asserts exactly one matching logical record. This does not prove requests reached
different Kubernetes pods; pod routing or observability must be configured separately.

## Setup (PowerShell)
```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Key variables
- `TESTFORGE_REGISTER_ENDPOINT`: registration API path.
- `TESTFORGE_REGISTER_PAYLOAD_JSON`: valid synthetic request body as JSON.
- `TESTFORGE_SUCCESS_STATUS_CODES`: success statuses, default `200,201`.
- `TESTFORGE_INVALID_PAYLOAD_JSON`: invalid request body.
- `TESTFORGE_CLIENT_ERROR_STATUS_CODES`: client-error statuses, default `400,422`.
- `TESTFORGE_LOOKUP_ENDPOINT`: read-back endpoint for persisted records.
- `TESTFORGE_IDENTITY_PATH`: dotted path to logical identity in registration payload.
- `TESTFORGE_LOOKUP_RECORDS_PATH`: dotted path to record/list in lookup response.
- `TESTFORGE_LOOKUP_IDENTITY_FIELD`: dotted path to identity field within each returned record.
- `TESTFORGE_LOOKUP_QUERY_PARAM`: lookup query parameter, default `identity`.
- `TESTFORGE_CONCURRENCY_WORKERS`: concurrent requests, default `8`.
- `TESTFORGE_CONCURRENT_ACCEPTED_STATUS_CODES`: accepted concurrency statuses, default `200,201,409`.
- `TESTFORGE_BASE_URL`, `TESTFORGE_TOKEN`, `TESTFORGE_TIMEOUT_SECONDS`: connection settings.

## Run
```powershell
python -m pytest -v
```

Tests lacking required configuration are skipped with an explicit explanation. Configured tests perform HTTP requests
and assert the documented status and record-count expectations.
'''
    env_example = '''TESTFORGE_BASE_URL=http://localhost:8000
TESTFORGE_TOKEN=
TESTFORGE_TIMEOUT_SECONDS=10
TESTFORGE_REGISTER_ENDPOINT=
TESTFORGE_REGISTER_PAYLOAD_JSON=
TESTFORGE_SUCCESS_STATUS_CODES=200,201
TESTFORGE_INVALID_PAYLOAD_JSON=
TESTFORGE_CLIENT_ERROR_STATUS_CODES=400,422
TESTFORGE_LOOKUP_ENDPOINT=
TESTFORGE_IDENTITY_PATH=
TESTFORGE_LOOKUP_RECORDS_PATH=
TESTFORGE_LOOKUP_IDENTITY_FIELD=
TESTFORGE_LOOKUP_QUERY_PARAM=identity
TESTFORGE_CONCURRENCY_WORKERS=8
TESTFORGE_CONCURRENT_ACCEPTED_STATUS_CODES=200,201,409
TESTFORGE_EXPECT_TIMEOUT=false
'''
    return [
        GeneratedFile(path="README.md", content=readme),
        GeneratedFile(path="requirements.txt", content="pytest>=8.3,<9\nrequests>=2.32,<3\npython-dotenv>=1.0,<2\n"),
        GeneratedFile(path=".env.example", content=env_example),
        GeneratedFile(path="config/settings.py", content=(
            "from __future__ import annotations\nimport os\n\n"
            "from dotenv import load_dotenv\n\n"
            "load_dotenv()\n\n"
            'BASE_URL = os.getenv("TESTFORGE_BASE_URL", "http://localhost:8000").rstrip("/")\n'
            'TOKEN = os.getenv("TESTFORGE_TOKEN")\n'
            'TIMEOUT_SECONDS = float(os.getenv("TESTFORGE_TIMEOUT_SECONDS", "10"))\n'
        )),
        GeneratedFile(path="clients/api_client.py", content=(
            "from __future__ import annotations\nimport requests\n"
            "from config.settings import BASE_URL, TIMEOUT_SECONDS, TOKEN\n\n"
            "class ApiClient:\n"
            "    def __init__(self, base_url: str = BASE_URL) -> None:\n"
            "        self.base_url = base_url.rstrip('/')\n"
            "        self.session = self.new_session()\n\n"
            "    def new_session(self) -> requests.Session:\n"
            "        session = requests.Session()\n"
            "        if TOKEN:\n"
            "            session.headers.update({'Authorization': f'Bearer {TOKEN}'})\n"
            "        return session\n\n"
            "    def _url(self, path: str) -> str:\n"
            "        return f'{self.base_url}/{path.lstrip(\"/\")}'\n\n"
            "    def get(self, path: str, **kwargs) -> requests.Response:\n"
            "        timeout = kwargs.pop('timeout', TIMEOUT_SECONDS)\n"
            "        return self.session.get(self._url(path), timeout=timeout, **kwargs)\n\n"
            "    def post(self, path: str, json: dict, **kwargs) -> requests.Response:\n"
            "        timeout = kwargs.pop('timeout', TIMEOUT_SECONDS)\n"
            "        return self.session.post(self._url(path), json=json, timeout=timeout, **kwargs)\n"
        )),
        GeneratedFile(path="tests/conftest.py", content=(
            "import pytest\nfrom clients.api_client import ApiClient\n\n"
            "@pytest.fixture\n"
            "def api_client() -> ApiClient:\n"
            "    return ApiClient()\n"
        )),
        GeneratedFile(path=f"tests/api/test_{slug}.py", content=_test_source(cases)),
        GeneratedFile(path="pyproject.toml", content=(
            "[tool.pytest.ini_options]\naddopts = \"-ra\"\ntestpaths = [\"tests\"]\n\n"
            "[tool.ruff]\nline-length = 100\n"
        )),
        GeneratedFile(path=".gitignore", content=".env\n.venv/\n.pytest_cache/\n__pycache__/\nreports/*\n!reports/.gitkeep\n"),
        GeneratedFile(path="reports/.gitkeep", content=""),
    ]


def generate(request: ScenarioRequest) -> StoredGeneration:
    interpretation, cases = analyze(request)

    return StoredGeneration(
        request=request,
        interpretation=interpretation,
        test_cases=cases,
        files=build_files(request, interpretation, cases),
        metadata={
            "provider": os.getenv("AI_PROVIDER", "local"),
            "prompt_version": "local-v1",
        },
    )

