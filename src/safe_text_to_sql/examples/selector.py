"""Dependency-light deterministic example selection."""

from __future__ import annotations

import math
import re

from safe_text_to_sql.models import ExampleRecord, SelectedExample

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "all",
        "along",
        "and",
        "are",
        "by",
        "each",
        "for",
        "from",
        "get",
        "how",
        "in",
        "is",
        "list",
        "of",
        "per",
        "the",
        "their",
        "to",
        "who",
        "with",
    }
)
_ALIASES = {
    "customers": "customer",
    "employees": "employee",
    "five": "5",
    "highest": "top",
    "longest": "duration",
    "most": "top",
    "purchased": "purchase",
    "purchases": "purchase",
    "reports": "report",
    "sales": "sale",
    "spent": "spend",
    "spending": "spend",
}


class ExampleSelector:
    """Rank examples by transparent normalized token overlap."""

    def __init__(self, examples: tuple[ExampleRecord, ...]) -> None:
        if not examples:
            raise ValueError("At least one example is required.")
        self._examples = examples
        self._tokens = tuple(_tokenize(example.question) for example in examples)

    def select(self, question: str, *, top_k: int) -> tuple[SelectedExample, ...]:
        """Return stable top-k selections and lexical match metadata."""

        if top_k <= 0:
            raise ValueError("top_k must be positive.")
        question_tokens = _tokenize(question)
        ranked: list[tuple[float, int, tuple[str, ...]]] = []
        for index, example_tokens in enumerate(self._tokens):
            matched = tuple(sorted(question_tokens & example_tokens))
            denominator = math.sqrt(max(len(question_tokens) * len(example_tokens), 1))
            score = len(matched) / denominator
            ranked.append((score, index, matched))

        if not any(score > 0 for score, _, _ in ranked):
            ranked = [(0.0, index, ()) for index in range(len(self._examples))]
        else:
            ranked.sort(key=lambda item: (-item[0], item[1]))

        return tuple(
            SelectedExample(
                example=self._examples[index],
                score=round(score, 6),
                matched_terms=matched,
            )
            for score, index, matched in ranked[: min(top_k, len(ranked))]
        )


def _tokenize(text: str) -> frozenset[str]:
    tokens: set[str] = set()
    for raw_token in _TOKEN_PATTERN.findall(text.casefold()):
        token = _ALIASES.get(raw_token, raw_token)
        if token.endswith("s") and len(token) > 3 and token not in _ALIASES:
            token = token[:-1]
        if token not in _STOP_WORDS:
            tokens.add(token)
    return frozenset(tokens)
