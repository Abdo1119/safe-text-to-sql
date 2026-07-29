from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch
from streamlit.testing.v1 import AppTest

from safe_text_to_sql.database import initializer
from safe_text_to_sql.database.initializer import (
    DatabaseInitializationError,
    initialize_database,
    verify_database_schema,
)
from safe_text_to_sql.database.sqlite import (
    DatabaseError,
    DatabaseErrorCode,
    SQLiteRepository,
)


def _rendered_text(app: AppTest) -> str:
    return " ".join(
        element.value
        for collection in (app.markdown, app.caption, app.info, app.warning, app.error, app.success)
        for element in collection
    )


def test_first_start_without_a_database_initializes_it_and_enables_the_query_button(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Reproduces the deployed failure: a fresh checkout has no generated database."""

    database_path = tmp_path / "data" / "demo" / "chinook_demo.sqlite"
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert not database_path.exists()

    app = AppTest.from_file("app.py", default_timeout=20)
    app.run()

    assert not app.exception
    assert database_path.is_file()
    verify_database_schema(database_path)
    submit_buttons = [button for button in app.button if button.label == "Run guarded query"]
    assert len(submit_buttons) == 1
    assert not submit_buttons[0].disabled
    assert "Database ready" in _rendered_text(app)
    assert str(database_path) not in _rendered_text(app)


def test_query_button_is_disabled_when_the_database_cannot_be_read(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Provisioning can succeed while the read-only query path is still unusable."""

    database_path = tmp_path / "demo.sqlite"
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def _unavailable(_self: SQLiteRepository) -> bool:
        raise DatabaseError(DatabaseErrorCode.UNAVAILABLE, "The demo database is unavailable.")

    monkeypatch.setattr(SQLiteRepository, "healthcheck", _unavailable)

    app = AppTest.from_file("app.py", default_timeout=20)
    app.run()

    assert not app.exception
    submit_buttons = [button for button in app.button if button.label == "Run guarded query"]
    assert len(submit_buttons) == 1
    assert submit_buttons[0].disabled
    rendered = _rendered_text(app)
    assert "queries are disabled" in rendered
    assert str(database_path) not in rendered


def test_safe_initialization_failure_stops_without_paths_or_stack_traces(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_path = tmp_path / "demo.sqlite"
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def _fail(path: Path, *, overwrite: bool = False) -> None:
        raise DatabaseInitializationError("Demo database initialization failed.")

    monkeypatch.setattr(initializer, "initialize_database", _fail)

    app = AppTest.from_file("app.py", default_timeout=20)
    app.run()

    assert not app.exception
    assert len(app.error) == 1
    rendered = _rendered_text(app)
    assert "could not be prepared" in rendered
    # The sanitized reason names the failing stage; without it the message is
    # undiagnosable on a host whose logs are not reachable.
    assert "Demo database initialization failed." in rendered
    assert str(tmp_path) not in rendered
    assert "Traceback" not in rendered
    assert not app.button


def test_streamlit_app_renders_safe_offline_workbench(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_path = tmp_path / "demo.sqlite"
    initialize_database(database_path)
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    app = AppTest.from_file("app.py", default_timeout=20)
    app.run()

    assert not app.exception
    assert app.title[0].value == "Safe Text-to-SQL"
    assert len(app.text_area) == 1
    assert any(button.label == "Run guarded query" for button in app.button)
    rendered = " ".join(
        element.value
        for collection in (app.markdown, app.caption, app.info, app.warning, app.error)
        for element in collection
    )
    assert "Ask questions. Inspect the query. Trust the boundary." in rendered
    for phase in ("Generate", "Guard", "Execute", "Answer"):
        assert phase in rendered
    assert "Offline demo · deterministic" in rendered
    assert "Database ready" in rendered
    assert str(database_path) not in rendered


def test_streamlit_app_renders_grounded_result_from_reviewed_question(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_path = tmp_path / "demo.sqlite"
    initialize_database(database_path)
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    app = AppTest.from_file("app.py", default_timeout=20)
    app.run()
    app.selectbox[0].select("Find the top 5 customers by total spending")
    submit_buttons = [button for button in app.button if button.label == "Run guarded query"]

    assert len(submit_buttons) == 1

    submit_buttons[0].click()
    app.run()

    assert not app.exception
    rendered = " ".join(item.value for item in app.markdown)
    assert "Grounded answer" in rendered
    assert "Validation passed" in rendered
    assert len(app.dataframe) == 1
    assert len(app.code) == 1
