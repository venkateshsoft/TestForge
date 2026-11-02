# AI generation pipeline

The implemented pipeline is explicit: validate the scenario request, interpret facts and assumptions, derive applicable coverage cases, build a bounded project manifest, then statically validate files. A future provider adapter should return the same Pydantic models, enforce prompt versioning and bounded retries, and keep uploaded content subordinate to security policy.
