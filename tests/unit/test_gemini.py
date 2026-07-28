from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from google.genai import errors

from safe_text_to_sql.config import SecretValue
from safe_text_to_sql.llm.gemini import (
    GeminiLLMProvider,
    ProviderError,
    ProviderErrorCode,
)
from safe_text_to_sql.models import (
    QueryResult,
    UserQuestion,
    ValidatedSQLQuery,
    ValidationError,
    ValidationErrorCode,
)


@dataclass
class _Response:
    text: str | None


class _Models:
    def __init__(self, responses: list[_Response | Exception]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _AsyncClient:
    def __init__(self, models: _Models) -> None:
        self.models = models

    async def __aenter__(self) -> _AsyncClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _Client:
    def __init__(self, models: _Models) -> None:
        self.aio = _AsyncClient(models)


class _ClientFactory:
    def __init__(self, responses: list[_Response | Exception]) -> None:
        self.models = _Models(responses)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> _Client:
        self.calls.append(kwargs)
        return _Client(self.models)


def _provider(
    responses: list[_Response | Exception],
) -> tuple[GeminiLLMProvider, _ClientFactory]:
    factory = _ClientFactory(responses)
    provider = GeminiLLMProvider(
        api_key=SecretValue("dummy-gemini-test-key"),
        model="gemini-test",
        request_timeout_seconds=12.5,
        max_retries=1,
        client_factory=factory,
    )
    return provider, factory


def _query() -> ValidatedSQLQuery:
    return ValidatedSQLQuery(
        sql="SELECT 1 LIMIT 1",
        referenced_tables=(),
        effective_limit=1,
        limit_was_added=False,
        limit_was_clamped=False,
    )


def test_generate_sql_builds_bounded_structured_request_and_parses_json() -> None:
    provider, factory = _provider([_Response('{"sql":"SELECT 1"}')])

    candidate = asyncio.run(provider.generate_sql(UserQuestion("Return one"), "schema context"))

    assert candidate.sql == "SELECT 1"
    assert candidate.provider == "gemini"
    assert factory.calls[0]["api_key"] == "dummy-gemini-test-key"
    http_options = factory.calls[0]["http_options"]
    assert http_options.timeout == 12_500
    assert http_options.retry_options.attempts == 2
    request = factory.models.calls[0]
    assert request["model"] == "gemini-test"
    assert request["config"].temperature == 0
    assert request["config"].response_mime_type == "application/json"
    assert "dummy-gemini-test-key" not in request["contents"]


def test_repair_and_answer_parse_their_expected_json_fields() -> None:
    provider, _ = _provider(
        [
            _Response('{"sql":"SELECT 2"}'),
            _Response('{"answer":"The result is two."}'),
        ]
    )
    question = UserQuestion("Return two")
    error = ValidationError(
        code=ValidationErrorCode.PARSE_ERROR,
        message="SQL could not be parsed.",
    )

    repaired = asyncio.run(provider.repair_sql(question, "SELECT broken", error, "schema"))
    answer = asyncio.run(
        provider.generate_answer(
            question,
            _query(),
            QueryResult(columns=("value",), rows=((2,),)),
        )
    )

    assert repaired.sql == "SELECT 2"
    assert answer.answer == "The result is two."


def test_invalid_response_is_mapped_without_exposing_response_content() -> None:
    private_response = "private-provider-response-content"
    provider, _ = _provider([_Response(private_response)])

    with pytest.raises(ProviderError) as exc_info:
        asyncio.run(provider.generate_sql(UserQuestion("Return one"), "schema"))

    assert exc_info.value.code is ProviderErrorCode.INVALID_RESPONSE
    assert private_response not in str(exc_info.value)


def test_api_error_is_mapped_to_safe_category() -> None:
    api_error = errors.APIError(
        429,
        {"error": {"message": "private request identifier abc-123"}},
    )
    provider, _ = _provider([api_error])

    with pytest.raises(ProviderError) as exc_info:
        asyncio.run(provider.generate_sql(UserQuestion("Return one"), "schema"))

    assert exc_info.value.code is ProviderErrorCode.RATE_LIMIT
    assert "abc-123" not in str(exc_info.value)
