from __future__ import annotations

from safe_text_to_sql.config import SecretValue
from safe_text_to_sql.llm.fake import FakeLLMProvider
from safe_text_to_sql.llm.gemini import GeminiLLMProvider
from safe_text_to_sql.llm.protocol import LLMProvider


def test_fake_provider_satisfies_runtime_protocol() -> None:
    assert isinstance(FakeLLMProvider(), LLMProvider)


def test_gemini_provider_satisfies_runtime_protocol_without_network() -> None:
    provider = GeminiLLMProvider(
        api_key=SecretValue("dummy-contract-key"),
        model="gemini-test",
        request_timeout_seconds=10,
        max_retries=0,
    )

    assert isinstance(provider, LLMProvider)
