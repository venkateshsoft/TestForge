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
    requirement: str = ""
    preconditions: list[str]
    steps: list[str]
    expected: str
    automation_feasibility: str = "API scaffold"
    validation_evidence: list[str] = Field(default_factory=list)
    applicable: bool = True


class ExtractedRequirement(BaseModel):
    id: str
    title: str
    category: str
    statement: str
    source_signals: list[str] = Field(default_factory=list)


class RequirementInterpretation(BaseModel):
    objective: str
    system_under_test: str
    facts: list[str]
    requirements: list[ExtractedRequirement] = Field(default_factory=list)
    assumptions: list[str]
    acceptance_criteria: list[str]
    risks: list[str]
    open_questions: list[str]
    coverage_gaps: list[str] = Field(default_factory=list)


class CoverageSummary(BaseModel):
    total_scenarios: int
    by_category: dict[str, int]
    critical_and_high_priority: list[str]
    requirements_covered: list[str]
    coverage_gaps: list[str]
    clarification_needed: list[str]


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
    coverage_summary: CoverageSummary = Field(default_factory=lambda: CoverageSummary(total_scenarios=0, by_category={}, critical_and_high_priority=[], requirements_covered=[], coverage_gaps=[], clarification_needed=[]))
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
    coverage_summary: CoverageSummary = Field(default_factory=lambda: CoverageSummary(total_scenarios=0, by_category={}, critical_and_high_priority=[], requirements_covered=[], coverage_gaps=[], clarification_needed=[]))
    files: list[GeneratedFile]
    validation: ValidationResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
