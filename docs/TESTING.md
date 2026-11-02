# Testing

Run the application tests with:

```powershell
pytest -q
```

The tests cover health, generation, structured output, validation, ZIP creation, and credential-like input rejection. The generated projects are statically parsed with Python `ast`; actual target-system execution is intentionally not enabled yet.
