from __future__ import annotations

import json
from pathlib import Path

import pytest

from safe_text_to_sql.examples.loader import ExampleLoadError, load_examples
from safe_text_to_sql.examples.selector import ExampleSelector


def test_loads_all_25_normalized_examples() -> None:
    examples = load_examples(Path("data/examples.json"))

    assert len(examples) == 25
    assert examples[0].example_id == "ex-001"
    assert examples[-1].example_id == "ex-025"
    assert all(example.question and example.sql for example in examples)


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "examples.json"
    path.write_text(
        json.dumps(
            [
                {"id": "duplicate", "question": "Question one", "sql": "SELECT 1"},
                {"id": "duplicate", "question": "Question two", "sql": "SELECT 2"},
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ExampleLoadError, match="unique"):
        load_examples(path)


def test_selector_returns_relevant_examples_with_metadata() -> None:
    selector = ExampleSelector(load_examples(Path("data/examples.json")))

    selections = selector.select("Which five customers spent the most?", top_k=3)

    assert len(selections) == 3
    assert selections[0].example.example_id == "ex-004"
    assert selections[0].score > 0
    assert {"customer", "spend"} <= set(selections[0].matched_terms)
    assert selections == selector.select("Which five customers spent the most?", top_k=3)


def test_selector_uses_stable_fallback_when_nothing_matches() -> None:
    selector = ExampleSelector(load_examples(Path("data/examples.json")))

    selections = selector.select("quasar zephyr", top_k=2)

    assert [item.example.example_id for item in selections] == ["ex-001", "ex-002"]
    assert all(item.score == 0 for item in selections)
    assert all(item.matched_terms == () for item in selections)


def test_selector_rejects_non_positive_top_k() -> None:
    selector = ExampleSelector(load_examples(Path("data/examples.json")))

    with pytest.raises(ValueError, match="positive"):
        selector.select("customers", top_k=0)
