# Architecture

The first vertical slice is a FastAPI application with a dependency-light browser dashboard. The API owns request validation, deterministic requirement analysis, project file generation, static validation, persistence, and archive creation. The browser never executes generated code.

Generation is intentionally provider-neutral: `app/generator.py` currently supplies a deterministic local provider so the product is usable without credentials. The `metadata.provider` field and prompt version make the seam explicit for a later official OpenAI SDK adapter.

Local persistence is one JSON document per generation under `TESTFORGE_DATA_DIR`. This keeps the initial product easy to run; PostgreSQL and a job queue are production follow-ups, not hidden assumptions.
