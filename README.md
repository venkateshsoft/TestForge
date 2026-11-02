# TestForge AI

TestForge AI is an AI-assisted test automation studio that turns plain-English QA scenarios into reviewable test plans and downloadable Python automation projects.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Open http://127.0.0.1:8001. The local provider is deterministic and works without an API key. An OpenAI adapter is not enabled in this repository yet; do not set an API key until that adapter is implemented.

## Production start command

The application is FastAPI and the ASGI entry point is `app.main:app`:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
```

Render configuration is provided in `render.yaml`. A container image is also defined in `Dockerfile`.

## Current vertical slice

- Scenario intake with domain, language, framework, environment, and generation mode.
- Structured requirement interpretation and coverage-oriented test plan.
- Coherent Python API project generation with configuration, client, fixtures, tests, and documentation.
- Safe path validation, secret scanning, syntax compilation, test collection, and dependency checks.
- Project persistence in a local JSON store and ZIP download.
- Explicit validation state; generated code is not presented as production-approved.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/SECURITY.md](docs/SECURITY.md), and [docs/TESTING.md](docs/TESTING.md) for scope and limitations.

Deployment instructions are in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), and portfolio-ready copy is in [docs/PORTFOLIO.md](docs/PORTFOLIO.md).
