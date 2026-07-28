"""Streamlit entry point for the Safe Text-to-SQL workbench."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from safe_text_to_sql.bootstrap import build_components, load_runtime_settings
from safe_text_to_sql.config import ConfigError
from safe_text_to_sql.ui import render_app


def main() -> None:
    st.set_page_config(
        page_title="Safe Text-to-SQL",
        page_icon="◫",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    project_root = Path(__file__).resolve().parent
    try:
        secrets = st.secrets.to_dict()
    except StreamlitSecretNotFoundError:
        secrets = {}

    try:
        settings = load_runtime_settings(
            project_root=project_root,
            streamlit_secrets=secrets,
        )
        components = build_components(settings, project_root=project_root)
    except ConfigError as exc:
        st.error(str(exc))
        st.info(
            "Use fake mode without a cloud key, or configure Gemini through local "
            "environment variables or Streamlit Secrets."
        )
        st.stop()
    except Exception:
        st.error("The application could not start with the current local configuration.")
        st.stop()

    render_app(settings, components)


if __name__ == "__main__":
    main()
