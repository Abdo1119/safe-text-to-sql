from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from safe_text_to_sql.bootstrap import provision_database
from safe_text_to_sql.config import Settings
from safe_text_to_sql.database import initializer
from safe_text_to_sql.database.initializer import (
    DatabaseInitializationError,
    DatabaseProvisionState,
    ensure_database,
    verify_database_schema,
)


def _row_count(path: Path, table: str) -> int:
    with sqlite3.connect(path) as connection:
        return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def test_first_startup_without_a_database_creates_a_verified_one(tmp_path: Path) -> None:
    """Streamlit Community Cloud starts from a checkout with no generated database."""

    database_path = tmp_path / "nested" / "demo.sqlite"

    state = ensure_database(database_path)

    assert state is DatabaseProvisionState.CREATED
    assert database_path.is_file()
    verify_database_schema(database_path)
    assert _row_count(database_path, "Track") == 14


def test_startup_with_an_existing_database_leaves_it_untouched(tmp_path: Path) -> None:
    database_path = tmp_path / "demo.sqlite"
    initializer.initialize_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute('INSERT INTO "Genre" VALUES (99, ?)', ("Marker",))
    before = database_path.read_bytes()

    state = ensure_database(database_path)

    assert state is DatabaseProvisionState.ALREADY_PRESENT
    assert database_path.read_bytes() == before
    assert _row_count(database_path, "Genre") == 6


def test_repeated_initialization_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "demo.sqlite"

    first = ensure_database(database_path)
    fingerprint = database_path.read_bytes()
    second = ensure_database(database_path)
    third = ensure_database(database_path)

    assert first is DatabaseProvisionState.CREATED
    assert second is DatabaseProvisionState.ALREADY_PRESENT
    assert third is DatabaseProvisionState.ALREADY_PRESENT
    assert database_path.read_bytes() == fingerprint


def test_zero_length_placeholder_is_replaced_rather_than_verified(tmp_path: Path) -> None:
    """An interrupted earlier run can leave an empty file that is not a database."""

    database_path = tmp_path / "demo.sqlite"
    database_path.touch()

    state = ensure_database(database_path)

    assert state is DatabaseProvisionState.CREATED
    verify_database_schema(database_path)


def test_existing_file_with_a_wrong_schema_fails_closed_without_deleting_it(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "demo.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE Unrelated (id INTEGER)")

    with pytest.raises(DatabaseInitializationError):
        ensure_database(database_path)

    assert database_path.is_file()


def test_failed_initialization_reports_safely_and_leaves_no_partial_database(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_path = tmp_path / "demo.sqlite"

    def _fail(path: Path, *, overwrite: bool = False) -> None:
        raise DatabaseInitializationError("Demo database initialization failed.")

    monkeypatch.setattr(initializer, "initialize_database", _fail)

    with pytest.raises(DatabaseInitializationError) as exc_info:
        ensure_database(database_path)

    assert not database_path.exists()
    assert str(tmp_path) not in str(exc_info.value)


def test_provision_database_resolves_a_relative_path_against_the_project_root(
    tmp_path: Path,
) -> None:
    settings = Settings.from_env(
        {
            "LLM_PROVIDER": "fake",
            "DATABASE_PATH": "data/demo/generated.sqlite",
        }
    )

    provisioning = provision_database(settings, project_root=tmp_path)

    assert provisioning.state is DatabaseProvisionState.CREATED
    assert not provisioning.used_fallback_location
    assert provisioning.path == tmp_path / "data" / "demo" / "generated.sqlite"
    assert provisioning.path.is_file()


def test_provision_database_needs_no_provider_credentials(tmp_path: Path) -> None:
    """Database provisioning must not depend on Gemini being configured."""

    settings = Settings.from_env(
        {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "dummy-provisioning-key",
            "DATABASE_PATH": str(tmp_path / "demo.sqlite"),
        }
    )

    provisioning = provision_database(settings, project_root=tmp_path)

    assert provisioning.state is DatabaseProvisionState.CREATED
    assert not provisioning.used_fallback_location


def test_provision_database_falls_back_when_the_checkout_is_not_writable(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """A read-only or non-persistent host mount must not disable the public demo."""

    fallback_root = tmp_path / "fallback"
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fallback_root))
    settings = Settings.from_env(
        {
            "LLM_PROVIDER": "fake",
            "DATABASE_PATH": "data/demo/demo.sqlite",
        }
    )

    def _reject_the_configured_location(path: Path) -> DatabaseProvisionState:
        if fallback_root not in path.parents:
            raise DatabaseInitializationError("The demo database location could not be created.")
        return ensure_database(path)

    monkeypatch.setattr(
        "safe_text_to_sql.bootstrap.ensure_database",
        _reject_the_configured_location,
    )

    provisioning = provision_database(settings, project_root=tmp_path / "checkout")

    assert provisioning.used_fallback_location
    assert provisioning.state is DatabaseProvisionState.CREATED
    assert provisioning.path == fallback_root / "safe-text-to-sql" / "demo.sqlite"
    verify_database_schema(provisioning.path)


def test_provision_database_reports_the_original_failure_when_the_fallback_also_fails(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "fallback"))
    settings = Settings.from_env(
        {
            "LLM_PROVIDER": "fake",
            "DATABASE_PATH": "data/demo/demo.sqlite",
        }
    )

    def _always_fail(path: Path) -> DatabaseProvisionState:
        raise DatabaseInitializationError("The demo database location could not be created.")

    monkeypatch.setattr("safe_text_to_sql.bootstrap.ensure_database", _always_fail)

    with pytest.raises(DatabaseInitializationError) as exc_info:
        provision_database(settings, project_root=tmp_path / "checkout")

    assert str(tmp_path) not in str(exc_info.value)
