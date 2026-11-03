# AI generation pipeline

The implemented pipeline is explicit: validate the scenario request, interpret facts and assumptions, decompose the text into traceable requirements, activate only matching domain rules, build a bounded coverage summary, generate scenario specifications, emit API scaffolds only where feasible, then statically validate files. Every scenario carries a requirement reference, feasibility statement, and suggested evidence.

The local rule set recognizes API, functional, boundary, concurrency, consistency, failure/recovery, Kubernetes, Helm, rolling deployments, readiness/liveness, pod recovery, Envoy routing, traffic continuity, performance, rollback, regression, observability, security, and CI/CD signals. It does not force unrelated categories onto narrow requests. A future provider adapter should return the same Pydantic models, enforce prompt versioning and bounded retries, and keep uploaded content subordinate to security policy.
