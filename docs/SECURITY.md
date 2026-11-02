# Security and residual risk

- Generated files are treated as untrusted output and are never executed by the web process.
- Uploaded scenario text is size-limited by the request schema and obvious credential markers are rejected.
- ZIP paths are checked for absolute paths, traversal, and Windows separators before packaging.
- Generated projects contain environment variable placeholders only.
- Static validation reports syntax, path, secret-pattern, and manifest checks separately.
- Production startup uses the platform-provided `PORT`, binds to `0.0.0.0`, applies security response headers, validates hostnames when `ALLOWED_HOSTS` is configured, and emits request IDs.
- A bounded request body check and single-process rate limiter provide baseline protection; use an edge proxy or managed gateway for distributed enforcement.

Residual risks: the local JSON store is not multi-user or access-controlled, the in-process rate limiter is not distributed, and execution workers are not implemented. Before enabling execution, use disposable non-root workers with network deny-by-default, resource quotas, secret isolation, and an external sandbox. Do not treat this increment as production-ready.
