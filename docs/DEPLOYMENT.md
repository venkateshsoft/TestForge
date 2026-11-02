# Deployment

## Render deployment

1. Create a GitHub repository without committing `.env`, `.venv`, `.testforge-data`, caches, backup files, or generated reports.
2. From the project directory, run:

   ```powershell
   git init
   git add .
   git commit -m "Prepare TestForge AI for deployment"
   git branch -M main
   git remote add origin https://github.com/<account>/<repository>.git
   git push -u origin main
   ```

3. In Render, choose **New → Blueprint**, connect the GitHub repository, and select `render.yaml`.
4. Set `ALLOWED_HOSTS` to the Render hostname, for example `testforge-ai.onrender.com`. Add a comma-separated custom domain if one is configured.
5. Deploy. Render supplies `PORT`; the configured command binds Uvicorn to `0.0.0.0` and that port.
6. Verify `/api/v1/health`, then open the root URL and submit a synthetic scenario.

Equivalent manual Render settings are:

- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/api/v1/health`

## Environment variables

Required deployment settings:

- `PORT`: supplied by Render; do not hardcode it.
- `ALLOWED_HOSTS`: deployed hostname(s).
- `TESTFORGE_DATA_DIR`: writable path. The current JSON store is ephemeral on typical Render web services; use a persistent disk or replace it with PostgreSQL before relying on saved projects.
- `RATE_LIMIT_PER_MINUTE`, `MAX_REQUEST_BYTES`, `LOG_LEVEL`: operational controls.

There are currently no required AI credentials because generation uses the local deterministic provider. Do not add an `OPENAI_API_KEY` until an actual provider adapter is implemented.

## Verification checklist

- `GET /api/v1/health` returns HTTP 200 and `{"status":"ok"}`.
- The dashboard loads from the public root URL.
- A generation returns HTTP 201.
- Validation returns a separate status for each check.
- ZIP download contains only the generated project tree.
- Logs contain request IDs and no credentials.

## Before public multi-user use

Add authentication and project authorization, durable storage, distributed rate limiting, external secrets management, a reverse proxy/WAF, and an isolated execution worker. The current app deliberately does not execute generated code.
