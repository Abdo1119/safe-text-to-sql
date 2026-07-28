"""Run deterministic fake-mode functional verification."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/demo/chinook_demo.sqlite"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/fake-evaluation.json"),
        help="Ignored JSON result path.",
    )
    arguments = parser.parse_args()

    examples = load_examples(Path("data/examples.json"))
    service = TextToSQLService(
        provider=FakeLLMProvider.from_examples(examples),
        repository=SQLiteRepository(arguments.database, max_rows=200),
        selector=ExampleSelector(examples),
        max_rows=200,
        max_repair_attempts=1,
        example_top_k=3,
        max_question_chars=500,
    )
    report = asyncio.run(
        run_evaluation(
            service,
            load_evaluation_cases(Path("evaluation/cases.json")),
            provider_mode="fake",
        )
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report.to_dict(), indent=2),
        encoding="utf-8",
    )
    print(
        "Deterministic functional verification: "
        f"{report.matched_cases}/{report.total_cases} expected results matched."
    )
    if exit_code := evaluation_exit_code(report):
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
