from __future__ import annotations

import os
import re
from collections import Counter

from .models import (
    CoverageSummary,
    Domain,
    ExtractedRequirement,
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


def _rule_matches(text: str, signals: tuple[str, ...]) -> list[str]:
    return [signal for signal in signals if signal in text]


def _scenario(
    number: int,
    requirement: ExtractedRequirement,
    title: str,
    category: str,
    priority: str,
    steps: list[str],
    expected: str,
    feasibility: str,
    evidence: list[str],
) -> TestCase:
    return TestCase(
        id=f"TF-{number:03d}",
        title=title,
        category=category,
        priority=priority,
        requirement=f"{requirement.id}: {requirement.statement}",
        preconditions=["A non-production target and synthetic data are available", "Documented configuration and acceptance criteria are supplied"],
        steps=steps,
        expected=expected,
        automation_feasibility=feasibility,
        validation_evidence=evidence,
    )


def analyze(request: ScenarioRequest) -> tuple[RequirementInterpretation, list[TestCase], CoverageSummary]:
    text = f"{request.title} {request.description} {request.domain}".lower()
    rules = [
        ("WORKFLOW", "Primary functional workflow", "Functional", ("workflow", "register", "upgrade", "deploy", "schedule", "submit", "process"), "Validate the primary workflow and its documented business outcome.", "Validate the requested primary workflow", "High", ["Execute the documented workflow with configured inputs", "Assert each documented state transition and outcome"], "The workflow completes according to the supplied contract; no undocumented status or business rule is assumed."),
        ("API", "API contract and response validation", "API validation", ("api", "http", "request", "response", "endpoint", "json"), "Validate request, response, status, and schema behaviour described by the requirement.", "Validate API contract behaviour", "High", ["Send a contract-valid request", "Assert configured response status and required fields", "Reject malformed or unexpected response content"], "The response satisfies the supplied API contract; exact status codes remain configurable when not provided."),
        ("NEGATIVE", "Invalid and negative behaviour", "Negative", ("invalid", "malformed", "reject", "error", "negative"), "Verify invalid inputs and failure responses do not create unintended state.", "Reject invalid inputs safely", "High", ["Submit each documented invalid or malformed input", "Inspect error response and side effects"], "Invalid input is rejected according to the documented contract and does not create unintended state."),
        ("BOUNDARY", "Boundary and limit conditions", "Boundary", ("boundary", "limit", "maximum", "minimum", "size", "capacity", "edge case"), "Verify behaviour at the explicit boundaries and limits stated by the requirement.", "Exercise stated boundary conditions", "Medium", ["Prepare values at, below, and above each stated boundary", "Assert documented acceptance or rejection"], "Boundary behaviour matches the supplied limits; no limit is invented when the requirement omits one."),
        ("CONCURRENCY", "Concurrent request and race-condition handling", "Concurrency", ("concurrent", "simultaneous", "race", "parallel", "duplicate", "idempotent"), "Verify the invariant remains true when logically equivalent operations overlap.", "Protect the business invariant under concurrency", "Critical", ["Issue equivalent operations concurrently through independent clients", "Collect all responses", "Read back state and compare it with the required invariant"], "The stated invariant holds after concurrent activity; worker count and accepted statuses come from configuration."),
        ("CONSISTENCY", "Data and session consistency", "Data integrity", ("consistency", "data integrity", "session", "subscriber", "record", "database", "transaction"), "Verify state remains consistent across the system boundaries named in the requirement.", "Verify cross-component consistency", "Critical", ["Capture relevant state before the workflow", "Execute the workflow", "Compare API, persisted, and session state"], "All named representations agree with the supplied consistency rule."),
        ("FAILURE", "Dependency failure and error propagation", "Failure handling", ("dependency failure", "dependency", "unavailable", "partition", "error propagation", "downstream"), "Verify dependency failures are surfaced and contained according to the requirement.", "Handle dependency failure safely", "High", ["Introduce the documented dependency failure or test double", "Observe propagated error and side effects", "Restore the dependency"], "Failure handling matches the documented contract and does not silently corrupt state."),
        ("RECOVERY", "Retry, timeout, and recovery behaviour", "Recovery and resilience", ("retry", "timeout", "recovery", "resilien", "restart", "recreate"), "Verify bounded retry, timeout, and recovery behaviour without duplicate side effects.", "Recover from transient failure", "High", ["Introduce a bounded transient failure or delay", "Observe retries and final outcome", "Verify recovery and state after restoration"], "Retries and recovery follow configured policy; no retry count or timeout is invented."),
        ("HELM", "Helm installation, upgrade, validation, and rollback", "Deployment", ("helm", "helm chart"), "Verify the Helm lifecycle operations named by the requirement.", "Validate Helm lifecycle", "Critical", ["Install or upgrade the chart in an isolated namespace", "Validate rendered configuration and release status", "Exercise the documented failed-upgrade and rollback path when required"], "Helm commands and release state meet the supplied acceptance criteria; execution requires cluster credentials and is not performed by this application.", "Infrastructure specification only", ["helm lint output", "helm upgrade/history/status output", "rollback verification evidence"]),
        ("ROLLING", "Rolling deployment and deployment status", "Deployment", ("rolling", "rollout", "deployment", "upgrade", "release"), "Verify rollout sequencing, deployment status, and availability during the requested deployment.", "Validate rolling deployment", "Critical", ["Start the documented rolling deployment", "Observe rollout status and available replicas", "Verify the new version is fully ready before completion"], "The rollout reaches the documented desired state without violating availability requirements.", "Infrastructure specification only", ["kubectl rollout status", "deployment conditions", "replica availability evidence"]),
        ("READINESS", "Pod readiness and liveness probes", "Kubernetes", ("readiness", "liveness", "probe"), "Verify probe behaviour controls traffic and restart decisions as described.", "Validate readiness and liveness probes", "High", ["Inspect configured probe definitions", "Exercise not-ready and unhealthy states in a safe test deployment", "Observe routing and restart outcomes"], "Readiness and liveness outcomes match the configured probe contract; probe thresholds are not invented.", "Infrastructure specification only", ["deployment manifest", "pod conditions/events", "probe response evidence"]),
        ("POD", "Pod failure and recovery", "Kubernetes", ("pod failure", "pod", "kubernetes", "cnf", "recreate", "crash"), "Verify failed pods are detected, replaced, and recovered without violating the stated service invariant.", "Validate pod failure and recovery", "Critical", ["Capture baseline pod and service state", "Induce the authorized test failure", "Observe replacement, readiness, and service recovery"], "The platform recovers according to the documented policy and the named service invariant remains true.", "Infrastructure specification only", ["pod events", "replacement pod readiness", "service health evidence"]),
        ("ENVOY", "Envoy routing, backend exclusion, timeout, and retry", "Service routing", ("envoy", "routing", "backend", "traffic distribution", "healthy backend", "unhealthy backend"), "Verify service routing selects healthy backends, excludes unhealthy ones, and applies documented timeout/retry behaviour.", "Validate Envoy traffic routing", "High", ["Observe traffic to healthy backends", "Make one backend unhealthy in the test environment", "Verify exclusion, timeout, retry, and distribution behaviour"], "Routing follows the supplied policy; no traffic percentage or retry count is invented.", "Infrastructure specification only", ["Envoy access logs", "cluster/endpoint health", "request trace evidence"]),
        ("TRAFFIC", "Traffic continuity during upgrade", "Availability", ("traffic continuity", "zero downtime", "availability", "service continuity", "no interruption"), "Verify traffic continues through the deployment or failure event described.", "Verify traffic continuity", "Critical", ["Generate controlled test traffic before and during the event", "Observe errors, latency, and routing", "Verify traffic after convergence"], "Traffic continuity meets the stated requirement; measurable thresholds remain configuration-driven.", "API/load scaffold plus infrastructure evidence", ["request result timeline", "latency/error measurements", "routing and rollout timeline"]),
        ("PERFORMANCE", "Performance, load, and scalability", "Performance", ("performance", "load", "latency", "throughput", "scalability", "scale", "capacity"), "Verify performance or scaling behaviour using the workload and thresholds supplied.", "Validate performance and scalability", "High", ["Apply the documented workload profile", "Measure throughput, latency, errors, and resource signals", "Compare results with supplied thresholds"], "Measured results are compared with supplied thresholds; no production SLA is invented.", "Load-test specification; executable only with an approved target and profile", ["load-test report", "latency/error metrics", "resource and replica metrics"]),
        ("ROLLBACK", "Rollback and release recovery", "Rollback", ("rollback", "roll back", "failed upgrade", "release recovery"), "Verify the documented rollback path restores the required service state.", "Validate rollback", "Critical", ["Create the documented failed or unsafe release condition", "Invoke the authorized rollback procedure", "Verify workload, routing, and state after rollback"], "Rollback restores the required documented state without silently losing or duplicating data.", "Infrastructure specification only", ["helm history", "rollback status", "post-rollback health and data evidence"]),
        ("REGRESSION", "Regression and backward compatibility", "Regression", ("regression", "backward compatibility", "existing behaviour", "compatibility"), "Verify existing supported workflows remain correct after the change.", "Run regression coverage", "High", ["Run the documented existing workflow suite", "Compare response, state, and compatibility results"], "Existing supported behaviour remains within the supplied acceptance criteria."),
        ("MONITORING", "Monitoring, logging, metrics, and observability", "Observability", ("monitoring", "observability", "logs", "metrics", "tracing", "alert"), "Verify the operational signals needed to diagnose the requested behaviour are emitted.", "Validate monitoring and observability", "Medium", ["Trigger the requested workflow and failure paths", "Collect logs, metrics, traces, and alerts", "Correlate signals with request and deployment timelines"], "Required signals are available and correlate to the event; signal names and thresholds remain configuration-driven.", "Infrastructure/observability specification only", ["logs", "metrics", "traces", "alert history"]),
        ("SECURITY", "Authentication, authorization, and secure handling", "Security", ("security", "authentication", "authorization", "access control", "tls", "secret"), "Verify security controls explicitly named by the requirement.", "Validate security controls", "High", ["Exercise allowed and denied identities using synthetic credentials", "Inspect authorization, transport, and secret-handling behaviour"], "Access and secret-handling behaviour matches the supplied security contract."),
        ("CICD", "CI/CD build, test, deployment gate, and release validation", "CI/CD", ("ci/cd", "pipeline", "build", "deployment gate", "release validation"), "Verify the CI/CD controls named by the requirement.", "Validate CI/CD release controls", "High", ["Run the configured build and automated tests", "Verify deployment gates and release validation", "Verify rollback gate behaviour where documented"], "Pipeline decisions follow the configured gates and preserve the release policy.", "CI/CD specification; executable in the configured pipeline", ["build logs", "test report", "gate decision", "release/rollback record"]),
    ]

    requirements: list[ExtractedRequirement] = []
    cases: list[TestCase] = []
    for key, title, category, signals, statement, case_title, priority, steps, expected, *extras in rules:
        matched = _rule_matches(text, signals)
        if key == "WORKFLOW" or matched:
            requirement = ExtractedRequirement(id=f"REQ-{key}", title=title, category=category, statement=statement, source_signals=matched or ["primary scenario"])
            requirements.append(requirement)
            feasibility = extras[0] if extras else "API scaffold"
            evidence = extras[1] if len(extras) > 1 else ["HTTP response and structured test report", "Configured logs or state evidence"]
            cases.append(_scenario(len(cases) + 1, requirement, case_title, category, priority, steps, expected, feasibility, evidence))

    # A narrow request should remain narrow; a detailed requirement naturally activates more rules.
    clarification_needed = [
        "Provide the authoritative endpoint, schema, and expected statuses for API execution." if any(req.category == "API validation" for req in requirements) else "",
        "Provide cluster, namespace, release, and authorization details before infrastructure execution." if any(req.category in {"Kubernetes", "Deployment", "Service routing", "Rollback"} for req in requirements) else "",
        "Provide measurable workload thresholds before performance results can be judged." if any(req.category == "Performance" for req in requirements) else "",
    ]
    clarification_needed = [item for item in clarification_needed if item]
    gaps = []
    if not any(req.category == "Observability" for req in requirements):
        gaps.append("Monitoring and correlation evidence was not explicitly requested.")
    if not any(req.category == "Security" for req in requirements):
        gaps.append("Security and authorization coverage was not explicitly requested.")
    interpretation = RequirementInterpretation(
        objective=f"Validate: {request.title}",
        system_under_test=_infer_sut(request),
        facts=[request.description],
        requirements=requirements,
        assumptions=[
            "Endpoints, payloads, credentials, thresholds, release names, and expected statuses must come from the supplied contract.",
            "Infrastructure scenarios are specifications unless the application is connected to an authorized test cluster.",
            "Tests use synthetic data in a non-production environment.",
        ],
        acceptance_criteria=[req.statement for req in requirements],
        risks=[
            "The generator does not infer undocumented infrastructure settings, SLAs, response codes, or business rules.",
            "Cross-pod routing and recovery cannot be proven by API-only execution without cluster and observability access.",
        ],
        open_questions=clarification_needed,
        coverage_gaps=gaps,
    )
    counts = Counter(case.category for case in cases)
    summary = CoverageSummary(
        total_scenarios=len(cases),
        by_category=dict(counts),
        critical_and_high_priority=[f"{case.id} — {case.title}" for case in cases if case.priority in {"Critical", "High"}],
        requirements_covered=[f"{req.id} — {req.title}" for req in requirements],
        coverage_gaps=gaps,
        clarification_needed=clarification_needed,
    )
    return interpretation, cases, summary


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
    if categories.intersection({"Functional", "API validation", "Positive"}):
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
    if categories.intersection({"Recovery and resilience", "Resilience"}):
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
    scenario_spec = "# Scenario specifications\n\n"
    scenario_spec += "These scenarios are mapped to extracted requirements. Infrastructure scenarios are documentation/specifications unless an authorized cluster, Helm release, routing layer, or observability system is configured.\n\n"
    for case in cases:
        scenario_spec += f"## {case.id}: {case.title}\n\n"
        scenario_spec += f"- Category: {case.category}\n- Priority: {case.priority}\n- Requirement: {case.requirement}\n- Automation feasibility: {case.automation_feasibility}\n- Expected results: {case.expected}\n- Evidence: {'; '.join(case.validation_evidence)}\n\n"
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

Tests lacking required configuration are skipped with an explicit explanation. Configured API tests perform HTTP
requests and assert documented expectations. Infrastructure scenarios are intentionally not emitted as fake
executable tests; use the scenario specification and suggested evidence to connect them to your environment.
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
        GeneratedFile(path="specs/scenario_matrix.md", content=scenario_spec),
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
    interpretation, cases, coverage_summary = analyze(request)

    return StoredGeneration(
        request=request,
        interpretation=interpretation,
        test_cases=cases,
        coverage_summary=coverage_summary,
        files=build_files(request, interpretation, cases),
        metadata={
            "provider": os.getenv("AI_PROVIDER", "local"),
            "prompt_version": "local-v1",
        },
    )
