from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch
from streamlit.testing.v1 import AppTest

from safe_text_to_sql.database.initializer import initialize_database


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
    assert any(button.label == "Generate guarded answer" for button in app.button)
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
    submit_buttons = [button for button in app.button if button.label == "Generate guarded answer"]

    assert len(submit_buttons) == 1

    submit_buttons[0].click()
    app.run()

    assert not app.exception
    rendered = " ".join(item.value for item in app.markdown)
    assert "Grounded answer" in rendered
    assert "Validation passed" in rendered
    assert len(app.dataframe) == 1
    assert len(app.code) == 1
