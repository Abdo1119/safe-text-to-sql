"""Runtime-only configuration and dependency construction."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from safe_text_to_sql.config import LLMProviderMode, Settings
from safe_text_to_sql.database.initializer import (
    DatabaseInitializationError,
    DatabaseProvisionState,
    ensure_database,
)
from safe_text_to_sql.database.sqlite import SQLiteRepository
from safe_text_to_sql.examples.loader import load_examples
from safe_text_to_sql.examples.selector import ExampleSelector
from safe_text_to_sql.llm.fake import FakeLLMProvider
from safe_text_to_sql.llm.gemini import GeminiLLMProvider
from safe_text_to_sql.llm.protocol import LLMProvider
from safe_text_to_sql.observability import configure_logging
from safe_text_to_sql.service import TextToSQLService

_RUNTIME_KEYS = frozenset(
    {
        "ALLOWED_SCHEMAS",
        "ALLOWED_TABLES",
        "APP_ENV",
        "DATABASE_PATH",
        "EXAMPLE_TOP_K",
        "GEMINI_API_KEY",
        "GEMINI_MAX_RETRIES",
        "GEMINI_MODEL",
        "GEMINI_REQUEST_TIMEOUT_SECONDS",
        "LLM_PROVIDER",
        "LOG_LEVEL",
        "MAX_QUESTION_CHARS",
        "MAX_REPAIR_ATTEMPTS",
        "MAX_RETURNED_ROWS",
    }
)


@dataclass(frozen=True, slots=True)
class AppComponents:
    """Constructed application dependencies without UI state."""

    provider: LLMProvider
    repository: SQLiteRepository
    service: TextToSQLService
    example_count: int


def merge_runtime_environment(
    environment: Mapping[str, str],
    secrets: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Merge approved Streamlit secrets without overriding environment values."""

    merged = dict(environment)
    if secrets is None:
        return merged
    for key in _RUNTIME_KEYS:
        if key not in merged and key in secrets:
            merged[key] = str(secrets[key])
    return merged


def load_runtime_settings(
    *,
    project_root: Path,
    streamlit_secrets: Mapping[str, Any] | None = None,
) -> Settings:
    """Load local dotenv values only inside the running application process."""

    load_dotenv(project_root / ".env", override=False)
    return Settings.from_env(merge_runtime_environment(os.environ, streamlit_secrets))


@dataclass(frozen=True, slots=True)
class DatabaseProvisioning:
    """Where the demo database ended up, and how it got there."""

    path: Path = field(repr=False)
    state: DatabaseProvisionState
    used_fallback_location: bool


def provision_database(settings: Settings, *, project_root: Path) -> DatabaseProvisioning:
    """Make the demo database exist before any query path needs it.

    Deployment targets such as Streamlit Community Cloud start from a fresh checkout
    where the generated database is absent, and no operator can run a command there.
    This needs no provider credentials, so it works identically in fake and Gemini
    mode.

    Some hosts serve the checkout from a read-only or non-persistent mount. Rather than
    leaving a public demo permanently unusable, fall back to a writable temporary
    location; callers surface that so the choice is never silent.
    """

    configured = _project_path(settings.database_path, project_root)
    try:
        return DatabaseProvisioning(
            path=configured,
            state=ensure_database(configured),
            used_fallback_location=False,
        )
    except DatabaseInitializationError:
        fallback = _fallback_database_path(settings.database_path)
        if fallback == configured:
            raise
        try:
            state = ensure_database(fallback)
        except DatabaseInitializationError:
            raise
        return DatabaseProvisioning(
            path=fallback,
            state=state,
            used_fallback_location=True,
        )


def _fallback_database_path(configured: Path) -> Path:
    return Path(tempfile.gettempdir()) / "safe-text-to-sql" / configured.name


def build_components(
    settings: Settings,
    *,
    project_root: Path,
    database_path: Path | None = None,
) -> AppComponents:
    """Build fixed local dependencies from validated settings."""

    database_path = database_path or _project_path(settings.database_path, project_root)
    examples = load_examples(project_root / "data" / "examples.json")
    selector = ExampleSelector(examples)
    provider: LLMProvider
    if settings.llm_provider is LLMProviderMode.GEMINI:
        if settings.gemini_api_key is None:
            raise RuntimeError("Validated Gemini settings are missing a key.")
        provider = GeminiLLMProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            request_timeout_seconds=settings.gemini_request_timeout_seconds,
            max_retries=settings.gemini_max_retries,
        )
    else:
        provider = FakeLLMProvider.from_examples(examples)

    repository = SQLiteRepository(
        database_path,
        max_rows=settings.max_returned_rows,
    )
    logger = configure_logging(settings.log_level)
    service = TextToSQLService(
        provider=provider,
        repository=repository,
        selector=selector,
        max_rows=settings.max_returned_rows,
        max_repair_attempts=settings.max_repair_attempts,
        example_top_k=settings.example_top_k,
        max_question_chars=settings.max_question_chars,
        allowed_schemas=settings.allowed_schemas,
        allowed_tables=settings.allowed_tables,
        logger=logger,
    )
    return AppComponents(
        provider=provider,
        repository=repository,
        service=service,
        example_count=len(examples),
    )


def _project_path(path: Path, project_root: Path) -> Path:
    return path if path.is_absolute() else project_root / path
