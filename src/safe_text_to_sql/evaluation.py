"""Reproducible evaluation for deterministic functional verification."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from safe_text_to_sql.service import ServiceError, TextToSQLService


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """One reviewed local evaluation case and expected result shape."""

    case_id: str
    category: str
    question: str
    expected_columns: tuple[str, ...]
    expected_first_row: tuple[Any, ...] | None
    expect_non_empty: bool


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    """Observed result for one case."""

    case_id: str
    question: str
    sql: str
    validation_status: str
    execution_status: str
    expected_result_match: bool
    error_category: str | None
    elapsed_ms: float
    provider_mode: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Serializable evaluation summary and records."""

    label: str
    provider_mode: str
    total_cases: int
    matched_cases: int
    records: tuple[EvaluationRecord, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "provider_mode": self.provider_mode,
            "total_cases": self.total_cases,
            "matched_cases": self.matched_cases,
            "records": [asdict(record) for record in self.records],
        }


class EvaluationCaseError(ValueError):
    """Raised when the checked-in evaluation set is invalid."""


def load_evaluation_cases(path: Path) -> tuple[EvaluationCase, ...]:
    """Load a non-empty, uniquely identified evaluation list."""

    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationCaseError("Evaluation cases could not be loaded.") from exc
    if not isinstance(payload, list) or not payload:
        raise EvaluationCaseError("Evaluation cases must be a non-empty list.")

    cases: list[EvaluationCase] = []
    identifiers: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise EvaluationCaseError("Every evaluation case must be an object.")
        case_id = _required_string(item, "id")
        if case_id in identifiers:
            raise EvaluationCaseError("Evaluation case IDs must be unique.")
        expected_columns = item.get("expected_columns")
        expected_first_row = item.get("expected_first_row")
        if not isinstance(expected_columns, list) or not all(
            isinstance(column, str) for column in expected_columns
        ):
            raise EvaluationCaseError("Expected columns must be a list of strings.")
        if expected_first_row is not None and not isinstance(expected_first_row, list):
            raise EvaluationCaseError("Expected first row must be a list or null.")
        cases.append(
            EvaluationCase(
                case_id=case_id,
                category=_required_string(item, "category"),
                question=_required_string(item, "question"),
                expected_columns=tuple(expected_columns),
                expected_first_row=(
                    tuple(expected_first_row) if expected_first_row is not None else None
                ),
                expect_non_empty=bool(item.get("expect_non_empty", True)),
            )
        )
        identifiers.add(case_id)
    return tuple(cases)


async def run_evaluation(
    service: TextToSQLService,
    cases: Sequence[EvaluationCase],
    *,
    provider_mode: str,
    clock: Callable[[], float] = time.perf_counter,
    timestamp_factory: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> EvaluationReport:
    """Run cases serially and record only safe, reproducible observations."""

    records: list[EvaluationRecord] = []
    for case in cases:
        started = clock()
        try:
            result = await service.ask(case.question)
        except ServiceError as exc:
            records.append(
                EvaluationRecord(
                    case_id=case.case_id,
                    question=case.question,
                    sql="",
                    validation_status="failed",
                    execution_status="failed",
                    expected_result_match=False,
                    error_category=exc.code.value,
                    elapsed_ms=round((clock() - started) * 1000, 3),
                    provider_mode=provider_mode,
                    timestamp=timestamp_factory().isoformat(),
                )
            )
            continue

        expected_match = _matches_expected_result(
            case,
            result.query_result.columns,
            result.query_result.rows,
        )
        records.append(
            EvaluationRecord(
                case_id=case.case_id,
                question=case.question,
                sql=result.validated_query.sql,
                validation_status="passed",
                execution_status="passed",
                expected_result_match=expected_match,
                error_category=None,
                elapsed_ms=round((clock() - started) * 1000, 3),
                provider_mode=provider_mode,
                timestamp=timestamp_factory().isoformat(),
            )
        )

    return EvaluationReport(
        label=(
            "deterministic_functional_verification"
            if provider_mode == "fake"
            else "provider_evaluation"
        ),
        provider_mode=provider_mode,
        total_cases=len(records),
        matched_cases=sum(record.expected_result_match for record in records),
        records=tuple(records),
    )


def _matches_expected_result(
    case: EvaluationCase,
    columns: tuple[str, ...],
    rows: tuple[tuple[Any, ...], ...],
) -> bool:
    if columns != case.expected_columns:
        return False
    if case.expect_non_empty and not rows:
        return False
    if case.expected_first_row is not None:
        return bool(rows) and rows[0] == case.expected_first_row
    return True


def _required_string(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EvaluationCaseError(f"Evaluation field '{key}' must be a string.")
    return value.strip()
