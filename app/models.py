from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Domain(StrEnum):
    API = "API"
    WEB_UI = "Web UI"
    DATABASE = "Database"
    PERFORMANCE = "Performance"
    KUBERNETES = "Kubernetes / Cloud Native"
    HEALTHCARE = "Healthcare PMS / RCM"
    HYBRID = "Hybrid / End-to-End"


class GenerationMode(StrEnum):
    SCRIPTS = "Generate individual scripts"
    FRAMEWORK = "Generate a complete automation framework"
    TEST_CASES = "Generate test cases and test data only"


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=20, max_length=12000)
    domain: Domain = Domain.API
    language: str = Field(default="Python", pattern="^(Python|Go|C\\+\\+)$")
    framework: str = Field(default="pytest + Requests", max_length=100)
    environment: str = Field(default="local or test environment", max_length=200)
    authentication: str = Field(default="Configure through environment variables", max_length=300)
    generation_mode: GenerationMode = GenerationMode.FRAMEWORK

    @field_validator("description")
    @classmethod
    def reject_obvious_secrets(cls, value: str) -> str:
        lowered = value.lower()
        for marker in ("-----begin private key-----", "aws_secret_access_key", "password="):
            if marker in lowered:
                raise ValueError("Do not submit credentials or private keys in the scenario")
        return value.strip()


class TestCase(BaseModel):
    id: str
    title: str
    category: str
    priority: str
    preconditions: list[str]
    steps: list[str]
    expected: str
    applicable: bool = True


class RequirementInterpretation(BaseModel):
    objective: str
    system_under_test: str
    facts: list[str]
    assumptions: list[str]
    acceptance_criteria: list[str]
    risks: list[str]
    open_questions: list[str]


class GeneratedFile(BaseModel):
    path: str
    content: str


class ValidationCheck(BaseModel):
    name: str
    status: str
    message: str


class ValidationResult(BaseModel):
    status: str
    checks: list[ValidationCheck]
    validated_at: datetime


class GenerationResponse(BaseModel):
    id: UUID
    created_at: datetime
    request: ScenarioRequest
    interpretation: RequirementInterpretation
    test_cases: list[TestCase]
    files: list[GeneratedFile]
    validation: ValidationResult | None = None


def utcnow() -> datetime:
    return datetime.now(UTC)


class StoredGeneration(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=utcnow)
    request: ScenarioRequest
    interpretation: RequirementInterpretation
    test_cases: list[TestCase]
    files: list[GeneratedFile]
    validation: ValidationResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
