from __future__ import annotations

import asyncio
from pathlib import Path

from safe_text_to_sql.database.initializer import initialize_database
from safe_text_to_sql.database.sqlite import SQLiteRepository
from safe_text_to_sql.examples.loader import load_examples
from safe_text_to_sql.examples.selector import ExampleSelector
from safe_text_to_sql.llm.fake import FakeLLMProvider
from safe_text_to_sql.service import TextToSQLService


def test_question_to_grounded_answer_offline(tmp_path: Path) -> None:
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
        request_id_factory=lambda: "req-e2e",
    )

    result = asyncio.run(service.ask("Which country generated the highest revenue?"))

    assert result.validated_query.sql.upper().endswith("LIMIT 1")
    assert result.query_result.columns == ("BillingCountry", "Revenue")
    assert result.query_result.rows[0][0] == "USA"
    assert "BillingCountry: USA" in result.answer.answer
