from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from safe_text_to_sql.database.initializer import initialize_database
from safe_text_to_sql.database.sqlite import SQLiteRepository
from safe_text_to_sql.evaluation import (
    evaluation_exit_code,
    load_evaluation_cases,
    run_evaluation,
)
from safe_text_to_sql.examples.loader import load_examples
from safe_text_to_sql.examples.selector import ExampleSelector
from safe_text_to_sql.llm.fake import FakeLLMProvider
from safe_text_to_sql.service import TextToSQLService


def test_loads_reviewed_evaluation_categories() -> None:
    cases = load_evaluation_cases(Path("evaluation/cases.json"))

    assert len(cases) >= 12
    categories = {case.category for case in cases}
    assert {
        "filtering",
        "aggregation",
        "joins",
        "grouping",
        "ordering",
        "nested_query",
        "cte",
        "window_function",
        "unsupported",
        "prompt_injection",
        "malicious",
    } <= categories


def test_fake_evaluation_records_reproducible_functional_results(tmp_path: Path) -> None:
    examples = load_examples(Path("data/examples.json"))
    database_path = tmp_path / "demo.sqlite"
    initialize_database(database_path)
    service = TextToSQLService(
        provider=FakeLLMProvider.from_examples(examples),
        repository=SQLiteRepository(database_path, max_rows=200),
        selector=ExampleSelector(examples),
        max_rows=200,
        max_repair_attempts=1,
        example_top_k=3,
        max_question_chars=500,
        request_id_factory=lambda: "req-evaluation",
    )
    cases = load_evaluation_cases(Path("evaluation/cases.json"))[:3]

    report = asyncio.run(
        run_evaluation(
            service,
            cases,
            provider_mode="fake",
            clock=lambda: 1.0,
            timestamp_factory=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        )
    )

    assert report.label == "deterministic_functional_verification"
    assert report.total_cases == 3
    assert report.matched_cases == 3
    assert all(record.validation_status == "passed" for record in report.records)
    assert all(record.execution_status == "passed" for record in report.records)
    assert all(record.expected_result_match for record in report.records)
    serialized = json.dumps(report.to_dict())
    assert "LLM accuracy" not in serialized
    assert "2026-07-29T00:00:00+00:00" in serialized
    assert report.succeeded


def test_evaluation_report_fails_when_any_expected_result_mismatches(tmp_path: Path) -> None:
    examples = load_examples(Path("data/examples.json"))
    database_path = tmp_path / "demo.sqlite"
    initialize_database(database_path)
    service = TextToSQLService(
        provider=FakeLLMProvider(generated_sql="SELECT 1 AS Wrong"),
        repository=SQLiteRepository(database_path, max_rows=200),
        selector=ExampleSelector(examples),
        max_rows=200,
        max_repair_attempts=0,
        example_top_k=3,
        max_question_chars=500,
    )
    case = load_evaluation_cases(Path("evaluation/cases.json"))[0]

    report = asyncio.run(run_evaluation(service, (case,), provider_mode="fake"))

    assert not report.succeeded
    assert evaluation_exit_code(report) == 1
