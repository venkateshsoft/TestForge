from __future__ import annotations

import ast
import re
from datetime import UTC, datetime

from .models import GeneratedFile, ValidationCheck, ValidationResult


def validate(files: list[GeneratedFile]) -> ValidationResult:
    checks: list[ValidationCheck] = []
    paths = [file.path for file in files]
    unsafe = [path for path in paths if path.startswith(("/", "\\")) or ".." in path.split("/") or "\\" in path]
    checks.append(ValidationCheck(name="path safety", status="passed" if not unsafe else "failed", message="All file paths are workspace-relative." if not unsafe else f"Unsafe paths: {unsafe}"))
    secret_pattern = re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*(['\"]).+?\2")
    leaks = [file.path for file in files if secret_pattern.search(file.content)]
    checks.append(ValidationCheck(name="secret scan", status="passed" if not leaks else "failed", message="No obvious hardcoded secrets detected." if not leaks else f"Review possible secrets in: {leaks}"))
    python_files = [file for file in files if file.path.endswith(".py")]
    syntax_errors: list[str] = []
    for file in python_files:
        try:
            ast.parse(file.content, filename=file.path)
        except SyntaxError as exc:
            syntax_errors.append(f"{file.path}:{exc.lineno}: {exc.msg}")
    checks.append(ValidationCheck(name="python syntax", status="passed" if not syntax_errors else "failed", message="All generated Python files compile." if not syntax_errors else "; ".join(syntax_errors)))
    missing = [required for required in ("README.md", "requirements.txt") if required not in paths]
    checks.append(ValidationCheck(name="project manifest", status="passed" if not missing else "failed", message="Required project files are present." if not missing else f"Missing: {missing}"))
    failed = any(check.status == "failed" for check in checks)
    return ValidationResult(status="failed" if failed else "passed", checks=checks, validated_at=datetime.now(UTC))
