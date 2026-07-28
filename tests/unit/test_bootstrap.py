from __future__ import annotations

from pathlib import Path

from safe_text_to_sql.bootstrap import build_components, merge_runtime_environment
from safe_text_to_sql.config import LLMProviderMode, Settings
from safe_text_to_sql.database.initializer import initialize_database
from safe_text_to_sql.llm.fake import FakeLLMProvider


def test_streamlit_secrets_fill_only_missing_allowed_environment_values() -> None:
    merged = merge_runtime_environment(
        {
            "LLM_PROVIDER": "fake",
            "GEMINI_MODEL": "environment-model",
            "UNRELATED": "keep",
        },
        {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "dummy-streamlit-secret",
            "GEMINI_MODEL": "secret-model",
            "UNAPPROVED_SECRET": "ignore",
        },
    )

    assert merged["LLM_PROVIDER"] == "fake"
    assert merged["GEMINI_MODEL"] == "environment-model"
    assert merged["GEMINI_API_KEY"] == "dummy-streamlit-secret"
    assert merged["UNRELATED"] == "keep"
    assert "UNAPPROVED_SECRET" not in merged


def test_build_components_uses_offline_provider_and_fixed_project_assets(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "demo.sqlite"
    initialize_database(database_path)
    settings = Settings.from_env(
        {
            "LLM_PROVIDER": "fake",
            "DATABASE_PATH": str(database_path),
        }
    )

    components = build_components(settings, project_root=Path.cwd())

    assert settings.llm_provider is LLMProviderMode.FAKE
    assert isinstance(components.provider, FakeLLMProvider)
    assert components.repository.healthcheck()
    assert components.example_count == 25
