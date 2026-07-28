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
    assert app.title[0].value == "Ask the music store"
    assert any("Offline fake mode" in item.value for item in app.caption)
    assert len(app.text_area) == 1
    assert any(button.label == "Run guarded query" for button in app.button)
    rendered = " ".join(
        element.value
        for collection in (app.markdown, app.caption, app.info, app.warning, app.error)
        for element in collection
    )
    assert str(database_path) not in rendered
